"""De boekhouding van de stichtingenlus — zonder CBF, lader of database.

Draaien vanuit de repo-root (geen testframework nodig, geen netwerk):

    python3 pipeline/test_lus.py

Waarom dit bestand bestaat: werkvoorraad/stichtingen.json is het voortgangslog
van de lus, en `plan` herschrijft het aan het begin van elke ronde. Gaat daar
iets mis, dan verdwijnt een gemeten uitkomst of draait een blok dat al klaar
was nog eens — en niets in de database laat dat zien. Hier ligt vast wat `plan`
bewaart, welke blokken `te_doen` teruggeeft en dat een droogloop geen voortgang
is. Organisaties zijn verzonnen; de lader wordt niet aangeroepen.

Sinds 5-10-2026 ook de herkansing: een boekjaar dat te vroeg gelezen werd, komt
op 1 oktober en 1 januari terug als nieuwe blokken. "Vandaag" wordt meegegeven,
zodat deze tests in 2027 hetzelfde zeggen als nu.
"""

import json
import os
import sys
import tempfile
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import lus  # noqa: E402

goed = 0
fout = 0


def check(omschrijving: str, voorwaarde: bool) -> None:
    global goed, fout
    if voorwaarde:
        goed += 1
    else:
        fout += 1
        print(f"  FOUT: {omschrijving}")


os.environ.pop("GITHUB_STEP_SUMMARY", None)
os.environ.pop("GITHUB_OUTPUT", None)
tijdelijk = tempfile.TemporaryDirectory()
basis = Path(tijdelijk.name)
lus.HIER = basis / "pipeline"
lus.WERKVOORRAAD = lus.HIER / "werkvoorraad" / "stichtingen.json"
lus.CACHE = lus.HIER / ".cache"

# Per populatie zoveel verzonnen organisaties: D/E twee blokken, C één, de rest leeg.
AANTALLEN = {("D,E", "actief"): 70, ("C", "actief"): 10}


def nep_selecteer(categorieen, erkenning):
    aantal = AANTALLEN.get((",".join(categorieen), erkenning), 0)
    return [{"naam": f"Stichting Verzonnen {i}"} for i in range(aantal)]


lus.cbf.selecteer = nep_selecteer

VANDAAG = date(2026, 10, 5)
JAREN = lus.boekjaren(VANDAAG)

# ---------- boekjaren uit de kalender ----------
check("op 5-10-2026 precies de rij die er vroeger vast stond",
      JAREN == (2024, 2023, 2025, 2022, 2021, 2020, 2019))
check("boekjaar 2026 nog niet vóór 1 juli 2027",
      2026 not in lus.boekjaren(date(2027, 6, 30)))
check("vanaf 1 juli 2027 wél, en 2025 vooraan",
      lus.boekjaren(date(2027, 7, 1))[:3] == (2025, 2024, 2026)
      and lus.boekjaren(date(2027, 7, 1))[-1] == 2019)

# ---------- plan: eerste keer ----------
lus.plan(50, VANDAAG)
voorraad = lus.lees()
ids = {t["id"] for t in voorraad["taken"]}
check("D/E: twee blokken per boekjaar", {f"de-{j}-01" for j in JAREN}
      | {f"de-{j}-02" for j in JAREN} <= ids)
check("C: één blok per boekjaar", {f"c-{j}-01" for j in JAREN} <= ids)
check("lege populaties leveren geen blokken", len(ids) == 3 * len(JAREN))
check("zonder gedraaide ronde geen herkansing", not any("-h" in i for i in ids))
check("het tweede blok begint waar het eerste ophoudt",
      next(t for t in voorraad["taken"] if t["id"] == "de-2024-02")["vanaf"] == 50
      and next(t for t in voorraad["taken"] if t["id"] == "de-2024-02")["aantal"] == 20)

# ---------- plan: uitkomsten blijven, omschrijving volgt de code ----------
for taak in voorraad["taken"]:
    if taak["id"] == "de-2024-01":
        taak.update(status="klaar", pogingen=1, gedraaid_op="2026-10-01 05:07",
                    minuten=3.5, telling={"opdracht": 31, "review": 4}, overgeslagen=2,
                    terugval=False, populatie="oude omschrijving")
voorraad["gepland_op"] = "2026-01-01 00:00"
lus.schrijf(voorraad)

lus.plan(50, VANDAAG)
voorraad = lus.lees()
blok = next(t for t in voorraad["taken"] if t["id"] == "de-2024-01")
check("plan bewaart de uitkomst van een gedraaid blok",
      blok["status"] == "klaar" and blok["telling"] == {"opdracht": 31, "review": 4}
      and blok["pogingen"] == 1 and blok["overgeslagen"] == 2)
check("plan neemt de omschrijving uit POPULATIES, niet uit het oude blok",
      blok["terugval"] is True and blok["populatie"] == lus.POPULATIES[0]["naam"])
check("plan zonder verandering laat gepland_op staan",
      voorraad["gepland_op"] == "2026-01-01 00:00")

# ---------- plan: wat uit het plan valt ----------
AANTALLEN[("C", "actief")] = 0
for taak in voorraad["taken"]:
    if taak["id"] == "c-2023-01":
        taak.update(status="klaar", telling={"opdracht": 5})
lus.schrijf(voorraad)
lus.plan(50, VANDAAG)
voorraad = lus.lees()
ids = {t["id"] for t in voorraad["taken"]}
check("een gedraaid blok dat uit het plan valt blijft in het log", "c-2023-01" in ids)
check("een open blok dat uit het plan valt verdwijnt", "c-2024-01" not in ids)
check("een plan dat wél verandert krijgt een nieuwe datum",
      voorraad["gepland_op"] != "2026-01-01 00:00")

# ---------- te_doen ----------
taken = [
    {"id": "a", "prioriteit": 20, "boekjaar": 2024, "vanaf": 0, "status": "open"},
    {"id": "b", "prioriteit": 10, "boekjaar": 2023, "vanaf": 50, "status": "open"},
    {"id": "c", "prioriteit": 10, "boekjaar": 2023, "vanaf": 0, "status": "open"},
    {"id": "d", "prioriteit": 10, "boekjaar": 2024, "vanaf": 0, "status": "klaar"},
    {"id": "e", "prioriteit": 10, "boekjaar": 2024, "vanaf": 50, "status": "mislukt",
     "pogingen": lus.MAX_POGINGEN - 1},
    {"id": "f", "prioriteit": 10, "boekjaar": 2024, "vanaf": 100, "status": "mislukt",
     "pogingen": lus.MAX_POGINGEN},
]
volgorde = [t["id"] for t in lus.te_doen({"taken": taken})]
check("een blok dat klaar is komt niet terug", "d" not in volgorde)
check("een mislukt blok komt terug zolang er pogingen over zijn", "e" in volgorde)
check("na MAX_POGINGEN niet meer", "f" not in volgorde)
check("volgorde: prioriteit, dan boekjaar zoals BOEKJAREN, dan vanaf",
      volgorde == ["e", "c", "b", "a"])

# ---------- herkansing ----------
# Zoals het echt ging: alles gelezen eind juli 2026, boekjaar 2025 dus te vroeg.
AANTALLEN.update({("D,E", "actief"): 70, ("C", "actief"): 10, ("A,B", "actief"): 10,
                  ("A,B,C,D,E", "ingetrokken"): 10})
lus.WERKVOORRAAD.unlink()
lus.plan(50, VANDAAG)
voorraad = lus.lees()
for taak in voorraad["taken"]:
    taak.update(status="klaar", pogingen=1, gedraaid_op="2026-07-30 18:45",
                telling={"geen_verslag": 40, "opdracht": 5})
lus.schrijf(voorraad)
voor = {t["id"]: dict(t) for t in voorraad["taken"]}

lus.plan(50, date(2026, 9, 30))
check("vóór 1 oktober geen herkansing", len(lus.lees()["taken"]) == len(voor)
      and not lus.te_doen(lus.lees()))

lus.plan(50, VANDAAG)
voorraad = lus.lees()
per_id = {t["id"]: t for t in voorraad["taken"]}
nieuw = sorted(set(per_id) - set(voor))
check("op 5-10-2026 komt boekjaar 2025 terug, voor D/E en C",
      nieuw == ["c-2025-h1-01", "de-2025-h1-01", "de-2025-h1-02"])
check("niet voor ingetrokken en A/B", not any(i.startswith(("ab-", "ingetrokken-"))
                                              for i in nieuw))
check("boekjaar 2024, voor het eerst gelezen ná zijn eigen herkansingsmomenten, "
      "komt niet terug", not any(i.startswith(("de-2024-h", "c-2024-h")) for i in per_id))
check("een herkansing is hetzelfde blok onder een eigen id",
      per_id["de-2025-h1-02"]["vanaf"] == 50 and per_id["de-2025-h1-02"]["aantal"] == 20
      and per_id["de-2025-h1-02"]["herkansing"] == "h1"
      and per_id["de-2025-h1-02"]["status"] == "open")
check("de klare blokken blijven klaar, met hun telling",
      all(per_id[i]["status"] == "klaar" and per_id[i]["telling"] == voor[i]["telling"]
          for i in voor))
check("herkansing eerst, D/E vóór C",
      [t["id"] for t in lus.te_doen(voorraad)]
      == ["de-2025-h1-01", "de-2025-h1-02", "c-2025-h1-01"])

# Half gedraaid: het eerste blok is klaar, ná het moment. De rest moet blijven.
per_id["de-2025-h1-01"].update(status="klaar", gedraaid_op="2026-10-06 05:07")
lus.schrijf(voorraad)
lus.plan(50, date(2026, 10, 7))
per_id = {t["id"]: t for t in lus.lees()["taken"]}
check("een half gedraaide herkansing houdt zijn open blokken",
      per_id.get("de-2025-h1-02", {}).get("status") == "open"
      and per_id["de-2025-h1-01"]["status"] == "klaar")

# Alles van h1 gedraaid in oktober; in januari volgt de staart.
voorraad = lus.lees()
for taak in voorraad["taken"]:
    if "-h1-" in taak["id"]:
        taak.update(status="klaar", gedraaid_op="2026-10-06 11:07")
lus.schrijf(voorraad)
lus.plan(50, date(2026, 12, 31))
check("na een gedraaide h1 niets meer tot januari", not lus.te_doen(lus.lees()))
lus.plan(50, date(2027, 1, 1))
per_id = {t["id"]: t for t in lus.lees()["taken"]}
check("op 1-1-2027 de tweede herkansing van 2025",
      {"de-2025-h2-01", "de-2025-h2-02", "c-2025-h2-01"} <= set(per_id)
      and [t["id"] for t in lus.te_doen(lus.lees())][0] == "de-2025-h2-01")
check("en de eerste blijft in het log", per_id["de-2025-h1-01"]["status"] == "klaar")

# Boekjaar 2026: eerst de gewone ronde in juli 2027, de herkansing pas in oktober.
voorraad = lus.lees()
for taak in voorraad["taken"]:
    taak.update(status="klaar", gedraaid_op=taak.get("gedraaid_op") or "2027-01-01 05:07")
lus.schrijf(voorraad)
lus.plan(50, date(2027, 7, 1))
open_ids = [t["id"] for t in lus.te_doen(lus.lees())]
check("in juli 2027 komt boekjaar 2026 vanzelf in het plan, zonder herkansing",
      "de-2026-01" in open_ids and not any("2026-h" in i for i in open_ids))
voorraad = lus.lees()
for taak in voorraad["taken"]:
    if taak["status"] == "open":
        taak.update(status="klaar", gedraaid_op="2027-07-01 05:07")
lus.schrijf(voorraad)
lus.plan(50, date(2027, 10, 1))
open_ids = [t["id"] for t in lus.te_doen(lus.lees())]
check("en op 1-10-2027 de herkansing van 2026",
      open_ids == ["de-2026-h1-01", "de-2026-h1-02", "c-2026-h1-01"])

# De workflow slaat een ronde zonder open blokken over; dat getal komt van plan.
uitvoer = basis / "github_output.txt"
os.environ["GITHUB_OUTPUT"] = str(uitvoer)
lus.plan(50, date(2027, 10, 1))
check("plan meldt het aantal open blokken aan de workflow",
      uitvoer.read_text(encoding="utf-8").strip().splitlines()[-1] == "open_blokken=3")
os.environ.pop("GITHUB_OUTPUT")

# ---------- draai: een droogloop is geen voortgang ----------
lus.schrijf({"bron": "cbf", "blokgrootte": 50, "taken": [
    {"id": "de-2024-01", "prioriteit": 10, "boekjaar": 2024, "vanaf": 0, "aantal": 50,
     "status": "open", "pogingen": 0, "telling": {}},
    {"id": "de-2024-02", "prioriteit": 10, "boekjaar": 2024, "vanaf": 50, "aantal": 20,
     "status": "open", "pogingen": 0, "telling": {}},
]})
rapporten = {
    "de-2024-01": {"telling": {"opdracht": 12}, "minuten": 1.0, "per_kantoor": {}},
    "de-2024-02": None,
}
lus._draai_blok = lambda taak, droogloop, werkers: rapporten[taak["id"]]

code = lus.draai(taken=2, tijdbudget=45, droogloop=True, werkers=1)
na = {t["id"]: t for t in lus.lees()["taken"]}
check("droogloop: blokken blijven open en houden hun pogingen",
      all(t["status"] == "open" and t["pogingen"] == 0 for t in na.values()))

code = lus.draai(taken=2, tijdbudget=45, droogloop=False, werkers=1)
na = {t["id"]: t for t in lus.lees()["taken"]}
check("echte ronde: een gelukt blok is klaar, met zijn telling",
      na["de-2024-01"]["status"] == "klaar" and na["de-2024-01"]["telling"] == {"opdracht": 12})
check("echte ronde: een mislukt blok telt een poging", na["de-2024-02"]["status"] == "mislukt"
      and na["de-2024-02"]["pogingen"] == 1)
check("een ronde met een mislukt blok eindigt niet met 0", code == 1)
ronde = json.loads((lus.CACHE / "lus_ronde.json").read_text(encoding="utf-8"))
check("het rondeverslag noemt de opdrachten", ronde["opdrachten"] == 12)

# ---------- de workflow: een lege ronde stopt na het plannen ----------
# Van 5-8 tot 5-10-2026 deed elke lege ronde toch de kantorenlijsten, en dat zette
# vier keer per dag een rij in `bronnen`. Een overgeslagen stap heeft lege outputs,
# en '' != '0' is in een workflow-expressie waar: de stappen ná de ronde moeten
# dus ook op leeg letten, anders pushen ze en verversen ze de site voor niets.
WORKFLOW = Path(__file__).resolve().parent.parent / ".github" / "workflows" / "stichtingenlus.yml"
stappen = {}
for stuk in WORKFLOW.read_text(encoding="utf-8").split("\n      - ")[1:]:
    kop = stuk.split("\n", 1)[0]
    if kop.startswith("name: "):
        stappen[kop.removeprefix("name: ").strip()] = stuk
ALLEEN_MET_WERK = "steps.plan.outputs.open_blokken != '0'"
for naam in ("poppler-utils installeren", "Kantorenlijsten bijwerken", "Ronde draaien"):
    check(f"'{naam}' alleen als er open blokken zijn", ALLEEN_MET_WERK in stappen.get(naam, ""))
check("het plan geeft het aantal open blokken door",
      "id: plan" in stappen.get("Werkvoorraad bijwerken", ""))
for naam, uitvoer in (("Voortgang vastleggen en pushen", "blokken"),
                      ("Website verversen", "blokken"),
                      ("Ronde geslaagd?", "code")):
    check(f"'{naam}' telt een overgeslagen ronde niet als werk",
          f"steps.ronde.outputs.{uitvoer} != ''" in stappen.get(naam, ""))
check("de melding raadt niet meer aan de cron uit te zetten",
      "Zet de cron uit" not in stappen.get("Klaar?", "x"))

tijdelijk.cleanup()
print(f"{goed}/{goed + fout} goed")
sys.exit(1 if fout else 0)
