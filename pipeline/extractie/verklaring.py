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

# Bezittelijke vorm, want dat is de kop van de oordeelparagraaf ("Ons oordeel met
# beperking", "Onze oordeelonthouding") en niet iets dat je in een beschouwing
# tegenkomt. Losse termen als "oordeelonthouding" of "oordeel met beperking"
# stonden ook in bestuursverslagen die het over de sector in het algemeen hadden —
# dat leverde twee onterechte oordeelonthoudingen op in de proefrit van boekjaar
# 2023 (Jeugdbescherming Brabant en Veilig Thuis Oost-Brabant, allebei in de zin
# "een hausse van verklaringen met beperking of oordeelonthoudingen").
OORDEEL_KENMERKEN = [
    ("afkeurend", ("ons afkeurend oordeel",)),
    ("oordeelonthouding", ("onze oordeelonthouding", "wij geven geen oordeel")),
    ("beperking", ("ons oordeel met beperking",)),
    ("goedkeurend", ("naar ons oordeel", "ons oordeel")),
]

# Ook geprobeerd en verworpen: het oordeel alleen zoeken in het stuk tekst vanaf de
# kop "controleverklaring van de onafhankelijke accountant". Klinkt logischer, maar
# die kop komt in een jaarrekening meerdere keren voor (inhoudsopgave, de
# verwijzing "de verklaring is opgenomen op pagina 69", en de verklaring zelf).
# Welke je ook kiest, je landt regelmatig ná de oordeelparagraaf: bij
# HagaZiekenhuis 2023 begon het venster middenin de fraudeparagraaf, waardoor een
# echt oordeel met beperking als goedkeurend uit de bus kwam. 38 oordelen sloegen
# op die manier de verkeerde kant op. De kopvorm hierboven doet het werk al.

# Waar gáát de controle over? "Controleverklaring van de onafhankelijke accountant"
# staat óók boven een verklaring bij een WNT-verantwoording of een financiële
# productieverantwoording, en dat zijn andere opdrachten dan de controle van de
# jaarrekening. Zonder dit onderscheid boeken we die als wettelijke controle en
# tellen ze mee in marktaandelen waar ze niet horen.
#
# Gemeten op de 686 geladen rijen van boekjaar 2023: 622 noemen de jaarrekening,
# 34 alleen WNT, 26 alleen productieverantwoording, 4 geen enkel kenmerk. Dus
# ongeveer één op de elf was verkeerd getypeerd.
#
# Let op de volgorde: een verzameldocument noemt vaak zowel de jaarrekening als de
# WNT-verantwoording. De jaarrekening is dan het zwaarste voorwerp en die wint.
VOORWERP_KENMERKEN = [
    (
        "wettelijke_controle",
        (
            "in de jaarverslaggeving opgenomen jaarrekening",
            "controle van de jaarrekening",
            "verklaring over de jaarrekening",
        ),
    ),
    (
        "wnt_verantwoording",
        (
            "wnt verantwoording",
            "verantwoordingsmodel wnt",
            "controleverklaring wnt",
            "wnt gegevens",
            "bezoldiging topfunctionarissen",
        ),
    ),
    (
        "productieverantwoording",
        (
            "financiele productieverantwoording",
            "productieverantwoording",
            "nacalculatie",
            "gerealiseerde productie",
        ),
    ),
    ("subsidieverklaring", ("subsidieverantwoording", "verantwoording subsidie")),
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
        # Waar de controle over gaat. None betekent: het is wél een
        # controleverklaring, maar we hebben niet kunnen vaststellen waarover —
        # dan is "wettelijke controle" een aanname en geen bevinding.
        "opdrachttype": (
            _eerste_treffer(genormaliseerd, VOORWERP_KENMERKEN)
            if soort == "controle"
            else None
        ),
        "oordeel": _eerste_treffer(genormaliseerd, OORDEEL_KENMERKEN)
        if soort == "controle"
        else None,
        "continuiteitsonzekerheid": any(
            woord in genormaliseerd for woord in CONTINUITEIT_KENMERKEN
        ),
        "kantoor": treffer["kantoor"] if treffer else None,
        "reden": None if treffer else "kantoornaam niet gevonden in de tekst",
    }
