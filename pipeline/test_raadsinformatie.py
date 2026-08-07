"""Leesregels voor controleverklaringen in raadsstukken.

De tekstfragmenten hieronder komen uit echte documenten in Open
Raadsinformatie; erboven staat welk geval ze afdekken.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "adapters"))

import raadsinformatie as ori  # noqa: E402

fouten = 0
gedaan = 0


def controleer(omschrijving: str, goed: bool, detail: str = "") -> None:
    global fouten, gedaan
    gedaan += 1
    fouten += not goed
    print(f"{'✓' if goed else '✗'} {omschrijving}")
    if not goed and detail:
        print(f"    {detail}")


# --- de standaardzin ---------------------------------------------------------
TEKST = (
    "Controleverklaring van de onafhankelijke accountant\n"
    "Aan het algemeen bestuur van de Gemeenschappelijke regeling WerkSaam "
    "Westfriesland te Hoorn\n"
    "A. VERKLARING OVER DE IN DE JAARSTUKKEN OPGENOMEN JAARREKENING 2018\n"
    "Ons oordeel\n"
    "Wij hebben de jaarrekening 2018 van de Gemeenschappelijke regeling WerkSaam "
    "Westfriesland te Hoorn gecontroleerd.\n"
)
uit = ori.verklaringen_uit(TEKST)
controleer(
    "de zin levert organisatie, boekjaar en plaats",
    len(uit) == 1
    and uit[0]["organisatie"] == "Gemeenschappelijke regeling WerkSaam Westfriesland"
    and uit[0]["boekjaar"] == 2018
    and uit[0]["plaats"] == "Hoorn",
    f"gevonden: {uit}",
)

# Een document dat de term alleen in een inhoudsopgave noemt levert niets op —
# dat is de rem op aanbiedingsbrieven en jaarstukken zonder verklaring.
controleer(
    "zonder de standaardzin geen verklaring",
    ori.verklaringen_uit(
        "Controleverklaring van de onafhankelijke accountant ......... 21\n"
        "Bijlagen I Begrotingscriterium over 2018\n"
    )
    == [],
)

# --- meerdere verklaringen in één bundel -------------------------------------
#
# Dit is het geval waar de bron om vraagt: een raadsbundel met de jaarstukken
# van twee gemeenschappelijke regelingen achter elkaar. Het handtekeningblok
# van de eerste mag niet aan de tweede worden toegeschreven.
BUNDEL = (
    "Wij hebben de jaarrekening 2020 van gemeenschappelijke regeling SSC DeSom "
    "te Wognum gecontroleerd.\n"
    + "vulling " * 200
    + "Alkmaar, 12 april 2021 Deloitte Accountants B.V. was getekend\n"
    + "Wij hebben de jaarrekening 2020 van gemeenschappelijke regeling GGD "
    "Hollands Noorden te Schagen gecontroleerd.\n"
    + "vulling " * 200
    + "Zwolle, 3 mei 2021 Flynth Audit B.V. was getekend\n"
)
uit = ori.verklaringen_uit(BUNDEL)
controleer(
    "twee verklaringen in één document worden allebei gezien",
    len(uit) == 2
    and uit[0]["boekjaar"] == 2020
    and "DeSom" in uit[0]["organisatie"]
    and "GGD" in uit[1]["organisatie"],
    f"gevonden: {[(v['organisatie'], v['boekjaar']) for v in uit]}",
)
eerste_venster = BUNDEL[uit[0]["venster"][0] : uit[0]["venster"][1]]
tweede_venster = BUNDEL[uit[1]["venster"][0] : uit[1]["venster"][1]]
controleer(
    "het venster van de eerste houdt op bij de tweede verklaring",
    "Deloitte" in eerste_venster and "Flynth" not in eerste_venster,
    "het venster liep door tot in de volgende verklaring",
)
controleer(
    "het venster van de tweede bevat alleen haar eigen kantoor",
    "Flynth" in tweede_venster,
)

# --- een onmogelijk jaartal -------------------------------------------------
controleer(
    "een jaarrekening over 2077 bestaat niet",
    ori.verklaringen_uit(
        "Wij hebben de jaarrekening 2077 van Gemeente Nergenshuizen te Nergens "
        "gecontroleerd."
    )
    == [],
)

# --- de aanhef hoort niet bij de naam ----------------------------------------
uit = ori.verklaringen_uit(
    "Aan het algemeen bestuur van gemeenschappelijke regeling SSC DeSom "
    "Wij hebben de jaarrekening 2020 van het algemeen bestuur van "
    "gemeenschappelijke regeling SSC DeSom te Wognum gecontroleerd."
)
controleer(
    "'algemeen bestuur van' hoort niet in de organisatienaam",
    uit and uit[0]["organisatie"] == "Gemeenschappelijke regeling SSC DeSom",
    f"gevonden: {uit[0]['organisatie']!r}" if uit else "niets gevonden",
)

# --- dezelfde organisatie ondanks tekstverschillen ---------------------------
#
# De documenttekst komt uit een pdf en daar sneuvelen koppeltekens. Zonder
# gelijke sleutel splitst de geschiedenis van één veiligheidsregio zich over
# twee organisaties.
PAREN = [
    ("Veiligheidsregio Noord-Holland Noord", "Veiligheidsregio NoordHolland Noord"),
    ("Gemeenschappelijke Regeling Regio West-Brabant", "Gemeenschappelijke Regeling Regio WestBrabant"),
    ("Gemeenschappelijke Regeling SED organisatie", "Gemeenschappelijke Regeling SED-organisatie"),
    ("gemeente Enkhuizen", "Gemeente Enkhuizen"),
]
for links, rechts in PAREN:
    controleer(
        f"zelfde sleutel: {links!r} en {rechts!r}",
        ori.matchsleutel(links) == ori.matchsleutel(rechts),
        f"{ori.matchsleutel(links)!r} != {ori.matchsleutel(rechts)!r}",
    )

# Twee échte verschillende organisaties mogen juist níét samenvallen.
controleer(
    "verschillende organisaties houden verschillende sleutels",
    ori.matchsleutel("Veiligheidsregio Utrecht")
    != ori.matchsleutel("Veiligheidsregio Flevoland"),
)

# --- de tekst kan als lijst binnenkomen --------------------------------------
controleer(
    "tekst per pagina wordt samengevoegd",
    ori._plat(["eerste", "tweede"]) == "eerste\ntweede" and ori._plat(None) == "",
)

# --- de naam mag niet over een kop heen lopen --------------------------------
#
# Den Haag zet "Ons oordeel" als kopje boven de verklaring, en de regel ervóór
# noemt de jaarrekening al. De naam liep dan door tot voorbij dat kopje en er
# ontstond een tweede, verzonnen "organisatie" naast de echte — mét accountant.
# Erger nog: die opgerekte match at de goede zin op, dus Den Haag raakte het jaar
# helemaal kwijt. Op 4.000 documenten (7-8-2026) gebeurde dat 26 keer.
DEN_HAAG = (
    "JAARREKENING 2016 VAN DE GEMEENTE DEN HAAG\n"
    "Controleverklaring van de onafhankelijke accountant\n"
    "Ons oordeel\n"
    "Wij hebben de jaarrekening 2016 van de gemeente Den Haag gecontroleerd.\n"
)
uit = ori.verklaringen_uit(DEN_HAAG)
controleer(
    "de naam stopt bij de kop, en de échte zin wordt alsnog gevonden",
    len(uit) == 1 and uit[0]["organisatie"] == "Gemeente Den Haag"
    and uit[0]["boekjaar"] == 2016,
    f"gevonden: {[(v['organisatie'], v['boekjaar']) for v in uit]}",
)

# --- een tussenzin over de reikwijdte ----------------------------------------
#
# Deze drie schrijfwijzen staan letterlijk in de bron en vielen allemaal weg
# omdat er iets tussen het jaartal en "van" stond.
for omschrijving, zin, verwacht in [
    (
        "(inclusief erratum)",
        "Wij hebben de jaarrekening 2020 (inclusief erratum) van de gemeente "
        "Renkum gecontroleerd.",
        "Gemeente Renkum",
    ),
    (
        "inclusief de SISA bijlage",
        "Wij hebben de jaarrekening 2016 inclusief de SISA bijlage (bijlage 7.1) "
        "van de Gemeenschappelijke Regeling Veiligheidsregio Zeeland gecontroleerd.",
        "Gemeenschappelijke Regeling Veiligheidsregio Zeeland",
    ),
    (
        "en de daarbij behorende bijlagen",
        "Wij hebben de jaarrekening 2014 en de daarbij behorende bijlagen van de "
        "gemeente Eindhoven gecontroleerd.",
        "Gemeente Eindhoven",
    ),
]:
    uit = ori.verklaringen_uit(zin)
    controleer(
        f"tussenzin: {omschrijving}",
        len(uit) == 1 and uit[0]["organisatie"] == verwacht,
        f"gevonden: {[v['organisatie'] for v in uit]}",
    )

# --- en wat de tussenzin níét mag doen ---------------------------------------
#
# De keerzijde, en die is scherper dan hij lijkt: Nederlandse organisatienamen
# zitten vol "van". Met een vrij gat tussen jaartal en "van" sloeg de zoeker het
# échte "van" over en haakte hij aan het "van" binnenín de naam. Dat halveerde
# 113 namen op 4.000 documenten: "Vereniging van Nederlandse Gemeenten" werd
# "Nederlandse Gemeenten" en "Regio Hart van Brabant" werd "Brabant". Een naam
# die stilletjes de helft mist is erger dan een naam die ontbreekt.
for omschrijving, zin, verwacht in [
    (
        "een naam mét 'van' erin blijft heel",
        "Wij hebben de jaarrekening 2021 van de Vereniging van Nederlandse "
        "Gemeenten gecontroleerd.",
        "Vereniging van Nederlandse Gemeenten",
    ),
    (
        "ook als de naam midden in een 'van' zit",
        "Wij hebben de jaarrekening 2022 van de Gemeenschappelijke Regeling Regio "
        "Hart van Brabant gecontroleerd.",
        "Gemeenschappelijke Regeling Regio Hart van Brabant",
    ),
]:
    uit = ori.verklaringen_uit(zin)
    controleer(
        omschrijving,
        len(uit) == 1 and uit[0]["organisatie"] == verwacht,
        f"gevonden: {[v['organisatie'] for v in uit]}",
    )

# Een ándere zin over dezelfde jaarrekening is geen ondertekende verklaring. Met
# een vrij gat leverden deze twee "het bestuur" en "GR-bestuur" op als
# organisatie — allebei bestaan niet.
for omschrijving, zin in [
    ("opgesteld onder verantwoordelijkheid van het bestuur",
     "De jaarrekening 2019 is opgesteld onder verantwoordelijkheid van het "
     "bestuur en wordt door ons gecontroleerd."),
    ("in opdracht van het GR-bestuur",
     "De jaarrekening 2020 wordt net als in voorgaande jaren in opdracht van het "
     "GR-bestuur gecontroleerd."),
]:
    uit = ori.verklaringen_uit(zin)
    controleer(f"geen verklaring: {omschrijving}", uit == [], f"gevonden: {uit}")

print(f"\n{gedaan - fouten}/{gedaan} goed")
raise SystemExit(1 if fouten else 0)
