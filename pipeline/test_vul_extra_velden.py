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


# Oud naar nieuw, ongeacht wat je typt. De velden die bij de organisatie horen
# (subsector, rechtsvorm, plaats) worden overschreven, dus de jaargang die als
# laatste draait bepaalt wat er staat. De standaardlijst van de workflow begint
# met het nieuwste jaar; die volgorde aanhouden gaf 2020 het laatste woord over
# waar een instelling vandaag gevestigd is.
check(
    "een kommalijst komt er oudste-eerst uit, ook als je hem andersom typt",
    gekozen_boekjaren(Argumenten("2023,2022")) == [2022, 2023],
)
check(
    "witruimte en lege stukken worden vergeven; dit wordt in een "
    "workflow-invoerveld getypt",
    gekozen_boekjaren(Argumenten(" 2023 ,, 2022,")) == [2022, 2023],
)
check(
    "dubbelen vallen weg",
    gekozen_boekjaren(Argumenten("2022,2023,2022")) == [2022, 2023],
)
check(
    "een lijst die je zelf typt draait van 2020 naar 2025",
    gekozen_boekjaren(Argumenten("2025,2024,2023,2022,2021,2020"))
    == [2020, 2021, 2022, 2023, 2024, 2025],
)

# "alle" haalt de jaargangen uit de downloadtabel. Dat is wat de workflow
# meegeeft, en het is er één plek in plaats van drie: de lijst stond ook in de
# twee invoervelden én nog eens hard in de stap zelf. Die laatste werd vergeten
# toen 2025 erbij kwam, en de run daarna stopte groen bij 2024 — alleen het
# nieuwste boekjaar, waar het om begonnen was, bleef leeg.
from digimv_dataset import DATASET_URL  # noqa: E402

check(
    "'alle' is elke jaargang uit de downloadtabel, oudste eerst",
    gekozen_boekjaren(Argumenten("alle")) == sorted(DATASET_URL),
)
check(
    "en dat is meer dan één jaargang, dus geen stille lege lijst",
    len(gekozen_boekjaren(Argumenten("alle"))) >= 6,
)
check(
    "hoofdletters en spaties rond 'alle' mogen; dit wordt getypt",
    gekozen_boekjaren(Argumenten("  Alle ")) == sorted(DATASET_URL),
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
