"""AFM-register financiële verslaggeving: gedeponeerde jaarverslagen ophalen.

Uitgevende instellingen met Nederland als lidstaat van herkomst (beursfondsen)
moeten hun jaarlijkse financiële verslaggeving bij de AFM deponeren
(Transparantierichtlijn); de AFM publiceert de gedeponeerde stukken in een
openbaar register. Dat is een centrale vindplaats van jaarverslagen — en dus
van controleverklaringen — van beursfondsen, terug tot boekjaar 2006.

Gemeten op 4-8-2026:

    export (csv)   9.645 deponeringen, waarvan 4.201 jaarlijkse
                   verslaggeving van 547 instellingen, boekjaren 2006-2025
                   (~150-270 per jaar); de export bevat géén documentlinks
    lijstpagina    ?page=1..N, 50 rijen per pagina, per rij een detail-id
    detailpagina   details?id=... met één documentlink per deponering
                   (downloadregisterfile.aspx met een versleuteld token)
    documenten     t/m boekjaar ~2019 een pdf; daarna een ESEF-zip met het
                   jaarverslag als xhtml (inline XBRL) erin

De leesroute voor beide documentsoorten eindigt in platte tekst, waarna
extractie/verklaring.py er de controleverklaring, het oordeel en het kantoor
uit haalt — precies zoals bij de CBF-verslagen. Let op: niet elk fonds heeft
een Nederlandse accountant (HAL Trust tekent bij PricewaterhouseCoopers
Bermuda); zulke gevallen horen géén match op te leveren en gaan naar de
review-wachtrij.
"""

import html
import re
import time
import urllib.request
import zipfile
from pathlib import Path

BASIS = "https://www.afm.nl"
REGISTER = f"{BASIS}/nl-nl/sector/registers/meldingenregisters/financiele-verslaggeving"
KOPPEN = {"User-Agent": "Mozilla/5.0 (WhoSigns-pipeline)"}


def _haal(url: str) -> bytes:
    verzoek = urllib.request.Request(url, headers=KOPPEN)
    with urllib.request.urlopen(verzoek, timeout=180) as antwoord:
        return antwoord.read()


def _schoon_cel(cel: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", cel))).strip()


def rijen_uit_lijst(pagina_html: str) -> list[dict]:
    """Deponeringen uit één lijstpagina: id, datum, instelling, boekjaar, soort."""
    rijen = []
    for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", pagina_html, re.S):
        treffer = re.search(r"details\?id=([A-Za-z0-9-]+)", tr)
        if not treffer:
            continue
        cellen = [_schoon_cel(c) for c in re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)]
        if len(cellen) < 4:
            continue
        rijen.append(
            {
                "id": treffer.group(1),
                "datum": cellen[0],
                "instelling": cellen[1],
                "boekjaar": cellen[2],
                "soort": cellen[3],
            }
        )
    return rijen


def aantal_paginas(pagina_html: str) -> int:
    nummers = [int(n) for n in re.findall(r'data-page-number="(\d+)"', pagina_html)]
    return max(nummers) if nummers else 1


def deponeringen(haal=_haal, pauze: float = 0.2) -> list[dict]:
    """Alle deponeringen uit het register, via de lijstpagina's.

    De csv-export van het register kent geen detail-ids, dus de lijstpagina's
    zijn de enige route naar de documenten (193 pagina's, ~2 minuten).
    """
    eerste = haal(f"{REGISTER}?page=1").decode("utf-8", "replace")
    alle = rijen_uit_lijst(eerste)
    for pagina in range(2, aantal_paginas(eerste) + 1):
        if pauze:
            time.sleep(pauze)
        rijen = rijen_uit_lijst(haal(f"{REGISTER}?page={pagina}").decode("utf-8", "replace"))
        if not rijen:
            break
        alle.extend(rijen)
    return alle


def jaarlijkse(deponeringen: list[dict]) -> list[dict]:
    """Jaarlijkse verslaggeving, nieuwste deponering per instelling en boekjaar.

    Het register schrijft de soort in twee spellingen ("Jaarlijkse Financiële"
    en "Jaarlijkse financiële") en een herdeponering vervangt een eerdere; de
    lijstpagina's staan nieuwste-eerst, dus de eerste die we tegenkomen wint.
    """
    gezien: set[tuple[str, str]] = set()
    uitkomst = []
    for rij in deponeringen:
        if not rij["soort"].lower().startswith("jaarlijkse"):
            continue
        sleutel = (rij["instelling"].casefold(), rij["boekjaar"])
        if sleutel in gezien:
            continue
        gezien.add(sleutel)
        uitkomst.append(rij)
    return uitkomst


def document_link(detail_html: str) -> tuple[str, str] | None:
    """(bestandsnaam, volledige url) van het gedeponeerde document."""
    link = re.search(r'href="(/downloadregisterfile\.aspx[^"]*)"', detail_html)
    if not link:
        return None
    url = BASIS + html.unescape(link.group(1))
    naam = re.search(r"([\w.-]+\.(?:pdf|zip|xhtml))", re.sub(r"<[^>]+>", " ", detail_html), re.I)
    return (naam.group(1) if naam else "document", url)


def haal_detail(deponering_id: str, haal=_haal) -> str:
    return haal(f"{REGISTER}/details?id={deponering_id}").decode("utf-8", "replace")


# Bloktags krijgen een regeleinde; alle andere tags verdwijnen geluidloos.
# Dat laatste is wezenlijk voor ESEF: inline-XBRL wikkelt spans dwars door
# woorden heen ("Amst<ix:...>elveen"), en een regeleinde per tag zou elke
# zin — en dus elk oordeelkenmerk — in stukken knippen.
_BLOKTAG = re.compile(
    r"</?(?:p|div|br|tr|td|th|li|ul|ol|table|thead|tbody|h[1-6]|section|article|blockquote)\b[^>]*>",
    re.I,
)
_STIJL_SCRIPT = re.compile(r"<(?:style|script)[^>]*>.*?</(?:style|script)>", re.S | re.I)


def xhtml_naar_tekst(xhtml: str) -> str:
    tekst = _STIJL_SCRIPT.sub(" ", xhtml)
    tekst = re.sub(r"<!--.*?-->", " ", tekst, flags=re.S)
    tekst = _BLOKTAG.sub("\n", tekst)
    tekst = re.sub(r"<[^>]+>", "", tekst)
    tekst = html.unescape(tekst)
    tekst = tekst.replace("\xad", "")  # zachte afbreekstreepjes
    tekst = re.sub(r"[ \t ]+", " ", tekst)
    return re.sub(r"\n\s*\n+", "\n", tekst).strip()


def tekst_uit_document(pad: Path) -> str:
    """Platte tekst uit een gedeponeerd document (pdf of ESEF-zip)."""
    kop = pad.open("rb").read(4)
    if kop[:2] == b"PK":  # zip: ESEF-pakket met het verslag als xhtml
        with zipfile.ZipFile(pad) as z:
            kandidaten = [
                i for i in z.infolist() if i.filename.lower().endswith((".xhtml", ".html"))
            ]
            if not kandidaten:
                return ""
            # Het verslag zelf is veruit het grootste xhtml-bestand in het pakket.
            grootste = max(kandidaten, key=lambda i: i.file_size)
            return xhtml_naar_tekst(z.read(grootste).decode("utf-8", "replace"))
    # Import hier, zodat de adapter ook zonder poppler te testen blijft.
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "extractie"))
    from verklaring import pdf_naar_tekst

    return pdf_naar_tekst(str(pad))
