"""Test: de nieuwe pagina's en blokken laten zien wat er al in de database staat,
zonder iets te beweren wat de data niet draagt.

Waarom dit bestaat. Gemeten op 5-10-2026 stond er meer in de database dan op de
site te vinden was:

- 784 gunningen (TED) waren alleen per organisatie, per kantoor en als acht
  regels "Recent gegund" te zien. /aanbestedingen toont ze per gunningsjaar.
  Een gunning is een benoeming, geen controle; dat zegt de pagina, en een
  telling per kantoor staat er alleen binnen één sector én één gunningsjaar,
  en alleen bij de overheid: van de 123 gunningen onder "overig bedrijfsleven"
  kwamen er 86 van gemeenten, veiligheidsregio's en provincies. Om dezelfde
  reden ook bij de overheid niet in een jaar waarin zo'n gunning elders staat:
  in 2025 stonden er 19 buiten de overheid, en met die erbij draaide de
  nummer één om. Dat gold op 5-10-2026 voor elk jaar behalve 2017.
- 3.439 van de 17.653 organisaties (19,5%) hebben een plaats, in 846
  schrijfwijzen ("AMSTERDAM" naast "Amsterdam"). /plaats/<naam> neemt die
  samen, alleen voor plaatsen met minstens drie organisaties, en zegt bovenaan
  dat de lijst niet volledig is. Geen aandeel en geen plek: een plaats is geen
  sector. organisatiesInGemeente zocht met eq en miste zo de varianten.
- De kantoorpagina had geen ontwikkeling in de tijd, terwijl de rijen van
  v_marktaandeel er al waren. "Per sector en boekjaar" zet een aandeel alleen
  bij een compleet boekjaar met minstens twintig controles in de sector
  (completeBoekjaren). De eerste versie toetste elk jaar alleen tegen het jaar
  ervóór, de regel van nieuwsteCompleteBoekjaar. Dat vangt een nieuwste jaar
  dat nog binnenloopt, maar niet de opbouwjaren waarin een sector half in de
  database stond: PwC kreeg zo 50,5% van de OOB in 2014 (190 van 376), tegen
  24,0% in 2015 bij 721 controles. Nu loopt de toets vanaf het nieuwste
  complete jaar terug, tegen het eerstvolgende complete jaar erna.
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
    "een telling per kantoor alleen in de sector overheid, vanaf LEIDER_MINIMUM, "
    "en niet in een jaar waarin een gemeente e.d. buiten de overheid staat",
    'const SECTOR_MET_TELLING = "overheid"' in aanbesteding
    and "sector === SECTOR_MET_TELLING && aantal >= LEIDER_MINIMUM && verkeerdIngedeeld === 0"
    in aanbesteding,
)
check(
    "verkeerdIngedeeld staat vóór de keuze voor een telling per kantoor",
    aanbesteding.find("const verkeerdIngedeeld")
    < aanbesteding.find("const metKantoorlijst")
    and aanbesteding.find("const verkeerdIngedeeld") >= 0,
)
check(
    "de pagina zegt waarom er geen telling per kantoor staat als de indeling scheef is",
    "Geen telling per kantoor voor ${gekozen}" in aanbesteding
    and "dat kan de volgorde bovenaan omdraaien" in aanbesteding,
)
check(
    "de telling per kantoor zegt zelf dat ze alleen de overheid volgens het register telt",
    "Het telt alleen opdrachtgevers die het register onder de overheid indeelt" in aanbesteding,
)
doorklik = aanbesteding.split("<Doorklik", 1)[-1]
check(
    "de doorklik deelt geen top drie uit de telling per kantoor uit",
    "metKantoorlijst" not in doorklik and "gunningen in de sector" not in doorklik,
)
check(
    "de gunningen zonder datum heten geen 'oudere TED-berichten' (het waren er "
    "vier uit 2024)",
    "oudere TED-berichten" not in aanbesteding and "TED noemde er geen" in aanbesteding,
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
complete_boekjaren = voorpagina.split("export function completeBoekjaren(", 1)[-1].split(
    "export function", 1
)[0]
check(
    "completeBoekjaren() begint bij nieuwsteCompleteBoekjaar en kopieert de "
    "vooruit-toets niet",
    "export function completeBoekjaren(" in voorpagina
    and "const nieuwste = nieuwsteCompleteBoekjaar(perJaar, minimum, compleet);"
    in complete_boekjaren
    and voorpagina.count("aantal >= compleet * vorig") == 1,
)
check(
    "completeBoekjaren() toetst elk eerder jaar tegen het eerstvolgende complete "
    "jaar erna, en schuift dat ijkpunt alleen mee met een jaar dat compleet bleek",
    "let ijkpunt = perJaar.get(nieuwste) ?? 0;" in complete_boekjaren
    and ".filter((jaar) => jaar < nieuwste).sort((a, b) => b - a)" in complete_boekjaren
    and "if (aantal >= minimum && aantal >= compleet * ijkpunt) { uit.add(jaar); ijkpunt = aantal; }"
    in complete_boekjaren,
)
check(
    "er is geen toets meer die een historisch jaar alleen tegen het jaar ervóór legt",
    "jaarCompleet" not in voorpagina,
)
check(
    "sectorreeksen() haalt 'compleet' uit completeBoekjaren",
    "export function sectorreeksen(" in voorpagina
    and "const complete = completeBoekjaren(totalen, minimum, compleet);" in voorpagina
    and "compleet: complete.has(boekjaar)," in voorpagina,
)
check(
    "een compleet jaar vóór de eerste eigen controle in een sector krijgt een 0, "
    "maar pas vanaf de eerste controle van het kantoor in welke sector dan ook",
    ".filter((jaar) => jaar >= eerste || (jaar >= eersteOoit && complete.has(jaar)))"
    in voorpagina,
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
check(
    "de voetnoot beschrijft de toets naar achteren, niet alleen 'het jaar ervoor'",
    "van het eerstvolgende complete boekjaar erna" in kantoor
    and "van het aantal controles van het jaar ervoor" not in kantoor,
)


# De regel van completeBoekjaren, nagerekend op de sectortotalen die op
# 5-10-2026 in v_marktaandeel stonden. Een rekenvoorbeeld naast de tekstcontroles
# hierboven, die de TypeScript gelijk houden met deze vorm: zo staat er ook wát
# de regel doet, en dat de opbouwjaren van de OOB en de overheid eruit vallen.
def complete_jaren(per_jaar: dict[int, int], minimum: int = 20, compleet: float = 0.8) -> set[int]:
    nieuwste = next(
        (
            jaar
            for jaar in sorted(per_jaar, reverse=True)
            if per_jaar[jaar] >= minimum
            and (
                not per_jaar.get(jaar - 1)
                or per_jaar[jaar] >= compleet * per_jaar[jaar - 1]
            )
        ),
        None,
    )
    if nieuwste is None:
        return set()
    uit = {nieuwste}
    ijkpunt = per_jaar[nieuwste]
    for jaar in sorted((j for j in per_jaar if j < nieuwste), reverse=True):
        if per_jaar[jaar] >= minimum and per_jaar[jaar] >= compleet * ijkpunt:
            uit.add(jaar)
            ijkpunt = per_jaar[jaar]
    return uit


OOB = {2009: 29, 2010: 151, 2011: 138, 2012: 184, 2013: 243, 2014: 376, 2015: 721,
       2016: 691, 2017: 708, 2018: 610, 2019: 663, 2020: 651, 2021: 636, 2022: 640,
       2023: 614, 2024: 576, 2025: 110}
OVERHEID = {2010: 61, 2011: 75, 2012: 116, 2013: 176, 2014: 174, 2015: 157, 2016: 191,
            2017: 240, 2018: 272, 2019: 306, 2020: 325, 2021: 301, 2022: 315, 2023: 297,
            2024: 307, 2025: 207}
CORPORATIES = {2007: 399, 2008: 398, 2009: 399, 2010: 400, 2011: 391, 2012: 383,
               2013: 375, 2014: 360, 2015: 346, 2016: 333, 2017: 318, 2018: 308,
               2019: 294, 2020: 287, 2021: 280, 2022: 276, 2023: 275, 2024: 271}
ZORG = {2010: 1, 2012: 2, 2013: 2, 2015: 1, 2016: 1, 2017: 4, 2018: 1, 2019: 836,
        2020: 837, 2021: 841, 2022: 824, 2023: 718, 2024: 816, 2025: 776}
check(
    "OOB: compleet van 2015 tot en met 2024; de opbouwjaren 2009–2014 en het "
    "binnenlopende 2025 niet",
    complete_jaren(OOB) == set(range(2015, 2025)),
)
check(
    "overheid: compleet van 2017 tot en met 2024 (2016: 191 tegen 80% van 240)",
    complete_jaren(OVERHEID) == set(range(2017, 2025)),
)
check(
    "woningcorporaties: elk jaar 2007–2024 compleet, ook al daalt het aantal",
    complete_jaren(CORPORATIES) == set(range(2007, 2025)),
)
check(
    "zorg: 2019–2025 compleet, ook 2023 (718 tegen 816), de losse vroege "
    "controles niet",
    complete_jaren(ZORG) == set(range(2019, 2026)),
)
check(
    "een jaar dat niet compleet is, verlaagt het ijkpunt niet voor de jaren ervóór",
    complete_jaren({2018: 60, 2019: 70, 2020: 100}) == {2020},
)
check(
    "na zo'n jaar telt een eerder jaar dat het eerstvolgende complete jaar wél "
    "haalt gewoon weer mee",
    complete_jaren({2018: 100, 2019: 50, 2020: 70, 2021: 100}) == {2018, 2021},
)
check(
    "onder de twintig controles is geen jaar compleet",
    complete_jaren({2022: 19, 2023: 19, 2024: 20}) == {2024},
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
