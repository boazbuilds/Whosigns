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

# --- de plausibiliteitscheck --------------------------------------------------
# De echte gevallen van 5-10-2026, met verzonnen organisaties: een bedrag in
# duizenden in plaats van euro's naast gewone jaren.
from vul_extra_velden import plausibel  # noqa: E402

check(
    "een bedrag in duizenden naast een gewoon jaar valt af (327.805.000 tegen 336.000)",
    not plausibel(327_805_000, {2021: 336_000}, 2020),
)
check(
    "en andersom ook: 231 euro tussen 161.000 en 251.000",
    not plausibel(231, {2022: 161_000, 2024: 251_000}, 2023),
)
check(
    "een gewone stijging gaat door, ook een flinke (x3 bij een kantoorwissel)",
    plausibel(180_000, {2021: 60_000}, 2022),
)
check(
    "zonder andere jaren valt er niets te vergelijken en gaat het bedrag door",
    plausibel(1_500_000, {}, 2020),
)
check(
    "het eigen boekjaar telt niet mee als vergelijking (dat is de oude waarde)",
    plausibel(336_000, {2021: 327_805_000}, 2021),
)
check(
    "één uitschieter in de vergelijking is genoeg om niet te schrijven",
    not plausibel(336_000, {2020: 327_805_000, 2022: 340_000}, 2021),
)
check("nul of negatief is nooit een honorarium", not plausibel(0, {}, 2020))

# --- de schrijfroute ----------------------------------------------------------
# Wat gaat er naar de database, met welk filter? Een nep-database legt de
# verzoeken vast; de organisaties zijn verzonnen.
import vul_extra_velden  # noqa: E402


class NepDb:
    def __init__(self, opdracht_bestaat=True):
        self.patches = []
        self.reviews = []
        self.bestaat_vragen = []
        self.opdracht_bestaat = opdracht_bestaat

    def selecteer_alles(self, tabel, query="select=*"):
        if tabel == "organisaties":
            return [{"id": 1, "kvk_nummer": "11111111"}, {"id": 2, "kvk_nummer": "22222222"}]
        if "honorarium_controle_eur=not.is.null" in query:
            # Organisatie 2 heeft in 2021 een gewoon controlehonorarium.
            return [{"organisatie_id": 2, "boekjaar": 2021, "honorarium_controle_eur": 50000}]
        # De gelezen controles: organisatie 1 heeft er een in 2019 en 2020,
        # organisatie 2 alleen marktonderzoek.
        return [{"organisatie_id": 1, "boekjaar": 2019}, {"organisatie_id": 1, "boekjaar": 2020}]

    def bijwerken(self, tabel, filter, velden):
        self.patches.append((tabel, filter, dict(velden)))

    def bestaat(self, tabel, filter):
        self.bestaat_vragen.append((tabel, filter))
        return self.opdracht_bestaat if tabel == "opdrachten" else False

    def invoegen(self, tabel, rij):
        self.reviews.append(rij)
        return rij


def draai(rijen, db):
    oud_cache, oud_db = vul_extra_velden.digimv_dataset.doelpopulatie_uit_cache, vul_extra_velden.Supabase
    vul_extra_velden.digimv_dataset.doelpopulatie_uit_cache = lambda boekjaar, cache: rijen
    vul_extra_velden.Supabase = lambda: db
    try:
        vul_extra_velden.vul_boekjaar(2020)
    finally:
        vul_extra_velden.digimv_dataset.doelpopulatie_uit_cache = oud_cache
        vul_extra_velden.Supabase = oud_db
    return [p for p in db.patches if p[0] == "opdrachten"]


import contextlib  # noqa: E402
import io  # noqa: E402

gewoon = {
    "kvk_nummer": "11111111", "naam": "Stichting Verzonnen",
    "honorarium_controle": "60000", "honorarium_overig": "5000",
    "honorarium_controle_vorig": "58000", "honorarium_overig_vorig": "4000",
}
db = NepDb()
with contextlib.redirect_stdout(io.StringIO()):
    patches = draai([gewoon], db)
lopend = [p for p in patches if "boekjaar=eq.2020" in p[1]]
vorig = [p for p in patches if "boekjaar=eq.2019" in p[1]]
check(
    "met een gelezen controle gaat het lopende jaar alléén daarheen, niet ook naar "
    "een marktonderzoekrij ernaast (anders telt het honorarium dubbel)",
    len(lopend) == 1
    and "type_opdracht=in.(wettelijke_controle,vrijwillige_controle)" in lopend[0][1],
)
check(
    "het vergelijkende cijfer gaat in één verzoek naar boekjaar J-1",
    len(vorig) == 1
    and vorig[0][2] == {"honorarium_controle_eur": "58000", "honorarium_overig_eur": "4000"},
)
check(
    "en alleen naar een wettelijke of vrijwillige controle zonder énig honorarium",
    "type_opdracht=in.(wettelijke_controle,vrijwillige_controle)" in vorig[0][1]
    and all(
        f"{k}=is.null" in vorig[0][1]
        for k in ("honorarium_controle_eur", "honorarium_overig_eur",
                  "honorarium_fiscaal_eur", "honorarium_nietcontrole_eur")
    ),
)
check("een gewone rij geeft geen review-geval", db.reviews == [])

# Een eenheidsfout tegen een ander jaar in de database (organisatie 2).
fout_rij = {"kvk_nummer": "22222222", "naam": "Stichting Verzonnen Twee",
            "honorarium_controle": "48000000", "honorarium_overig": "900000"}
db = NepDb()
with contextlib.redirect_stdout(io.StringIO()):
    patches = draai([fout_rij], db)
check(
    "een bedrag dat een factor 1.000 afwijkt wordt niet geschreven",
    not any("honorarium_controle_eur" in p[2] for p in patches),
)
check(
    "het gaat wel naar de review-queue, zonder naam in de payload",
    len(db.reviews) == 1
    and db.reviews[0]["soort"] == "plausibiliteit"
    and "organisatie" not in db.reviews[0]["payload"]
    and "Verzonnen" not in str(db.reviews[0]["payload"]),
)
check(
    "een bestaand geval wordt gezocht in élke status, niet alleen 'open'",
    any(t == "review_queue" and "status" not in f for t, f in db.bestaat_vragen),
)

zonder_gelezen = {"kvk_nummer": "22222222", "naam": "Stichting Verzonnen Twee",
                  "honorarium_controle": "52000"}
db = NepDb()
with contextlib.redirect_stdout(io.StringIO()):
    patches = draai([zonder_gelezen], db)
check(
    "zonder gelezen controle gaat het honorarium naar de marktonderzoekrij",
    len(patches) == 1 and "type_opdracht=in.(controle_onbepaald)" in patches[0][1],
)

# Zonder rij om op te schrijven geen review-geval: niets na te kijken.
db = NepDb(opdracht_bestaat=False)
with contextlib.redirect_stdout(io.StringIO()):
    draai([fout_rij], db)
check("zonder doelrij geen review-geval", db.reviews == [])

# Lopend en vergelijkend cijfer in dezelfde rij die niet bij elkaar passen.
from vul_extra_velden import zelfde_rij_plausibel  # noqa: E402

check("34.073 naast 677 in één rij past niet", not zelfde_rij_plausibel("34073", "677"))
check("60.000 naast 58.000 past", zelfde_rij_plausibel("60000", "58000"))
check("zonder vergelijkend cijfer valt er niets te toetsen", zelfde_rij_plausibel("60000", None))
db = NepDb()
with contextlib.redirect_stdout(io.StringIO()):
    patches = draai([{**gewoon, "honorarium_controle_vorig": "580"}], db)
check(
    "past het niet, dan wordt geen van beide geschreven",
    not any(
        k.startswith("honorarium_") for p in patches for k in p[2]
    ),
)

print(f"{goed}/{goed + fout} goed")
sys.exit(1 if fout else 0)
