"""Autoriteit woningcorporaties (dVi) — de accountant staat er als veld in.

De enige bron tot nu toe die de accountant *gestructureerd* levert: geen archief, geen
pdf's, geen OCR. Hoofdstuk 1 van de verantwoordingsinformatie (dVi) heeft per corporatie
een kolom `Accountant`, met KvK-nummer, instellingsnaam en gemeente ernaast.

    https://data.overheid.nl  ->  dataset "Verantwoordingsinformatie woningcorporaties
                                  (dVi<jaar>-hfd1)"  ->  xlsx  ->  blad "Data H1"

Licentie **CC-0**: vrij te gebruiken, bronvermelding niet verplicht (we doen het wel).

Gemeten op 5-8-2026, alle achttien jaargangen:

| Jaargang | Corporaties | Accountant gevuld | Vorm |
|---|---|---|---|
| dVi2007 | 455 | 455 (100%) | ZIP, `Corp_H1_Algemeen_j07.xlsx` |
| dVi2008 | 430 | 430 (100%) | idem, drie accountantkolommen |
| dVi2009 | 418 | 418 (100%) | idem |
| dVi2010 | 400 | 400 (100%) | idem, eerste jaar mét KvK-nummer |
| dVi2011 | 389 | 389 (100%) | idem |
| dVi2012 | 380 | 380 (100%) | idem |
| dVi2013 | 378 | 378 (100%) | idem |
| dVi2015 | 349 | 349 (100%) | los xlsx, `CorpGeg_AccountantOrg_j1515` |
| dVi2022 | 277 | 277 (100%) | los xlsx, `Accountant` |
| dVi2024 | 272 | 272 (100%) | los xlsx, `Accountant` |

T/m 2013 staat een jaargang als één ZIP met ruim veertig bestanden; alleen
`Corp_H1_Algemeen` heeft één regel per corporatie. Vanaf 2014 is hoofdstuk 1
een los xlsx. Zie `docs/bestaande-databases.md`.

Zes eigenaardigheden van de bron, alle zes hier opgelost. De eerste drie gelden
overal, de laatste drie alleen voor de jaargangen t/m 2013:

1. **De veldnaam wisselt per jaargang** (zoals bij DigiMV). We zoeken de kolom daarom op
   patroon, niet op een vaste naam.
2. **Het blad wisselt van plek.** In dVi2022 staat de data op blad 2 ("Data H1"), in
   dVi2024 op blad 16 (want dat bestand bevat hoofdstuk 1 t/m 5). We nemen het eerste
   blad waarvan de koprij een accountant-kolom heeft.
3. **De schrijfwijze is zelfgerapporteerd en dus rommelig**: "BDO Audit & Assurance
   B.V.", "BDO Audit en Assurance BV", "BDO Audit&Assurace BV", "BDO Audit @ Assurance
   B.V." en gewoon "BDO" — in één jaargang. `KORTE_NAMEN` en `_MERKPATRONEN` hieronder
   vangen de merknamen op. Die staan bewust *niet* in `seed/kantoor_alias.csv`: dat is
   de lijst voor het herkennen van ondertekeningen in pdf's, en een losse "BDO" hoort
   daar niet in.
4. **dVi2008 heeft drie accountantkolommen**, waarvan de eerste de persóón is en niet
   het kantoor. Zie `ACCOUNTANT_ORGANISATIE`.
5. **Vóór 2010 staat er geen KvK-nummer in**, alleen het corporatienummer.
   `brug_naar_kvk` vertaalt dat met de jaargangen die beide velden dragen.
6. **De kolomnamen zijn de interne modelveldnamen** (`CorpGeg_StatNm_DB_j0707`) in
   plaats van leesbare koppen. Zie `KOLOMPATRONEN`.

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

OUDSTE_BOEKJAAR = 2007
NIEUWSTE_BOEKJAAR = 2024

# T/m 2013 staat een jaargang als één ZIP met alle hoofdstukken erin; vanaf 2014
# is hoofdstuk 1 een los xlsx. Beide bevatten hetzelfde: één regel per corporatie
# met de accountantsorganisatie erbij.
LAATSTE_BUNDELJAAR = 2013

XLSX_NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"

# Kolommen die we nodig hebben, per patroon (de exacte naam wisselt per jaargang).
#
# De oude jaargangen gebruiken de veldnamen uit het dVi-model zelf en niet de
# leesbare koppen van later: `CorpGeg_StatNm_DB_j0707` in plaats van
# "Instellingsnaam", `CorpGeg_NmGemVest_DB_j0707` in plaats van "Gemeente",
# `IdCorp_j07` in plaats van "L-nummer". Zonder die patronen bleef naam en
# gemeente leeg — en omdat de lader dan het KvK-nummer als naam invult, staan er
# nu 71 corporaties in de database die "24112244" heten.
KOLOMPATRONEN = {
    "kvk_nummer": r"^kvk[_ ]?nummer$|kvk",
    "naam": r"^instellingsnaam$|corporatienaam|naam.*instelling|statnm",
    "gemeente": r"^gemeente$|nmgemvest",
    "instellingsnummer": r"^instellingsnummer$|^l-?nummer$|^idcorp",
    "accountant": r"accountant",
}

# Welke accountant-kolom je moet hebben als er meer dan één is.
#
# dVi2008 heeft er drie: `CorpGeg_AccountantNaam_j0808` (de persoon, "Drs. H.D.M.
# Plomp RA"), `CorpGeg_AccountantOrg_j0808` (het kantoor) en
# `CorpGeg_AccountantPlaats_j0808`. Op alfabetische kolomvolgorde wint de
# persoonsnaam, en dan zou WhoSigns beweren dat "Drs. H.D.M. Plomp RA" een
# accountantskantoor is. Vandaar: de organisatiekolom heeft voorrang, en een
# kolom die overduidelijk de persoon of de vestigingsplaats is telt nooit mee.
ACCOUNTANT_ORGANISATIE = re.compile(r"accountant\w*org|accountantsorganisatie", re.I)
ACCOUNTANT_GEEN_ORGANISATIE = re.compile(r"accountant\w*(naam|plaats|nr|nummer)", re.I)

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
    # Schrijffouten in dezelfde ruiswoorden, geteld op de jaargangen 2007-2013:
    # "Deloitte Accountans", "Deloitte Acocuntants", "BDO Audit & Assureance".
    "accountans", "acocuntants", "accountantskantoor", "assureance", "acc",
    "aa", "ra", "registeraccountant", "accontants",
}

# Merken die in de oude jaargangen onder een andere of verhaspelde naam staan.
#
# De opgave is met de hand ingevuld en dat is te zien: BDO heette tot 2010 "BDO
# CampsObers" en komt in vijftien schrijfwijzen voor ("BDO Camps Obers", "BDO
# ChampsObers", "B.D.O. CampsObers"), PricewaterhouseCoopers in acht ("Price
# Waterhouse Coopers", "PricewatrerhouseCoopers", aan elkaar geplakt met
# "Accountants"), en Deloitte staat er twee keer als "Deloiite".
#
# Dit is bewust een korte lijst van patronen en geen zoek-op-gelijkenis: elk
# patroon noemt één merk dat maar één kantoor kan zijn. Wat er niet in staat
# valt gewoon af en komt in de review-queue — kleine kantoren als "Du Roi",
# "Westpark" en "Accountantskantoor E. Nikkels" horen daar thuis, want die
# staan niet in het AFM-register en mogen niet geraden worden.
_MERKPATRONEN: list[tuple[re.Pattern, str]] = [
    (re.compile(r"ch?amps?\s*obers|\bbdo\b", re.I), "BDO Audit & Assurance B.V."),
    (re.compile(r"price\s*wat\w*hous\w*\s*coopers", re.I),
     "PricewaterhouseCoopers Accountants N.V."),
    (re.compile(r"\bdelo[il]+t+e\b", re.I), "Deloitte Accountants B.V."),
    # Alleen aan het begin: "Berk N.V." is het kantoor dat later Baker Tilly Berk
    # werd, maar een naam als "Van den Berk & Partners" is dat niet.
    (re.compile(r"^berk\b", re.I), "Baker Tilly (Netherlands) B.V."),
    (re.compile(r"\bgibo\b", re.I), "Flynth Audit B.V."),
    (re.compile(r"foederer", re.I), "Crowe Foederer Audit & Assurance B.V."),
]

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
            if boekjaar <= LAATSTE_BUNDELJAAR:
                # Deze jaargangen staan als één ZIP met alle hoofdstukken; er is
                # geen los hoofdstuk 1 om uit te kiezen.
                if url.lower().endswith(".zip"):
                    kandidaten.append((0, url))
                continue
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
    voorkeur: str | None = None
    for letter, kop in koprij.items():
        kop_tekst = str(kop).strip()
        if ACCOUNTANT_ORGANISATIE.search(kop_tekst):
            voorkeur = voorkeur or letter
        for veld, patroon in KOLOMPATRONEN.items():
            if veld in gevonden:
                continue
            if veld == "accountant" and ACCOUNTANT_GEEN_ORGANISATIE.search(kop_tekst):
                # De persoonsnaam of de vestigingsplaats van de accountant; nooit
                # het kantoor. Zie de toelichting bij ACCOUNTANT_ORGANISATIE.
                continue
            if re.search(patroon, kop_tekst, re.I):
                gevonden[veld] = letter
    if voorkeur:
        gevonden["accountant"] = voorkeur
    return gevonden if "accountant" in gevonden else None


def _schoon_kvk(waarde: str) -> str:
    """KvK-nummer op één vaste vorm: acht cijfers, met voorloopnul.

    De bron is hierin niet consequent: dVi2010 schrijft `1032035`, dVi2013
    schrijft `01032035` voor dezelfde corporatie. Omdat het KvK-nummer de sleutel
    is waarop organisaties worden samengevoegd, leverde dat twee rijen op voor
    één corporatie — 66 van de 436 corporaties in de database staan er dubbel in.
    Acht cijfers is de officiële lengte, dus daar trekken we alles naartoe.
    """
    cijfers = re.sub(r"\D", "", waarde or "")
    if not cijfers:
        return ""
    return cijfers.zfill(8) if len(cijfers) <= 8 else cijfers


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
    # Stap 0: een merk dat alleen onder een oude of verhaspelde naam voorkomt.
    # Vóór de kernwoorden, want juist die verhaspeling maakt de sleutel onbruikbaar.
    for patroon, kantoor in _MERKPATRONEN:
        if patroon.search(schoon):
            return kantoor
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
                    "kvk_nummer": _schoon_kvk(
                        str(rij.get(kolommen.get("kvk_nummer", ""), ""))
                    ),
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


_H1_IN_ZIP = re.compile(r"Corp[_ ]?H1[_ ]", re.I)


def hoofdstuk1_uit_zip(inhoud: bytes) -> bytes:
    """Het hoofdstuk-1-bestand uit een gebundelde jaargang (2007 t/m 2013).

    Zo'n ZIP bevat ruim veertig xlsx-bestanden — balans, huurontwikkeling,
    bezit per gemeente. Alleen `Corp_H1_Algemeen_jNN.xlsx` heeft één regel per
    corporatie met de accountantsorganisatie erbij.
    """
    with zipfile.ZipFile(io.BytesIO(inhoud)) as archief:
        namen = [n for n in archief.namelist() if _H1_IN_ZIP.search(n)]
        if not namen:
            namen = [
                n
                for n in archief.namelist()
                if n.lower().endswith(".xlsx") and "algemeen" in n.lower()
            ]
        if not namen:
            raise LookupError("geen hoofdstuk-1-bestand in de ZIP")
        return archief.read(sorted(namen)[0])


def corporaties(boekjaar: int, cache: Path | None = None) -> list[dict]:
    """Alle corporaties van dit boekjaar met hun accountant, opgehaald bij de bron."""
    url = dataset_url(boekjaar)
    bundel = boekjaar <= LAATSTE_BUNDELJAAR
    pad = None
    if cache is not None:
        cache.mkdir(exist_ok=True)
        pad = cache / f"dvi{boekjaar}_h1.{'zip' if bundel else 'xlsx'}"
    if pad is not None and pad.exists():
        inhoud = pad.read_bytes()
    else:
        inhoud = _haal(url, timeout=600)
        if pad is not None:
            pad.write_bytes(inhoud)
    if bundel:
        inhoud = hoofdstuk1_uit_zip(inhoud)
    return _lees(inhoud, boekjaar, url)


# Boekjaren waarin de bron zelf een KvK-nummer meelevert. Vóór 2010 niet.
EERSTE_JAAR_MET_KVK = 2010


def brug_naar_kvk(cache: Path | None = None, jaren: range | None = None) -> dict[str, str]:
    """Corporatienummer -> KvK-nummer, opgebouwd uit de jaargangen die beide hebben.

    De jaargangen 2007 t/m 2009 noemen geen KvK-nummer, alleen het corporatienummer
    (`IdCorp`, de L-nummers van de toezichthouder). Zonder KvK kan de lader een
    corporatie niet aan een organisatie koppelen en zou een derde van de winst
    hier wegvallen.

    Het corporatienummer is wél stabiel: nagemeten op de zeven bundeljaargangen is
    het in elke jaargang uniek, en het overleeft naamswijzigingen — L0013 heet in
    2007 "Stichting Wonen 's-Hertogenbosch" en in 2013 "Stichting Zayaz", maar het
    is dezelfde corporatie. Daarom bouwen we de vertaling uit de jaargangen die
    beide velden dragen. Dekking, gemeten: 400 van de 455 corporaties in 2007
    (88%), 400 van 430 in 2008 (93%) en 400 van 418 in 2009 (96%).

    Wat niet in de brug zit is een corporatie die vóór 2010 is opgeheven of
    gefuseerd. Die krijgt geen KvK-nummer en wordt door de lader gemeld als
    `geen_kvk` — nooit stil geraden.
    """
    brug: dict[str, str] = {}
    for boekjaar in jaren or range(EERSTE_JAAR_MET_KVK, LAATSTE_BUNDELJAAR + 1):
        try:
            rijen = corporaties(boekjaar, cache=cache)
        except Exception:  # noqa: BLE001 — één jaargang mag ontbreken
            continue
        for rij in rijen:
            nummer = (rij.get("instellingsnummer") or "").strip()
            kvk = (rij.get("kvk_nummer") or "").strip()
            if nummer and kvk:
                brug.setdefault(nummer, kvk)
    return brug
