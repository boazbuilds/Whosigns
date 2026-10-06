"""Wie komt er op de leeslijst van het DigiMV-archief?

Draaien vanuit de repo-root (geen testframework nodig, geen netwerk):

    python3 pipeline/test_digimv_archief.py

Waarom dit bestand bestaat: `doelpopulatie()` bepaalt met `heeft_verklaring()`
wie er überhaupt gelezen wordt. Keek die test alleen naar het topniveau, dan
viel een organisatie die haar stukken onder een vestiging hangt stilletjes af —
en dat zag je nergens terug, want ze kwam ook niet in `verwerkt_<jaar>.txt` en
dus niet in een telling. De lezer erachter (`verklaringen()`) kon die stukken
allang lezen; alleen de voorselectie was strenger. Deze tests leggen vast dat de
twee hetzelfde zien.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "adapters"))

from digimv_archief import (  # noqa: E402
    alle_documenten,
    heeft_verklaring,
    verklaringen,
)

fouten = 0
gedaan = 0


def controleer(omschrijving: str, goed: bool, detail: str = "") -> None:
    global fouten, gedaan
    gedaan += 1
    fouten += not goed
    print(f"{'✓' if goed else '✗'} {omschrijving}")
    if not goed and detail:
        print(f"    {detail}")


VERKLARING = {"type": "Accountantsverklaring", "url": "https://voorbeeld/av.pdf"}
JAARREKENING = {"type": "Jaarrekening", "url": "https://voorbeeld/jr.pdf"}

# Het gewone geval: alles op het topniveau.
controleer(
    "verklaring op het topniveau telt mee",
    heeft_verklaring({"documents": [JAARREKENING, VERKLARING]}),
)

# Het geval waar het om gaat. Systematisch in onder meer boekjaar 2022: de
# stukken hangen per vestiging onder locations[] en het topniveau is leeg.
ONDER_VESTIGING = {
    "name": "Voorbeeldzorg",
    "documents": [],
    "locations": [{"name": "Hoofdvestiging", "documents": [VERKLARING]}],
}
controleer(
    "verklaring onder locations[] telt óók mee",
    heeft_verklaring(ONDER_VESTIGING),
    "deze organisatie viel vroeger uit de doelpopulatie",
)

controleer(
    "verklaring onder desaveuElements telt óók mee",
    heeft_verklaring({"desaveuElements": [{"documents": [VERKLARING]}]}),
)

# De voorselectie mag niet strenger zijn dan de lezer erachter: alles wat
# verklaringen() zou oppakken, moet ook door heeft_verklaring() komen.
for omschrijving, organisatie in [
    ("topniveau", {"documents": [VERKLARING]}),
    ("vestiging", ONDER_VESTIGING),
    ("desaveu", {"desaveuElements": [{"documents": [VERKLARING]}]}),
]:
    controleer(
        f"voorselectie en lezer zien hetzelfde ({omschrijving})",
        bool(verklaringen(organisatie)) == heeft_verklaring(organisatie),
        f"verklaringen: {len(verklaringen(organisatie))}, "
        f"heeft_verklaring: {heeft_verklaring(organisatie)}",
    )

# En wie niets heeft, komt er niet in — anders haalt de oogst duizenden
# organisaties op waar niets te lezen valt.
for omschrijving, organisatie in [
    ("helemaal leeg", {}),
    ("alleen een jaarrekening", {"documents": [JAARREKENING]}),
    ("lege vestiging", {"documents": [], "locations": [{"documents": []}]}),
    ("vestiging zonder verklaring", {"locations": [{"documents": [JAARREKENING]}]}),
]:
    controleer(
        f"geen verklaring blijft geen verklaring ({omschrijving})",
        not heeft_verklaring(organisatie),
    )

# alle_documenten hoort niet om te vallen over ontbrekende of lege sleutels;
# de bron levert ze alle drie in de praktijk.
for omschrijving, organisatie in [
    ("geen enkele sleutel", {}),
    ("documents is None", {"documents": None}),
    ("locations is None", {"locations": None}),
    ("vestiging zonder documents", {"locations": [{}]}),
]:
    try:
        alle_documenten(organisatie)
        goed = True
        detail = ""
    except Exception as fout:  # noqa: BLE001 — juist dát testen we
        goed = False
        detail = repr(fout)
    controleer(f"alle_documenten blijft heel ({omschrijving})", goed, detail)

print(f"\n{gedaan - fouten}/{gedaan} goed")
raise SystemExit(1 if fouten else 0)
