"""Test: een kantoor dat uit het AFM-register verdween heet nergens nog vergunninghouder.

Waarom dit bestaat. Sinds 5-10-2026 zet laad_kantoren.py een AFM-nummer dat het
register niet meer kent op `actief = false`, en haalt het de OOB- en Wta-vlag
weg. De kantoorpagina zei daarna nog steeds "reguliere Wta-vergunning" — die
keek alleen naar het AFM-nummer, en dat blijft staan. De zoekpagina zette er
"Wta" bij, ook bij kantoren die nooit een vergunning hadden.

Het label hangt nu aan `actief`. Daar zit één val in die TypeScript niet ziet:
het type Kantoor belooft het veld, maar komt het niet mee in de select, dan is
het `undefined` en heet elk kantoor op de site ineens vervallen. Vandaar de
eerste controle.

Een tekstcontrole op de bron, net als test_site_kantoorfilter.py. Commentaar
telt niet mee.
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


BLOKCOMMENTAAR = re.compile(r"/\*.*?\*/|\{/\*.*?\*/\}", re.DOTALL)
REGELCOMMENTAAR = re.compile(r"(?m)^[ \t]*//.*$")


def bron(pad: str) -> str:
    tekst = (WEB / pad).read_text(encoding="utf-8")
    tekst = BLOKCOMMENTAAR.sub(" ", tekst)
    tekst = REGELCOMMENTAAR.sub(" ", tekst)
    return " ".join(tekst.split())


db = bron("lib/db.ts")
kern = re.search(r'const KANTOOR_KERN = "([^"]+)"', db)
check(
    "actief wordt bij elk kantoor opgehaald (KANTOOR_KERN)",
    kern is not None and "actief" in kern.group(1).split(","),
)

kantoorpagina = bron("app/kantoor/[slug]/page.tsx")
check(
    "de kantoorpagina noemt een verdwenen kantoor niet meer vergunninghouder",
    'kantoor.actief ? ( "reguliere Wta-vergunning" ) : ( "niet meer in het AFM-register" )'
    in kantoorpagina,
)

zoekpagina = bron("app/zoeken/page.tsx")
check(
    "de zoekpagina: geen vergunning, Wta, of vervallen — afhankelijk van nummer en actief",
    '!kantoor.afm_nummer ? "geen" : kantoor.actief ? "Wta" : "vervallen"' in zoekpagina,
)

print(f"{goed}/{goed + fout} goed")
sys.exit(1 if fout else 0)
