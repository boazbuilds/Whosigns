"""Wat de oogst opschrijft, en wat de kolom toestaat.

Draaien vanuit de repo-root (geen testframework nodig, geen netwerk):

    python3 pipeline/test_laad_zorg_rapport.py

Waarom dit bestand bestaat: op 12-8-2026 viel de eerste lading van de
oogstrapporten om op HTTP 400. Negentien van de ruim 2.500 regels hadden een
leeg `oordeel` — verklaringen waarvan de tekstherkenning het oordeel niet
prijsgaf — en een lege string is geen geldige waarde voor die kolom. De lader
schrijft per rij, dus die ene rij nam de rest mee: van de ruim duizend nieuwe
opdrachten kwamen er tachtig binnen.

De les is niet "vang de fout af" maar "leeg is een ontbrekende waarde, geen
waarde". Deze tests leggen die vertaling vast, en ook waar hij júist niet geldt.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from laad_zorg_rapport import opdracht_uit_rapportrij  # noqa: E402

# De vier oordelen die de kolom toestaat (init.sql: opdrachten_oordeel_check).
TOEGESTAAN = {"goedkeurend", "beperking", "oordeelonthouding", "afkeurend"}

fouten = 0
gedaan = 0


def controleer(omschrijving: str, goed: bool, detail: str = "") -> None:
    global fouten, gedaan
    gedaan += 1
    fouten += not goed
    print(f"{'✓' if goed else '✗'} {omschrijving}")
    if not goed and detail:
        print(f"    {detail}")


def rapportrij(**velden) -> dict:
    basis = {
        "kvk": "12345678",
        "naam": "Stichting Voorbeeldzorg",
        "plaats": "Utrecht",
        "boekjaar": "2019",
        "kantoor": "Deloitte Accountants B.V.",
        "kantoor_sleutel": "13000015",
        "afm_nummer": "13000015",
        "type_opdracht": "wettelijke_controle",
        "oordeel": "goedkeurend",
        "grond_beperking": "",
        "continuiteitsonzekerheid": "",
    }
    basis.update(velden)
    return basis


# --- het geval dat de lading omver trok ---------------------------------------
uit = opdracht_uit_rapportrij(rapportrij(oordeel=""), 1, 2, 3)
controleer(
    "leeg oordeel wordt null, niet een lege string",
    uit["oordeel"] is None,
    f"gevonden: {uit['oordeel']!r}",
)

# Alleen spaties is net zo goed leeg; die komen uit een pdf-tabel.
uit = opdracht_uit_rapportrij(rapportrij(oordeel="   "), 1, 2, 3)
controleer(
    "een oordeel van alleen spaties wordt óók null",
    uit["oordeel"] is None,
    f"gevonden: {uit['oordeel']!r}",
)

# En wat er wél staat blijft ongemoeid.
for oordeel in sorted(TOEGESTAAN):
    uit = opdracht_uit_rapportrij(rapportrij(oordeel=oordeel), 1, 2, 3)
    controleer(
        f"een echt oordeel blijft staan: {oordeel}",
        uit["oordeel"] == oordeel,
        f"gevonden: {uit['oordeel']!r}",
    )

# Wat de functie teruggeeft moet de kolomvoorwaarde overleven: null of een van
# de vier. Dat is precies de test die de database ook doet.
for waarde in ["", "   ", "goedkeurend", "afkeurend"]:
    uit = opdracht_uit_rapportrij(rapportrij(oordeel=waarde), 1, 2, 3)
    controleer(
        f"uitkomst voldoet aan de kolomvoorwaarde bij {waarde!r}",
        uit["oordeel"] is None or uit["oordeel"] in TOEGESTAAN,
        f"gevonden: {uit['oordeel']!r}",
    )

# --- dezelfde regel voor grond_beperking --------------------------------------
uit = opdracht_uit_rapportrij(rapportrij(grond_beperking=""), 1, 2, 3)
controleer("lege grond_beperking wordt null", uit["grond_beperking"] is None)

uit = opdracht_uit_rapportrij(
    rapportrij(grond_beperking="onvoldoende controle-informatie over de opbrengsten"),
    1, 2, 3,
)
controleer(
    "een ingevulde grond_beperking blijft staan",
    uit["grond_beperking"] == "onvoldoende controle-informatie over de opbrengsten",
)

# --- en waar de regel júist niet geldt ----------------------------------------
#
# De oogst schrijft "ja" als de verklaring een paragraaf over materiële
# continuïteitsonzekerheid bevat, en anders niets. Leeg betekent daar dus "die
# paragraaf staat er niet" — onwaar, niet onbekend. Zou dit null worden, dan
# stond op de site bij 888 van de 928 verklaringen over 2019 "onbekend" terwijl
# er gewoon gekeken is.
uit = opdracht_uit_rapportrij(rapportrij(continuiteitsonzekerheid=""), 1, 2, 3)
controleer(
    "lege continuiteitsonzekerheid wordt onwaar, niet null",
    uit["continuiteitsonzekerheid"] is False,
    f"gevonden: {uit['continuiteitsonzekerheid']!r}",
)

uit = opdracht_uit_rapportrij(rapportrij(continuiteitsonzekerheid="ja"), 1, 2, 3)
controleer(
    "continuiteitsonzekerheid 'ja' wordt waar",
    uit["continuiteitsonzekerheid"] is True,
)

# --- de rest van de rij -------------------------------------------------------
uit = opdracht_uit_rapportrij(rapportrij(boekjaar="2021"), 7, 8, 9)
controleer("boekjaar wordt een getal", uit["boekjaar"] == 2021)
controleer("organisatie, kantoor en bron worden doorgegeven",
           (uit["organisatie_id"], uit["kantoor_id"], uit["bron_id"]) == (7, 8, 9))
controleer("type_opdracht wordt niet gegokt",
           uit["type_opdracht"] == "wettelijke_controle")

# --- en tot slot de echte rapporten -------------------------------------------
#
# Geen theorie: laat de functie los op elke regel die er nu ligt en controleer
# dat er niets uit komt wat de kolomvoorwaarde zou schenden.
import csv  # noqa: E402

for pad in sorted(Path("pipeline/oogst").glob("zorg_*.csv")):
    rijen = list(csv.DictReader(pad.open(encoding="utf-8")))
    slecht = []
    for rij in rijen:
        if not (rij.get("kvk") or "").strip():
            continue
        uit = opdracht_uit_rapportrij(rij, 1, 2, 3)
        if not (uit["oordeel"] is None or uit["oordeel"] in TOEGESTAAN):
            slecht.append(uit["oordeel"])
    controleer(
        f"{pad.name}: alle {len(rijen)} regels leveren een toegestaan oordeel",
        not slecht,
        f"niet toegestaan: {sorted(set(slecht))[:5]}",
    )

print(f"\n{gedaan - fouten}/{gedaan} goed")
raise SystemExit(1 if fouten else 0)
