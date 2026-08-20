"""Test: de site mag een aandeel geen marktaandeel noemen.

Waarom dit bestaat. Op de voorpagina en op /kantoren stond onder het podium
"% van de markt". Die noemer is de som van alle controles die voor dat boekjaar
in de database staan — over alle sectoren heen. De database wordt echter sector
voor sector en boekjaar voor boekjaar gevuld, en die mengeling verschilt sterk.
Gemeten op 20-8-2026:

    2007   479 controles — 100% woningcorporaties
    2015 1.248 controles — OOB 57%, woningcorporaties 27%, overheid 14%
    2019 2.211 controles — zorg 37%, OOB 25%, overheid 16%, corporaties 13%, goede doelen 7%
    2024 2.108 controles — zorg 29%, OOB 28%, overheid 17%, corporaties 12%, goede doelen 12%
    2025 1.080 controles — zorg 56%, overheid 22%, goede doelen 14%, OOB 7%

Daardoor vertelde de voorpagina een onwaar verhaal over een kantoor met naam en
toenaam: Deloitte stond in 2007 op 43,8% en in 2024 op 12,2%, en dat verschil
komt volledig doordat er sectoren bij kwamen waarin Deloitte minder sterk is —
niet doordat het kantoor cliënten verloor.

Per sector klopt het aandeel wél. Dat rekent v_marktaandeel uit, gepartitioneerd
per (boekjaar, sector), en zo staat het op /sectoren en /sector/[naam]. Die
partitie werd op de twee ranglijstpagina's ongedaan gemaakt door alles op te
tellen en er opnieuw een percentage over te nemen.

Deze test kijkt naar de tekst van de pagina's, want dit is een bewering en geen
berekening: het getal was al die tijd rekenkundig juist, alleen het bijschrift
was onwaar. Whitespace wordt eerst platgeslagen, zodat het opnieuw afbreken van
een JSX-regel de test niet rood maakt.
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


# Commentaar telt niet mee. Deze test gaat over wat een bezoeker leest, en de
# uitleg boven de som citeert juist de oude, onware zin — anders zou een correcte
# pagina rood worden om zijn eigen verantwoording. Blokcommentaar gaat er in zijn
# geheel uit; regelcommentaar alleen als het een hele regel is, zodat "https://"
# midden in een regel blijft staan.
BLOKCOMMENTAAR = re.compile(r"/\*.*?\*/", re.DOTALL)
REGELCOMMENTAAR = re.compile(r"(?m)^[ \t]*//.*$")


def plat(pad: Path) -> str:
    """De tekst zonder commentaar, met alle witruimte teruggebracht tot één spatie."""
    tekst = pad.read_text(encoding="utf-8")
    tekst = BLOKCOMMENTAAR.sub(" ", tekst)
    tekst = REGELCOMMENTAAR.sub(" ", tekst)
    return " ".join(tekst.split())


bladzijden = sorted(WEB.glob("app/**/*.tsx")) + sorted(WEB.glob("components/*.tsx"))
check("er zijn pagina's om te controleren", len(bladzijden) > 5)

# --- niemand noemt het weer marktaandeel ---------------------------------------
schuldig = [p for p in bladzijden if "% van de markt" in plat(p)]
check(
    "geen enkele pagina zet '% van de markt' onder een getal dat over alle "
    "sectoren heen is opgeteld: " + ", ".join(p.name for p in schuldig),
    not schuldig,
)

# --- de twee pagina's die het toch tonen, zeggen erbij wat het is ---------------
for naam in ("app/page.tsx", "app/kantoren/page.tsx"):
    pad = WEB / naam
    tekst = plat(pad)
    check(f"{naam} bestaat nog", pad.exists())
    if not pad.exists():
        continue
    check(
        f"{naam} rekent nog steeds een aandeel uit over de hele ranglijst",
        "aantal_controles / totaal" in tekst.replace("  ", " "),
    )
    check(
        f"{naam} zegt erbij dat het over de database gaat en niet over de markt",
        "in de database staat, niet van de hele markt" in tekst,
    )
    check(
        f"{naam} wijst door naar de sectoren, waar het aandeel wél klopt",
        'href="/sectoren"' in tekst,
    )
    check(
        f"{naam} noemt de noemer bij het percentage, zodat het zichtbaar is "
        "waarover het percentage gaat",
        "controles`}" in tekst,
    )

# --- het colofon vertelt dat de dekking onvolledig is ---------------------------
colofon = plat(WEB / "app/layout.tsx")
check(
    "het colofon zegt dat de gegevens nog worden aangevuld; zonder die zin leest "
    "de site als een volledig marktoverzicht",
    "Nog niet compleet" in colofon,
)
check(
    "en het colofon zegt waar een aandeel over gaat",
    "niet over de hele markt" in colofon,
)

# --- de sectorpagina mag het wél zeggen, want daar klopt de noemer --------------
sector = plat(WEB / "app/sector/[naam]/page.tsx")
check(
    "de sectorpagina rekent nog steeds binnen één sector af",
    "% van deze sector" in sector,
)

print(f"{goed}/{goed + fout} goed")
sys.exit(1 if fout else 0)
