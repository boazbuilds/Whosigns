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
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "adapters"))

import cbf  # noqa: E402

HIER = Path(__file__).resolve().parent
WERKVOORRAAD = HIER / "werkvoorraad" / "stichtingen.json"
CACHE = HIER / ".cache"
LADER = HIER / "laad_stichtingen.py"

BLOKGROOTTE = 50

# Boekjaren in de volgorde waarin ze het product het snelst iets laten zien.
# 2024 is de volste jaargang (93% van de organisaties heeft er een verslag), 2023
# staat er direct achter zodat de eerste wisselingen na twee jaargangen zichtbaar
# zijn. 2025 is nog aan het vullen (deponeringstermijn) en 2019–2021 hebben een
# lagere dekking, dus die komen achteraan. Ouder dan 2019 houdt het CBF niet aan.
BOEKJAREN = (2024, 2023, 2025, 2022, 2021, 2020, 2019)

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
# nieuwe blokken) of zet de status van die blokken terug op `open`.
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


def plan(blokgrootte: int) -> int:
    """Bouwt de werkvoorraad uit het CBF-register; bestaande uitkomsten blijven."""
    voorraad = lees()
    bestaand = {taak["id"]: taak for taak in voorraad["taken"]}
    taken: list[dict] = []

    for populatie in POPULATIES:
        organisaties = cbf.selecteer(populatie["categorieen"], populatie["erkenning"])
        blokken = -(-len(organisaties) // blokgrootte)
        print(
            f"{populatie['naam']}: {len(organisaties)} organisaties "
            f"→ {blokken} blok{'ken' if blokken != 1 else ''} × "
            f"{len(BOEKJAREN)} boekjaren",
            flush=True,
        )
        if not organisaties:
            continue
        for boekjaar in BOEKJAREN:
            for nummer, vanaf in enumerate(
                range(0, len(organisaties), blokgrootte), start=1
            ):
                taak_id = f"{populatie['sleutel']}-{boekjaar}-{nummer:02d}"
                taak = {
                    "id": taak_id,
                    "prioriteit": populatie["prioriteit"],
                    "populatie": populatie["naam"],
                    "boekjaar": boekjaar,
                    # Als tekst en niet als lijst: precies wat de lader op de
                    # opdrachtregel wil, en het houdt de werkvoorraad leesbaar
                    # (een lijst van twee kost in JSON vier regels).
                    "categorieen": ",".join(populatie["categorieen"]),
                    "erkenning": populatie["erkenning"],
                    "soorten": ",".join(populatie["soorten"]),
                    "terugval": populatie.get("terugval", False),
                    "ocr": populatie.get("ocr", True),
                    "vanaf": vanaf,
                    "aantal": min(blokgrootte, len(organisaties) - vanaf),
                    "status": "open",
                    "pogingen": 0,
                    "gedraaid_op": None,
                    "minuten": None,
                    "telling": {},
                }
                # Bestaat het blok al, dan houden we de **uitkomst** en niet de
                # omschrijving. De code zegt wat een blok is, de werkvoorraad wat er
                # met dat blok gebeurd is. Zou je het hele oude blok overnemen, dan
                # bereikt een wijziging in POPULATIES (een categorie erbij, terugval
                # aan) de blokken nooit die al gepland waren — en dan staat er iets
                # in de code dat niet gebeurt.
                oud = bestaand.get(taak_id)
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
            "boekjaren": list(BOEKJAREN),
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
    print(f"\n{len(taken)} blokken in de werkvoorraad ({len(nieuw)} nieuw)")
    if weggevallen:
        print(f"{len(weggevallen)} nog niet gedraaide blokken vallen buiten het plan")
    print(f"Werkvoorraad: {WERKVOORRAAD.relative_to(HIER.parent)}")
    return 0


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
            f"| blok | boekjaar | organisaties | opdracht | review | status |",
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
