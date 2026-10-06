"""Wat de kantorenlader in de database aan- en uitzet.

Draaien vanuit de repo-root (geen testframework nodig, geen netwerk):

    python3 pipeline/test_laad_kantoren.py

Waarom dit bestand bestaat: tot 5-10-2026 kon laad_kantoren.py alleen toevoegen.
Een kantoor dat uit het AFM-register verdween bleef in de database actief, mét
zijn vlaggen — zo stond de AFM zelf vijf weken nadat ze uit haar eigen export was
verdwenen nog als zevende OOB-kantoor op de site. Nu zet de lader uit wat het
register niet meer kent, en dat is precies het soort stap dat bij een kapotte
seed in één keer de halve markt uitzet. Hier ligt vast wanneer hij dat doet en
wanneer vooral niet. Alle kantoren zijn verzonnen; de database is nep.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent / "adapters"))
sys.path.insert(0, str(Path(__file__).resolve().parent / "extractie"))

import laad_kantoren as lader  # noqa: E402

goed = 0
fout = 0


def check(omschrijving: str, voorwaarde: bool) -> None:
    global goed, fout
    if voorwaarde:
        goed += 1
    else:
        fout += 1
        print(f"  FOUT: {omschrijving}")


class NepDatabase:
    """Doet wat laad_kantoren van Supabase vraagt, en onthoudt het."""

    def __init__(self, rijen: list[dict]):
        self.rijen = rijen
        self.upserts: list[tuple[str, list[dict]]] = []
        self.bijgewerkt: list[tuple[str, str, dict]] = []
        self.bronnen = 0

    def selecteer_alles(self, tabel: str, query: str) -> list[dict]:
        assert tabel == "kantoren", tabel
        return [dict(rij) for rij in self.rijen]

    def invoegen(self, tabel: str, rij: dict) -> dict:
        self.bronnen += 1
        return {"id": 1, **rij}

    def upsert(self, tabel: str, rijen: list[dict], conflict: str) -> int:
        self.upserts.append((tabel, rijen))
        return len(rijen)

    def bijwerken(self, tabel: str, filter: str, velden: dict) -> None:
        self.bijgewerkt.append((tabel, filter, velden))


def afm(nummer: str, naam: str, oob: str = "nee") -> dict:
    return {
        "afm_nummer": nummer, "naam": naam, "rechtsvorm": "Besloten Vennootschap",
        "plaats": "Ergens", "oob_vergunning": oob, "vergunning_sinds": "2008-09-29",
        "website": "", "status": "Verleend", "sleutel": nummer, "wta_vergunning": True,
    }


def db_rij(id_: int, nummer: str, naam: str, actief: bool = True, oob: bool = False) -> dict:
    return {
        "id": id_, "afm_nummer": nummer, "naam": naam, "actief": actief,
        "oob_vergunning": oob, "wta_vergunning": actief,
    }


# Een register van 220 verzonnen kantoren, net boven de ondergrens van 200.
REGISTER = [afm(str(91000000 + i), f"Vulkantoor {i} Audit B.V.") for i in range(220)]
VERVALLEN = [{
    "afm_nummer": "90000002", "naam": "Maatschap Duinroos Accountants",
    "rechtsvorm": "Maatschap", "plaats": "Ergens", "vergunning_sinds": "2008-09-29",
    "website": "", "afwezig_sinds": "2026-09-28", "toelichting": "niet meer in de export",
    "sleutel": "90000002", "wta_vergunning": False, "wta_ooit": True,
}]
ALIASSEN = [{"alias": "Duinroos en Vennoten", "afm_nummer": "90000002"}]


def draai(register: list[dict], db: NepDatabase) -> int:
    lader.laad_kantoren = lambda: [dict(k) for k in register]
    lader.laad_vervallen_kantoren = lambda: [dict(k) for k in VERVALLEN]
    lader.laad_overige_kantoren = lambda: []
    lader.laad_aliassen = lambda: list(ALIASSEN)

    def nooit_online():
        raise AssertionError("offline hoort het register niet op te halen")

    lader.afm_register.haal_register_op = nooit_online
    return lader.main(offline=True, db=db)


def upserts_naar(db: NepDatabase, tabel: str) -> list[dict]:
    return [rij for t, rijen in db.upserts if t == tabel for rij in rijen]


# ---------- de gewone week: één nummer weg, één vervallen ----------
db = NepDatabase(
    [db_rij(i + 1, k["afm_nummer"], k["naam"]) for i, k in enumerate(REGISTER)]
    + [
        db_rij(500, "90000002", "Maatschap Duinroos Accountants"),
        db_rij(501, "90000009", "Stichting Toezicht Op Iedereen", oob=True),
        db_rij(502, "90000010", "Al Lang Weg B.V.", actief=False),
    ]
)
code = draai(REGISTER, db)
check("een gewone run eindigt met 0", code == 0)

kantoorrijen = {rij["sleutel"]: rij for rij in upserts_naar(db, "kantoren")}
verv = kantoorrijen.get("90000002", {})
check("vervallen kantoor: zelfde sleutel als de bestaande rij (het AFM-nummer)",
      verv.get("afm_nummer") == "90000002")
check("vervallen kantoor: inactief, geen OOB, geen Wta-vergunning meer",
      verv.get("actief") is False and verv.get("oob_vergunning") is False
      and verv.get("wta_vergunning") is False)
check("vervallen kantoor: de toelichting zegt sinds wanneer, en waarom",
      "28-9-2026" in (verv.get("toelichting") or "")
      and "niet meer in de export" in (verv.get("toelichting") or ""))
check("registerkantoren blijven actief met vergunning",
      all(kantoorrijen[k["afm_nummer"]]["actief"] and kantoorrijen[k["afm_nummer"]]["wta_vergunning"]
          for k in REGISTER))

check("precies één bijwerking: het nummer dat in geen enkele lijst staat",
      len(db.bijgewerkt) == 1 and db.bijgewerkt[0][1] == "id=in.(501)")
check("en die zet actief, OOB en Wta uit",
      db.bijgewerkt and db.bijgewerkt[0][2]
      == {"actief": False, "oob_vergunning": False, "wta_vergunning": False})

alias = upserts_naar(db, "kantoor_alias")
check("een alias naar een vervallen nummer vindt de bestaande rij",
      alias == [{"alias": "Duinroos en Vennoten", "kantoor_id": 500}])
check("offline haalt het register niet op en registreert wel één bron", db.bronnen == 1)

# ---------- tweede keer: niets meer uit te zetten ----------
db2 = NepDatabase(
    [db_rij(i + 1, k["afm_nummer"], k["naam"]) for i, k in enumerate(REGISTER)]
    + [db_rij(501, "90000009", "Stichting Toezicht Op Iedereen", actief=False)]
)
draai(REGISTER, db2)
check("een rij die al uit staat wordt niet elke run opnieuw bijgewerkt", not db2.bijgewerkt)

# ---------- de ondergrens: een afgekapte seed zet niets uit ----------
db3 = NepDatabase(
    [db_rij(i + 1, k["afm_nummer"], k["naam"]) for i, k in enumerate(REGISTER)]
)
code = draai(REGISTER[:150], db3)
check("afgekapte seed: niets op inactief gezet", not db3.bijgewerkt)
check("afgekapte seed: de run wordt rood", code == 1)
check("afgekapte seed: wat er wél staat wordt nog gewoon bijgewerkt",
      len([r for r in upserts_naar(db3, "kantoren") if r["wta_vergunning"]]) == 150)

db4 = NepDatabase(
    [db_rij(i + 1, k["afm_nummer"], k["naam"]) for i, k in enumerate(REGISTER)]
)
code = draai(REGISTER[:199] + REGISTER[200:], db4)
check("één kantoor minder is geen afgekapte seed", code == 0 and len(db4.bijgewerkt) == 1)

# ---------- de zuivere stukjes ----------
check(
    "te_deactiveren: alleen AFM-rijen die het register niet kent en nog iets aan hebben",
    [r["id"] for r in lader.te_deactiveren(
        [
            db_rij(1, "1", "a"),
            db_rij(2, "2", "b"),
            db_rij(3, "3", "c", actief=False),
            {"id": 4, "afm_nummer": None, "naam": "zonder nummer", "actief": True},
        ],
        {"1"},
    )] == [2],
)

# ---------- en verderop in de pijplijn ----------
#
# Een verdwenen kantoor heeft wta_vergunning False. Zonder wta_ooit erbij werd een
# wettelijke controle die het destijds bevoegd tekende ineens vrijwillig.
import stichtingen  # noqa: E402

resultaat = {"soort": "controle", "wta_kenmerk": True, "kantoor": VERVALLEN[0]}
check("stichtingen: wettelijke controle bij een vervallen kantoor blijft wettelijk",
      stichtingen._opdrachttype(resultaat) == "wettelijke_controle")
resultaat = {"soort": "controle", "wta_kenmerk": True,
             "kantoor": {"wta_vergunning": False, "wta_ooit": False}}
check("stichtingen: zonder vergunning, nu of toen, blijft het vrijwillig",
      stichtingen._opdrachttype(resultaat) == "vrijwillige_controle")

print(f"{goed}/{goed + fout} goed")
sys.exit(1 if fout else 0)
