"""Test: de website-afspraken uit "website-snel" blijven staan.

Waarom dit bestaat. Dingen die stil terug kunnen sluipen, en die je op de
site pas ziet als het misgaat:

1. Een pagina die Next een uur bewaart (ISR) mag een databasefout niet zelf
   afvangen en als <Foutmelding> tonen. Voor Next is dat een geslaagde versie:
   op 5-10-2026 nagedaan met een storing, en /honoraria gaf daarna een uur lang
   "De gegevens konden niet worden opgehaald" (16.700 bytes, x-nextjs-cache
   HIT). Een geworpen fout laat de vorige versie staan. Een stille terugval
   (.catch) is daar net zo erg: de lege lijst gaat een uur de cache in. Alleen
   de uitzonderingen in TOEGESTANE_CATCH mogen, elk met de reden erbij.
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
   van de productiedatabase), en de CI-job kent alleen de publishable key. Hij
   staat in een eigen workflow met een padfilter: een ronde las op 5-10-2026
   ~800 verzoeken en ~28 MB uit Supabase, ook bij een pull request zonder één
   regel van de website.
6. Een paar rekenregels draaien echt, in node (vanaf 22.18 leest node zelf
   TypeScript): paginaUitZoek met een reusachtig getal (op 5-10-2026 gaf
   ?pagina=99999999999999999999 de eerste pagina met status 200, in plaats
   van een 404), de nummers van <Paginering>, het eigen saldo op
   /wisselingen?kantoor= en de groepering van /honoraria. Zonder geschikte
   node slaat dit deel zich over, met een melding; in
   .github/workflows/website.yml (SITE_LOGICA_VERPLICHT) mag dat niet.
7. De linkcontrole draait tegen een nagemaakte site: hij moet falen op een
   pagina met een foutmelding (die heeft status 200), /zoeken nooit opvragen
   en zich aan zijn grens per soort houden.
"""

import http.server
import json
import os
import re
import shutil
import subprocess
import sys
import threading
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

# Elke .catch op een ISR-pagina moet hier staan, met de reden. Een nieuwe (ook
# een die bij een merge binnenkomt) valt anders niet op: de pagina doet het
# gewoon, tot de eerste storing een uur lang een lege versie in de cache zet.
TOEGESTANE_CATCH = {
    # los(): een los dashboardblok valt weg zonder iets te beweren; de kern van
    # de voorpagina faalt wel hard. De dagvraag is een spelletje en mag nooit
    # de voorpagina breken. Allebei bewust zo gelaten op 5-10-2026.
    "app/page.tsx": ["belofte.catch(", "dagvraag(vandaag).catch(() => null)"],
    # In generateMetadata: de pagina zelf vraagt daarna hetzelfde zonder catch
    # en gooit door, dus zonder database komt er geen versie in de cache.
    "app/organisatie/[slug]/page.tsx": ["vindOrganisatie(slug).catch(() => null)"],
    "app/sector/[naam]/page.tsx": ["vindSector(veiligGedecodeerd(naam)).catch(() => null)"],
    "app/subsector/[naam]/page.tsx": [
        "vindSubsector(veiligGedecodeerd(naam)).catch(() => null)",
    ],
    "app/accountant/[sleutel]/page.tsx": [
        "accountantOpSlug(veiligGedecodeerd(sleutel), slug).catch(() => null)",
    ],
}
for pagina in ISR_PAGINAS:
    code = plat(WEB / pagina)
    toegestaan = TOEGESTANE_CATCH.get(pagina, [])
    gedekt = sum(code.count(stuk) for stuk in toegestaan)
    check(
        f"{pagina} vangt geen fout stil af buiten TOEGESTANE_CATCH "
        f"({code.count('.catch(')} keer .catch, {gedekt} toegestaan)",
        code.count(".catch(") == gedekt,
    )
    if pagina == "app/page.tsx":
        continue
    metadata = code.split("export async function generateMetadata", 1)[-1]
    metadata = metadata.split("export default", 1)[0]
    pagina_zelf = code.split("export default", 1)[-1]
    for stuk in toegestaan:
        check(
            f"{pagina}: de catch staat in generateMetadata, en de pagina zelf vraagt "
            "hetzelfde zonder catch",
            stuk in metadata and stuk not in pagina_zelf
            and stuk.replace(".catch(() => null)", ";") in pagina_zelf,
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


# --- 3b. grenzen en kerncijfers die niet mogen misleiden ---------------------------
organisaties = plat(WEB / "app" / "sector" / "[naam]" / "organisaties" / "page.tsx")
check(
    "de organisatielijst vraagt voorbij de laatste pagina niets op en geeft dan een 404",
    "gevonden && pagina <= aantalPaginasVan(gevonden.aantal) "
    "? await organisatiesInSectorPagina(" in organisaties
    and "if (!gevonden || rijen.length === 0) notFound();" in organisaties,
)
check(
    "en de titel van zo'n pagina zegt dat ook",
    'if (pagina > aantalPaginasVan(gevonden.aantal)) return { title: "Pagina niet gevonden" };'
    in organisaties,
)
wisselpagina = plat(WEB / "app" / "wisselingen" / "page.tsx")
check(
    "/wisselingen?kantoor= toont het eigen saldo, en geen 'beste' of 'slechtste "
    "saldo' uit rijen die allemaal over dat ene kantoor gaan",
    "const eigen = kantoor ? saldoVanKantoor(rijen, kantoor.id) : null;" in wisselpagina
    and "const saldi = eigen ? [] : saldoPerKantoor(rijen);" in wisselpagina,
)
check(
    "wisselingen() haalt op de oude weg alles op als er op sector wordt gefilterd, "
    "en kort pas na het filter in",
    "opties.limiet && !opSector" in db
    and "return opties.limiet ? volledig.slice(0, opties.limiet) : volledig;" in db,
)


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
check(
    "de linkcontrole faalt op een gerenderde foutmelding, met de klasse die "
    "Foutmelding echt gebruikt",
    'class="foutvlak"' in linkcheck
    and 'className="foutvlak"' in plat(WEB / "components" / "onderdelen.tsx"),
)
foutscherm = re.search(r'const FOUTSCHERM = "([^"]+)";', linkcheck)
check(
    "en op het scherm van app/error.tsx, met een zin die daar echt staat",
    foutscherm is not None and foutscherm.group(1) in plat(WEB / "app" / "error.tsx"),
)
ci = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
check("ci.yml bouwt de site niet zelf: dat doet website.yml, met een padfilter",
      "next build" not in ci and "linkcheck" not in ci)
werkpad = ROOT / ".github" / "workflows" / "website.yml"
werk = werkpad.read_text(encoding="utf-8") if werkpad.exists() else ""
check("website.yml bestaat", bool(werk))
check("die bouwt de site en draait de linkcontrole",
      "npx next build" in werk and "node scripts/linkcheck.mjs" in werk)
check("die kent alleen de publishable key, geen secret",
      "sb_publishable_" in werk and "secrets." not in werk and "SERVICE_ROLE" not in werk.upper()
      and "sb_secret_" not in werk)
triggers = werk.split("\njobs:", 1)[0]
check(
    "website.yml draait bij een pull request en op main, maar alleen als web/ of de "
    "migraties veranderen",
    "pull_request:" in triggers and "push:" in triggers
    and triggers.count('- "web/**"') == 2
    and triggers.count('- "supabase/migrations/**"') == 2
    and triggers.count("paths:") == 2 and "paths-ignore" not in triggers,
)
check("en rekent daar de websitelogica verplicht na",
      "SITE_LOGICA_VERPLICHT" in werk and "python3 pipeline/test_site_snel.py" in werk)


# --- 6. rekenregels, echt uitgevoerd in node ----------------------------------------
VERPLICHT = os.environ.get("SITE_LOGICA_VERPLICHT") == "1"
NODE = shutil.which("node")


def node_leest_typescript() -> bool:
    if not NODE:
        return False
    try:
        uit = subprocess.run([NODE, "-p", "process.features.typescript"],
                             capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.TimeoutExpired):
        return False
    return uit.stdout.strip() in {"strip", "transform"}


# analyse.ts importeert "./paden" zonder extensie, zoals Next dat wil; node zoekt
# dan niet zelf naar paden.ts. Deze haak probeert het nog eens met ".ts".
HAAK = (
    "export async function resolve(s, c, n) { try { return await n(s, c); } "
    'catch (e) { if (s.startsWith(".")) return n(s + ".ts", c); throw e; } }'
)


def in_node(code: str):
    script = (
        'import { register } from "node:module";\n'
        f'register("data:text/javascript," + encodeURIComponent({json.dumps(HAAK)}));\n'
        f"const paden = await import({json.dumps((WEB / 'lib' / 'paden.ts').as_uri())});\n"
        f"const analyse = await import({json.dumps((WEB / 'lib' / 'analyse.ts').as_uri())});\n"
        + code
    )
    uit = subprocess.run([NODE, "--no-warnings", "--input-type=module", "-e", script],
                         capture_output=True, text=True, timeout=60)
    if uit.returncode != 0:
        print(uit.stderr[-2000:])
        return None
    return json.loads(uit.stdout)


if node_leest_typescript():
    # Verzonnen kantoren en organisaties; alleen de vorm telt.
    uitkomst = in_node("""
const p = paden.paginaUitZoek;
const kantoorUit = (pad) => paden.sleutelUitSlug(new URL("http://x" + pad).searchParams.get("kantoor"));
const wissel = (van, naar) => ({ van_kantoor_id: van, naar_kantoor_id: naar });
const regel = (id, boekjaar, sector) => ({ id, boekjaar, organisaties: sector === undefined ? null : { sector } });
console.log(JSON.stringify({
  gewoon: p("3"), leeg: p(undefined), tekst: p("abc"), min: p("-3"), komma: p("2.5"),
  nul: p("0"), lijst: p(["4", "9"]),
  reus: p("99999999999999999999"), heelReus: p("9".repeat(400)),
  offsetReus: String((p("99999999999999999999") - 1) * 100),
  nummers: [[7, 25], [1, 3], [1, 10], [4, 10], [25, 25], [1, 1]].map(([n, a]) => paden.paginaNummers(n, a)),
  saldo: analyse.saldoVanKantoor([wissel(7, 3), wissel(3, 7), wissel(5, 7), wissel(5, 3), wissel(3, 5)], 7),
  saldoNul: analyse.saldoVanKantoor([wissel(3, 5)], 7),
  groepen: analyse.perBoekjaarEnSector([
    regel(1, 2022, "zorg"), regel(2, 2023, "zorg"), regel(3, 2023, "onderwijs"),
    regel(4, 2023, "zorg"), regel(5, 2023), regel(6, 2023, null), regel(7, 2023, "zorg"),
  ]).map((j) => [j.boekjaar, j.aantal, j.sectoren.map(([s, lijst]) => [s, lijst.map((r) => r.id)])]),
  orgPad1: paden.sectorOrganisatiesPad("goede doelen", 1),
  orgPad3: paden.sectorOrganisatiesPad("goede doelen", 3),
  wisselLeeg: paden.wisselingenPad(),
  wisselSector: paden.wisselingenPad({ sector: "goede doelen", jaar: 2023 }),
  terugMetAfm: kantoorUit(paden.wisselingenPad({ kantoor: { id: 12, afm_nummer: "99999999", naam: "Verzonnen & Zn Accountants" } })),
  terugZonderAfm: kantoorUit(paden.wisselingenPad({ kantoor: { id: 12, afm_nummer: null, naam: "Verzonnen & Zn Accountants" } })),
}));
""")
    check("de websitelogica draait in node", uitkomst is not None)
    u = uitkomst or {}
    check("paginaUitZoek: een gewoon nummer blijft staan", u.get("gewoon") == 3 and u.get("lijst") == 4)
    check("paginaUitZoek: leeg, tekst, negatief, een breuk en 0 worden pagina 1",
          [u.get(k) for k in ("leeg", "tekst", "min", "komma", "nul")] == [1, 1, 1, 1, 1])
    check(
        "paginaUitZoek: een reusachtig getal blijft een veilig geheel getal, voorbij "
        "elke laatste pagina (gaf op 5-10-2026 de eerste pagina terug)",
        u.get("reus") == 2**53 - 1 and u.get("heelReus") == 2**53 - 1,
    )
    check("en geeft dus nooit een offset als '1e+22' in de PostgREST-URL",
          isinstance(u.get("offsetReus"), str) and u["offsetReus"].isdigit())
    check(
        "paginaNummers: eerste en laatste altijd, twee rond de huidige, één '…' per gat",
        u.get("nummers") == [
            [1, None, 5, 6, 7, 8, 9, None, 25],
            [1, 2, 3],
            [1, 2, 3, None, 10],
            [1, 2, 3, 4, 5, 6, None, 10],
            [1, None, 23, 24, 25],
            [1],
        ],
    )
    check(
        "saldoVanKantoor telt wat dit kantoor won en verloor, en negeert de rest",
        u.get("saldo") == {"gewonnen": 2, "verloren": 1, "saldo": 1}
        and u.get("saldoNul") == {"gewonnen": 0, "verloren": 0, "saldo": 0},
    )
    check(
        "perBoekjaarEnSector: nieuwste jaar eerst, de grootste sector eerst, geen sector "
        "apart, en binnen een sector de volgorde van de query",
        u.get("groepen") == [
            [2023, 6, [["zorg", [2, 4, 7]], [None, [5, 6]], ["onderwijs", [3]]]],
            [2022, 1, [["zorg", [1]]]],
        ],
    )
    check(
        "sectorOrganisatiesPad: pagina 1 zonder parameter, de rest met",
        u.get("orgPad1") == "/sector/goede-doelen/organisaties"
        and u.get("orgPad3") == "/sector/goede-doelen/organisaties?pagina=3",
    )
    check(
        "wisselingenPad: zonder filters kaal, met sector en jaar als parameters",
        u.get("wisselLeeg") == "/wisselingen"
        and u.get("wisselSector") == "/wisselingen?jaar=2023&sector=goede-doelen",
    )
    check(
        "het kantoor in wisselingenPad komt er op /wisselingen weer zo uit (AFM-nummer "
        "of intern id)",
        u.get("terugMetAfm") == {"nummer": "99999999", "id": None}
        and u.get("terugZonderAfm") == {"nummer": "k12", "id": 12},
    )
else:
    print("  overgeslagen: de rekenregels in node (geen node die zelf TypeScript leest)")
    check("node met TypeScript is er, waar dat verplicht is (SITE_LOGICA_VERPLICHT)",
          not VERPLICHT)


# --- 7. de linkcontrole tegen een nagemaakte site ------------------------------------
class NepSite(http.server.BaseHTTPRequestHandler):
    """Een site met verzonnen pagina's, in de vorm die linkcheck.mjs leest."""

    opgevraagd: list[str] = []
    met_fouten = False

    def do_GET(self) -> None:
        NepSite.opgevraagd.append(self.path)
        links = ""
        inhoud = ""
        if self.path == "/":
            doelen = ["/kantoren", "/zoeken?q=verzonnen", "/zoeken",
                      "/sector/verzonnen/organisaties?pagina=2", "/organisatie/o1-verzonnen"]
            doelen += [f"/kantoor/k{n}-verzonnen-kantoor" for n in range(1, 13)]
            links = "".join(f'<a href="{d}">x</a>' for d in doelen)
        elif NepSite.met_fouten and self.path == "/sector/verzonnen/organisaties?pagina=2":
            inhoud = ('<div class="foutvlak"><strong>De gegevens konden niet worden '
                      'opgehaald.</strong><p class="klein"><code>verzonnen storing</code>'
                      "</p></div>")
        elif NepSite.met_fouten and self.path == "/organisatie/o1-verzonnen":
            inhoud = "<h1>Even niet</h1><p>Deze pagina kon niet worden opgebouwd. Meestal</p>"
        html = (
            "<html><head><title>Verzonnen pagina</title>"
            '<meta name="description" content="Een verzonnen pagina."/></head>'
            f'<body><a href="/">Start</a>{links}{inhoud}</body></html>'
        ).encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(html)))
        self.end_headers()
        self.wfile.write(html)

    def log_message(self, *args) -> None:
        pass


def linkcontrole(met_fouten: bool):
    NepSite.opgevraagd = []
    NepSite.met_fouten = met_fouten
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), NepSite)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    # Zonder proxy: het is een adres op deze machine.
    omgeving = {k: v for k, v in os.environ.items() if "proxy" not in k.lower()}
    try:
        uit = subprocess.run(
            [NODE, str(WEB / "scripts" / "linkcheck.mjs"),
             f"http://127.0.0.1:{server.server_address[1]}"],
            capture_output=True, text=True, timeout=120, env=omgeving,
        )
    finally:
        server.shutdown()
        server.server_close()
    return uit.returncode, uit.stdout + uit.stderr, list(NepSite.opgevraagd)


if NODE:
    code, uitvoer, opgevraagd = linkcontrole(met_fouten=True)
    check("de linkcontrole faalt op een pagina met een foutmelding, ook al is de status 200",
          code == 1 and "/sector/verzonnen/organisaties?pagina=2" in uitvoer
          and "foutmelding op de pagina: verzonnen storing" in uitvoer)
    check("en op het foutscherm van app/error.tsx",
          "/organisatie/o1-verzonnen" in uitvoer and "foutscherm" in uitvoer)
    check("/zoeken wordt nooit opgevraagd, ook niet als er een link naar staat",
          not any(pad.startswith("/zoeken") for pad in opgevraagd))
    kantoren = [pad for pad in opgevraagd if pad.startswith("/kantoor/")]
    check(f"hooguit acht kantoorpagina's (nu {len(kantoren)})", len(kantoren) == 8)
    code, uitvoer, _ = linkcontrole(met_fouten=False)
    check("zonder foutmeldingen slaagt de linkcontrole",
          code == 0 and "Geen kapotte links." in uitvoer)
else:
    print("  overgeslagen: de linkcontrole tegen een nagemaakte site (geen node)")
    check("node is er, waar dat verplicht is (SITE_LOGICA_VERPLICHT)", not VERPLICHT)

print(f"{goed}/{goed + fout} goed")
sys.exit(1 if fout else 0)
