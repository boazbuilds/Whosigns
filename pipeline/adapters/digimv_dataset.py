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
import re
import subprocess
import urllib.request
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

NS_TABLE = "{urn:oasis:names:tc:opendocument:xmlns:table:1.0}"
NS_OFFICE = "{urn:oasis:names:tc:opendocument:xmlns:office:1.0}"
NS_TEXT = "{urn:oasis:names:tc:opendocument:xmlns:text:1.0}"

KOPPEN = {"User-Agent": "Mozilla/5.0 (WhoSigns-pipeline)"}

_BASIS = (
    "https://www.jaarverantwoordingzorg.nl/site/binaries/site-content/"
    "collections/documents"
)

# Downloadadressen per boekjaar; een jaargang kan uit meerdere bestanden bestaan.
# `.zip` wordt uitgepakt met het externe `unzip`, want boekjaar 2019 gebruikt
# Deflate64 en dat kan Python's zipfile niet.
#
# 2019 t/m 2021 staan hier bewust NIET: die gebruiken een ouder exportformaat
# (sheets `x9conc_total_*`, veldnamen `c_kvk`/`c_naam`) en de datadictionary van
# 2019 bevat géén accountantsverklaring-velden. Daar is de doelpopulatie dus niet
# uit te halen; gebruik voor die jaren `--lijst-uit`. Zie digimv.md.
DATASET_URL: dict[int, list[str]] = {
    2024: [
        f"{_BASIS}/2026/03/23/dataset-2024---deel-{deel}/"
        f"digimv2024-openbaar-20260129-multipletables-part-{deel}.ods"
        for deel in (1, 2, 3, 4)
    ],
    2023: [
        f"{_BASIS}/2024/10/08/definitieve-dataset-2023/"
        f"DigiMV2023_MultipleTables_20241001_0927.ods"
    ],
    2022: [
        f"{_BASIS}/2024/05/28/definitieve-dataset-2022/"
        f"DigiMV2022_20240527_ODS_MultipleTables.zip"
    ],
}

# Kolommen worden op náám opgezocht in de koprij, niet op positie. Dat moet, want
# dezelfde velden staan per jaargang op andere sheets en andere plekken:
# qRechtsvormKvk zit in 2023 op RowData_09[224] en in 2022 op RowData_11[176].
# Eerste patroon dat past wint, dus de volgorde is een voorkeursvolgorde.
VELDPATRONEN: dict[str, tuple[str, ...]] = {
    "kvk": ("externalorganizationid", "qnawkvk", "c_kvk"),
    "naam": ("qnawnaam", "qnawnaamlrza", "c_naam", "name"),
    "plaats": ("qnawplaatslrza", "qnawplaats", "c_plaats", "town"),
    "rechtsvorm": ("qrechtsvormkvk",),
    "omzet": ("qbatenzorg_0",),
    "honorarium_controle": ("acc_jr_contr",),
    "honorarium_overig": ("acc_ov_contr",),
    "honorarium_fiscaal": ("acc_fisc_adv",),
    "honorarium_nietcontrole": ("acc_niet_contr",),
    "wisselvlag": ("qaccountantwissel",),
    # `qNawSBIcodesLrza` bewust niet meegenomen: 1.122 van de 1.140 organisaties
    # hebben daar letterlijk "(Geen geregistreerde SBI-codes beschikbaar)" staan.
    # Achttien echte codes is geen kolom waard.
    # Oordeel én datum per gedeponeerd document. Bewust NIET qAccVerklVorm: dat is
    # het vragenlijstveld en dat wordt verkeerd ingevuld (46 oordeelonthoudingen
    # tegen 8 in het documentveld, terwijl onze pdf-extractie er 5 vond).
    "oordeel_gerapporteerd": ("bestandaccverklsoortcontroleverkl",),
    "verklaring_datum": ("bestanddatumaccountantsverklaring",),
}

# Hoe de bron het oordeel schrijft -> onze woordenlijst (gelijk aan de check in
# supabase/migrations/20260727000000_init.sql).
OORDEEL_UIT_BRON = {
    "goedkeurende controleverklaring": "goedkeurend",
    "controleverklaring met beperking": "beperking",
    "controleverklaring met oordeelonthouding": "oordeelonthouding",
    "afkeurende controleverklaring": "afkeurend",
}

# Het soort verklaring heeft per jaargang een andere veldnaam: 2023 heeft het
# per document (`bestandAccountantsVerklaringSoort_N`), 2022 als losse vraag
# (`qAccVerklSoort_qAccVerklSoort`). Beide patronen meenemen; alle kolommen die
# passen worden gelezen, want een organisatie kan meerdere verklaringen hebben.
VERKLARINGSOORT_PATRONEN = ("bestandaccountantsverklaringsoort", "qaccverklsoort")

# Zorgsoort staat in tientallen kolommen (qAGBzorgsoortOrg_1 t/m _101); we nemen
# de eerste die gevuld is.
ZORGSOORT_PATROON = "qagbzorgsoortorg_"

# De dataset kent 61 AGB-zorgsoorten. Te fijnmazig om op te navigeren (en de staart
# is lang: 30 waarden komen minder dan 20 keer voor), dus teruggebracht tot negen
# groepen. Bewust een expliciete tabel en geen trefwoordregels: dit is data die op
# de site komt, dus het moet na te lopen zijn wat waar landt.
#
# Wat hier niet in staat, krijgt geen subsector — niet "Overig". Liever leeg dan
# een verzamelbak die suggereert dat we het weten.
SUBSECTOR: dict[str, str] = {}


def _groep(naam: str, soorten: list[str]) -> None:
    for soort in soorten:
        SUBSECTOR[soort] = naam


_groep("Ziekenhuizen en klinieken", [
    "Ziekenhuizen", "Zelfstandige Behandelcentra", "Medisch Specialisten",
    "Radiotherapeutische Centra", "Dialyse Centra", "Klinisch-Genetische Centra",
    "Audiologische Centra", "Instellingen voor Revalidatiedagbehandeling",
    "Overige Artsen",
])
_groep("Ouderenzorg", [
    "WLZ Gecombineerd", "Verzorgingshuizen", "Gecombineerde Verpleeginrichtingen",
    "Koepels en Beheerstichtingen WLZ", "Instellingen voor Dagverpleging voor Ouderen",
    "Beheerstichtingen Verzorgingstehuizen",
    "Verpleeginrichtingen voor Somatische Ziekten",
    "Verpleeginrichtingen voor Psycho-Geriatrische Patienten",
])
_groep("Thuiszorg en wijkverpleging", [
    "Thuiszorginstellingen", "Kraamzorg",
    "ZZP-ers in wijkverpleging/ PGB aanbieders / Beheerstichtingen",
])
_groep("Geestelijke gezondheidszorg", [
    "Psychologische Zorgverleners", "RIBW", "GGZ Instellingen (PUK/PAAZ)", "RIAGG",
    "Instellingen voor Psychiatrische Deeltijdbehandeling",
    "Consultatiebureaus voor Alcohol en Drugs",
])
_groep("Gehandicaptenzorg", [
    "Instellingen voor Verstandelijk Gehandicapten", "Gezinsvervangende Tehuizen",
    "Instellingen voor Auditief Gehandicapten", "Beheerstichtingen Dagverblijven",
])
_groep("Jeugd- en pedagogische zorg", [
    "Sociaal Pedagogische Diensten", "Kinderdagverblijven",
])
_groep("Eerstelijns- en paramedische zorg", [
    "Huisartsen", "Fysiotherapeuten", "Logopedisten", "Podotherapeuten",
    "Verloskundigen", "Ergotherapeuten", "Dietisten", "Oefentherapeuten",
    "Pedicuren", "Schoonheidspecialisten", "Gezondheidscentra", "Bedrijfsartsen",
    "Dienstenstructuren (ANW-Diensten)",
    "Overige therapeuten en Complementair en Aanvullende zorg",
])
_groep("Tandheelkundige zorg", [
    "Tandartsen", "Tandheelkundige Centra", "Mondhygienisten",
    "Tandtechnici / Tandprothetici",
    "Tandarts - Specialisten (Dento-Maxillaire Orthopedie)",
    "Tandarts - Specialisten (Mondziekten en Kaakchirurgie)",
])
_groep("Publieke en ondersteunende zorg", [
    "GGD", "Ambulancediensten", "Trombosediensten", "Leveranciers Hulpmiddelen",
    "Laboratoria(Huisartsenlab./Gemeensch.Lab/Gemeensch Apoth+Lab",
    "Declaranten/Servicebureaus/Zorgverzekeraars", "Rechtspersonen",
    "Diverse Samenwerkingsverbanden", "Overige Instellingen",
])


def _paragraaftekst(p) -> str:
    """Alle tekst van één alinea, inclusief wat in kind-elementen zit.

    De oude variant nam alleen `p.text` en de staarten van kinderen mee. Tekst
    die in een `<text:span>` staat (opmaak) viel daardoor stil weg, en de
    ODS-notatie voor herhaalde spaties (`<text:s/>`) en tabs verdween — twee
    woorden plakten dan zonder scheiding aan elkaar. Nagemeten op de volledige
    jaargang 2023 (1.140 organisaties): identieke uitkomst, dus dit repareert
    alleen de randgevallen die de oude weg stil verminkte.
    """
    delen = [p.text or ""]
    for sub in p:
        if sub.tag == f"{NS_TEXT}s":
            delen.append(" " * int(sub.get(f"{NS_TEXT}c", 1)))
        elif sub.tag == f"{NS_TEXT}tab":
            delen.append("\t")
        elif sub.tag == f"{NS_TEXT}line-break":
            delen.append("\n")
        else:
            delen.append("".join(sub.itertext()))
        delen.append(sub.tail or "")
    return "".join(delen)


def _celtekst(cel) -> str:
    waarde = cel.get(f"{NS_OFFICE}value")
    if waarde is not None:
        return waarde
    return "\n".join(
        _paragraaftekst(p) for p in cel.iter(f"{NS_TEXT}p")
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


def download(boekjaar: int, doelmap: Path) -> list[Path]:
    """Haalt alle bestanden van een jaargang op en geeft de .ods-paden terug.

    Bewaart wat al is opgehaald, zodat een herstart niets herhaalt. Een `.zip`
    wordt uitgepakt met het externe `unzip`: boekjaar 2019 gebruikt Deflate64 en
    Python's zipfile weigert dat ("compression method is not supported").
    """
    if boekjaar not in DATASET_URL:
        raise ValueError(
            f"geen download-adres bekend voor boekjaar {boekjaar}. "
            f"Bekend: {sorted(DATASET_URL)}. Voor oudere jaargangen: gebruik "
            f"--lijst-uit; zie pipeline/adapters/digimv.md."
        )
    doelmap.mkdir(parents=True, exist_ok=True)
    paden = []

    for nummer, url in enumerate(DATASET_URL[boekjaar], start=1):
        is_zip = url.lower().endswith(".zip")
        pad = doelmap / f"digimv{boekjaar}_{nummer}{'.zip' if is_zip else '.ods'}"
        if not (pad.exists() and pad.stat().st_size > 1_000_000):
            verzoek = urllib.request.Request(url, headers=KOPPEN)
            with urllib.request.urlopen(verzoek, timeout=600) as antwoord:
                pad.write_bytes(antwoord.read())
        if not is_zip:
            paden.append(pad)
            continue

        uitpakmap = doelmap / f"digimv{boekjaar}_{nummer}_uit"
        if not any(uitpakmap.glob("*.ods")):
            uitpakmap.mkdir(exist_ok=True)
            subprocess.run(
                ["unzip", "-o", "-q", str(pad), "-d", str(uitpakmap)], check=True
            )
        paden.extend(sorted(uitpakmap.glob("*.ods")))

    return paden


def kolomkoppen(ods_pad: Path) -> dict[str, list[str]]:
    """Kop van elke sheet — om bij een nieuwe jaargang de posities te controleren."""
    koppen: dict[str, list[str]] = {}
    for sheet, rijnr, cellen in rijen(ods_pad):
        if rijnr == 1:
            koppen[sheet] = cellen
    return koppen


def _bedrag(waarde: str) -> str:
    """Bedragen: alleen echte getallen, en 0 telt als 'niet opgegeven'.

    De bron zet bij een groot deel van de organisaties nullen in de
    honorariumvelden. Dat betekent niet dat er geen accountantskosten waren, maar
    dat de vraag niet is ingevuld. Een nul opslaan zou een onwaarheid zijn.

    Twee puntconventies door elkaar: het machineattribuut (office:value) schrijft
    "1234.5" met een decimale punt, de weergavetekst "1.234.567" met punten als
    duizendtallen. Eén punt met één of twee cijfers erachter lezen we als
    decimaal — anders werd 1234.5 stilletjes 12345.
    """
    schoon = waarde.strip()
    if not re.fullmatch(r"\d+\.\d{1,2}", schoon):
        schoon = schoon.replace(".", "").replace(",", ".")
    try:
        getal = float(schoon)
    except ValueError:
        return ""
    return "" if getal == 0 else f"{getal:.0f}"


def _datum(waarde: str) -> str:
    """'29-07-2024' -> '2024-07-29'. Iets anders dan dd-mm-jjjj wordt genegeerd."""
    delen = waarde.strip().split("-")
    if len(delen) != 3 or not all(d.isdigit() for d in delen):
        return ""
    dag, maand, jaar = delen
    if len(jaar) != 4 or not (1 <= int(maand) <= 12) or not (1 <= int(dag) <= 31):
        return ""
    return f"{jaar}-{maand.zfill(2)}-{dag.zfill(2)}"


def _zoek_kolommen(cellen: list[str]) -> dict:
    """Bepaalt uit een koprij welke kolom welk veld is.

    Op naam, niet op positie: dezelfde velden staan per jaargang op andere plekken.
    """
    laag = [k.strip().lower() for k in cellen]
    gevonden: dict = {"velden": {}, "zorgsoort": [], "verklaringsoort": []}

    for veld, patronen in VELDPATRONEN.items():
        for patroon in patronen:
            treffer = next(
                (i for i, k in enumerate(laag) if k.startswith(patroon)), None
            )
            if treffer is not None:
                gevonden["velden"][veld] = treffer
                break

    gevonden["zorgsoort"] = [
        i for i, k in enumerate(laag) if k.startswith(ZORGSOORT_PATROON)
    ]
    gevonden["verklaringsoort"] = [
        i
        for i, k in enumerate(laag)
        if any(k.startswith(p) for p in VERKLARINGSOORT_PATRONEN)
    ]
    return gevonden


def doelpopulatie(ods_paden: list[Path] | Path, boekjaar: int) -> list[dict]:
    """Organisaties met minstens één controleverklaring, plus de extra velden.

    Eén doorloop per bestand. De eerste kolom (`Code`, in oudere jaargangen
    `ConcernCode`) koppelt de sheets aan elkaar; welke kolom welk veld is wordt
    per sheet uit de koprij bepaald, niet uit een tabel met posities.

    Wat de bron niet levert blijft leeg — nooit geschat, nooit afgeleid.
    """
    paden = [ods_paden] if isinstance(ods_paden, Path) else list(ods_paden)
    identiteit: dict[str, dict] = {}
    extra: dict[str, dict] = {}
    met_controle: set[str] = set()

    for pad in paden:
        kolommen: dict = {"velden": {}, "zorgsoort": [], "verklaringsoort": []}
        for _sheet, rijnr, cellen in rijen(pad):
            if rijnr == 1:
                kolommen = _zoek_kolommen(cellen)
                continue

            def cel(index: int) -> str:
                return cellen[index].strip() if index < len(cellen) else ""

            code = cel(0)
            if not code:
                continue
            velden = kolommen["velden"]

            if "kvk" in velden and "naam" in velden:
                kvk = cel(velden["kvk"])
                naam = cel(velden["naam"])
                if kvk and naam:
                    zorgsoort = next(
                        (cel(i) for i in kolommen["zorgsoort"] if cel(i)), ""
                    )
                    identiteit[code] = {
                        "kvk_nummer": kvk,
                        "naam": naam,
                        "plaats": cel(velden.get("plaats", -1)) if "plaats" in velden else "",
                        "subsector": SUBSECTOR.get(zorgsoort, ""),
                    }

            # Kleine letters vergelijken: 2023 schrijft "controleverklaring",
            # 2022 "Controleverklaring".
            if any(
                cel(i).lower() == "controleverklaring"
                for i in kolommen["verklaringsoort"]
            ):
                met_controle.add(code)

            for naam_veld, index in velden.items():
                if naam_veld in ("kvk", "naam", "plaats"):
                    continue
                doel = extra.setdefault(code, {})
                if naam_veld == "wisselvlag":
                    waarde = cel(index).lower()
                    if waarde in ("ja", "nee"):
                        doel["wissel_gerapporteerd"] = waarde == "ja"
                elif naam_veld == "rechtsvorm":
                    if cel(index):
                        doel["rechtsvorm"] = cel(index)
                elif naam_veld == "oordeel_gerapporteerd":
                    oordeel = OORDEEL_UIT_BRON.get(cel(index).lower())
                    if oordeel:
                        doel["oordeel_gerapporteerd"] = oordeel
                elif naam_veld == "verklaring_datum":
                    datum = _datum(cel(index))
                    if datum:
                        doel["verklaring_datum"] = datum
                else:
                    bedrag = _bedrag(cel(index))
                    if bedrag:
                        doel[naam_veld] = bedrag

    uit = []
    for code in met_controle:
        org = identiteit.get(code)
        if org:
            uit.append({**org, **extra.get(code, {}), "boekjaar": boekjaar})
    return sorted(uit, key=lambda o: o["naam"])


# Kolommen van de doelpopulatie-csv. Vast in deze volgorde, zodat een oud
# cachebestand herkenbaar is aan de kop.
CSV_VELDEN = [
    "kvk_nummer", "naam", "plaats", "boekjaar", "subsector", "rechtsvorm",
    "omzet", "wissel_gerapporteerd", "oordeel_gerapporteerd",
    "verklaring_datum", "honorarium_controle", "honorarium_overig",
    "honorarium_fiscaal", "honorarium_nietcontrole",
]


def schrijf_csv(organisaties: list[dict], pad: Path) -> None:
    with pad.open("w", newline="", encoding="utf-8") as f:
        schrijver = csv.DictWriter(
            f, fieldnames=CSV_VELDEN, extrasaction="ignore", restval=""
        )
        schrijver.writeheader()
        schrijver.writerows(organisaties)


def lees_csv(pad: Path) -> list[dict]:
    with pad.open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def doelpopulatie_uit_cache(boekjaar: int, cache: Path) -> list[dict]:
    """De doelpopulatie, uit de cache of anders opnieuw bepaald.

    Beide laders gebruiken dit. Zonder gemeenschappelijk punt liep het mis: een
    cachebestand uit een oudere versie van deze code mist nieuwe kolommen, en dan
    hoort het opnieuw gemaakt te worden — niet gebruikt en niet als fout gemeld.

    Dat is precies wat een run van 2u22m liet sneuvelen. `vul_extra_velden` gaf
    "verwijder het bestand en draai opnieuw" en stopte met exit 1, wat nutteloos
    advies is aan een job die niemand bekijkt. `laad_zorg` controleerde helemaal
    niet en gebruikte de oude lijst stil, waardoor de nieuwe velden ook tijdens het
    laden nooit werden weggeschreven.

    De koprij is de versiecontrole: wijkt die af van CSV_VELDEN, dan is het
    bestand van vóór een wijziging en gooien we het weg.
    """
    pad = cache / f"doelpopulatie_{boekjaar}.csv"
    if pad.exists():
        with pad.open(encoding="utf-8") as f:
            kop = next(csv.reader(f), [])
        if kop == CSV_VELDEN:
            return lees_csv(pad)
        print(
            f"{pad.name} komt uit een oudere versie ({len(kop)} kolommen in plaats "
            f"van {len(CSV_VELDEN)}); opnieuw bepalen.",
            flush=True,
        )
        pad.unlink()

    print(f"dataset boekjaar {boekjaar} ophalen en ontleden...", flush=True)
    organisaties = doelpopulatie(download(boekjaar, cache), boekjaar)
    schrijf_csv(organisaties, pad)
    return lees_csv(pad)
