"""Wat telt als een verzonnen organisatie, en wat vooral niet.

Draaien vanuit de repo-root (geen testframework nodig, geen netwerk):

    python3 pipeline/test_opruim.py

Waarom dit bestaat: dit script verwijdert rijen, en dat is onomkeerbaar. De
grens tussen "dit is een stuk zin" en "dit is een naam" moet daarom vastliggen,
en vooral aan de kant van laten staan. Elke naam hieronder komt uit de database
of uit de meting die de fout aan het licht bracht.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from opruim_verzonnen_organisaties import beoordeel  # noqa: E402

fouten = 0
gedaan = 0


def controleer(omschrijving: str, goed: bool, detail: str = "") -> None:
    global fouten, gedaan
    gedaan += 1
    fouten += not goed
    print(f"{'✓' if goed else '✗'} {omschrijving}")
    if not goed and detail:
        print(f"    {detail}")


# --- stukken zin, gemeten op 4.000 raadsstukken (7-8-2026) -------------------
for naam in [
    "Gemeente Den Haag Ons oordeel Wij hebben de jaarrekening 2016 van de gemeente Den Haag",
    "GEMEENTE DEN HAAG Ons oordeel Wij hebben de jaarrekening 2021 van de gemeente Den Haag",
    "Gemeenschappelijke regeling Recreatieschap Drenthe aan. De jaarrekening is",
    "WVS-groep. De jaarrekening 2012 is door de accountant (Deloitte Accountants BV)",
    "Gemeenten en gemeenschappelijke regelingen. Dit standpunt volgen zij. Zij hebben de jaarrekening",
    "Stichting Omnisscholen (hierna ‘de stichting’) te Heinkenszand (hierna ‘de jaarrekening’)",
]:
    controleer(f"stuk zin: {naam[:52]!r}", beoordeel(naam) == "zin", beoordeel(naam))

# --- "(hierna: X)" is geen zinsflard maar een naam ---------------------------
#
# Dit stond hier bijna verkeerd in. "hierna" was eerst een reden om weg te
# gooien, en dat is gewone juridische schrijfwijze die middenin échte namen
# staat. Deze zes komen alle uit de raadsinformatie-oogst en bestaan gewoon; ze
# zouden met hun hele geschiedenis zijn verdwenen. Gevonden door te kijken wat
# het script zóu weggooien, vóór het ooit had gedraaid.
for naam in [
    "Gemeenschappelijke Regeling Gemeenschappelijke Vuilverwerking Dordrecht en Omstreken (hierna Gevudo)",
    "Gemeenschappelijke Regeling Delta (hierna: Delta)",
    "Gemeenschappelijke Regeling Op/maat (hierna: Op/maat)",
    "Onderdeel Programmabureau van de Veiligheidsregio Zuid Limburg (hierna: Programmabureau)",
    "Onderdeel Bevolkingszorg van de Veiligheidsregio Zuid Limburg (hierna: Bevolkingszorg)",
    "Onderdeel Burgernet van de Veiligheidsregio Zuid Limburg (hierna: Burgernet)",
]:
    controleer(
        f"'(hierna: …)' blijft staan: {naam[:46]!r}",
        beoordeel(naam) == "goed",
        beoordeel(naam),
    )

# --- echte namen, en die moeten met rust gelaten worden ----------------------
#
# Deze staan allemaal in de database. Eén verkeerde treffer hier haalt een echte
# organisatie met haar hele geschiedenis weg.
for naam in [
    "Gemeente Den Haag",
    "Gemeenschappelijke Regeling Veiligheidsregio Midden- en West-Brabant",
    "Vereniging van Nederlandse Gemeenten",
    "Gemeenschappelijke Regeling Regio Hart van Brabant",
    "Stichting Openbaar Onderwijs Land van Altena",
    "Gemeenschappelijke Regeling Milieusamenwerking en Afvalverwerking Regio Nijmegen",
    "Omgevingsdienst Rivierenland",
    "Regionaal Archief Rivierenland",
    "WVS-groep",
    "Stichting Omnisscholen",
    # Een controlestichting mag "controle" heten; alleen zinswoorden tellen.
    "Stichting Waarborgfonds Sociale Woningbouw",
]:
    controleer(f"echte naam: {naam[:52]!r}", beoordeel(naam) == "goed", beoordeel(naam))

# --- een jaartal alleen is geen bewijs ---------------------------------------
#
# Wel melden, nooit automatisch weghalen: zo'n naam kán echt bestaan.
for naam in ["Stichting Rotterdam 2018", "Programma 2020 B.V."]:
    controleer(
        f"twijfel, blijft staan: {naam!r}", beoordeel(naam) == "twijfel", beoordeel(naam)
    )

# Een lege naam is geen stuk zin; die hoort niet stil weggehaald te worden.
controleer("een lege naam levert geen verwijderoordeel op", beoordeel("") == "goed")

print(f"\n{gedaan - fouten}/{gedaan} goed")
raise SystemExit(1 if fouten else 0)
