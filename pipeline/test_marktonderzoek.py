"""Test: de herleiding en vormeisen van de marktonderzoek-lader.

Zonder netwerk en zonder database: de verkorte-namenlijst, het splitsen van
velden met meerdere kantoren, en de rijvalidatie. De echte aanlevering staat
bewust niet in de repository.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent / "adapters"))
sys.path.insert(0, str(Path(__file__).resolve().parent / "extractie"))

from kantoor_match import bouw_index, laad_kantoren  # noqa: E402
from laad_marktonderzoek import (  # noqa: E402
    VERKORT,
    geldige_rij,
    herleid_kantoren,
    lees_map,
)

goed = 0
fout = 0


def check(omschrijving: str, voorwaarde: bool) -> None:
    global goed, fout
    if voorwaarde:
        goed += 1
    else:
        fout += 1
        print(f"  FOUT: {omschrijving}")


index = bouw_index(laad_kantoren())

k, o = herleid_kantoren("KPMG", index)
check("KPMG herleidt naar 13000121", k == ["13000121"] and not o)

k, o = herleid_kantoren("Confinant", index)
check("Confinant herleidt naar 13020070", k == ["13020070"] and not o)

k, o = herleid_kantoren("Confinant Audit & Assurance", index)
check("de lange Confinant-schrijfwijze herleidt ook", k == ["13020070"] and not o)

k, o = herleid_kantoren("E & Y ; KPMG", index)
check(
    "twee kantoren in één veld worden allebei herleid (en dus review)",
    set(k) == {"13020186", "13000121"} and not o,
)

k, o = herleid_kantoren("KPMG; KPMG", index)
check("dubbel hetzelfde kantoor vouwt samen tot één", k == ["13000121"] and not o)

k, o = herleid_kantoren("kpmg/naolis", index)
check(
    "een onherleidbaar deel blijft onherleidbaar (geen gok)",
    k == ["13000121"] and o == ["naolis"],
)

check(
    "de volledige AFM-naam herleidt via de gewone matcher",
    herleid_kantoren("KPMG Accountants N.V.", index)[0] == ["13000121"],
)

check(
    "verkorte namen wijzen alleen naar bestaande AFM-nummers",
    set(VERKORT.values())
    <= {r["afm_nummer"] for r in laad_kantoren()},
)

check(
    "een geldige rij komt genormaliseerd door",
    geldige_rij({"kvk": "0603-2957", "naam": "X", "boekjaar": "2024", "accountant": "KPMG"})
    == {"kvk": "06032957", "naam": "X", "boekjaar": 2024, "accountant": "KPMG"},
)
check(
    "zonder kvk of jaartal wordt een rij geweigerd",
    geldige_rij({"kvk": "123", "naam": "X", "boekjaar": "2024", "accountant": "K"}) is None
    and geldige_rij({"kvk": "06032957", "naam": "X", "boekjaar": "?", "accountant": "K"}) is None,
)

# De aanlevermap zelf: elke rij moet door de validatie komen, want de lader
# draait vanzelf zodra hier iets op main landt — een kapotte aanlevering hoort
# hier te sneuvelen en niet stil in de workflow.
aanlevering = lees_map()
check("de aanlevermap heeft rijen", len(aanlevering) >= 1)
check(
    "elke aangeleverde rij komt door de validatie",
    all(geldige_rij(r) is not None for r in aanlevering),
)
check(
    "kvk+boekjaar+accountant is uniek in de aanlevering",
    len({(r["kvk"], r["boekjaar"], r["accountant"].lower()) for r in aanlevering})
    == len(aanlevering),
)

print(f"{goed}/{goed + fout} goed")
sys.exit(1 if fout else 0)
