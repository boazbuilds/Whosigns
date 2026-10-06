"""Test: een kantoor dat uit het AFM-register verdween heet nergens nog vergunninghouder.

Waarom dit bestaat. Sinds 5-10-2026 zet laad_kantoren.py een AFM-nummer dat het
register niet meer kent op `actief = false`, en haalt het de OOB- en Wta-vlag
weg. De kantoorpagina zei daarna nog steeds "reguliere Wta-vergunning" — die
keek alleen naar het AFM-nummer, en dat blijft staan. De zoekpagina zette er
"Wta" bij, ook bij kantoren die nooit een vergunning hadden.

Daarna hadden drie pagina's elk een eigen regel: /zoeken keek naar het
AFM-nummer en `actief` ("geen", "Wta", "vervallen"), /kantoren naar
`wta_vergunning` ("geen Wta-vergunning"), en de lijst op /kantoren zette een
streepje bij alles zonder OOB. Over dezelfde 58 kantoren zonder Wta-vergunning
(op 5-10-2026: 55 zonder AFM-nummer en 3 die uit het register verdwenen) zeiden
ze dus drie verschillende dingen. Nu staat de regel op één plek,
vergunningSoort() in web/lib/paden.ts, en tonen alle drie de pagina's hetzelfde
onderdeel <Vergunning>.

Daar zitten twee vallen in die TypeScript niet ziet. Het type Kantoor belooft
`actief` en `wta_vergunning`, maar komen ze niet mee in de select, dan zijn ze
`undefined` en heet elk kantoor ineens vervallen of vergunningloos. En de
volgorde telt: een achtergebleven vlag op een verdwenen kantoor mocht het tot
5-10-2026 vijf weken lang OOB-kantoor laten heten (de AFM zelf, migratie
20261005120000), dus "verdwenen" gaat vóór de vlaggen.

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


# --- de velden komen mee ----------------------------------------------------------
db = bron("lib/db.ts")
kern = re.search(r'const KANTOOR_KERN = "([^"]+)"', db)
velden = kern.group(1).split(",") if kern else []
check("actief wordt bij elk kantoor opgehaald (KANTOOR_KERN)", "actief" in velden)
check("wta_vergunning ook", "wta_vergunning" in velden)

# --- de regel staat op één plek, in deze volgorde -----------------------------------
paden = bron("lib/paden.ts")
regel = re.search(r"export function vergunningSoort\([^)]*\): Vergunningsoort \{(.*?)\}", paden)
check("vergunningSoort() staat in paden.ts", regel is not None)
stappen = regel.group(1) if regel else ""
check(
    "zonder AFM-nummer geen vergunning, dan verdwenen, dan OOB, dan Wta, anders geen",
    stappen.strip()
    == 'if (!kantoor.afm_nummer) return "geen"; '
    'if (!kantoor.actief) return "vervallen"; '
    'if (kantoor.oob_vergunning) return "oob"; '
    'if (kantoor.wta_vergunning) return "wta"; '
    'return "geen";',
)

# --- en één onderdeel met de woorden ---------------------------------------------------
onderdelen = bron("components/onderdelen.tsx")
check(
    "het onderdeel Vergunning rekent met vergunningSoort()",
    "export function Vergunning(" in onderdelen
    and "const soort = vergunningSoort(kantoor);" in onderdelen,
)
voluit = re.search(r"const VERGUNNING_VOLUIT: Record<Vergunningsoort, string> = \{(.*?)\};", onderdelen)
kort = re.search(r"const VERGUNNING_KORT: Record<Vergunningsoort, string> = \{(.*?)\};", onderdelen)
check(
    "voluit, op de kantoorpagina: een verdwenen kantoor staat 'niet meer in het "
    "AFM-register', alleen een actief kantoor heeft een 'reguliere Wta-vergunning'",
    voluit is not None
    and 'vervallen: "niet meer in het AFM-register"' in voluit.group(1)
    and 'wta: "reguliere Wta-vergunning"' in voluit.group(1)
    and 'geen: "geen Wta-vergunning"' in voluit.group(1),
)
check(
    "kort, in een tabel: 'vervallen' en 'geen Wta-vergunning', niet een kaal 'geen'",
    kort is not None
    and 'vervallen: "vervallen"' in kort.group(1)
    and 'geen: "geen Wta-vergunning"' in kort.group(1),
)

# --- de drie pagina's gebruiken dat onderdeel en geen eigen regel ----------------------
for pad, aanroep in (
    ("app/kantoor/[slug]/page.tsx", "<Vergunning kantoor={kantoor} voluit />"),
    ("app/zoeken/page.tsx", '<Vergunning kantoor={kantoor} className="zacht klein" />'),
    ("app/kantoren/page.tsx", '<Vergunning kantoor={rij.kantoor} className="zacht" />'),
    ("app/kantoren/page.tsx", "<Vergunning kantoor={kantoor} />"),
):
    tekst = bron(pad)
    check(f"{pad} toont het gedeelde label ({aanroep})", aanroep in tekst)
for pad in ("app/kantoor/[slug]/page.tsx", "app/zoeken/page.tsx", "app/kantoren/page.tsx"):
    tekst = bron(pad)
    check(
        f"{pad} heeft geen eigen regel op actief of wta_vergunning meer",
        "kantoor.actief ?" not in tekst
        and "kantoor.wta_vergunning ?" not in tekst
        and "function Vergunning(" not in tekst,
    )

print(f"{goed}/{goed + fout} goed")
sys.exit(1 if fout else 0)
