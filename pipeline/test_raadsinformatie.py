"""Leesregels voor controleverklaringen in raadsstukken.

De tekstfragmenten hieronder komen uit echte documenten in Open
Raadsinformatie; erboven staat welk geval ze afdekken.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "adapters"))

import raadsinformatie as ori  # noqa: E402

fouten = 0


def controleer(omschrijving: str, goed: bool, detail: str = "") -> None:
    global fouten
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

totaal = 7 + len(PAREN) + 3
print(f"\n{totaal - fouten}/{totaal} goed")
raise SystemExit(1 if fouten else 0)
