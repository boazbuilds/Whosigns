"""Tests voor laad_corporaties.py: wat telt als al geladen, en welke
marktonderzoekrij mag weg.

Draaien: python3 pipeline/test_laad_corporaties.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import laad_corporaties  # noqa: E402

goed = 0
totaal = 0


def check(omschrijving: str, voorwaarde: bool) -> None:
    global goed, totaal
    totaal += 1
    if voorwaarde:
        goed += 1
    else:
        print(f"  ✗ {omschrijving}")


filter_ = laad_corporaties.onbepaald_filter(12, 2025, 7)
check("alleen deze organisatie en dit boekjaar",
      "organisatie_id=eq.12&boekjaar=eq.2025" in filter_)
check("alleen de marktonderzoekrij", "type_opdracht=eq.controle_onbepaald" in filter_)
check("alleen bij hetzelfde kantoor: een ander kantoor is een tegenspraak",
      "kantoor_id=eq.7" in filter_)
for veld in ("honorarium_controle_eur", "honorarium_overig_eur", "oordeel",
             "oordeel_gerapporteerd", "tekenend_accountant"):
    check(f"een rij met {veld} blijft staan", f"&{veld}=is.null" in filter_)

bron = Path(laad_corporaties.__file__).read_text()
check("een marktonderzoekrij telt niet als al geladen",
      "&type_opdracht=neq.controle_onbepaald" in bron)
check("de rij gaat pas weg ná de geschreven controle",
      bron.index('"organisatie_id,boekjaar,type_opdracht",')
      < bron.index("db.verwijderen(\"opdrachten\", onbepaald_filter("))

print(f"{goed}/{totaal} goed")
sys.exit(0 if goed == totaal else 1)
