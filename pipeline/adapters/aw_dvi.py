"""Autoriteit woningcorporaties (dVi) — de accountant staat er als veld in.

De enige bron tot nu toe die de accountant *gestructureerd* levert: geen archief, geen
pdf's, geen OCR. Hoofdstuk 1 van de verantwoordingsinformatie (dVi) heeft per corporatie
een kolom `Accountant`, met KvK-nummer, instellingsnaam en gemeente ernaast.

    https://data.overheid.nl  ->  dataset "Verantwoordingsinformatie woningcorporaties
                                  (dVi<jaar>-hfd1)"  ->  xlsx  ->  blad "Data H1"

Licentie **CC-0**: vrij te gebruiken, bronvermelding niet verplicht (we doen het wel).

Gemeten op 30-7-2026:

| Jaargang | Corporaties | Accountant gevuld | Veldnaam |
|---|---|---|---|
| dVi2015 | 349 | 349 (100%) | `CorpGeg_AccountantOrg_j1515` |
| dVi2022 | 277 | 277 (100%) | `Accountant` |
| dVi2024 | 272 | 272 (100%) | `Accountant` |

Jaargangen 2007 t/m 2024 staan online; vanaf 2014 zijn ze los per hoofdstuk en het
makkelijkst te gebruiken. Zie `docs/bestaande-databases.md`.

Drie eigenaardigheden van de bron, alle drie hier opgelost:

1. **De veldnaam wisselt per jaargang** (zoals bij DigiMV). We zoeken de kolom daarom op
   patroon, niet op een vaste naam.
2. **Het blad wisselt van plek.** In dVi2022 staat de data op blad 2 ("Data H1"), in
   dVi2024 op blad 16 (want dat bestand bevat hoofdstuk 1 t/m 5). We nemen het eerste
   blad waarvan de koprij een accountant-kolom heeft.
3. **De schrijfwijze is zelfgerapporteerd en dus rommelig**: "BDO Audit & Assurance
   B.V.", "BDO Audit en Assurance BV", "BDO Audit&Assurace BV", "BDO Audit @ Assurance
   B.V." en gewoon "BDO" — in één jaargang. `KORTE_NAMEN` hieronder vangt de losse
   merknamen op. Die staan bewust *niet* in `seed/kantoor_alias.csv`: dat is de lijst
   voor het herkennen van ondertekeningen in pdf's, en een losse "BDO" hoort daar niet in.

Let op bij het opdrachttype: een woningcorporatie is op grond van de Woningwet
controleplichtig, dus dit zijn **wettelijke controles** — anders dan bij de goede doelen.
Dit veld is wel zelfgerapporteerd en geen ondertekening; het is dus een feit uit een
verantwoordingsopgave aan de toezichthouder, niet uit een verklaring.

Geen dependencies buiten de standaardbibliotheek.
"""

import io
import json
import re
import sys
import urllib.request
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "extractie"))

from kantoor_match import kernnaam, laad_kantoren, normaliseer  # noqa: E402

CKAN_ZOEK = (
    "https://data.overheid.nl/data/api/3/action/package_search"
    "?q=verantwoordingsinformatie+woningcorporaties&rows=100"
)
USER_AGENT = "WhoSigns/0.1 (open-data-import; contact via repo)"
BRON_URL = (
    "https://www.ilent.nl/onderwerpen/autoriteit-woningcorporaties/"
    "publicaties-cijfers-en-wetgeving-autoriteit-woningcorporaties/publicaties-en-data/open-data"
)

# De jaargangen die los per hoofdstuk staan en dus zonder gedoe te lezen zijn.
OUDSTE_BOEKJAAR = 2014
NIEUWSTE_BOEKJAAR = 2024

XLSX_NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"

# Kolommen die we nodig hebben, per patroon (de exacte naam wisselt per jaargang).
KOLOMPATRONEN = {
    "kvk_nummer": r"^kvk[_ ]?nummer$|kvk",
    "naam": r"^instellingsnaam$|corporatienaam|naam.*instelling",
    "gemeente": r"^gemeente$",
    "instellingsnummer": r"^instellingsnummer$|^l-?nummer$",
    "accountant": r"accountant",
}

# Woorden die in bijna elke kantoornaam staan en dus niets onderscheiden. Eraf halen
# maakt "Verstegen Accountants & Belastingadviseurs" en "Verstegen accountants en
# adviseurs B.V." tot dezelfde sleutel.
_RUISWOORDEN = {
    "accountants", "accountant", "accoutants", "acountants", "accountancy",
    "registeraccountants", "audit", "auditors", "assurance", "adviseurs",
    "belastingadviseurs", "adviseur", "consultants", "en", "amp", "nederland",
    "netherlands", "group", "groep", "bv", "nv", "llp", "b", "v", "n", "maatschap",
    "coopers",  # "Pricewaterhouse Coopers" -> zelfde sleutel als PricewaterhouseCoopers
    "berk",     # "Baker Tilly Berk" was de naam tot 2018
}

# Merknamen die zonder verdere aanduiding maar één kantoor kunnen betekenen.
KORTE_NAMEN = {
    "bdo": "BDO Audit & Assurance B.V.",
    "deloitte": "Deloitte Accountants B.V.",
    "baker tilly": "Baker Tilly (Netherlands) B.V.",
    "bakertilly": "Baker Tilly (Netherlands) B.V.",
    "ey": "EY Accountants B.V.",
    "ernst young": "EY Accountants B.V.",
    "kpmg": "KPMG Accountants N.V.",
    "pwc": "PricewaterhouseCoopers Accountants N.V.",
    "pricewaterhouse": "PricewaterhouseCoopers Accountants N.V.",
    "pricewaterhousecoopers": "PricewaterhouseCoopers Accountants N.V.",
    "mazars": "Forvis Mazars Accountants N.V.",
    "forvis mazars": "Forvis Mazars Accountants N.V.",
    "verstegen": "Verstegen accountants en adviseurs B.V.",
    "flynth": "Flynth Audit B.V.",
    "q concepts": "Q-Concepts Accountancy B.V.",
    "qconcepts": "Q-Concepts Accountancy B.V.",
    "share impact": "Share Impact Accountants B.V.",
    "eshuis": "Eshuis Registeraccountants B.V.",
}


def _kernwoorden(waarde: str) -> str:
    """Naam terugbrengen tot de onderscheidende woorden.

    'Verstegen Accountants & Belastingadviseurs B.V.' -> 'verstegen'
    'Baker Tilly Berk N.V.'                           -> 'baker tilly'
    'Deloitte Accoutants B.V.' (typefout in de bron)  -> 'deloitte'
    """
    woorden = [w for w in normaliseer(waarde).split() if w not in _RUISWOORDEN]
    return " ".join(woorden)


def _afm_op_kernwoorden() -> dict[str, str]:
    """Kernwoorden -> officiële AFM-naam, voor de kantoren waar dat eenduidig is."""
    telling: dict[str, list[str]] = {}
    for kantoor in laad_kantoren():
        sleutel = _kernwoorden(kernnaam(kantoor["naam"]))
        if sleutel:
            telling.setdefault(sleutel, []).append(kantoor["naam"])
    # Alleen sleutels die naar precies één kantoor wijzen; de rest is ambigu en gaat
    # via de review-queue (guardrail: nooit stil mergen).
    return {s: namen[0] for s, namen in telling.items() if len(namen) == 1}


def _haal(url: str, timeout: int = 120, pogingen: int = 3) -> bytes:
    """Ophalen met een paar pogingen: data.overheid.nl is soms minuten onbereikbaar."""
    laatste: Exception | None = None
    for poging in range(pogingen):
        try:
            verzoek = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(verzoek, timeout=timeout) as antwoord:
                return antwoord.read()
        except Exception as fout:  # noqa: BLE001 — bron mag traag zijn
            laatste = fout
            if poging < pogingen - 1:
                import time

                time.sleep(5 * (poging + 1))
    raise laatste  # type: ignore[misc]


def dataset_url(boekjaar: int) -> str:
    """De xlsx-URL van hoofdstuk 1 voor dit boekjaar, opgezocht via de CKAN-API.

    De slug wisselt per jaargang (`dvi2022-hfd1`, `dvi2024-hfd1-tm-hfd5`, soms met een
    extra streepje), dus we zoeken op titel in plaats van een URL te construeren.
    """
    data = json.loads(_haal(CKAN_ZOEK).decode("utf-8"))["result"]["results"]
    kandidaten = []
    for pakket in data:
        titel = pakket.get("title", "")
        if not re.search(rf"dVi{boekjaar}\b", titel, re.I):
            continue
        if "prognose" in titel.lower():  # dPi is de prognose, niet de verantwoording
            continue
        for bron in pakket.get("resources", []):
            url = bron.get("url") or ""
            naam = (bron.get("name") or "").lower()
            if not url.lower().endswith((".xlsx", ".xls")):
                continue
            if "veldnamen" in naam or "model" in naam:  # datadictionary, geen data
                continue
            # Woordgrens verplicht: het label van dVi2019-H4 op data.overheid.nl
            # luidt (fout) "dVi2019 hoofdstuk 14", en zonder \b matchte
            # "hoofdstuk 1" dáárin — waarna de run hoofdstuk 4 (Treasury) las
            # en boekjaar 2019 omviel op "geen blad met een accountant-kolom".
            if re.search(r"hoofdstuk 1\b|h1\b|hfd1\b", naam):
                kandidaten.append((0, url))
            elif "t/m" in naam:
                # De gebundelde bestanden ("hfd1 t/m hfd5", jaargang 2024) zijn
                # de terugvaloptie; een los hoofdstuk 1 gaat altijd voor.
                kandidaten.append((1, url))
    if not kandidaten:
        raise LookupError(f"geen dVi-hoofdstuk 1 gevonden voor boekjaar {boekjaar}")
    return min(kandidaten)[1]


def _bladen(inhoud: bytes):
    """Elk werkblad als lijst rijen (dict van kolomletter -> waarde)."""
    archief = zipfile.ZipFile(io.BytesIO(inhoud))
    gedeeld = []
    if "xl/sharedStrings.xml" in archief.namelist():
        gedeeld = [
            "".join(t.itertext())
            for t in ET.fromstring(archief.read("xl/sharedStrings.xml"))
        ]
    bladnamen = sorted(
        (n for n in archief.namelist() if re.match(r"xl/worksheets/sheet\d+\.xml$", n)),
        key=lambda n: int(re.search(r"sheet(\d+)", n).group(1)),
    )
    for naam in bladnamen:
        blad = ET.fromstring(archief.read(naam))
        rijen = []
        for rij in blad.iter(f"{XLSX_NS}row"):
            cellen = {}
            for cel in rij.iter(f"{XLSX_NS}c"):
                letter = re.match(r"([A-Z]+)", cel.get("r") or "A1").group(1)
                waarde = cel.find(f"{XLSX_NS}v")
                if waarde is None or waarde.text is None:
                    continue
                cellen[letter] = (
                    gedeeld[int(waarde.text)] if cel.get("t") == "s" else waarde.text
                )
            if cellen:
                rijen.append(cellen)
        yield rijen


def _kolommen(koprij: dict) -> dict[str, str] | None:
    """Kolomletters per gewenst veld, of None als dit blad geen accountant-kolom heeft."""
    gevonden: dict[str, str] = {}
    for letter, kop in koprij.items():
        kop_tekst = str(kop).strip()
        for veld, patroon in KOLOMPATRONEN.items():
            if veld in gevonden:
                continue
            if re.search(patroon, kop_tekst, re.I):
                gevonden[veld] = letter
    return gevonden if "accountant" in gevonden else None


def normaliseer_kantoornaam(waarde: str, afm: dict[str, str] | None = None) -> str:
    """Zelfgerapporteerde naam -> de naam zoals het AFM-register die kent.

    Drie stappen, allemaal deterministisch:
    1. de naam terugbrengen tot zijn onderscheidende woorden (rechtsvorm en
       'accountants/adviseurs/audit' eraf);
    2. is dat een bekende merknaam (`KORTE_NAMEN`)? dan die;
    3. wijzen die kernwoorden naar precies één kantoor in het AFM-register? dan die.

    Lukt geen van de drie, dan komt de naam ongewijzigd terug en laat de matcher hem
    vallen — waarna de lader hem in de review-queue zet. Nooit stil gokken.
    """
    schoon = re.sub(r"\s+", " ", (waarde or "").strip())
    sleutel = _kernwoorden(schoon)
    if not sleutel:
        return schoon
    if sleutel in KORTE_NAMEN:
        return KORTE_NAMEN[sleutel]
    if afm is None:
        afm = _afm_op_kernwoorden()
    return afm.get(sleutel, schoon)


def corporaties_uit_bestand(pad: Path, boekjaar: int, bron_url: str = "") -> list[dict]:
    """Zelfde als `corporaties`, maar uit een al gedownload xlsx.

    Nodig omdat data.overheid.nl geregeld minuten lang niets teruggeeft; dan haal je het
    bestand met de hand op en gaat de run alsnog door.
    """
    return _lees(pad.read_bytes(), boekjaar, bron_url or f"bestand: {pad.name}")


def _lees(inhoud: bytes, boekjaar: int, bron_url: str) -> list[dict]:
    """Het eerste blad met een accountant-kolom uitlezen.

    Elke rij: {kvk_nummer, naam, gemeente, instellingsnummer, accountant_ruw,
    accountant, boekjaar, bron_url}. `accountant_ruw` blijft staan zoals de corporatie
    het opgaf — dat is het feit uit de bron; `accountant` is de genormaliseerde vorm die
    we matchen.
    """
    afm = _afm_op_kernwoorden()
    for rijen in _bladen(inhoud):
        if len(rijen) < 2:
            continue
        kolommen = _kolommen(rijen[0])
        if not kolommen:
            continue
        uit = []
        for rij in rijen[1:]:
            accountant_ruw = str(rij.get(kolommen["accountant"], "")).strip()
            if not accountant_ruw:
                continue
            uit.append(
                {
                    "kvk_nummer": str(rij.get(kolommen.get("kvk_nummer", ""), "")).strip(),
                    "naam": str(rij.get(kolommen.get("naam", ""), "")).strip(),
                    "gemeente": str(rij.get(kolommen.get("gemeente", ""), "")).strip(),
                    "instellingsnummer": str(
                        rij.get(kolommen.get("instellingsnummer", ""), "")
                    ).strip(),
                    "accountant_ruw": accountant_ruw,
                    "accountant": normaliseer_kantoornaam(accountant_ruw, afm),
                    "boekjaar": boekjaar,
                    "bron_url": bron_url,
                }
            )
        if uit:
            return uit
    raise LookupError(f"geen blad met een accountant-kolom in dVi{boekjaar}")


def corporaties(boekjaar: int, cache: Path | None = None) -> list[dict]:
    """Alle corporaties van dit boekjaar met hun accountant, opgehaald bij de bron."""
    url = dataset_url(boekjaar)
    pad = None
    if cache is not None:
        cache.mkdir(exist_ok=True)
        pad = cache / f"dvi{boekjaar}_h1.xlsx"
    if pad is not None and pad.exists():
        inhoud = pad.read_bytes()
    else:
        inhoud = _haal(url)
        if pad is not None:
            pad.write_bytes(inhoud)
    return _lees(inhoud, boekjaar, url)
