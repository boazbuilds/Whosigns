"""Tests voor de naam- en plaatsschoonmaak — elk geval komt uit de echte database.

Draaien vanuit de repo-root (geen testframework nodig, geen netwerk):

    python3 pipeline/test_digimv.py

Waarom dit bestand bestaat: het DigiMV-archief levert namen en plaatsen zoals de
indiener ze intypte. Op 3-8-2026 stonden er daardoor 394 gemeenten in KAPITALEN
op de site, elf namen met losse spaties en één organisatie met haar naam dubbel
achter elkaar. De schoonmaak hoort die gevallen op te lossen zonder ooit een
naam te beschadigen die al goed was.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "adapters"))

from digimv import schoon_naam, schoon_plaats  # noqa: E402

NAAM_GEVALLEN = [
    # het echte geval: naam dubbel, tweede keer mét rechtsvorm (KvK 41032279)
    (
        "Woon & Zorgcentrum HerfstzonWoon & Zorgcentrum Herfstzon (Stichting)",
        "Woon & Zorgcentrum Herfstzon (Stichting)",
    ),
    # exact dubbel zonder toevoeging
    ("Zorggroep NoordwestZorggroep Noordwest", "Zorggroep Noordwest"),
    # losse spaties (echte gevallen: Amarant, Treant Zorggroep)
    ("Amarant ", "Amarant"),
    ("Treant Zorggroep  (Stichting)", "Treant Zorggroep (Stichting)"),
    ("Mediant,  Stichting voor Geestelijke Gezondheidszorg", "Mediant, Stichting voor Geestelijke Gezondheidszorg"),
    # korte herhaling is toeval, geen dubbeling: blijft staan
    ("Tomtom", "Tomtom"),
    ("Zorg en Zorg B.V.", "Zorg en Zorg B.V."),
    # al goed: blijft exact gelijk
    ("Stichting HagaZiekenhuis", "Stichting HagaZiekenhuis"),
]

PLAATS_GEVALLEN = [
    ("GOOR", "Goor"),
    ("DEN HAAG", "Den Haag"),
    ("ALPHEN AAN DEN RIJN", "Alphen aan den Rijn"),
    ("BERGEN OP ZOOM", "Bergen op Zoom"),
    ("CAPELLE AAN DEN IJSSEL", "Capelle aan den IJssel"),
    ("IJSSELSTEIN", "IJsselstein"),
    ("'S-GRAVENHAGE", "'s-Gravenhage"),
    # de bron laat de apostrof soms weg
    ("S-HERTOGENBOSCH", "'s-Hertogenbosch"),
    ("'T HARDE", "'t Harde"),
    ("NIEUW-VENNEP", "Nieuw-Vennep"),
    # al goed: blijft onaangeraakt, ook als de spelling afwijkt
    ("Goor", "Goor"),
    ("den Haag", "den Haag"),
    ("", ""),
]


def main() -> int:
    fouten = 0
    for invoer, verwacht in NAAM_GEVALLEN:
        uitkomst = schoon_naam(invoer)
        goed = uitkomst == verwacht
        fouten += not goed
        print(f"{'✓' if goed else '✗'} naam   {invoer!r}")
        if not goed:
            print(f"    verwacht: {verwacht!r}\n    gevonden: {uitkomst!r}")
    for invoer, verwacht in PLAATS_GEVALLEN:
        uitkomst = schoon_plaats(invoer)
        goed = uitkomst == verwacht
        fouten += not goed
        print(f"{'✓' if goed else '✗'} plaats {invoer!r}")
        if not goed:
            print(f"    verwacht: {verwacht!r}\n    gevonden: {uitkomst!r}")

    totaal = len(NAAM_GEVALLEN) + len(PLAATS_GEVALLEN)
    print(f"\n{totaal - fouten}/{totaal} goed")
    return 1 if fouten else 0


if __name__ == "__main__":
    raise SystemExit(main())
