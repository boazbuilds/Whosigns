"""Test: een oud rapport in .cache mag nooit de basis van een nieuwe oogst worden.

Waarom dit bestaat. Op 17-8-2026 begon de oogst van boekjaar 2023 bovenop een
`resultaat_2023.csv` van 29 juli. Dat bestand had de kolommen van toen — zeven —
en de oogst schreef er rijen met elf achteraan. Twee commits lang zag dat er
gezond uit: het rapport groeide, de teller liep. Pas bij het teruglezen bleek het
een mengsel van twee indelingen, en zo'n rapport gaat regelrecht de database in.

Het gat zat niet in de controle zelf maar in wat ervóór stond: de functie
vergeleek de kopregel met die van de repo-kopie, en sloeg bij gebrek daaraan
alles over. Precies bij een nieuw boekjaar is er geen repo-kopie.

Deze test draait de echte shellfunctie, niet een nabouw ervan. `opzij` en
`herstel_rapport` worden uit `oogst_zorg.sh` geknipt en in een tijdelijke map
losgelaten op verzonnen bestanden. Een nabouw zou meegroeien met mijn aannames;
de functie uit het script kan alleen slagen als hij het echt doet.
"""

import re
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from laad_zorg import RAPPORT_KOLOMMEN  # noqa: E402
from laad_zorg_rapport import VERPLICHT  # noqa: E402
from nakijk_ocr import RAPPORT_KOLOMMEN as OCR_KOLOMMEN  # noqa: E402

SCRIPT = Path(__file__).resolve().parent / "oogst_zorg.sh"
GOED = ",".join(RAPPORT_KOLOMMEN)
OUD = "kvk,naam,plaats,boekjaar,kantoor,afm_nummer,oordeel"

goed = 0
fout = 0


def check(omschrijving: str, voorwaarde: bool) -> None:
    global goed, fout
    if voorwaarde:
        goed += 1
    else:
        fout += 1
        print(f"  FOUT: {omschrijving}")


def functies_uit_script() -> str:
    """Knipt `kopregel`, `opzij` en `herstel_rapport` uit het script.

    Vanaf de eerste van de drie tot vlak vóór de losse aanroep `herstel_rapport`
    onderaan. Verdwijnt of hernoemt er een, dan faalt deze test met een duidelijke
    melding in plaats van stilletjes niets te testen.

    Het beginpunt wordt gezocht en niet vastgelegd op één naam: toen `kopregel`
    erbij kwam stond die vóór `opzij`, viel buiten de knip, en faalde elke test
    op "command not found" -- ook met een script dat het gewoon goed deed.
    """
    tekst = SCRIPT.read_text(encoding="utf-8")
    posities = []
    for naam in ("kopregel", "opzij", "herstel_rapport"):
        plek = tekst.find(f"{naam}() {{")
        if plek < 0:
            raise AssertionError(f"de functie {naam} staat niet meer in het script")
        posities.append(plek)
    begin = min(posities)
    einde = re.search(r"^herstel_rapport$", tekst[begin:], re.MULTILINE)
    if einde is None:
        raise AssertionError("de aanroep van herstel_rapport staat niet meer in het script")
    return tekst[begin : begin + einde.start()]


def draai(
    kopregel_cache,
    regels_cache,
    kopregel_repo,
    regels_repo,
    verwerkt=True,
    einde="\r\n",
    einde_repo=None,
):
    """Zet een situatie klaar en draait de echte functie erop los.

    `einde` is standaard CRLF, want zo staan de bestanden er echt: python's
    csv.writer schrijft \\r\\n. Deze test schreef eerst alleen LF, en juist
    daardoor kwam er een versie doorheen die elke correcte repo-kopie afwees --
    de vergelijking zag "...onzekerheid\\r" naast "...onzekerheid". Een test die
    nettere bestanden maakt dan de werkelijkheid bewijst niets.

    Geeft terug wat er ná afloop in .cache staat: de kopregel van het rapport
    (of None als het er niet meer is), het aantal regels, of het opzij-bestand
    bestaat, en of de bekekenlijst er nog is.
    """
    with tempfile.TemporaryDirectory() as map_naam:
        tijdelijk = Path(map_naam)
        cache = tijdelijk / "cache"
        oogst = tijdelijk / "oogst"
        cache.mkdir()
        oogst.mkdir()
        rapport = cache / "resultaat_2023.csv"
        bekeken = cache / "verwerkt_2023.txt"
        bewaard = oogst / "zorg_2023.csv"

        def schrijf(pad, kop, aantal, regeleinde):
            regels = [kop] + [f"rij{i}" for i in range(aantal)]
            pad.write_bytes((regeleinde.join(regels) + regeleinde).encode("utf-8"))

        if kopregel_cache is not None:
            schrijf(rapport, kopregel_cache, regels_cache, einde)
        if verwerkt:
            bekeken.write_text("12345678\n", encoding="utf-8")
        if kopregel_repo is not None:
            schrijf(bewaard, kopregel_repo, regels_repo, einde_repo or einde)

        script = f"""
set -uo pipefail
BOEKJAAR=2023
RAPPORT="{rapport}"
VERWERKT="{bekeken}"
OOGST="{oogst}"
KOLOMMEN="{GOED}"
{functies_uit_script()}
herstel_rapport
"""
        klaar = subprocess.run(
            ["bash", "-c", script], capture_output=True, text=True, timeout=30
        )
        kop = None
        aantal = 0
        if rapport.exists():
            regels = rapport.read_text(encoding="utf-8").splitlines()
            kop = regels[0] if regels else ""
            aantal = len(regels)
        return {
            "kop": kop,
            "regels": aantal,
            "opzij": (cache / "resultaat_2023.csv.oud").exists(),
            "bekeken": bekeken.exists(),
            "bekeken_opzij": (cache / "verwerkt_2023.txt.oud").exists(),
            "uitvoer": klaar.stdout + klaar.stderr,
            "code": klaar.returncode,
        }


# --- de fout van 17-8-2026 zelf ------------------------------------------------
# Oud rapport in .cache, en van dit boekjaar bestaat nog geen repo-kopie.
zonder_repo = draai(OUD, 22, None, 0)
check(
    "oud rapport zonder repo-kopie wordt niet als beginpunt gebruikt",
    zonder_repo["kop"] is None,
)
check(
    "oud rapport zonder repo-kopie gaat opzij als .oud",
    zonder_repo["opzij"],
)
check(
    "de bekekenlijst gaat mee opzij, anders slaan we die organisaties nooit meer aan",
    zonder_repo["bekeken_opzij"] and not zonder_repo["bekeken"],
)
check(
    "de functie meldt wat ze doet",
    "kolommen" in zonder_repo["uitvoer"],
)

# Hetzelfde, maar mét een repo-kopie in het oude formaat. Die mag evenmin winnen:
# de oogst committeerde het foute rapport óók, dus zonder deze regel zet elke
# herstart de fout keurig terug.
oud_beide = draai(OUD, 22, OUD, 30)
check(
    "een repo-kopie in het oude formaat wordt ook niet teruggezet",
    oud_beide["kop"] is None,
)

# En een repo-kopie in het oude formaat zonder iets in .cache: ook niet.
alleen_oude_repo = draai(None, 0, OUD, 30)
check(
    "een oude repo-kopie wordt niet teruggezet als .cache leeg is",
    alleen_oude_repo["kop"] is None,
)

# --- het gewone geval blijft werken --------------------------------------------
goed_zonder_repo = draai(GOED, 5, None, 0)
check(
    "een rapport met de juiste kolommen blijft staan",
    goed_zonder_repo["kop"] == GOED and goed_zonder_repo["regels"] == 6,
)
check(
    "en gaat niet opzij",
    not goed_zonder_repo["opzij"],
)
check(
    "en de bekekenlijst blijft staan",
    goed_zonder_repo["bekeken"],
)

# Repo-kopie heeft de herstart overleefd en is langer: die wint.
repo_langer = draai(GOED, 3, GOED, 40)
check(
    "de langere repo-kopie wint van een kortere in .cache",
    repo_langer["regels"] == 41,
)

# .cache is verder dan de repo-kopie: dan is .cache de actuele stand.
cache_langer = draai(GOED, 40, GOED, 3)
check(
    "een .cache dat verder is dan de repo-kopie blijft staan",
    cache_langer["regels"] == 41,
)

# Niets in .cache, wel een repo-kopie: gewoon terugzetten.
alleen_repo = draai(None, 0, GOED, 12)
check(
    "zonder .cache wordt de repo-kopie teruggezet",
    alleen_repo["kop"] == GOED and alleen_repo["regels"] == 13,
)

# --- regeleindes ---------------------------------------------------------------
# Het echte bestand is CRLF (csv.writer), de kolommenlijst uit python is LF. Wie
# die twee rauw vergelijkt wijst elk correct rapport af. Dat gebeurde op
# 17-8-2026 na een rollback: de repo-kopie met negen opdrachten werd geweigerd,
# en de oogst zou met een leeg rapport zijn verdergegaan terwijl de lijst met
# achtenveertig bekeken organisaties bleef staan.
for naam, einde in (("CRLF", "\r\n"), ("LF", "\n")):
    uit = draai(None, 0, GOED, 9, einde=einde)
    check(
        f"een repo-kopie met {naam}-regeleindes wordt herkend en teruggezet",
        uit["kop"] == GOED and uit["regels"] == 10,
    )
    uit = draai(GOED, 4, None, 0, einde=einde)
    check(
        f"een goed rapport met {naam}-regeleindes blijft staan",
        uit["kop"] == GOED and not uit["opzij"],
    )

# Gemengd: .cache van de lader (CRLF) naast een repo-kopie die ooit door iets
# anders is geschreven (LF). Zelfde kolommen, dus dat is geen reden voor alarm.
gemengd = draai(GOED, 3, GOED, 40, einde="\r\n", einde_repo="\n")
check(
    "gelijke kolommen met verschillende regeleindes gelden als gelijk",
    not gemengd["opzij"] and gemengd["regels"] == 41,
)

# Niets in .cache en geen repo-kopie: een schone start, zonder klachten.
niets = draai(None, 0, None, 0)
check(
    "een schone start levert geen rapport en geen fout op",
    niets["kop"] is None and niets["code"] == 0,
)
check(
    "en laat de bekekenlijst met rust",
    niets["bekeken"],
)

# Ontbreekt de bekekenlijst, dan mag het opzijleggen daar niet over struikelen.
zonder_lijst = draai(OUD, 22, None, 0, verwerkt=False)
check(
    "opzijleggen werkt ook als er geen bekekenlijst is",
    zonder_lijst["opzij"] and zonder_lijst["code"] == 0,
)

# --- één lijst kolommen, niet drie ---------------------------------------------
check(
    "laad_zorg en laad_zorg_rapport gebruiken dezelfde kolommen",
    RAPPORT_KOLOMMEN == VERPLICHT,
)
check(
    "laad_zorg en nakijk_ocr gebruiken dezelfde kolommen",
    RAPPORT_KOLOMMEN == OCR_KOLOMMEN,
)
check(
    "de lijst staat maar op één plek letterlijk in de pipeline",
    sum(
        1
        for pad in Path(__file__).resolve().parent.glob("*.py")
        if not pad.name.startswith("test_")
        and '"kantoor_sleutel",\n' in pad.read_text(encoding="utf-8")
    )
    == 1,
)
check(
    "het script vraagt de kolommen op bij laad_zorg",
    "RAPPORT_KOLOMMEN" in SCRIPT.read_text(encoding="utf-8"),
)

# --- de kolommen zelf ----------------------------------------------------------
check(
    "kantoor_sleutel zit erin; zonder die kolom kan het rapport niet ingeladen worden",
    "kantoor_sleutel" in RAPPORT_KOLOMMEN,
)
check(
    "de oude indeling van 29 juli is niet gelijk aan de huidige",
    OUD != GOED,
)

print(f"{goed}/{goed + fout} goed")
sys.exit(1 if fout else 0)
