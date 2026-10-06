"""Test: een aandeel of plek geldt binnen één sector én één boekjaar.

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

Daarna heette het "% van wat er in de database staat", met een disclaimer. Dat
bleef een aandeel over sectoren heen. En de sectorpagina telde wél binnen één
sector, maar over álle boekjaren samen: op 5-10-2026 stond Deloitte daar bij de
woningcorporaties op 27,3% (1.666 van 6.093 over 2007–2024), terwijl het per
jaar tussen 11 en 16% lag; de financiële dienstverlening kreeg "Eshuis 54,5%"
op 6 van 11 controles verspreid over dertien jaar. De kantoorpagina zette
"18,2% van alles wat in deze database staat" en "#1 in de ranglijst" onder
Deloitte, beide over alle sectoren en jaren.

De regel is sindsdien: een percentage of een plek alleen binnen één sector en
één boekjaar — het nieuwste boekjaar dat voor die sector al compleet is
(nieuwsteCompleteBoekjaar in web/lib/voorpagina.ts). Waar een pagina sectoren
of jaren samen toont, staan er aantallen: van veel naar weinig, maar zonder
podium en zonder rangnummer. De eerste versie van deze regel haalde alleen het
percentage weg; de voorpagina hield een podium (PwC 290, Deloitte 272, BDO 268
in 2024) en /kantoren?jaar=alles "De top drie in alle boekjaren" met Deloitte
op 1 — een plek over alle sectoren en over 2007–2025 samen.

Op de sectorpagina deelt het podium bij gelijke aantallen dezelfde plek uit
als de tabel. Het deelde eerst 1, 2, 3 uit in sorteervolgorde: bij de overheid
in 2024 (46, 30, 26 en 26 controles) stond één van de twee met 26 op het
podium en de ander niet.

Deze test kijkt naar de tekst van de pagina's, want dit is een bewering en geen
berekening: het getal was al die tijd rekenkundig juist, alleen de noemer was
de verkeerde. Whitespace wordt eerst platgeslagen, zodat het opnieuw afbreken
van een JSX-regel de test niet rood maakt.
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
# geheel uit, ook als JSX-commentaar; regelcommentaar alleen als het een hele
# regel is, zodat "https://" midden in een regel blijft staan.
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

# --- de twee ranglijsten over alle sectoren tonen alleen aantallen -------------
for naam in ("app/page.tsx", "app/kantoren/page.tsx"):
    pad = WEB / naam
    check(f"{naam} bestaat nog", pad.exists())
    if not pad.exists():
        continue
    tekst = plat(pad)
    check(
        f"{naam} rekent geen aandeel meer uit over de hele ranglijst",
        "aantal_controles / totaal" not in tekst
        and "aantal_controles / totaalControles" not in tekst,
    )
    check(
        f"{naam} zet geen Aandeelbalk (met percentage) in een ranglijst over "
        "alle sectoren; een Telbalk zonder percentage mag",
        "<Aandeelbalk" not in tekst and "<Telbalk" in tekst,
    )
    check(
        f"{naam} zegt erbij dat een aandeel alleen binnen één sector en één "
        "boekjaar geldt",
        "alleen binnen één sector en één boekjaar" in tekst,
    )
    check(
        f"{naam} geeft over alle sectoren heen geen plek: geen podium, geen "
        "rangnummer, geen kop 'Ranglijst' of 'top drie'",
        "<Podiumplek" not in tekst
        and "<Rang " not in tekst
        and "<h2>Ranglijst" not in tekst
        and "top drie" not in tekst
        and "De grootste kantoren" not in tekst,
    )
    check(
        f"{naam} wijst door naar de sectoren, waar het aandeel wél staat",
        'href="/sectoren"' in tekst,
    )
    check(
        f"{naam} opent op het nieuwste complete boekjaar, met de regel uit "
        "voorpagina.ts, en niet op het nieuwste boekjaar zonder meer",
        "nieuwsteCompleteBoekjaar(" in tekst
        and "boekjarenMetControles())[0]" not in tekst
        and ": jaren[0] ?? null" not in tekst,
    )

# --- de compleetheidsregel staat op één plek ------------------------------------
voorpagina = plat(WEB / "lib/voorpagina.ts")
check(
    "nieuwsteCompleteBoekjaar staat naast LEIDER_COMPLEET en gebruikt die",
    "export function nieuwsteCompleteBoekjaar(" in voorpagina
    and "compleet = LEIDER_COMPLEET" in voorpagina,
)
check(
    "de sectorleiders gebruiken dezelfde regel, niet een eigen kopie",
    voorpagina.count("aantal >= compleet * vorig") == 1,
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
    "niet over de hele markt" in colofon and "binnen één sector en één boekjaar" in colofon,
)

# --- de sectorpagina: aandeel en plek in één boekjaar ---------------------------
sector = plat(WEB / "app/sector/[naam]/page.tsx")
check(
    "de sectorpagina kiest het boekjaar van het aandeel met nieuwsteCompleteBoekjaar",
    "nieuwsteCompleteBoekjaar(" in sector,
)
check(
    "de sectorpagina rekent geen aandeel meer over het totaal van alle boekjaren",
    "rij.totaal / totaalControles" not in sector
    and "deel={rij.totaal}" not in sector
    and "van deze sector" not in sector,
)
check(
    "het podium en de aandeelkolom delen door de controles van dat ene boekjaar",
    "/ controlesLeiderJaar" in sector and "geheel={controlesLeiderJaar}" in sector,
)
check(
    "onder het minimum geen podium maar de mededeling dat er te weinig is",
    "Te weinig controles voor een aandeel" in sector,
)
check(
    "podium en tabel geven bij gelijke aantallen dezelfde plek (plekIn), niet "
    "een plek in sorteervolgorde",
    "plek={plekIn(rij)}" in sector
    and "<Rang nummer={plekIn(rij)} />" in sector
    and "plek={i + 1}" not in sector,
)
check(
    "een gelijke stand op de laagste podiumplek gaat er als groep af, met een zin",
    "delen plek {grensplek}, met elk {inLeiderJaar(gedeeld[0][1])} controles" in sector,
)

# --- de subsectorpagina: idem, en alleen binnen de eigen sector ----------------
subsector = plat(WEB / "app/subsector/[naam]/page.tsx")
check(
    "de subsectorpagina kiest het boekjaar van het aandeel met nieuwsteCompleteBoekjaar",
    "nieuwsteCompleteBoekjaar(" in subsector,
)
check(
    "de subsectorpagina deelt niet meer door het totaal over alle boekjaren",
    "rij.aantal) / totaal)" not in subsector and "/ totaalAandeelJaar" in subsector,
)
check(
    "de subsectorpagina telt alleen organisaties uit de eigen sector mee",
    "inSector.has(opdracht.organisatie_id)" in subsector,
)

# --- de kantoorpagina: een plek per sector en boekjaar --------------------------
kantoor = plat(WEB / "app/kantoor/[slug]/page.tsx")
check(
    "de kantoorpagina zegt niet meer welk deel 'van alles wat in deze database "
    "staat' een kantoor heeft",
    "van alles wat in deze database staat" not in kantoor,
)
check(
    "de kantoorpagina noemt geen plek 'in de ranglijst' over alle sectoren",
    "in de ranglijst </span>" not in kantoor and "positie + 1" not in kantoor,
)
check(
    "de plek komt uit sectorposities(), per sector en boekjaar",
    "sectorposities(" in kantoor and "hoofd.plek" in kantoor,
)

print(f"{goed}/{goed + fout} goed")
sys.exit(1 if fout else 0)
