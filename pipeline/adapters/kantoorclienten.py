"""Cliënten van één kantoor, uit losse openbare jaarstukken.

Waarom dit naast de andere bronnen bestaat
------------------------------------------
De bestaande bronnen werken *populatie-eerst*: er is één partij die voor een
hele sector publiceert (DigiMV voor de zorg, de dVi voor corporaties, het CBF
voor goede doelen, het AFM-register voor beursfondsen), en daaruit rolt vanzelf
wie welke accountant heeft.

Voor een kantoor zónder OOB-vergunning bestaat zo'n lijst niet. Die kantoren
hoeven geen transparantieverslag met cliëntenlijst te publiceren, en hun
cliënten zijn meestal besloten vennootschappen die hun jaarrekening bij de
Kamer van Koophandel deponeren — en de KvK is voor dit project uitgesloten.

Wat er dan overblijft is *document-eerst*: je vindt per organisatie een
openbaar jaarstuk waarin de accountant met naam wordt genoemd. Dat is handwerk
per geval, maar het levert wél harde, controleerbare feiten op.

De guardrail die dit werkbaar maakt
-----------------------------------
Een seed-regel is hier niet meer dan een bewéring: "in dit document staat dat
kantoor X tekende bij organisatie Y over boekjaar Z". Deze module haalt het
document er zelf bij en controleert die bewering vóórdat er iets wordt
weggeschreven. Klopt hij niet — het document is verdwenen, zit achter een
inlog, of noemt het kantoor helemaal niet — dan komt er géén rij in de
database, alleen een regel in het rapport.

Dat is bewust strenger dan bij de andere bronnen. Daar staat een centrale
uitgever garant voor de inhoud; hier is de enige garantie het document zelf.
"""

import html
import re
import urllib.request
from pathlib import Path

KOPPEN = {"User-Agent": "Mozilla/5.0 (WhoSigns-pipeline)"}

# Bronnen die feitelijk een doorverkoop van het Handelsregister zijn. De KvK is
# voor dit project uitgesloten (besluit van de opdrachtgever), en dan is een
# afgeleide daarvan het net zo goed. Liever hier hard weigeren dan erop
# vertrouwen dat iedereen die een seed-regel toevoegt eraan denkt.
_KVK_AFGELEID = re.compile(
    r"(?:^|\.)(?:kvk\.nl|company\.info|companyinfo\.nl|drimble\.nl|"
    r"opencorporates\.com|bedrijfsdata\.nl|graydon\.nl|creditsafe\.nl|"
    r"handelsregister\.nl)(?:/|$)",
    re.I,
)


class BronGeweigerd(Exception):
    """De opgegeven vindplaats mag niet als bron dienen."""


def controleer_vindplaats(url: str) -> None:
    """Weigert vindplaatsen die niet als openbare bron mogen tellen."""
    if not url.lower().startswith(("http://", "https://")):
        raise BronGeweigerd(f"geen webadres: {url}")
    gastheer = re.sub(r"^https?://", "", url, flags=re.I).split("/")[0].lower()
    if _KVK_AFGELEID.search(gastheer) or _KVK_AFGELEID.search(f".{gastheer}/"):
        raise BronGeweigerd(
            f"{gastheer} is (een afgeleide van) het Handelsregister; "
            "de KvK is als bron uitgesloten"
        )


def haal_document(url: str, doel: Path) -> Path:
    """Haalt het document één keer op; wat er al staat, blijft staan."""
    controleer_vindplaats(url)
    if not (doel.exists() and doel.stat().st_size > 1000):
        verzoek = urllib.request.Request(url, headers=KOPPEN)
        with urllib.request.urlopen(verzoek, timeout=180) as antwoord:
            doel.write_bytes(antwoord.read())
    return doel


# Bloktags krijgen een regeleinde; alle andere tags verdwijnen geluidloos, zodat
# een naam die in de opmaak door een <span> wordt onderbroken heel blijft.
_BLOKTAG = re.compile(
    r"</?(?:p|div|br|tr|td|th|li|ul|ol|table|h[1-6]|section|article)\b[^>]*>", re.I
)
_STIJL_SCRIPT = re.compile(r"<(?:style|script)[^>]*>.*?</(?:style|script)>", re.S | re.I)


def html_naar_tekst(bron: str) -> str:
    tekst = _STIJL_SCRIPT.sub(" ", bron)
    tekst = re.sub(r"<!--.*?-->", " ", tekst, flags=re.S)
    tekst = _BLOKTAG.sub("\n", tekst)
    tekst = re.sub(r"<[^>]+>", "", tekst)
    tekst = html.unescape(tekst).replace("\xad", "")
    tekst = re.sub(r"[ \t ]+", " ", tekst)
    return re.sub(r"\n\s*\n+", "\n", tekst).strip()


def tekst_uit_document(pad: Path) -> str:
    """Platte tekst uit een opgehaald document (pdf of webpagina)."""
    kop = pad.open("rb").read(5)
    if kop.startswith(b"%PDF"):
        import sys

        sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "extractie"))
        from verklaring import tekst_uit_pdf

        # Met OCR-terugval: een gescande jaarrekening is geen zeldzaamheid.
        tekst, _ = tekst_uit_pdf(str(pad), ocr=True)
        return tekst
    return html_naar_tekst(pad.read_bytes().decode("utf-8", "replace"))


def _losse_woorden(naam: str) -> list[str]:
    return [w for w in re.split(r"[^a-z0-9]+", naam.lower()) if w]


# Woorden die in bijna elke kantoornaam staan en dus niets onderscheiden.
_ALGEMEEN = {
    "accountants", "accountant", "audit", "assurance", "registeraccountants",
    "adviseurs", "advies", "bv", "nv", "b", "v", "n", "en", "de", "het", "van",
    "group", "groep", "nederland", "maatschap", "accountancy", "controle",
}


def noemt_kantoor(tekst: str, kantoornaam: str, aliassen: list[str] | None = None) -> str | None:
    """Het letterlijke stuk tekst waarin het kantoor voorkomt, of None.

    Zoekt op het kenmerkende deel van de naam ("Confinant"), niet op de hele
    statutaire naam: in een verklaring staat vaak "Confinant Audit & Assurance
    B.V." maar in de ondertekening soms alleen "Confinant". Zoeken op de volle
    naam zou die tweede vorm missen, en dan zou een echte cliënt onterecht
    worden afgewezen.
    """
    kandidaten = [kantoornaam, *(aliassen or [])]
    kernen = []
    for kandidaat in kandidaten:
        woorden = [w for w in _losse_woorden(kandidaat) if w not in _ALGEMEEN and len(w) > 2]
        if woorden:
            kernen.append(woorden[0])
    if not kernen:
        return None

    plat = re.sub(r"\s+", " ", tekst)
    for kern in kernen:
        treffer = re.search(rf"\b{re.escape(kern)}\w*", plat, re.I)
        if treffer:
            begin = max(0, treffer.start() - 90)
            return plat[begin : treffer.end() + 110].strip()
    return None
