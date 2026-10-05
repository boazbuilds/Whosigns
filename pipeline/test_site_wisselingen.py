"""Test: de organisatiepagina wijst dezelfde wisselingen aan als v_wisselingen.

Waarom dit bestaat. wisseljaren() in web/lib/analyse.ts telde ook
`controle_onbepaald` mee, de view v_wisselingen niet. Toen dat 49 gelezen
zorgverklaringen waren scheelde het twee wisselingen. Sinds het marktonderzoek
(35.582 regels, allemaal `controle_onbepaald`) werden het er 517 bij 495
organisaties, gemeten op 5-10-2026: 2.226 "wisselingen" op de
organisatiepagina's tegen 1.709 in de view. Een gelezen verklaring van kantoor
A gevolgd door een marktonderzoek-regel bij kantoor B kreeg het label
"wisseling", "gewisseld in boekjaar X" in de kop en een doorklik naar
/wisselingen, waar hij niet stond. Met alleen de wettelijke en vrijwillige
controle zijn het er precies 1.709, verschil nul in beide richtingen.

Met die strikte set kwam er een nieuwe valkuil in de kop "Huidige accountant".
Die naam komt uit periodes(), mét controle_onbepaald, het jaartal van de
wisseling uit de strikte set. Bij 108 organisaties lag de laatste strikte
wisseling vóór het begin van de huidige periode (5-10-2026), bij 22 omdat het
huidige kantoor alleen uit het marktonderzoek komt: "PwC marktonderzoek — 1
boekjaar (2025), gewisseld in boekjaar 2015", terwijl 2015 de wisseling van
Deloitte naar EY was. Nu staat "gewisseld in boekjaar X" er alleen als X het
eerste jaar van de huidige periode is, en anders de laatste vastgestelde
wisseling mét het kantoor waar die heen ging.

De definitie van een wisseling staat in SQL. Deze test leest de typen uit de
nieuwste migratie die v_wisselingen maakt en eist dat de website precies
dezelfde set gebruikt — wie de view verandert, ziet hier dat de site mee moet.
"""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WEB = ROOT / "web"
MIGRATIES = ROOT / "supabase" / "migrations"

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


def typen_in_view(view: str) -> set[str] | None:
    """De opdrachttypen uit de laatste `create or replace view <view>`."""
    laatste = None
    for pad in sorted(MIGRATIES.glob("*.sql")):
        sql = re.sub(r"--[^\n]*", " ", pad.read_text(encoding="utf-8"))
        for blok in re.finditer(
            rf"create\s+or\s+replace\s+view\s+{view}\b(.*?);", sql, re.DOTALL | re.IGNORECASE
        ):
            laatste = blok.group(1)
    if laatste is None:
        return None
    lijst = re.search(r"type_opdracht\s+in\s*\(([^)]*)\)", laatste, re.IGNORECASE)
    if not lijst:
        return None
    return set(re.findall(r"'([a-z_]+)'", lijst.group(1)))


def controle_types() -> set[str]:
    """CONTROLE_TYPES uit web/lib/paden.ts."""
    tekst = plat(WEB / "lib" / "paden.ts")
    lijst = re.search(r"CONTROLE_TYPES: readonly string\[\] = \[([^\]]*)\]", tekst)
    return set(re.findall(r'"([a-z_]+)"', lijst.group(1))) if lijst else set()


# --- een nep-migratie om de lezer zelf te testen --------------------------------
voorbeeld = (
    "create or replace view v_wisselingen as\n"
    "with wc as (select * from opdrachten\n"
    "  where type_opdracht in ('wettelijke_controle', 'vrijwillige_controle')) select 1;"
)
gevonden = re.search(r"type_opdracht\s+in\s*\(([^)]*)\)", voorbeeld)
check(
    "de lezer haalt de typen uit een view-definitie",
    gevonden is not None
    and set(re.findall(r"'([a-z_]+)'", gevonden.group(1)))
    == {"wettelijke_controle", "vrijwillige_controle"},
)

# --- de echte definities ---------------------------------------------------------
view = typen_in_view("v_wisselingen")
site = controle_types()
check("v_wisselingen is in de migraties te vinden, met een typefilter", bool(view))
check("CONTROLE_TYPES is in paden.ts te vinden", bool(site))
check(
    f"de site telt dezelfde typen als v_wisselingen (site {sorted(site)}, "
    f"view {sorted(view or [])})",
    view == site,
)
check(
    "controle_onbepaald is geen wisseltype: een verklaring waarvan het voorwerp "
    "onbekend is bewijst niet dat de jaarrekeningcontrole verhuisde",
    "controle_onbepaald" not in site,
)
marktaandeel = typen_in_view("v_marktaandeel")
check(
    "v_marktaandeel telt dezelfde typen; dat is waar CONTROLE_TYPES voor staat",
    marktaandeel == site,
)

# --- analyse.ts gebruikt die set voor wisseljaren --------------------------------
analyse = plat(WEB / "lib" / "analyse.ts")
check(
    "WISSEL_VOORRANG komt uit CONTROLE_TYPES, niet uit een eigen lijst",
    "WISSEL_VOORRANG: Record<string, number> = Object.fromEntries( CONTROLE_TYPES.map(" in analyse,
)
check(
    "wisseljaren() rekent met WISSEL_VOORRANG",
    re.search(
        r"export function wisseljaren\([^)]*\)[^{]*\{ return overgangen\("
        r"controleKantoorPerJaar\(opdrachten, WISSEL_VOORRANG\)\); \}",
        analyse,
    )
    is not None,
)
check(
    "de kop 'Huidige accountant' mag wel op controle_onbepaald blijven leunen",
    re.search(r"export function periodes\([^)]*\)[^{]*\{ const perJaar = "
              r"controleKantoorPerJaar\(opdrachten\);", analyse)
    is not None,
)

# --- de organisatiepagina ----------------------------------------------------------
org = plat(WEB / "app" / "organisatie" / "[slug]" / "page.tsx")
check(
    "de doorklik 'wie wisselde er nog meer' gaat naar het boekjaar zelf",
    "naar: `/wisselingen?jaar=${laatsteWisseljaar}`" in org,
)
check(
    "het label 'wisseling' volgt de strikte set",
    "wissels = wisseljaren(opdrachten)" in org
    and 'wissels.has(opdracht.boekjaar) ? ( <> <span className="label label-let-op">wisseling' in org,
)
check(
    "een overgang op een onbepaalde controle heet 'ander kantoor', niet 'wisseling'",
    "onbevestigdeWisseljaren(opdrachten)" in org and "ander kantoor" in org,
)
check(
    "de kop zegt alleen 'gewisseld in boekjaar X' als X het begin van de huidige "
    "periode is: anders leest het als 'sinds X bij dit kantoor'",
    "const beginHuidige = huidige ? Math.min(...huidige.jaren) : null;" in org
    and "const wisselNaarHuidige = laatsteWisseljaar !== null && laatsteWisseljaar === beginHuidige;"
    in org
    and "{wisselNaarHuidige ? `, gewisseld in boekjaar ${laatsteWisseljaar}`" in org,
)
check(
    "ging de laatste vastgestelde wisseling naar een eerdere periode, dan staat erbij "
    "naar welk kantoor",
    "`, laatste vastgestelde wisseling in boekjaar ${laatsteWisseljaar} "
    "(naar ${naarBijLaatsteWissel})`" in org
    and "reeksen.find((r) => r.jaren.includes(laatsteWisseljaar))?.kantoorNaam" in org,
)
check(
    "'gewisseld in boekjaar' staat nergens anders op de pagina",
    org.count("gewisseld in boekjaar") == 1,
)

print(f"{goed}/{goed + fout} goed")
sys.exit(1 if fout else 0)
