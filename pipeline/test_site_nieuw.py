"""Test: de nieuwe pagina's en blokken laten zien wat er al in de database staat,
zonder iets te beweren wat de data niet draagt.

Waarom dit bestaat. Gemeten op 5-10-2026 stond er meer in de database dan op de
site te vinden was:

- 784 gunningen (TED) waren alleen per organisatie, per kantoor en als acht
  regels "Recent gegund" te zien. /aanbestedingen toont ze per gunningsjaar.
  Een gunning is een benoeming, geen controle; dat zegt de pagina, en een
  telling per kantoor staat er alleen binnen één sector én één gunningsjaar,
  en alleen bij de overheid: van de 123 gunningen onder "overig bedrijfsleven"
  kwamen er 86 van gemeenten, veiligheidsregio's en provincies.
- 3.439 van de 17.653 organisaties (19,5%) hebben een plaats, in 846
  schrijfwijzen ("AMSTERDAM" naast "Amsterdam"). /plaats/<naam> neemt die
  samen, alleen voor plaatsen met minstens drie organisaties, en zegt bovenaan
  dat de lijst niet volledig is. Geen aandeel en geen plek: een plaats is geen
  sector. organisatiesInGemeente zocht met eq en miste zo de varianten.
- De kantoorpagina had geen ontwikkeling in de tijd, terwijl de rijen van
  v_marktaandeel er al waren. "Per sector en boekjaar" zet een aandeel alleen
  bij een compleet boekjaar met minstens twintig controles in de sector — met
  dezelfde regel als nieuwsteCompleteBoekjaar, niet een kopie.
- De sectorpagina zei "Nog geen opdrachten in deze sector" bij de handel, met
  4.095 opdrachten uit het marktonderzoek. Die staan nu als telling van
  organisaties per boekjaar in een apart blok "Volgens marktonderzoek", zonder
  verdeling per kantoor: het onderzoek dekt 22 kantoren en twee van de vier
  grootste niet, dus zo'n verdeling zou de aanlevering laten zien en niet de
  markt.

Tekstcontroles op de paginabron, net als test_site_aandeel.py; commentaar telt
niet mee. De migratie wordt als SQL gelezen, ook zonder commentaar.
"""

import re
import sys
from pathlib import Path

WORTEL = Path(__file__).resolve().parent.parent
WEB = WORTEL / "web"

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
SQLCOMMENTAAR = re.compile(r"(?m)--.*$")


def plat(pad: Path) -> str:
    tekst = pad.read_text(encoding="utf-8")
    tekst = BLOKCOMMENTAAR.sub(" ", tekst)
    tekst = REGELCOMMENTAAR.sub(" ", tekst)
    return " ".join(tekst.split())


def pagina(*delen: str) -> str:
    return plat(WEB.joinpath(*delen))


# Wat geen enkele nieuwe pagina mag: een aandeel of plek over sectoren heen.
GEEN_RANGLIJST = ("<Aandeelbalk", "<Podiumplek", "<Rang ", "% van de markt")

# --- /aanbestedingen ------------------------------------------------------------
aanbesteding = pagina("app", "aanbestedingen", "page.tsx")
check(
    "/aanbestedingen haalt alle gunningen op met alleGunningen()",
    "alleGunningen()" in aanbesteding,
)
check(
    "/aanbestedingen herhaalt dat een gunning een benoeming is en geen controle",
    "Een gunning zegt wie er benoemd is en wanneer — niet of de controle er kwam" in aanbesteding,
)
check(
    "/aanbestedingen noemt het gunningsjaar, niet een boekjaar",
    "gunningsjaar" in aanbesteding and "niet een boekjaar" in aanbesteding,
)
check(
    "/aanbestedingen zet geen aandeel, podium of rangnummer",
    not any(teken in aanbesteding for teken in GEEN_RANGLIJST),
)
check(
    "een telling per kantoor alleen in de sector overheid en vanaf LEIDER_MINIMUM",
    'const SECTOR_MET_TELLING = "overheid"' in aanbesteding
    and "sector === SECTOR_MET_TELLING && aantal >= LEIDER_MINIMUM" in aanbesteding,
)
check(
    "de telling per kantoor gebeurt binnen het gekozen jaar én die ene sector",
    "getoond.filter((g) => sectorVan(g) === sector && g.kantoren)" in aanbesteding,
)
check(
    "het lopende jaar is niet de standaard en heet 'loopt nog'",
    "jaren.find((j) => j < ditJaar)" in aanbesteding and "loopt nog" in aanbesteding,
)
check(
    "de sectorindeling van de opdrachtgever krijgt een waarschuwing als die "
    "aantoonbaar niet klopt",
    "verkeerdIngedeeld > 0" in aanbesteding,
)
check(
    "de grafiek op /aanbestedingen heeft een tabel eronder",
    "<Kolomgrafiek" in aanbesteding and 'samenvatting="Als tabel"' in aanbesteding,
)

db = pagina("lib", "db.ts")
check(
    "alleGunningen sorteert uniek (via gunningen(), op datum en id)",
    "export function alleGunningen()" in db and "order=gunningsdatum.desc,id.desc" in db,
)

# Ingangen naar /aanbestedingen
dashboard = pagina("components", "dashboard.tsx")
recent = dashboard.split("export function RecentGegund", 1)[-1]
check("RecentGegund op de voorpagina linkt naar /aanbestedingen", 'href="/aanbestedingen"' in recent)
layout = pagina("app", "layout.tsx")
check(
    "menu én colofon linken naar /aanbestedingen",
    layout.count('href="/aanbestedingen"') >= 2,
)
kantoor = pagina("app", "kantoor", "[slug]", "page.tsx")
check(
    "de kantoorpagina linkt bij de gewonnen aanbestedingen naar /aanbestedingen",
    'href="/aanbestedingen"' in kantoor,
)

# --- /plaats/<naam> ---------------------------------------------------------------
plaats = pagina("app", "plaats", "[naam]", "page.tsx")
paden = pagina("lib", "paden.ts")
check("plaatsPad() bestaat en bouwt /plaats/<slug>", "export function plaatsPad(" in paden and "`/plaats/${slug(plaats)}`" in paden)
check(
    "schrijfwijzen gaan samen op slug(), en op niets anders",
    "export function plaatsgroepen(" in paden and "const sleutel = slug(plaats);" in paden,
)
check("de drempel voor een plaatspagina staat op één plek", "export const PLAATS_MINIMUM = 3;" in paden)
check(
    "de plaatspagina geeft onder de drempel een 404",
    "plaats.aantal >= PLAATS_MINIMUM ? plaats : null" in plaats and "notFound()" in plaats,
)
check(
    "de plaatspagina zegt bovenaan dat ze niet volledig is, met de vulgraad "
    "gemeten op het moment van tonen",
    "Niet volledig." in plaats and 'tel("organisaties")' in plaats and "metPlaats" in plaats,
)
check(
    "de plaatspagina toont geen aandeel of plek, en geen telling per kantoor",
    not any(teken in plaats for teken in GEEN_RANGLIJST + ("<Telbalk",))
    and "geen aandelen of plekken" in plaats,
)
check(
    "de laatste controle telt alleen wettelijke en vrijwillige controles",
    "CONTROLE_TYPES.includes(opdracht.type_opdracht)" in plaats,
)
check(
    "organisatiesInPlaats zet elke schrijfwijze tussen aanhalingstekens in in.()",
    "export function organisatiesInPlaats(" in db and "gemeente=in.(${encodeURIComponent(lijst)})" in db,
)
check(
    "organisatiesInGemeente zoekt zonder hoofdletters en zonder jokertekens",
    "gemeente=ilike.${encodeURIComponent(letterlijk)}" in db
    and "gemeente=eq.${encodeURIComponent(gemeente)}" not in db,
)
organisatie = pagina("app", "organisatie", "[slug]", "page.tsx")
check(
    "de plaats op de organisatiepagina is een link, maar alleen als de "
    "plaatspagina bestaat",
    "<Link href={plaatsPad(org.gemeente)}>" in organisatie
    and "anderePlaatsgenoten.length + 1 >= PLAATS_MINIMUM" in organisatie,
)

# --- kantoorpagina: per sector en boekjaar -------------------------------------
voorpagina = pagina("lib", "voorpagina.ts")
check(
    "sectorreeksen() gebruikt jaarCompleet, en nieuwsteCompleteBoekjaar ook — "
    "één regel, geen kopie",
    "export function sectorreeksen(" in voorpagina
    and "compleet: jaarCompleet(totalen, boekjaar, minimum, compleet)" in voorpagina
    and ".find((jaar) => jaarCompleet(perJaar, jaar, minimum, compleet))" in voorpagina
    and voorpagina.count("aantal >= compleet * vorig") == 1,
)
check(
    "de kantoorpagina rekent de reeks uit de al opgehaalde rijen, zonder extra verzoek",
    "sectorreeksen(marktRijen, kantoor.id)" in kantoor,
)
check(
    "een aandeel per sector en boekjaar staat er alleen bij een compleet jaar",
    "cel.compleet ? procent((100 * cel.aantal) / cel.controles)" in kantoor
    and "reeks.jaren.filter((j) => j.compleet)" in kantoor,
)
check(
    "de grafiekjes hergebruiken Kolomgrafiek, met de tabel achter 'Als tabel'",
    "<Kolomgrafiek" in kantoor and "Als tabel, alle sectoren en boekjaren" in kantoor,
)
check(
    "de kantoorpagina zegt dat een aandeel tussen sectoren niets zegt",
    "Tussen sectoren zegt het niets" in kantoor,
)

# --- sectorpagina: marktonderzoek apart ----------------------------------------
sector = pagina("app", "sector", "[naam]", "page.tsx")
check(
    "de sectorpagina zegt niet meer 'Nog geen opdrachten' bij een sector met "
    "marktonderzoek",
    "Nog geen opdrachten in deze sector" not in sector
    and "Nog geen gelezen wettelijke of vrijwillige controles in deze sector" in sector,
)
blok = sector.split("function Marktonderzoek", 1)[-1].split("export default", 1)[0]
check(
    "het marktonderzoek staat in een eigen blok met het label marktonderzoek "
    "en 'zelf aangeleverd'",
    "<h2>Volgens marktonderzoek</h2>" in blok
    and 'bron_type: "marktonderzoek", betrouwbaarheid: "zelf_aangeleverd"' in blok
    and "(zelf aangeleverd)" in blok,
)
check(
    "het blok toont geen kantoor en zet geen aandeel, podium of balk",
    not any(
        teken in blok
        for teken in GEEN_RANGLIJST
        + ("<Telbalk", "procent(", "kantoor_id", "KantoorLink", "kantoorPad", "<Wapen")
    ),
)
check(
    "het blok legt uit dat het voorwerp van de opdracht onbekend is",
    "niet waarover de opdracht ging" in blok,
)
mo = db.split("export function marktonderzoekPerSector", 1)[-1]
check(
    "marktonderzoekPerSector vraagt geen kantoor op, en wacht netjes op de view",
    "kantoor" not in mo.split("order=boekjaar.desc", 1)[0].lower()
    and 'zolangNieuw<MarktonderzoekJaar>( "v_marktonderzoek_per_sector"' in mo,
)

migratie = WORTEL / "supabase" / "migrations" / "20261006140000_marktonderzoek_per_sector.sql"
check("de migratie voor v_marktonderzoek_per_sector bestaat", migratie.exists())
if migratie.exists():
    sql = " ".join(SQLCOMMENTAAR.sub(" ", migratie.read_text(encoding="utf-8")).split()).lower()
    uitvoer = sql.split("select ond.boekjaar", 1)[-1].split("from onderzoek", 1)[0]
    check(
        "de view geeft boekjaar, sector en aantallen, en geen kantoor",
        "ond.sector" in uitvoer and "aantal_organisaties" in uitvoer and "kantoor" not in uitvoer,
    )
    check(
        "de view telt alleen marktonderzoek met voorwerp onbekend",
        "b.bron_type = 'marktonderzoek'" in sql and "o.type_opdracht = 'controle_onbepaald'" in sql,
    )
    check(
        "de view leest met de rechten van wie hem opvraagt (RLS blijft gelden)",
        "with (security_invoker = on)" in sql,
    )

print(f"{goed}/{goed + fout} goed")
sys.exit(1 if fout else 0)
