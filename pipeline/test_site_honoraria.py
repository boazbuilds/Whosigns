"""Test: de honoraria mogen niet als "de fee van deze opdracht" worden getoond.

Waarom dit bestaat. Art. 2:382a BW verplicht de jaarrekening de honoraria van de
accountant te noemen, in vier categorieën: controle van de jaarrekening, overige
controlewerkzaamheden (w.o. WNT), fiscale advisering en niet-controlediensten.
Openbaar dus, en daarom mogen ze op de site.

Maar het is niet de prijs van de opdracht. Het is wat de organisatie ten laste
van dat boekjaar heeft verantwoord, doorgaans voor het hele accountantsnetwerk.
De vier optellen tot één getal en daar "fee" boven zetten leest als een factuur
en is dat niet — dezelfde soort fout als het marktaandeel dat over alle sectoren
heen werd opgeteld en toch "% van de markt" heette (zie test_site_aandeel.py).

Daarom: vier kolommen apart, het wetsartikel erbij, en een streepje waar de bron
niets zegt. Een streepje is geen nul: een honorarium van nul is een bewering, een
ontbrekend honorarium is een leemte.
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


BLOK = re.compile(r"/\*.*?\*/", re.DOTALL)
REGEL = re.compile(r"(?m)^[ \t]*//.*$")


def plat(pad: Path) -> str:
    tekst = pad.read_text(encoding="utf-8")
    return " ".join(REGEL.sub(" ", BLOK.sub(" ", tekst)).split())


VELDEN = (
    "honorarium_controle_eur",
    "honorarium_overig_eur",
    "honorarium_fiscaal_eur",
    "honorarium_nietcontrole_eur",
)

bladzijden = sorted(WEB.glob("app/**/*.tsx")) + sorted(WEB.glob("lib/*.ts"))
alles = {p: plat(p) for p in bladzijden}

check(
    "de vier honorariumvelden worden ergens opgehaald",
    any(all(v in t for v in VELDEN) for t in alles.values()),
)

toont = [p for p, t in alles.items() if "honorarium_controle_eur" in t and "<td" in t]
check(
    "er is een pagina die ze toont",
    bool(toont),
)

for pad in toont:
    tekst = alles[pad]
    check(
        f"{pad.name}: alle vier de categorieën staan er, niet alleen de controle",
        all(v in tekst for v in VELDEN),
    )
    check(
        f"{pad.name}: het wetsartikel staat erbij, zodat zichtbaar is wat dit is",
        "2:382a" in tekst,
    )
    check(
        f"{pad.name}: er staat bij dat een streepje geen nul is",
        "niet dat het nul" in tekst or "geen nul" in tekst,
    )
    # De vier bij elkaar optellen en als één bedrag tonen is precies de fout die
    # dit bestand moet tegenhouden.
    opgeteld = re.search(
        r"honorarium_\w+_eur\s*\+\s*.{0,40}honorarium_\w+_eur", tekst
    )
    check(
        f"{pad.name}: de vier categorieën worden niet opgeteld tot één bedrag",
        opgeteld is None,
    )
    check(
        f"{pad.name}: het woord 'fee' wordt niet als kop gebruikt",
        not re.search(r">\s*fee\b", tekst, re.I),
    )

# euro() mag geen nul verzinnen waar de bron niets zegt.
paden_ts = (WEB / "lib/paden.ts").read_text(encoding="utf-8")
check(
    "euro() geeft null terug bij een ontbrekend bedrag in plaats van € 0",
    "if (bedrag === null || bedrag === undefined) return null;" in paden_ts,
)

print(f"{goed}/{goed + fout} goed")
sys.exit(1 if fout else 0)
