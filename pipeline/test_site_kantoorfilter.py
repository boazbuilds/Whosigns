"""Test: de sectorregel op een kantoorpagina toont de eigen cliënten.

Waarom dit bestaat. In "Waar dit kantoor werkt" op /kantoor/[slug] linkte de
sectornaam naar de landelijke sectorpagina. Wie bij WITh Accountants op "Goede
doelen" klikte (69 van de 72 cliënten) kwam dus niet bij de goede doelen van
WITh uit, maar bij een ranglijst van álle kantoren in die sector — een andere
vraag dan de klik stelde. Sinds 21-8-2026 (verzoek van de opdrachtgever) linkt
de sectornaam naar de eigen cliëntenlijst, gefilterd op die sector; de
landelijke pagina blijft bereikbaar via "hele sector →" en de doorklikken.

Dit is een tekstcontrole op de paginabron, net als test_site_aandeel.py: het te
bewaken gedrag is een bewering over waar een klik heen leidt, geen berekening.
Commentaar telt niet mee, anders zou de uitleg in de code de test kunnen voeden.
"""

import re
import sys
from pathlib import Path

PAGINA = (
    Path(__file__).resolve().parent.parent
    / "web" / "app" / "kantoor" / "[slug]" / "page.tsx"
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


BLOKCOMMENTAAR = re.compile(r"/\*.*?\*/|\{/\*.*?\*/\}", re.DOTALL)
REGELCOMMENTAAR = re.compile(r"(?m)^[ \t]*//.*$")

tekst = PAGINA.read_text(encoding="utf-8")
tekst = BLOKCOMMENTAAR.sub(" ", tekst)
tekst = REGELCOMMENTAAR.sub(" ", tekst)
plat = " ".join(tekst.split())

check(
    "de sectornaam linkt naar de eigen pagina met een sectorfilter",
    # Sinds de jaarkiezer bouwt clientenPad de link; de sectornaam geeft
    # jaar=null mee ("alle boekjaren") en de padbouwer zet het sectorfilter.
    "clientenPad(null, sector)" in plat
    and 'zoek.set("sector", slugVan(sector))' in plat
    and "#clienten" in plat,
)
check(
    "de landelijke sectorpagina blijft bereikbaar vanaf dezelfde regel",
    "hele sector" in plat and "sectorPad(sector)" in plat,
)
check(
    "de cliëntentabel toont de gefilterde lijst, niet altijd alles",
    # Sinds 5-10-2026 per pagina van CLIENTEN_PER_PAGINA: de tabel toont een
    # stuk uit de gefilterde lijst, nog steeds niet uit alle cliënten.
    "clientenOpPagina.map((client)" in plat
    and "const clientenOpPagina = clientenGetoond.slice(" in plat,
)
check(
    "een pagina voorbij het einde valt terug op de laatste in plaats van een "
    "lege lijst, en het totaal in de kop blijft de hele gefilterde lijst",
    "Math.min(paginaUitZoek(paginaRuw), aantalPaginas)" in plat
    and "` (${clientenGetoond.length})`" in plat,
)
check(
    "een ander jaar of een andere sector begint weer op pagina 1",
    "const clientenPad = (jaar: number | null, sector: string | null, pagina = 1) =>" in plat
    and 'if (pagina > 1) zoek.set("pagina", String(pagina));' in plat,
)
check(
    "een onbekende sectorwaarde valt terug op alle cliënten in plaats van "
    "stil op nul",
    "?? null" in plat and "!sectorFilter || c.sector === sectorFilter" in plat,
)
check(
    "de jaarkiezer staat boven de lijst en houdt een weg naar alle jaren open",
    'aria-label="Kies een boekjaar"' in plat and "Alle jaren" in plat,
)
check(
    "een onzinnig jaartal valt terug op het standaardjaar in plaats van "
    "stil op nul",
    ": standaardJaar" in plat,
)
check(
    "bij een actief filter staat er een weg terug naar alle sectoren",
    "Alle sectoren" in plat,
)
check(
    "de sectie heeft het anker waar de filterlink heen springt",
    'id="clienten"' in plat,
)

print(f"{goed}/{goed + fout} goed")
sys.exit(1 if fout else 0)
