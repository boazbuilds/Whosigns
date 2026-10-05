"""Test: "Stand per …" in de kop van de site komt uit nieuwe opdrachten, niet uit bronnen.

Draaien vanuit de repo-root (geen netwerk, geen node):

    python3 pipeline/test_site_stand_per.py

Waarom dit bestaat. laatstBijgewerkt() nam het jongste `bronnen.opgehaald_op`, en
elke laadrun schrijft een bronregel, ook als hij niets vindt. Op 5-10-2026 stond er
daardoor "Stand per 5 oktober 2026", terwijl de jongste opdracht van 22 september
was en de jongste gunning van 21 augustus. Tekstcontrole op de bron, net als de
andere test_site_*.py; commentaar telt niet mee.
"""

import re
import sys
from pathlib import Path

WEB = Path(__file__).resolve().parent.parent / "web"

goed = 0
fout = 0


def check(omschrijving: str, voorwaarde: bool) -> None:
    global goed, fout
    if voorwaarde:
        goed += 1
    else:
        fout += 1
        print(f"  FOUT: {omschrijving}")


BLOKCOMMENTAAR = re.compile(r"/\*.*?\*/", re.DOTALL)
REGELCOMMENTAAR = re.compile(r"(?m)^[ \t]*//.*$")

bron = (WEB / "lib" / "db.ts").read_text(encoding="utf-8")
bron = REGELCOMMENTAAR.sub(" ", BLOKCOMMENTAAR.sub(" ", bron))
treffer = re.search(
    r"export async function laatstBijgewerkt\(\)(.*?)\n}\n", bron, re.DOTALL
)
check("laatstBijgewerkt bestaat nog", treffer is not None)
functie = treffer.group(1) if treffer else ""

check("leest geen bronnen meer", "bronnen" not in functie and "opgehaald_op" not in functie)
check("neemt de jongste created_at", "order=created_at.desc&limit=1" in functie)
check("van opdrachten én gunningen",
      '"opdrachten"' in functie and '"gunningen"' in functie)
check("een mislukte vraag kost de datum niet de hele kop", ".catch(" in functie)

layout = (WEB / "app" / "layout.tsx").read_text(encoding="utf-8")
check("de kop gebruikt nog steeds laatstBijgewerkt", "laatstBijgewerkt()" in layout)

print(f"{goed}/{goed + fout} goed")
sys.exit(1 if fout else 0)
