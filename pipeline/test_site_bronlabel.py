"""Test: een opdracht uit aangeleverd marktonderzoek draagt dat label.

Waarom dit bestaat. De labelplicht uit docs/concept.md: bij elk gegeven hoort
zichtbaar te zijn of het uit een openbare bron komt of door iemand zelf is
aangeleverd. Het colofon belooft dat opdrachten uit het marktonderzoek "het
bronlabel marktonderzoek" dragen. Maar op de organisatiepagina hing het hele
label aan `bronnen.url`, en het marktonderzoek is de enige bron zonder url.
Gemeten op 5-10-2026: 35.582 opdrachten bij 12.726 organisaties stonden met een
streepje in de kolom Bron, waarvan 11.646 organisaties met niets anders dan
marktonderzoek. Op de kantoorpagina en op /honoraria stond het label nergens.

Alleen het soort bron mag zichtbaar zijn, nooit de leverancier: de
leveranciersnaam staat niet in de database en hoort ook niet in de code.
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


def plat(pad: Path) -> str:
    tekst = pad.read_text(encoding="utf-8")
    tekst = BLOKCOMMENTAAR.sub(" ", tekst)
    tekst = REGELCOMMENTAAR.sub(" ", tekst)
    return " ".join(tekst.split())


org = plat(WEB / "app" / "organisatie" / "[slug]" / "page.tsx")
kantoor = plat(WEB / "app" / "kantoor" / "[slug]" / "page.tsx")
honoraria = plat(WEB / "app" / "honoraria" / "page.tsx")
onderdelen = plat(WEB / "components" / "onderdelen.tsx")
db = plat(WEB / "lib" / "db.ts")
analyse = plat(WEB / "lib" / "analyse.ts")

# --- de kolom Bron op de organisatiepagina ---------------------------------------
BEGIN = '<td className="klein"> {opdracht.bronnen ? ('
EIND = '<span className="zacht">—</span> )} </td>'
begin = org.find(BEGIN)
eind = org.find(EIND, begin)
check(
    "de Bron-cel begint met de vraag óf er een bron is, niet óf er een url is",
    begin >= 0 and eind > begin,
)
if begin >= 0 and eind > begin:
    binnen = org[begin:eind]
    check(
        "het soort bron staat er ook zonder url: bron_type twee keer, in de link "
        "en in de terugval",
        binnen.count("{opdracht.bronnen.bron_type}") == 2
        and "opdracht.bronnen.url ? (" in binnen,
    )
    url_einde = binnen.find("{opdracht.bronnen.bron_type} </span> )}")
    check(
        "de betrouwbaarheid (publiek of zelf aangeleverd) staat ná de url-keuze, "
        "dus ook zonder url",
        url_einde >= 0 and binnen.find("opdracht.bronnen.betrouwbaarheid ?", url_einde) > 0,
    )
check(
    "de oude vorm, waarin alles aan de url hing, is weg",
    "{opdracht.bronnen?.url ? (" not in org,
)

# --- het label zelf -----------------------------------------------------------------
check(
    "Aangeleverd toont alleen iets bij een zelf aangeleverde bron",
    'bron.betrouwbaarheid !== "zelf_aangeleverd") return null' in onderdelen,
)
label = re.search(r'<span className="label label-vaag" title=\{titel\}> (.*?) </span>', onderdelen)
check(
    "Aangeleverd toont het soort bron, hooguit met de boekjaren erachter, en "
    "niets anders",
    label is not None
    and label.group(1)
    == "{gedeeltelijk ? `${bron.bron_type} ${deel}` : bron.bron_type}"
    and "const deel = jaren?.length ? jarenKort(jaren)" in onderdelen,
)

# --- waar opdrachten staan, staat het label -----------------------------------------
check(
    "de kop 'Huidige accountant' en de relatiegeschiedenis dragen het label",
    org.count("<Aangeleverd bron={huidige.aangeleverd}") == 1
    and org.count("<Aangeleverd bron={reeks.aangeleverd}") == 1,
)
check(
    "periodes() onthoudt welke jaren op een aangeleverde bron rusten",
    'bron?.betrouwbaarheid === "zelf_aangeleverd"' in analyse
    and "periode.aangeleverdeJaren.push(jaar)" in analyse,
)
check(
    "de cliëntenlijst van een kantoor draagt het label",
    "<Aangeleverd bron={client.bronLaatste} />" in kantoor
    and "bronLaatste: stand.bron" in analyse,
)
check(
    "/honoraria draagt het label bij het kantoor",
    "<Aangeleverd bron={rij.bronnen} />" in honoraria,
)
check(
    "de bron wordt daarvoor ook opgehaald, op de kantoorpagina en bij de honoraria",
    db.count("bronnen(bron_type,betrouwbaarheid)") >= 2,
)

# --- nooit een leverancier ----------------------------------------------------------
# Het label is het soort bron uit de database. Een vaste tekst met een
# bedrijfsnaam of een bestandsnaam zou hier opvallen als een tweede string naast
# "marktonderzoek" in de labelcode; die is er niet.
check(
    "de labelcode noemt geen bestandsnaam of extensie",
    not re.search(r"\.(csv|xlsx?|json)\b", onderdelen),
)

print(f"{goed}/{goed + fout} goed")
sys.exit(1 if fout else 0)
