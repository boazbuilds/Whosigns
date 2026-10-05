"""De boekhouding van de stichtingenlus — zonder CBF, lader of database.

Draaien vanuit de repo-root (geen testframework nodig, geen netwerk):

    python3 pipeline/test_lus.py

Waarom dit bestand bestaat: werkvoorraad/stichtingen.json is het voortgangslog
van de lus, en `plan` herschrijft het aan het begin van elke ronde. Gaat daar
iets mis, dan verdwijnt een gemeten uitkomst of draait een blok dat al klaar
was nog eens — en niets in de database laat dat zien. Hier ligt vast wat `plan`
bewaart, welke blokken `te_doen` teruggeeft en dat een droogloop geen voortgang
is. Organisaties zijn verzonnen; de lader wordt niet aangeroepen.
"""

import json
import os
import sys
import tempfile
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

# ---------- plan: eerste keer ----------
lus.plan(50)
voorraad = lus.lees()
ids = {t["id"] for t in voorraad["taken"]}
check("D/E: twee blokken per boekjaar", {f"de-{j}-01" for j in lus.BOEKJAREN}
      | {f"de-{j}-02" for j in lus.BOEKJAREN} <= ids)
check("C: één blok per boekjaar", {f"c-{j}-01" for j in lus.BOEKJAREN} <= ids)
check("lege populaties leveren geen blokken", len(ids) == 3 * len(lus.BOEKJAREN))
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

lus.plan(50)
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
lus.plan(50)
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

tijdelijk.cleanup()
print(f"{goed}/{goed + fout} goed")
sys.exit(1 if fout else 0)
