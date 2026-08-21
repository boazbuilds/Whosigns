"""Test: de boekjaarkeuze van vul_extra_velden.

Waarom dit bestaat. Tot 21-8-2026 kon dit script één boekjaar aan en draaide
het in zorgdata.yml alleen voor het lijstjaar (2023). De honoraria van 2022 —
leesbaar sinds de koprijreparatie in digimv_dataset — kwamen daardoor nergens
binnen: de opdrachtgever keek op /honoraria en zag alleen 2023. De workflow
"Honoraria bijvullen" geeft nu een kommalijst mee, en die wordt hier ontleed.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent / "adapters"))

from vul_extra_velden import gekozen_boekjaren  # noqa: E402

goed = 0
fout = 0


def check(omschrijving: str, voorwaarde: bool) -> None:
    global goed, fout
    if voorwaarde:
        goed += 1
    else:
        fout += 1
        print(f"  FOUT: {omschrijving}")


class Argumenten:
    def __init__(self, boekjaren="", boekjaar=2023):
        self.boekjaren = boekjaren
        self.boekjaar = boekjaar


check(
    "een kommalijst wordt in volgorde ontleed",
    gekozen_boekjaren(Argumenten("2023,2022")) == [2023, 2022],
)
check(
    "witruimte en lege stukken worden vergeven; dit wordt in een "
    "workflow-invoerveld getypt",
    gekozen_boekjaren(Argumenten(" 2023 ,, 2022,")) == [2023, 2022],
)
check(
    "dubbelen vallen weg met behoud van volgorde",
    gekozen_boekjaren(Argumenten("2022,2023,2022")) == [2022, 2023],
)
check(
    "zonder lijst valt hij terug op --boekjaar; zo blijft zorgdata.yml werken",
    gekozen_boekjaren(Argumenten("", 2021)) == [2021],
)
check(
    "de lijst wint van --boekjaar als beide er staan",
    gekozen_boekjaren(Argumenten("2020", 2023)) == [2020],
)

print(f"{goed}/{goed + fout} goed")
sys.exit(1 if fout else 0)
