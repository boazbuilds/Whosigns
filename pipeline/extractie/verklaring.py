"""Uit een gedeponeerde pdf halen: soort verklaring + welk kantoor tekende.

Geen LLM. Twee deterministische stappen:
1. `pdftotext` (poppler) haalt de tekstlaag eruit.
2. Trefwoorden bepalen het soort verklaring; `kantoor_match` zoekt de kantoornaam
   op in de gesloten AFM-lijst.

Alleen een controleverklaring is een wettelijke controle. Samenstellings- en
beoordelingsverklaringen komen vaak van kantoren zónder Wta-vergunning — die horen
niet in `opdrachten` als wettelijke controle, en dat er geen match is, is dan juist
correct gedrag.

Gemeten op een steekproef van 41 zorg-pdf's (juli 2026, boekjaar 2023):
26 van de 27 controleverklaringen correct herleid tot een AFM-vergunninghouder
(96%), zonder valse matches. De rest: gescande pdf's zonder tekstlaag en één
verklaring waarin de kantoornaam alleen als logo staat — die gaan naar de
review-queue.

Guardrail: we halen uitsluitend de kantoornaam op. De naam van de tekenend
accountant staat wel in de tekst, maar wordt niet gezocht, niet teruggegeven en
niet gelogd.
"""

import subprocess

from kantoor_match import normaliseer

# Volgorde telt: een controleverklaring noemt vaak óók 'samengesteld'.
SOORT_KENMERKEN = [
    (
        "controle",
        (
            "controleverklaring van de onafhankelijke accountant",
            "naar ons oordeel",
            "ons oordeel",
        ),
    ),
    ("beoordeling", ("beoordelingsverklaring", "standaard 2400")),
    ("samenstelling", ("samenstellingsverklaring", "standaard 4410", "samengesteld")),
]

OORDEEL_KENMERKEN = [
    ("afkeurend", ("afkeurend oordeel",)),
    ("oordeelonthouding", ("oordeelonthouding", "geen oordeel tot uitdrukking")),
    ("beperking", ("oordeel met beperking", "verklaring met beperking")),
    ("goedkeurend", ("goedkeurend oordeel", "getrouw beeld", "naar ons oordeel")),
]

CONTINUITEIT_KENMERKEN = (
    "materiele onzekerheid over de continuiteit",
    "onzekerheid van materieel belang omtrent de continuiteit",
    "gerede twijfel over de continuiteit",
)


def pdf_naar_tekst(pad: str) -> str:
    """Lege string als de pdf geen tekstlaag heeft (gescand)."""
    resultaat = subprocess.run(
        ["pdftotext", "-q", pad, "-"], capture_output=True, text=True
    )
    return resultaat.stdout


def _eerste_treffer(genormaliseerd: str, kenmerken: list[tuple]) -> str | None:
    for label, sleutelwoorden in kenmerken:
        if any(woord in genormaliseerd for woord in sleutelwoorden):
            return label
    return None


def analyseer(tekst: str, index: dict) -> dict:
    """Geeft soort, oordeel, continuïteitsonzekerheid en kantoor.

    `kantoor` is None wanneer er geen betrouwbare match is; de aanroeper zet zo'n
    geval in de review_queue in plaats van te gokken.
    """
    from kantoor_match import zoek_kantoor

    genormaliseerd = normaliseer(tekst)
    if len(genormaliseerd) < 50:
        return {
            "soort": None,
            "oordeel": None,
            "continuiteitsonzekerheid": None,
            "kantoor": None,
            "reden": "geen tekstlaag (gescande pdf)",
        }

    soort = _eerste_treffer(genormaliseerd, SOORT_KENMERKEN)
    treffer = zoek_kantoor(tekst, index)
    return {
        "soort": soort,
        "oordeel": _eerste_treffer(genormaliseerd, OORDEEL_KENMERKEN)
        if soort == "controle"
        else None,
        "continuiteitsonzekerheid": any(
            woord in genormaliseerd for woord in CONTINUITEIT_KENMERKEN
        ),
        "kantoor": treffer["kantoor"] if treffer else None,
        "reden": None if treffer else "kantoornaam niet gevonden in de tekst",
    }
