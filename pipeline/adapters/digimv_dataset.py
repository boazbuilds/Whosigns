"""Leest de DigiMV-jaardataset (.ods) en levert de doelpopulatie per boekjaar.

Waarom dit bestand bestaat: het archief met verklaring-pdf's is duur om te
doorlopen (één zoekopdracht plus één download per organisatie). De dataset
vertelt ons vooraf wíé überhaupt een controleverklaring heeft gedeponeerd, en
dat scheelt het leeuwendeel van het werk:

    boekjaar 2023, 6.131 organisaties
      2.159  hebben enige verklaring gedeponeerd
      1.010  daarvan een CONTROLEverklaring   <- de doelpopulatie
      4.389  hebben helemaal niets gedeponeerd

Alleen een controleverklaring is een wettelijke controle; samenstellings- en
beoordelingsverklaringen komen van kantoren zonder Wta-vergunning en horen
terecht niet in het AFM-register (zie digimv.md).

**De kantoornaam staat NIET in de dataset.** Nagetrokken op boekjaar 2023:
`bestandInstellingAccountantsVerklaring_N` klinkt alsof het het kantoor is, maar
bevat de zórginstelling waar de verklaring over gaat ("(de organisatie als
geheel)" bij 1.625 van de 1.743 gevulde rijen). Het kantoor komt dus uit de pdf.

Techniek: content.xml in zo'n .ods is ~300 MB, dus streamend lezen met iterparse
en elementen direct opruimen. Niets in het geheugen houden behalve wat we nodig
hebben.
"""

import csv
import io
import urllib.request
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

NS_TABLE = "{urn:oasis:names:tc:opendocument:xmlns:table:1.0}"
NS_OFFICE = "{urn:oasis:names:tc:opendocument:xmlns:office:1.0}"
NS_TEXT = "{urn:oasis:names:tc:opendocument:xmlns:text:1.0}"

KOPPEN = {"User-Agent": "Mozilla/5.0 (WhoSigns-pipeline)"}

# Downloadadres per boekjaar. De vindplaatsen staan in digimv.md; nieuwe
# jaargangen hier toevoegen zodra ze verschijnen.
DATASET_URL = {
    2023: (
        "https://www.jaarverantwoordingzorg.nl/site/binaries/site-content/"
        "collections/documents/2024/10/08/definitieve-dataset-2023/"
        "DigiMV2023_MultipleTables_20241001_0927.ods"
    ),
}

# Kolomposities in RowData_01 (boekjaar 2023). Veldnamen wisselen per jaargang;
# controleer ze bij een nieuwe jaargang met `kolomkoppen()`.
KOLOM = {
    2023: {
        "code": 0,
        "kvk": 2,          # ExternalOrganizationId
        "kvk_reserve": 21,  # qNawKvk
        "naam": 23,        # qNawNaam
        "naam_reserve": 22,  # qNawNaamLrza
        "plaats": 28,      # qNawPlaatsLrza
    },
}

# In RowData_19 staan de verklaringen in blokken van zeven kolommen; de vierde
# kolom van elk blok is de soort. Het aantal blokken varieert per organisatie.
SOORT_EERSTE_KOLOM = 3
SOORT_STAP = 7
MAX_VERKLARINGEN = 36


def _celtekst(cel) -> str:
    waarde = cel.get(f"{NS_OFFICE}value")
    if waarde is not None:
        return waarde
    return "\n".join(
        (p.text or "") + "".join(sub.tail or "" for sub in p)
        for p in cel.iter(f"{NS_TEXT}p")
    ).strip()


def rijen(ods_pad: Path, sheets: set[str] | None = None):
    """Levert (sheetnaam, rijnummer, cellen) streamend op. Rij 1 is de kop."""
    with zipfile.ZipFile(ods_pad) as z, z.open("content.xml") as f:
        sheet = None
        rijnr = 0
        actief = False
        for gebeurtenis, el in ET.iterparse(f, events=("start", "end")):
            if gebeurtenis == "start" and el.tag == f"{NS_TABLE}table":
                sheet = el.get(f"{NS_TABLE}name")
                rijnr = 0
                actief = sheets is None or sheet in sheets
            elif gebeurtenis == "end" and el.tag == f"{NS_TABLE}table-row":
                if actief:
                    cellen: list[str] = []
                    for cel in el.findall(f"{NS_TABLE}table-cell"):
                        # Opvulling tot 16.384 kolommen niet uitrollen.
                        herhaal = min(
                            int(cel.get(f"{NS_TABLE}number-columns-repeated", 1)), 300
                        )
                        cellen.extend([_celtekst(cel)] * herhaal)
                    while cellen and cellen[-1] == "":
                        cellen.pop()
                    if cellen:
                        rijnr += 1
                        yield sheet, rijnr, cellen
                el.clear()
            elif gebeurtenis == "end" and el.tag == f"{NS_TABLE}table":
                el.clear()


def download(boekjaar: int, doelmap: Path) -> Path:
    """Haalt de dataset op (en bewaart hem, zodat een herstart niets herhaalt)."""
    if boekjaar not in DATASET_URL:
        raise ValueError(
            f"geen download-adres bekend voor boekjaar {boekjaar}; "
            f"zie pipeline/adapters/digimv.md voor de vindplaatsen"
        )
    doelmap.mkdir(parents=True, exist_ok=True)
    pad = doelmap / f"digimv{boekjaar}.ods"
    if pad.exists() and pad.stat().st_size > 1_000_000:
        return pad
    verzoek = urllib.request.Request(DATASET_URL[boekjaar], headers=KOPPEN)
    with urllib.request.urlopen(verzoek, timeout=300) as antwoord:
        pad.write_bytes(antwoord.read())
    return pad


def kolomkoppen(ods_pad: Path) -> dict[str, list[str]]:
    """Kop van elke sheet — om bij een nieuwe jaargang de posities te controleren."""
    koppen: dict[str, list[str]] = {}
    for sheet, rijnr, cellen in rijen(ods_pad):
        if rijnr == 1:
            koppen[sheet] = cellen
    return koppen


def doelpopulatie(ods_pad: Path, boekjaar: int) -> list[dict]:
    """Organisaties met minstens één controleverklaring: KvK, naam, plaats.

    Eén doorloop over het bestand; RowData_01 levert de identificatie,
    RowData_19 de soorten verklaring. `Code` koppelt de twee.
    """
    if boekjaar not in KOLOM:
        raise ValueError(
            f"kolomposities voor boekjaar {boekjaar} onbekend — draai eerst "
            f"kolomkoppen() en vul KOLOM aan (veldnamen wisselen per jaargang)"
        )
    kolom = KOLOM[boekjaar]
    organisaties: dict[str, dict] = {}
    met_controle: set[str] = set()

    for sheet, rijnr, cellen in rijen(ods_pad, {"RowData_01", "RowData_19"}):
        if rijnr == 1:
            continue

        def cel(index: int) -> str:
            return cellen[index].strip() if index < len(cellen) else ""

        if sheet == "RowData_01":
            code = cel(kolom["code"])
            organisaties[code] = {
                "kvk_nummer": cel(kolom["kvk"]) or cel(kolom["kvk_reserve"]),
                "naam": cel(kolom["naam"]) or cel(kolom["naam_reserve"]),
                "plaats": cel(kolom["plaats"]),
            }
        else:
            for blok in range(MAX_VERKLARINGEN):
                if cel(SOORT_EERSTE_KOLOM + SOORT_STAP * blok) == "controleverklaring":
                    met_controle.add(cel(0))
                    break

    uit = []
    for code in met_controle:
        org = organisaties.get(code)
        if org and org["kvk_nummer"] and org["naam"]:
            uit.append({**org, "boekjaar": boekjaar})
    return sorted(uit, key=lambda o: o["naam"])


def schrijf_csv(organisaties: list[dict], pad: Path) -> None:
    with pad.open("w", newline="", encoding="utf-8") as f:
        schrijver = csv.DictWriter(f, fieldnames=["kvk_nummer", "naam", "plaats", "boekjaar"])
        schrijver.writeheader()
        schrijver.writerows(organisaties)


def lees_csv(pad: Path) -> list[dict]:
    with pad.open(encoding="utf-8") as f:
        return list(csv.DictReader(f))
