"""Test: welke deponeringen vóór de download afvallen.

Waarom dit bestaat. `laad_beursfondsen.py` haalt per deponering een document
van 5-30 MB op. De regel "bestaande rijen winnen" greep tot 22-9-2026 pas ná
dat ophalen, en daardoor kostte een tweede run over hetzelfde bereik net zoveel
als de eerste — honderden downloads om er daarna achter te komen dat het al in
de database stond. Sindsdien valt dat er één stap eerder uit, en dat maakt de
maandelijkse run in beursfondsdata.yml mogelijk.

Eerder overslaan mag alleen als het net zo zeker is als de controle die erna
komt. Twee dingen horen daarom níét te worden overgeslagen, en dat is precies
wat hier wordt bewaakt:

- een instelling waarvan er twéé organisaties met dezelfde naamsleutel in de
  database staan (naamgenoot of dubbel aangemaakt). Slaat de filter die over,
  dan verdwijnt het verslag stil, terwijl de gewone route hem naar de
  review-wachtrij stuurt;
- een deponering met een onleesbaar boekjaar. Twijfel is hier geen grond om
  iets weg te gooien.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent / "adapters"))
sys.path.insert(0, str(Path(__file__).resolve().parent / "extractie"))

from laad_beursfondsen import nog_te_lezen, orgsleutel  # noqa: E402

goed = 0
fout = 0


def check(omschrijving: str, voorwaarde: bool) -> None:
    global goed, fout
    if voorwaarde:
        goed += 1
    else:
        fout += 1
        print(f"  FOUT: {omschrijving}")


ORGS = {
    orgsleutel("Voorbeeld Holding N.V."): [{"id": 11, "naam": "Voorbeeld Holding N.V."}],
    orgsleutel("Nieuwe Beurs B.V."): [{"id": 12, "naam": "Nieuwe Beurs B.V."}],
    # Twee rijen met dezelfde naamsleutel: een naamgenoot of een dubbel.
    orgsleutel("Dubbel N.V."): [{"id": 13, "naam": "Dubbel N.V."}, {"id": 14, "naam": "Dubbel N.V."}],
}
BESTAAND = {(11, 2025), (12, 2024), (13, 2025), (14, 2025)}


def deponering(instelling: str, boekjaar: str) -> dict:
    return {"id": f"d-{instelling}-{boekjaar}", "instelling": instelling, "boekjaar": boekjaar}


rijen = [
    deponering("Voorbeeld Holding N.V.", "2025"),   # staat er al -> weg
    deponering("Voorbeeld Holding N.V.", "2024"),   # ander boekjaar -> blijft
    deponering("Nieuwe Beurs B.V.", "2025"),        # ander boekjaar -> blijft
    deponering("Onbekende Zaak N.V.", "2025"),      # onbekende instelling -> blijft
    deponering("Dubbel N.V.", "2025"),              # naamconflict -> blijft
    deponering("Voorbeeld Holding N.V.", "onbekend"),  # geen jaartal -> blijft
]
uit = nog_te_lezen(rijen, ORGS, BESTAAND)
overgebleven = {(r["instelling"], r["boekjaar"]) for r in uit}

check(
    "een boekjaar dat al een wettelijke controle heeft wordt niet opgehaald",
    ("Voorbeeld Holding N.V.", "2025") not in overgebleven,
)
check(
    "een ander boekjaar van dezelfde instelling blijft wél staan",
    ("Voorbeeld Holding N.V.", "2024") in overgebleven,
)
check(
    "een instelling die de database niet kent blijft staan",
    ("Onbekende Zaak N.V.", "2025") in overgebleven,
)
check(
    "bij twee organisaties met dezelfde naamsleutel wordt er niets overgeslagen; "
    "dat geval hoort naar de review-wachtrij en niet stil weg",
    ("Dubbel N.V.", "2025") in overgebleven,
)
check(
    "een deponering zonder leesbaar boekjaar blijft staan",
    ("Voorbeeld Holding N.V.", "onbekend") in overgebleven,
)
check("er valt precies één deponering af", len(uit) == len(rijen) - 1)

# Zonder iets in de database valt er niets af: de eerste run leest alles.
check(
    "een lege database laat alles staan",
    len(nog_te_lezen(rijen, {}, set())) == len(rijen),
)

print(f"{goed}/{goed + fout} goed")
sys.exit(1 if fout else 0)
