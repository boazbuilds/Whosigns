"""Terugvalroute: de verklaring van de eigen website van een stichting halen.

Elke ANBI moet gegevens op internet publiceren, en het ANBI-bestand van de
Belastingdienst geeft van vrijwel elke instelling een website (45.554 van 45.554
actieve beschikkingen, zie `anbi.py`). Waar het CBF geen jaarverslag heeft — of waar
het geüploade bestand alleen het bestuursverslag blijkt te zijn — is die site de
enige plek waar de controleverklaring nog kan staan.

Deze route is **bewust een terugval en geen hoofdroute**: een eerste ruwe poging
haalde 1 kantoor uit 12 sites. Wat er misgaat is inmiddels bekend en hier
aangepakt:

1. Menu's die via JavaScript worden opgebouwd, geven geen links in de html →
   daarom ook een lijstje vaste paden proberen (`/anbi`, `/jaarverslag`, …), want
   de ANBI-publicatiepagina bestaat per definitie.
2. Het jaarverslag is soms een **html-pagina** ("online jaarverslag") in plaats van
   een pdf → html-tekst wordt net zo goed geanalyseerd als pdf-tekst.
3. De hoogst scorende pdf was regelmatig een privacyverklaring of beleidsplan →
   scoren op woorden die op jaarstukken duiden, en het boekjaar meewegen.
4. Eén niveau diep is te weinig → twee niveaus, met een harde limiet op het aantal
   verzoeken per site.

Guardrails: alleen GET-verzoeken, een pauze tussen verzoeken, een limiet op het
aantal pagina's en op de bestandsgrootte, en nooit buiten het domein van de
organisatie zelf. Wat we vinden gaat als bron-URL mee de database in, zodat elk
feit naar de vindplaats verwijst.

Geen dependencies buiten de standaardbibliotheek.
"""

import html as html_module
import re
import time
import urllib.error
import urllib.parse
import urllib.request

USER_AGENT = "WhoSigns/0.1 (open-data-import; contact via repo)"
PAUZE_S = 0.4
MAX_PAGINAS = 8          # verzoeken per site, inclusief de vaste paden
MAX_DOCUMENTEN = 4       # documenten die we daadwerkelijk analyseren
MAX_HTML_BYTES = 3_000_000
MAX_DOC_BYTES = 40_000_000

# Paden die er bij een ANBI vaak zijn, ook als het menu met JavaScript wordt gebouwd.
VASTE_PADEN = (
    "/anbi",
    "/anbi-informatie",
    "/over-ons/anbi",
    "/jaarverslag",
    "/jaarverslagen",
    "/jaarrekening",
    "/publicaties",
    "/downloads",
)

_JAARSTUK = re.compile(
    r"jaarverslag|jaarrekening|jaarbericht|jaarrapport|annual[-_ ]?report|"
    r"jaarcijfers|financieel|financiele|verantwoording|anbi|publicatieplicht|"
    r"download|documenten|over-ons|over_ons",
    re.I,
)
_STERK = re.compile(r"jaarverslag|jaarrekening|jaarcijfers|annual[-_ ]?report", re.I)
_JAAR = re.compile(r"20(1[5-9]|2[0-9])")
_LINK = re.compile(r"""<a\b[^>]*?href\s*=\s*["']([^"']+)["'][^>]*>(.*?)</a>""", re.I | re.S)
_SCRIPT = re.compile(r"<(script|style)\b.*?</\1>", re.I | re.S)
_TAG = re.compile(r"<[^>]+>")


def _haal(url: str, maximum: int, timeout: int = 25) -> tuple[str, str, bytes]:
    verzoek = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(verzoek, timeout=timeout) as antwoord:
            return (
                antwoord.geturl(),
                antwoord.headers.get("Content-Type", ""),
                antwoord.read(maximum),
            )
    finally:
        time.sleep(PAUZE_S)


def tekst_uit_html(inhoud: bytes) -> str:
    """Leesbare tekst uit een html-pagina — voor jaarverslagen die geen pdf zijn."""
    ruw = inhoud.decode("utf-8", "replace")
    ruw = _SCRIPT.sub(" ", ruw)
    return re.sub(r"\s+", " ", html_module.unescape(_TAG.sub(" ", ruw)))


def _links(inhoud: bytes, basis: str) -> list[tuple[str, str]]:
    uit = []
    for href, tekst in _LINK.findall(inhoud.decode("utf-8", "replace")):
        if href.startswith(("mailto:", "tel:", "#", "javascript:")):
            continue
        volledig = urllib.parse.urljoin(basis, href.strip())
        if not volledig.startswith(("http://", "https://")):
            continue
        uit.append((volledig, re.sub(r"\s+", " ", _TAG.sub(" ", tekst)).strip()[:120]))
    return uit


def _zelfde_site(url: str, basis: str) -> bool:
    """Alleen binnen het eigen domein blijven (www-prefix telt als hetzelfde)."""
    def kern(waarde: str) -> str:
        return urllib.parse.urlparse(waarde).netloc.lower().removeprefix("www.")

    return kern(url) == kern(basis)


def _is_pdf(url: str) -> bool:
    return url.lower().split("?")[0].endswith(".pdf")


def score(url: str, tekst: str, boekjaar: int | None = None) -> int:
    """Hoe waarschijnlijk is dit het jaarstuk met de verklaring erin?"""
    geheel = f"{url} {tekst}"
    punten = 0
    if _JAARSTUK.search(geheel):
        punten += 2
    if _STERK.search(geheel):
        punten += 4
    if re.search(r"jaarrekening", geheel, re.I):
        punten += 2
    if re.search(r"privacy|meldregeling|beleidsplan|statuten|algemene voorwaarden|"
                 r"vacature|nieuwsbrief|cookie", geheel, re.I):
        punten -= 5
    jaren = [int("20" + m) for m in _JAAR.findall(geheel)]
    if jaren:
        recentste = max(jaren)
        punten += 1
        if boekjaar and recentste == boekjaar:
            punten += 5          # precies het gevraagde boekjaar
        elif boekjaar and recentste > boekjaar:
            punten -= 2          # nieuwer jaar: staat de gevraagde verklaring niet in
        else:
            punten += max(0, recentste - 2018) // 2
    return punten


def zoek_documenten(website: str, boekjaar: int | None = None) -> list[dict]:
    """Kandidaat-jaarstukken op de site van een organisatie, beste eerst.

    Elk resultaat: {'url', 'titel', 'soort': 'pdf'|'html', 'score'}. Alleen
    opgehaalde html wordt doorzocht; de documenten zelf haalt de aanroeper op
    (`haal_document`), zodat hij de ruwe bytes kan bewaren vóór verwerking.
    """
    if not website:
        return []
    if not website.startswith(("http://", "https://")):
        website = f"https://{website}"

    verzoeken = 0
    try:
        basis_url, soort, inhoud = _haal(website, MAX_HTML_BYTES)
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError):
        return []
    verzoeken += 1
    if "pdf" in soort:  # site verwijst direct naar een pdf
        return [{"url": basis_url, "titel": "", "soort": "pdf", "score": 0}]

    documenten: dict[str, dict] = {}
    paginas: dict[str, str] = {}

    def verwerk_html(url: str, inhoud: bytes) -> None:
        for gevonden, titel in _links(inhoud, url):
            if not _zelfde_site(gevonden, basis_url):
                continue
            if _is_pdf(gevonden):
                documenten.setdefault(gevonden, {"url": gevonden, "titel": titel,
                                                 "soort": "pdf"})
            elif _JAARSTUK.search(f"{gevonden} {titel}"):
                paginas.setdefault(gevonden, titel)

    verwerk_html(basis_url, inhoud)

    # Vaste paden alleen proberen als de homepage weinig opleverde: dat scheelt de
    # bron verzoeken bij sites die hun links gewoon in de html hebben staan.
    if len(documenten) < 2:
        for pad in VASTE_PADEN:
            paginas.setdefault(urllib.parse.urljoin(basis_url, pad), pad.strip("/"))

    for url, titel in sorted(
        paginas.items(), key=lambda p: -score(p[0], p[1], boekjaar)
    ):
        if verzoeken >= MAX_PAGINAS:
            break
        try:
            echte_url, soort, pagina = _haal(url, MAX_HTML_BYTES)
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError):
            continue
        verzoeken += 1
        if "pdf" in soort:
            documenten.setdefault(echte_url, {"url": echte_url, "titel": titel,
                                              "soort": "pdf"})
            continue
        if "html" not in soort:
            continue
        verwerk_html(echte_url, pagina)
        # Een online jaarverslag in html: de verklaring staat dan op de pagina zelf.
        if re.search(r"controleverklaring|independent auditor", tekst_uit_html(pagina), re.I):
            documenten.setdefault(echte_url, {"url": echte_url, "titel": titel,
                                              "soort": "html"})

    for document in documenten.values():
        document["score"] = score(document["url"], document["titel"], boekjaar)
    return sorted(documenten.values(), key=lambda d: -d["score"])[:MAX_DOCUMENTEN]


def haal_document(document: dict) -> bytes | None:
    """Ruwe bytes van een kandidaat; None als het niets bruikbaars is."""
    try:
        _url, soort, inhoud = _haal(document["url"], MAX_DOC_BYTES, timeout=60)
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError):
        return None
    if document["soort"] == "pdf" and not inhoud.startswith(b"%PDF"):
        return None
    if document["soort"] == "html" and "html" not in soort:
        return None
    return inhoud
