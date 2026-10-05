"""De lus: de goededoelensector in kleine rondes de database in.

Eén grote bulk-run is het slechtste van twee werelden — hij duurt uren, valt om op
één slechte pdf, en je ziet pas aan het eind of de uitkomst klopt. Deze lus doet
hetzelfde werk in **blokken van 50 organisaties**, met de voortgang in de repo
zodat elke ronde te lezen en na te lopen is:

    werkvoorraad/stichtingen.json   welke blokken er zijn en wat ze opleverden
    lus.py draai                    het volgende blok zoeken en in Supabase zetten
    workflow "Stichtingenlus"       doet dat op een vast ritme, ronde na ronde,
                                    elke ronde op een eigen branch met een draft-PR

Draaien vanuit de repo-root:

    python3 pipeline/lus.py plan                # werkvoorraad (her)bouwen
    python3 pipeline/lus.py stand               # wat is klaar, wat staat open
    python3 pipeline/lus.py draai --taken 3     # de volgende drie blokken doen
    python3 pipeline/lus.py draai --droogloop   # zonder database, alleen meten

`plan` mag altijd opnieuw: bestaande uitkomsten blijven staan, alleen blokken die
er nog niet waren komen erbij. Wat de bron zegt (hoeveel organisaties er in een
categorie zitten) wordt dus elke keer opnieuw opgehaald, maar wat wij al gedaan
hebben nooit overschreven.

**Waarom een boekjaar twee keer terugkomt.** Een blok dat klaar is, draait nooit
meer. Dat ging mis bij boekjaar 2025: de lus las het op 30-7-2026, midden in de
publicatietermijn, en kreeg bij D/E en bij C elk 132× "geen verslag". Op 5-10-2026
waren dat er nog 44 en 50 — het CBF had er sindsdien 88 en 82 bij — en de lus
stond stil omdat alle 133 blokken klaar waren. Daarom plant `plan` zelf een
herkansing (HERKANSINGEN): een boekjaar komt op 1 oktober en op 1 januari daarna
opnieuw langs, als nieuwe blokken naast de oude, maar alleen als de laatste ronde
van dat boekjaar vóór dat moment lag. De lader slaat wat al een gelezen opdracht
heeft over vóór de download, dus een herkansing haalt alleen op wat nog open was.
Zo loopt de lus vanzelf mee, ook met boekjaar 2026 in 2027 — zonder dat iemand de
code hoeft aan te passen.

**Waarom deze volgorde.** De werkvoorraad is gesorteerd op wat het meeste oplevert
per verzoek, gemeten in `docs/bronverkenning-stichtingen.md`: eerst categorie D/E
(daar is een controleverklaring een harde norm, trefkans 73–81%), en daarbinnen
boekjaar 2024 en 2023 vóór de rest — want pas als twee opeenvolgende jaargangen
binnen zijn, kan de site een accountantswisseling laten zien. Dat is het punt van
het product, dus dat wil je in ronde twee hebben en niet in ronde twintig.

**Waarom in blokken en niet in één keer.** Niet omdat het lang duurt: het CBF
levert een hele jaargang in twee en een halve minuut. Wel omdat elke ronde iets
oplevert dat een mens kan nalopen vóór de volgende begint — welke kantoren kwamen
langs, welke namen kennen we nog niet, klopt het aantal. Eén run van 133 blokken
geeft aan het eind één grote hoop met dezelfde fout er 133 keer in.

Geen dependencies buiten de standaardbibliotheek.
"""

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import date, datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "adapters"))

import cbf  # noqa: E402

HIER = Path(__file__).resolve().parent
WERKVOORRAAD = HIER / "werkvoorraad" / "stichtingen.json"
CACHE = HIER / ".cache"
LADER = HIER / "laad_stichtingen.py"

BLOKGROOTTE = 50

# Vanaf wanneer een boekjaar in het plan komt: 1 juli van het jaar erna, als
# (maand, dag). De Erkenningsregeling geeft een goed doel zes maanden na afloop van
# het boekjaar voor het jaarverslag; daarvóór staat er bij het CBF vrijwel niets.
INSTROOM = (7, 1)


def boekjaren(vandaag: date) -> tuple[int, ...]:
    """De boekjaren in het plan, in de volgorde waarin ze het product het snelst
    iets laten zien.

    Hier stond een vaste rij, (2024, 2023, 2025, 2022, 2021, 2020, 2019), en die
    regel levert hij op 5-10-2026 precies op. Het volle jaar vóór het jongste
    eerst (2024: 93% van de organisaties heeft er een verslag), het jaar daarvoor
    er direct achter zodat de eerste wisselingen na twee jaargangen zichtbaar
    zijn, dan het jongste jaar (dat vult nog) en de rest achteraan. Ouder dan
    `cbf.OUDSTE_BOEKJAAR` houdt het CBF niet aan.

    Afgeleid van de datum en niet uitgeschreven: anders komt boekjaar 2026 in
    2027 pas in het plan als iemand eraan denkt de code aan te passen.
    """
    jongste = vandaag.year - (1 if (vandaag.month, vandaag.day) >= INSTROOM else 2)
    volgorde = (
        jongste - 1, jongste - 2, jongste,
        *range(jongste - 3, cbf.OUDSTE_BOEKJAAR - 1, -1),
    )
    return tuple(j for j in volgorde if j >= cbf.OUDSTE_BOEKJAAR)


BOEKJAREN = boekjaren(date.today())

# Wanneer een boekjaar opnieuw gelezen wordt: (label, jaren na het boekjaar, maand),
# steeds op de eerste van de maand. Boekjaar 2025 dus op 1-10-2026 (h1) en op
# 1-1-2027 (h2).
#
# Oktober omdat dan het gros er staat. Boekjaar 2025 bij D/E: op 30-7-2026 had het
# CBF van 132 organisaties nog geen verslag, op 5-10-2026 van 44. Van boekjaar 2024
# missen er nu, een jaar later, nog 19: na oktober komt er dus nog een staart
# achteraan, en die is voor januari. Een herkansing draait alleen als de laatste
# ronde van dat boekjaar vóór het moment lag: boekjaar 2024 is pas in juli 2026
# gelezen, ruim na zijn eigen oktober en januari, en dan valt er niets in te
# halen. Gemeten: twintig D/E-verslagen over 2024 zonder gelezen opdracht opnieuw
# gelezen op 5-10-2026, nul opdrachten.
HERKANSINGEN = (("h1", 1, 10), ("h2", 2, 1))

# De populaties waaruit de werkvoorraad wordt opgebouwd, op volgorde van wat ze
# opleveren. Alle aantallen hieronder zijn gemeten op boekjaar 2024, niet geschat
# (`laad_stichtingen.py --droogloop`, 30-7-2026) — zie de bronverkenning.
#
# Overal `soorten: ["controle"]`, en dat is de belangrijkste keuze in dit bestand.
# Categorie C mág van de Erkenningsregeling volstaan met een samenstelling, maar
# een deel van die organisaties laat wél controleren. Die controles meenemen levert
# 20 opdrachten per jaargang op tegen 11 review-gevallen (64%). Ook de
# samenstellingsverklaringen meenemen levert er 7 bij, maar zet er 62 review-rijen
# tegenover — met kandidaat-namen als "Overlopende passiva Accountants", want in een
# klein jaarrekeningetje zonder verklaring vist het patroon posten uit de balans op.
# Dan vult de review-queue zich met werk dat niemand doet, en wat je erin vindt is
# geen jaarrekeningcontrole en telt dus niet mee in de marktaandelen. Wie het toch
# wil, kan het met de lader (`--soorten beoordeling,samenstelling`); de lus plant
# het niet. In categorie A/B geldt hetzelfde, en daar nog sterker.
#
# Samen dekken deze vier populaties alle 826 vermeldingen in het CBF-register: de
# 714 met een actieve erkenning en de 112 ingetrokken. Binnen deze bron valt er dus
# niets meer bij te plannen — een volgende sector is een nieuwe bron (route 3 in de
# bronverkenning: woningcorporaties eerst).
POPULATIES = (
    {
        # 295 organisaties, 194 opdrachten en 47 review in boekjaar 2024 (80%).
        # Dit is de kern van de sector en het bewezen deel van de route.
        "sleutel": "de",
        "naam": "categorie D/E, actieve erkenning",
        "categorieen": ["D", "E"],
        "erkenning": "actief",
        "soorten": ["controle"],
        "terugval": True,
        "prioriteit": 10,
        # De kern komt terug als het jongste boekjaar is aangevuld; zie
        # HERKANSINGEN. Leesproef 5-10-2026: van twintig D/E-verslagen over 2025
        # zonder gelezen opdracht leverden er negen een opdracht op.
        "herkansing": True,
    },
    {
        # 157 organisaties, 20 opdrachten en 11 review in boekjaar 2024 (64%).
        # Minder opbrengst per verzoek dan D/E, maar het zijn echte
        # jaarrekeningcontroles: 19 vrijwillige en 1 wettelijke.
        "sleutel": "c",
        "naam": "categorie C, actieve erkenning",
        "categorieen": ["C"],
        "erkenning": "actief",
        "soorten": ["controle"],
        "terugval": True,
        "prioriteit": 20,
        # Ook C: daar had het CBF op 5-10-2026 110 verslagen over 2025 staan,
        # waarvan er 100 nog niet gelezen waren. De twee populaties daaronder
        # niet: bij een ingetrokken erkenning komen er geen nieuwe jaargangen
        # meer bij (2025: 103× geen verslag), en A/B leverde 2-4 opdrachten per
        # jaargang op.
        "herkansing": True,
    },
    {
        # 110 organisaties die de erkenning kwijt zijn. Van de 14 uit D/E leverde
        # boekjaar 2024 2 opdrachten op en 10× "geen verslag" — logisch, want wie de
        # erkenning verliest verdwijnt ook uit de nieuwe jaargangen. De oudere
        # boekjaren zijn hier het interessante deel, en het is een halve minuut
        # per blok.
        "sleutel": "ingetrokken",
        "naam": "ingetrokken erkenning (alle categorieën)",
        "categorieen": ["A", "B", "C", "D", "E"],
        "erkenning": "ingetrokken",
        "soorten": ["controle"],
        # Juist hier: bij een ingetrokken erkenning is het CBF-bestand er vaak niet
        # meer (10 van de 14 in boekjaar 2024), en dan is de eigen site alles wat
        # er nog is.
        "terugval": True,
        "prioriteit": 30,
    },
    {
        # De staart: 262 organisaties met baten onder €200k. Gemeten op boekjaar
        # 2024 levert dit **2 opdrachten en 5 review-gevallen** op — 201 verslagen
        # hebben geen controleverklaring en 33 zijn gescand. Dat is dus geen
        # jachtterrein maar een nalezing: ergens tussen die kleine stichtingen zit
        # er één die zich vrijwillig laat controleren, en die hoort er net zo goed
        # bij. Het kost 1,4 minuut per jaargang, dus het mag achteraan meelopen.
        #
        # Bewust wél `controle` en niets anders: in A/B is de norm een
        # samenstellingsverklaring of zelfs een kascommissie, en die massaal
        # binnenhalen zou de review-queue vullen met balansposten (zie de opmerking
        # bovenaan en beslissing 9).
        #
        # En bewust **zonder terugval**, terwijl die er bij de andere drie aan staat:
        # 201 van de 262 CBF-bestanden hebben geen controleverklaring, en dat is hier
        # geen halve levering maar het antwoord — zo'n stichting laat niet
        # controleren. De terugval zou dus 250 websites afgaan om te vinden wat er
        # niet is.
        "sleutel": "ab",
        "naam": "categorie A/B, actieve erkenning",
        "categorieen": ["A", "B"],
        "erkenning": "actief",
        "soorten": ["controle"],
        "terugval": False,
        # En om dezelfde reden geen OCR: van vier nagekeken gescande A/B-verslagen had
        # er drie géén verklaring en de vierde een samenstelling zonder kantoor. Bij
        # 33 scans per jaargang is dat een half uur rekenwerk om te bevestigen wat de
        # basiskans al zei. Bij D/E is het net omgekeerd — zie `_lees_pdf`.
        "ocr": False,
        "prioriteit": 40,
    },
)

MAX_POGINGEN = 3

# Wat er bij het herplannen van een bestaand blok bewaard blijft: alles wat een
# gedraaide ronde heeft vastgesteld. De rest van het blok komt uit POPULATIES.
#
# Let op de grens hiervan: een blok dat al `klaar` is, wordt niet opnieuw gedraaid,
# ook niet als je zijn omschrijving verandert. Wil je een afgeronde populatie met
# nieuwe instellingen overdoen, geef hem dan een nieuwe `sleutel` (dan zijn het
# nieuwe blokken). De status terugzetten op `open` werkt alleen op de databranch
# zelf: een werkvoorraad die op main verandert, verliest het bij het samenvoegen
# van die op de databranch (zie stichtingenlus.yml). Een herkansing is om dezelfde
# reden een nieuw blok-id en geen status die terug op open gaat.
UITKOMST_VELDEN = (
    "status", "pogingen", "gedraaid_op", "minuten", "telling", "overgeslagen",
)


# ---------------------------------------------------------------- werkvoorraad


def _nu() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")


def lees() -> dict:
    if not WERKVOORRAAD.exists():
        return {"bron": "cbf", "blokgrootte": BLOKGROOTTE, "taken": []}
    return json.loads(WERKVOORRAAD.read_text(encoding="utf-8"))


def schrijf(voorraad: dict) -> None:
    """Opslaan met vaste opmaak: de git-diff moet te lezen zijn, want die diff
    ís het voortgangslog (zelfde afspraak als bij seed/kantoren.csv)."""
    WERKVOORRAAD.parent.mkdir(parents=True, exist_ok=True)
    WERKVOORRAAD.write_text(
        json.dumps(voorraad, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _sorteersleutel(taak: dict) -> tuple:
    return (
        taak["prioriteit"],
        BOEKJAREN.index(taak["boekjaar"]) if taak["boekjaar"] in BOEKJAREN else 99,
        taak["vanaf"],
    )


def te_doen(voorraad: dict) -> list[dict]:
    """Blokken die nog werk zijn, in de volgorde waarin ze gedaan moeten worden.

    Een mislukt blok komt terug tot MAX_POGINGEN: de bron geeft weleens een
    HTTP-fout, en dat mag geen gat in de dekking achterlaten.
    """
    open_taken = [
        taak
        for taak in voorraad["taken"]
        if taak["status"] == "open"
        or (taak["status"] == "mislukt" and taak.get("pogingen", 0) < MAX_POGINGEN)
    ]
    return sorted(open_taken, key=_sorteersleutel)


def herkansingen(
    sleutel: str, boekjaar: int, bestaand: dict[str, dict], vandaag: date
) -> list[str]:
    """Welke herkansingen van dit boekjaar in het plan horen (hun labels).

    Een herkansing die al in de werkvoorraad staat, blijft in het plan: ook als
    hij half gedraaid is. Anders zou het eerste klare blok de laatste ronde ná
    het moment leggen, en dan vielen de open blokken ernaast uit het plan.

    Een nieuwe komt er alleen als het moment voorbij is én dit boekjaar al eens
    gedraaid heeft, vóór dat moment. Heeft het nog nooit gedraaid, dan doet de
    gewone ronde het werk al; is het al ná het moment gelezen, dan valt er niets
    in te halen dat die ronde niet ook zag.
    """
    voorvoegsel = f"{sleutel}-{boekjaar}-"
    laatst = max(
        (
            taak["gedraaid_op"]
            for taak_id, taak in bestaand.items()
            if taak_id.startswith(voorvoegsel) and taak.get("gedraaid_op")
        ),
        default=None,
    )
    uit = []
    for label, jaren_erna, maand in HERKANSINGEN:
        if any(taak_id.startswith(f"{voorvoegsel}{label}-") for taak_id in bestaand):
            uit.append(label)
            continue
        moment = date(boekjaar + jaren_erna, maand, 1)
        # `gedraaid_op` is "JJJJ-MM-DD UU:MM"; als tekst vergelijken met
        # "JJJJ-MM-DD" klopt, en een ronde op de dag zelf telt als erna.
        if moment <= vandaag and laatst is not None and laatst < moment.isoformat():
            uit.append(label)
    return uit


def plan(blokgrootte: int, vandaag: date | None = None) -> int:
    """Bouwt de werkvoorraad uit het CBF-register; bestaande uitkomsten blijven."""
    vandaag = vandaag or date.today()
    jaren = boekjaren(vandaag)
    voorraad = lees()
    bestaand = {taak["id"]: taak for taak in voorraad["taken"]}
    taken: list[dict] = []

    for populatie in POPULATIES:
        organisaties = cbf.selecteer(populatie["categorieen"], populatie["erkenning"])
        blokken = -(-len(organisaties) // blokgrootte)
        print(
            f"{populatie['naam']}: {len(organisaties)} organisaties "
            f"→ {blokken} blok{'ken' if blokken != 1 else ''} × "
            f"{len(jaren)} boekjaren",
            flush=True,
        )
        if not organisaties:
            continue
        for boekjaar in jaren:
            # De gewone ronde, en daarna wat er aan herkansingen bij hoort. Een
            # herkansing is precies hetzelfde blok onder een eigen id, iets eerder
            # in de rij: het nieuwste boekjaar is waar de bezoeker op wacht.
            rondes = [("", populatie["prioriteit"])]
            if populatie.get("herkansing"):
                for label in herkansingen(populatie["sleutel"], boekjaar, bestaand, vandaag):
                    voorvoegsel = f"{populatie['sleutel']}-{boekjaar}-{label}-"
                    if not any(taak_id.startswith(voorvoegsel) for taak_id in bestaand):
                        print(f"  boekjaar {boekjaar}: herkansing {label} erbij", flush=True)
                    rondes.append((label, populatie["prioriteit"] - 5))
            for label, prioriteit in rondes:
                for nummer, vanaf in enumerate(
                    range(0, len(organisaties), blokgrootte), start=1
                ):
                    taak = _blok(populatie, boekjaar, label, nummer, vanaf,
                                 prioriteit, blokgrootte, len(organisaties))
                    # Bestaat het blok al, dan houden we de **uitkomst** en niet de
                    # omschrijving. De code zegt wat een blok is, de werkvoorraad wat
                    # er met dat blok gebeurd is. Zou je het hele oude blok
                    # overnemen, dan bereikt een wijziging in POPULATIES (een
                    # categorie erbij, terugval aan) de blokken nooit die al gepland
                    # waren — en dan staat er iets in de code dat niet gebeurt.
                    oud = bestaand.get(taak["id"])
                    if oud:
                        taak.update({v: oud[v] for v in UITKOMST_VELDEN if v in oud})
                    taken.append(taak)

    behouden = {taak["id"] for taak in taken}
    verdwenen = [
        taak
        for taak in voorraad["taken"]
        if taak["id"] not in behouden and taak["status"] != "open"
    ]
    if verdwenen:
        # Een blok dat uit het plan valt terwijl het al gedraaid heeft, bewaren we:
        # de uitkomst is een gemeten feit en mag niet uit het log verdwijnen.
        print(f"{len(verdwenen)} gedraaide blokken vallen buiten het plan; behouden")
        taken.extend(verdwenen)

    taken = sorted(taken, key=lambda t: t["id"])
    nieuw = behouden - set(bestaand)
    weggevallen = set(bestaand) - {taak["id"] for taak in taken}
    veranderd = bool(nieuw or weggevallen) or voorraad.get("blokgrootte") != blokgrootte

    voorraad.update(
        {
            "bron": "cbf",
            "blokgrootte": blokgrootte,
            "boekjaren": list(jaren),
            "taken": taken,
        }
    )
    # `gepland_op` alleen bijwerken als het plan écht anders is. Dit commando draait
    # aan het begin van elke ronde — zo bereikt een nieuwe populatie uit POPULATIES
    # de lopende lus — en zonder deze voorwaarde zou dat elke ronde één regel ruis
    # in de diff geven bij een plan dat niet is veranderd.
    if veranderd or not voorraad.get("gepland_op"):
        voorraad["gepland_op"] = _nu()

    schrijf(voorraad)
    open_blokken = len(te_doen(voorraad))
    print(f"\n{len(taken)} blokken in de werkvoorraad ({len(nieuw)} nieuw)")
    if weggevallen:
        print(f"{len(weggevallen)} nog niet gedraaide blokken vallen buiten het plan")
    print(f"Werkvoorraad: {WERKVOORRAAD.relative_to(HIER.parent)}")
    # Voor de workflow: is er niets te doen, dan slaat hij de rest van de ronde
    # over. Zo'n lege ronde deed wél de kantorenlijsten opnieuw, en dat zette elke
    # keer een rij in `bronnen` — vier per dag sinds 5-8-2026, en de site las daar
    # de datum "Stand per …" uit.
    uitvoer = os.environ.get("GITHUB_OUTPUT")
    if uitvoer:
        with open(uitvoer, "a", encoding="utf-8") as bestand:
            bestand.write(f"open_blokken={open_blokken}\n")
    return 0


def _blok(
    populatie: dict,
    boekjaar: int,
    herkansing: str,
    nummer: int,
    vanaf: int,
    prioriteit: int,
    blokgrootte: int,
    totaal: int,
) -> dict:
    """Eén blok zoals de code het beschrijft, nog zonder uitkomst."""
    deel = f"{herkansing}-" if herkansing else ""
    taak = {
        "id": f"{populatie['sleutel']}-{boekjaar}-{deel}{nummer:02d}",
        "prioriteit": prioriteit,
        "populatie": populatie["naam"],
        "boekjaar": boekjaar,
        # Als tekst en niet als lijst: precies wat de lader op de opdrachtregel
        # wil, en het houdt de werkvoorraad leesbaar (een lijst van twee kost in
        # JSON vier regels).
        "categorieen": ",".join(populatie["categorieen"]),
        "erkenning": populatie["erkenning"],
        "soorten": ",".join(populatie["soorten"]),
        "terugval": populatie.get("terugval", False),
        "ocr": populatie.get("ocr", True),
        "vanaf": vanaf,
        "aantal": min(blokgrootte, totaal - vanaf),
        "status": "open",
        "pogingen": 0,
        "gedraaid_op": None,
        "minuten": None,
        "telling": {},
    }
    if herkansing:
        taak["herkansing"] = herkansing
    return taak


# ---------------------------------------------------------------- stand


def _totalen(voorraad: dict) -> dict[str, int]:
    totaal: dict[str, int] = {}
    for taak in voorraad["taken"]:
        for status, aantal in (taak.get("telling") or {}).items():
            totaal[status] = totaal.get(status, 0) + aantal
    return totaal


def stand() -> int:
    voorraad = lees()
    if not voorraad["taken"]:
        print("Werkvoorraad is leeg — draai eerst `python3 pipeline/lus.py plan`.")
        return 1

    per_status: dict[str, int] = {}
    for taak in voorraad["taken"]:
        per_status[taak["status"]] = per_status.get(taak["status"], 0) + 1
    klaar = per_status.get("klaar", 0)
    totaal = len(voorraad["taken"])

    print(f"Werkvoorraad {WERKVOORRAAD.relative_to(HIER.parent)}")
    print(f"  gepland op   {voorraad.get('gepland_op', '?')}")
    print(f"  blokken      {klaar}/{totaal} klaar ({100 * klaar // totaal}%)")
    for status, aantal in sorted(per_status.items()):
        if status != "klaar":
            print(f"  {status:12s} {aantal}")

    print("\nGeoogst tot nu toe:")
    for status, aantal in sorted(_totalen(voorraad).items(), key=lambda p: -p[1]):
        print(f"  {status:14s} {aantal:5d}")

    print("\nPer boekjaar (opdrachten):")
    per_jaar: dict[int, int] = {}
    for taak in voorraad["taken"]:
        per_jaar[taak["boekjaar"]] = per_jaar.get(taak["boekjaar"], 0) + (
            taak.get("telling") or {}
        ).get("opdracht", 0)
    for boekjaar in sorted(per_jaar, reverse=True):
        print(f"  {boekjaar}  {per_jaar[boekjaar]:5d}")

    volgende = te_doen(voorraad)
    print(f"\nNog te doen: {len(volgende)} blokken")
    for taak in volgende[:5]:
        print(
            f"  {taak['id']:24s} {taak['populatie']}, "
            f"organisatie {taak['vanaf'] + 1}–{taak['vanaf'] + taak['aantal']}"
        )
    return 0


# ---------------------------------------------------------------- draaien


def _draai_blok(taak: dict, droogloop: bool, werkers: int) -> dict | None:
    """Eén blok door de lader. Geeft het JSON-rapport terug, of None bij een fout."""
    rapport = CACHE / f"lus_{taak['id']}.json"
    rapport.unlink(missing_ok=True)
    opdracht = [
        sys.executable,
        str(LADER),
        "--boekjaar", str(taak["boekjaar"]),
        "--categorieen", taak["categorieen"],
        "--soorten", taak["soorten"],
        "--erkenning", taak["erkenning"],
        "--vanaf", str(taak["vanaf"]),
        "--aantal", str(taak["aantal"]),
        "--werkers", str(werkers),
        "--rapport-json", str(rapport),
    ]
    if taak.get("terugval"):
        opdracht.append("--terugval")
    # Standaard aan, dus alleen de uitzondering hoeft op de opdrachtregel. Een taak uit
    # een oudere werkvoorraad zonder deze sleutel krijgt daarmee OCR, en dat is de
    # bedoeling: het is winst bij elke populatie behalve A/B.
    if not taak.get("ocr", True):
        opdracht.append("--geen-ocr")
    if droogloop:
        opdracht.append("--droogloop")

    print(f"\n{'=' * 70}\n{taak['id']}: {' '.join(opdracht[2:])}\n{'=' * 70}", flush=True)
    uitkomst = subprocess.run(opdracht, cwd=HIER.parent, check=False)
    if uitkomst.returncode != 0 or not rapport.exists():
        print(f"{taak['id']}: lader gaf code {uitkomst.returncode}", flush=True)
        return None
    return json.loads(rapport.read_text(encoding="utf-8"))


def draai(taken: int, tijdbudget: int, droogloop: bool, werkers: int) -> int:
    voorraad = lees()
    wachtrij = te_doen(voorraad)
    if not wachtrij:
        print("Niets te doen — de werkvoorraad is leeg of af.")
        _schrijf_ronde({"blokken": [], "afgerond": True})
        return 0

    begin = time.time()
    gedaan: list[dict] = []
    per_kantoor: dict[str, int] = {}
    onbekend: dict[str, int] = {}

    for taak in wachtrij[:taken]:
        verstreken = (time.time() - begin) / 60
        if gedaan and verstreken > tijdbudget:
            print(f"\nTijdbudget van {tijdbudget} min op na {verstreken:.0f} min; stop.")
            break

        rapport = _draai_blok(taak, droogloop, werkers)
        uitkomst = {
            "id": taak["id"],
            "boekjaar": taak["boekjaar"],
            "vanaf": taak["vanaf"],
            "aantal": taak["aantal"],
            "status": "mislukt" if rapport is None else "klaar",
            "telling": (rapport or {}).get("telling", {}),
        }
        gedaan.append(uitkomst)
        for naam, aantal in (rapport or {}).get("per_kantoor", {}).items():
            per_kantoor[naam] = per_kantoor.get(naam, 0) + aantal
        for naam, aantal in (rapport or {}).get("onbekende_kantoren", {}).items():
            onbekend[naam] = onbekend.get(naam, 0) + aantal

        # Een droogloop is een meting en geen voortgang: er staat niets in de
        # database, dus het blok moet gewoon open blijven staan. Zou hij op "klaar"
        # gaan, dan slaat de eerstvolgende echte ronde die organisaties over en
        # zit er een gat in de dekking dat niemand meer ziet.
        if droogloop:
            continue

        taak["pogingen"] = taak.get("pogingen", 0) + 1
        taak["gedraaid_op"] = _nu()
        taak["status"] = uitkomst["status"]
        if rapport is not None:
            taak["minuten"] = rapport.get("minuten")
            taak["telling"] = rapport.get("telling", {})
            taak["overgeslagen"] = rapport.get("overgeslagen", 0)

        # Na elk blok opslaan, niet aan het eind: een ronde die halverwege wordt
        # afgekapt (tijdslimiet van de runner) mag geen werk verliezen dat al
        # in de database staat — anders doet de volgende ronde het dubbel.
        schrijf(voorraad)

    if not droogloop:
        schrijf(voorraad)
    ronde = _vat_samen(voorraad, gedaan, per_kantoor, onbekend, droogloop)
    _schrijf_ronde(ronde)
    print("\n" + ronde["tekst"])
    return 0 if all(blok["status"] == "klaar" for blok in gedaan) else 1


def _vat_samen(
    voorraad: dict,
    gedaan: list[dict],
    per_kantoor: dict[str, int],
    onbekend: dict[str, int],
    droogloop: bool,
) -> dict:
    """Het verslag van deze ronde: commitbericht, PR-tekst en machineleesbaar."""
    telling: dict[str, int] = {}
    for taak in gedaan:
        for status, aantal in (taak.get("telling") or {}).items():
            telling[status] = telling.get(status, 0) + aantal
    opdrachten = telling.get("opdracht", 0)
    jaren = sorted({taak["boekjaar"] for taak in gedaan}, reverse=True)
    open_blokken = len(te_doen(voorraad))
    klaar_blokken = sum(1 for t in voorraad["taken"] if t["status"] == "klaar")

    titel = (
        f"Stichtingenlus: {opdrachten} opdrachten uit "
        f"{len(gedaan)} blok{'ken' if len(gedaan) != 1 else ''} "
        f"(boekjaar {', '.join(str(j) for j in jaren)})"
    )
    if droogloop:
        titel = f"[droogloop] {titel}"

    regels = [
        f"| {taak['id']} | {taak['boekjaar']} | "
        f"{taak['vanaf'] + 1}–{taak['vanaf'] + taak['aantal']} | "
        f"{(taak.get('telling') or {}).get('opdracht', 0)} | "
        f"{(taak.get('telling') or {}).get('review', 0)} | "
        f"{taak['status']} |"
        for taak in gedaan
    ]
    tekst = "\n".join(
        [
            titel,
            "",
            "| blok | boekjaar | organisaties | opdracht | review | status |",
            "|---|---|---|---|---|---|",
            *regels,
            "",
            "Totaal deze ronde: "
            + ", ".join(f"{aantal}× {status}" for status, aantal in
                        sorted(telling.items(), key=lambda p: -p[1]))
            + ".",
            "",
            f"Werkvoorraad: {klaar_blokken} van {len(voorraad['taken'])} blokken klaar, "
            f"{open_blokken} te gaan.",
        ]
    )
    if per_kantoor:
        tekst += "\n\nKantoren in deze ronde: " + ", ".join(
            f"{naam} ({aantal})"
            for naam, aantal in sorted(per_kantoor.items(), key=lambda p: -p[1])[:12]
        )
    if onbekend:
        # Dit is de oogst die de kantorenlijst laat groeien; zonder deze regel in
        # de PR blijft de review-queue een tabel waar niemand naar kijkt.
        tekst += (
            "\n\nOnbekende namen uit de review-gevallen (kandidaat voor "
            "`seed/kantoren_overig.csv` of `kantoor_alias.csv`): "
            + ", ".join(
                f"{naam} ({aantal})"
                for naam, aantal in sorted(onbekend.items(), key=lambda p: -p[1])[:12]
            )
        )
    return {
        "titel": titel,
        "tekst": tekst,
        "blokken": [taak["id"] for taak in gedaan],
        "branch": f"data/stichtingen-{gedaan[0]['id']}" if gedaan else "",
        "opdrachten": opdrachten,
        "telling": telling,
        "open_blokken": open_blokken,
        "afgerond": open_blokken == 0,
        "droogloop": droogloop,
    }


def _schrijf_ronde(ronde: dict) -> None:
    """Uitkomst van de ronde waar de workflow bij kan (branchnaam, PR-tekst)."""
    CACHE.mkdir(exist_ok=True)
    (CACHE / "lus_ronde.json").write_text(
        json.dumps(ronde, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    if ronde.get("tekst"):
        (CACHE / "lus_ronde.md").write_text(ronde["tekst"] + "\n", encoding="utf-8")
    samenvatting = os.environ.get("GITHUB_STEP_SUMMARY")
    if samenvatting and ronde.get("tekst"):
        with open(samenvatting, "a", encoding="utf-8") as bestand:
            bestand.write(ronde["tekst"] + "\n")


# ---------------------------------------------------------------- cli


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    onder = parser.add_subparsers(dest="opdracht", required=True)

    plannen = onder.add_parser("plan", help="werkvoorraad (her)bouwen uit het register")
    plannen.add_argument("--blokgrootte", type=int, default=BLOKGROOTTE)

    onder.add_parser("stand", help="voortgang en opbrengst tot nu toe")

    draaien = onder.add_parser("draai", help="de volgende blokken doen")
    # Zes blokken is precies één jaargang categorie D/E (295 organisaties ÷ 50).
    # Een ronde is dus een boekjaar, en dat is de eenheid waarin je erover praat.
    draaien.add_argument("--taken", type=int, default=6, help="hoeveel blokken")
    draaien.add_argument(
        "--tijdbudget", type=int, default=45, help="stop na zoveel minuten"
    )
    draaien.add_argument("--werkers", type=int, default=4)
    draaien.add_argument("--droogloop", action="store_true")

    argumenten = parser.parse_args()
    if argumenten.opdracht == "plan":
        return plan(argumenten.blokgrootte)
    if argumenten.opdracht == "stand":
        return stand()
    return draai(
        argumenten.taken,
        argumenten.tijdbudget,
        argumenten.droogloop,
        argumenten.werkers,
    )


if __name__ == "__main__":
    raise SystemExit(main())
