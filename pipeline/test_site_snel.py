"""Test: de website-afspraken uit "website-snel" blijven staan.

Waarom dit bestaat. Vijf dingen die stil terug kunnen sluipen, en die je op
de site pas ziet als het misgaat:

1. Een pagina die Next een uur bewaart (ISR) mag een databasefout niet zelf
   afvangen en als <Foutmelding> tonen. Voor Next is dat een geslaagde versie:
   op 5-10-2026 nagedaan met een storing, en /honoraria gaf daarna een uur lang
   "De gegevens konden niet worden opgehaald" (16.700 bytes, x-nextjs-cache
   HIT). Een geworpen fout laat de vorige versie staan.
2. De organisatie-, sector-, subsector- en accountantpagina's zijn ISR via
   `generateStaticParams() { return []; }`. Eén `searchParams` erin en ze zijn
   zonder melding weer dynamisch: elke weergave een render, nooit uit de CDN.
3. De views achter zolangNieuw() moeten in een migratie staan. Een tikfout in
   de naam valt niet op: de terugval vangt hem en de site doet het gewoon,
   alleen voor altijd langzaam.
4. Zachte tekst haalt 4,5:1. --inkt-flauw haalt op papier 3,28:1; axe vond op
   5-10-2026 op elk van twaalf pagina's 10 tot 253 tekstregels in die kleur.
   Die blijft alleen voor grafiekvlakken, en voor het pijltje in de donkere
   menubalk, waar hij 4,79:1 haalt.
5. De linkcontrole in CI vraagt /zoeken nooit op (die schrijft in de zoeklog
   van de productiedatabase), en de CI-job kent alleen de publishable key.
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
JSXCOMMENTAAR = re.compile(r"\{/\*.*?\*/\}", re.DOTALL)


def zonder_commentaar(tekst: str) -> str:
    tekst = JSXCOMMENTAAR.sub(" ", tekst)
    tekst = BLOKCOMMENTAAR.sub(" ", tekst)
    tekst = REGELCOMMENTAAR.sub(" ", tekst)
    return " ".join(tekst.split())


def plat(pad: Path) -> str:
    return zonder_commentaar(pad.read_text(encoding="utf-8"))


# --- 1. ISR-pagina's tonen geen eigen foutmelding ---------------------------------
ISR_PAGINAS = [
    "app/page.tsx",
    "app/honoraria/page.tsx",
    "app/accountants/page.tsx",
    "app/sectoren/page.tsx",
    "app/organisatie/[slug]/page.tsx",
    "app/sector/[naam]/page.tsx",
    "app/subsector/[naam]/page.tsx",
    "app/accountant/[sleutel]/page.tsx",
]
check(
    "de commentaarstripper laat code staan en haalt commentaar weg",
    zonder_commentaar("// return <Foutmelding />\nconst a = 1; /* <Foutmelding> */")
    == "const a = 1;",
)
for pagina in ISR_PAGINAS:
    code = plat(WEB / pagina)
    check(f"{pagina} rendert geen <Foutmelding> (die zou een uur in de cache staan)",
          "<Foutmelding" not in code)
sectoren_code = plat(WEB / "app" / "sectoren" / "page.tsx")
check(
    "/sectoren vangt geen fout stil af met een lege lijst (die stond een uur als "
    "'0 kantoren met controles' in de cache)",
    ".catch(() => [])" not in sectoren_code,
)

# --- 2. detailpagina's zijn ISR en blijven dat --------------------------------------
for pagina in [
    "app/organisatie/[slug]/page.tsx",
    "app/sector/[naam]/page.tsx",
    "app/subsector/[naam]/page.tsx",
    "app/accountant/[sleutel]/page.tsx",
]:
    code = plat(WEB / pagina)
    check(f"{pagina} ververst per uur", "export const revalidate = 3600;" in code)
    check(
        f"{pagina} bouwt niets vooraf maar wel bij het eerste bezoek",
        re.search(r"export function generateStaticParams\(\)[^;]*?\{ return \[\]; \}", code)
        is not None,
    )
    check(f"{pagina} leest geen searchParams (dan is hij weer dynamisch)",
          "searchParams" not in code)

# --- 3. elke view achter zolangNieuw staat in een migratie ---------------------------
alle_sql = " ".join(
    re.sub(r"--[^\n]*", " ", pad.read_text(encoding="utf-8")).lower()
    for pad in sorted(MIGRATIES.glob("*.sql"))
)
db = plat(WEB / "lib" / "db.ts")
views = set(re.findall(r'zolangNieuw<[^>]*>\(\s*"(v_[a-z_]+)"', db))
check("db.ts gebruikt zolangNieuw voor v_sectoren, v_subsectoren en v_wisselingen_sector",
      {"v_sectoren", "v_subsectoren", "v_wisselingen_sector"} <= views)
for view in sorted(views):
    check(
        f"{view} wordt in een migratie gemaakt",
        re.search(rf"create\s+(or\s+replace\s+)?view\s+{view}\b", alle_sql) is not None,
    )
for view in ["v_sectoren", "v_subsectoren", "v_wisselingen_sector"]:
    check(
        f"{view} draait met de rechten van wie hem leest (security_invoker), zoals de "
        "andere views",
        re.search(rf"create\s+or\s+replace\s+view\s+{view}\s+with\s*\(\s*security_invoker\s*=\s*on\s*\)",
                  alle_sql) is not None,
    )
check(
    "v_sectoren telt een lege sector niet mee, net als de oude telling in TypeScript",
    re.search(r"view\s+v_sectoren\b.*?where\s+sector\s+is\s+not\s+null\s+and\s+sector\s*<>\s*''",
              alle_sql, re.DOTALL) is not None,
)

# Gepagineerde verzoeken met een unieke staart (zie haalAlles in db.ts).
for wat, patroon in [
    ("alleKantoren", r"kantoren\?select=\$\{velden\}&order=naam\.asc,id\.asc"),
    ("accountantsVanKantoor", r"order=boekjaar\.desc,opdracht_id\.asc"),
    ("opdrachtenVanAccountant", r"order=boekjaar\.desc,organisatie_id\.asc,opdracht_id\.asc"),
    ("organisatiesInSectorPagina", r"order=naam\.asc,id\.asc` \+ `&limit=\$\{perPagina\}"),
]:
    check(f"{wat} sorteert op een unieke staart", re.search(patroon, db) is not None)


# --- 4. contrast van zachte tekst -------------------------------------------------
def luminantie(hexkleur: str) -> float:
    h = hexkleur.lstrip("#")
    kanalen = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    lin = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in kanalen]
    return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]


def contrast(a: str, b: str) -> float:
    la, lb = sorted([luminantie(a), luminantie(b)], reverse=True)
    return (la + 0.05) / (lb + 0.05)


check("contrastformule: zwart op wit is 21:1", round(contrast("#000000", "#ffffff"), 1) == 21.0)

css_tekst = (WEB / "app" / "globals.css").read_text(encoding="utf-8")
css = BLOKCOMMENTAAR.sub(" ", css_tekst)
tokens = dict(re.findall(r"(--[a-z0-9-]+):\s*(#[0-9a-fA-F]{6})\s*;", css))
check("de kleurtokens zijn te lezen", {"--papier", "--vel", "--papier-diep", "--inkt"} <= set(tokens))
tekstkleur = tokens.get("--inkt-tekst-flauw")
check("er is een apart token voor zachte tekst", tekstkleur is not None)
for achtergrond in ["--papier", "--vel", "--papier-diep"]:
    if tekstkleur and achtergrond in tokens:
        verhouding = contrast(tekstkleur, tokens[achtergrond])
        check(f"--inkt-tekst-flauw op {achtergrond} haalt 4,5:1 (nu {verhouding:.2f})",
              verhouding >= 4.5)
check(
    "--inkt-flauw zelf haalt die 4,5:1 op papier níét — daarom het aparte token",
    contrast(tokens.get("--inkt-flauw", "#000000"), tokens.get("--papier", "#000000")) < 4.5,
)


def tekst_in_flauw(stylesheet: str) -> list[str]:
    """Selectoren die tekst (color, niet background of border) in --inkt-flauw zetten."""
    uit = []
    for selector, inhoud in re.findall(r"([^{}]+)\{([^{}]*)\}", stylesheet):
        if re.search(r"(?<![-\w])color:\s*var\(--inkt-flauw\)", inhoud):
            uit.append(" ".join(selector.split()))
    return uit


check(
    "de lezer vindt color, maar niet background of border-color",
    tekst_in_flauw(".a { color: var(--inkt-flauw); } .b { background: var(--inkt-flauw); }"
                   " .c { border-color: var(--inkt-flauw); }") == [".a"],
)
toegestaan = {".hoofdmenu > li.heeft-uitklap > a::after"}
gevonden = tekst_in_flauw(css)
check(f"alleen het pijltje in de donkere menubalk is tekst in --inkt-flauw (nu: {gevonden})",
      set(gevonden) <= toegestaan)
check("en dat pijltje haalt 4,5:1 op de donkere balk",
      contrast(tokens.get("--inkt-flauw", "#ffffff"), tokens.get("--inkt", "#ffffff")) >= 4.5)

grafieken = plat(WEB / "components" / "grafieken.tsx")
check(
    "een balkkant met aria-label heeft een rol (een kale span mag geen label dragen)",
    grafieken.count('role="img"') >= 2
    and len(re.findall(r'className="balanskant balans-(links|rechts)" role="img"', grafieken)) == 2,
)
check("het hoofdmenu zegt welke rubriek de huidige is",
      'aria-current={hier ? "page" : eronder ? "true" : undefined}'
      in plat(WEB / "components" / "menulink.tsx"))

# --- 5. CI: linkcontrole zonder /zoeken, alleen de publishable key -----------------
linkcheck = plat(WEB / "scripts" / "linkcheck.mjs")
check("de linkcontrole slaat /zoeken over", 'pad.startsWith("/zoeken")' in linkcheck)
check("de linkcontrole begint nergens bij /zoeken",
      re.search(r"const BEGIN = \[[^\]]*zoeken", linkcheck) is None)
ci = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
job = ci.split("\n  website:", 1)[1] if "\n  website:" in ci else ""
check("ci.yml heeft een job 'website'", bool(job))
check("die job bouwt de site en draait de linkcontrole",
      "npx next build" in job and "node scripts/linkcheck.mjs" in job)
check("die job kent alleen de publishable key, geen secret",
      "sb_publishable_" in job and "secrets." not in job and "SERVICE_ROLE" not in job.upper()
      and "sb_secret_" not in job)

print(f"{goed}/{goed + fout} goed")
sys.exit(1 if fout else 0)
