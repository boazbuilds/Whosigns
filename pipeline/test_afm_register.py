"""Test: een OOB-vergunning erbij of eraf mag nooit ongemerkt binnenkomen.

De wekelijkse snapshot van het AFM-register draait vanzelf en commit vanzelf.
Dat is precies de bedoeling — de git-historie is het mutatielog — maar het
betekent ook dat een verandering in de bron zonder tussenkomst op de site komt.

Voor de meeste velden is dat goed. Voor de OOB-vlag niet. Die zegt wie er bij
organisaties van openbaar belang mag tekenen, het zijn er jarenlang precies zes,
en op 15-8-2026 stond de AFM er zelf ineens als zevende in — de toezichthouder
die de vergunning verléént, met een vergunning. Twee dagen later stond ze op de
site tussen de Big Four. De pipeline deed niets fout: de officiële XML-export
zegt het echt. Er was alleen niets dat het opmerkte.

Deze test is dat "iets". Hij kijkt naar de seed-CSV zoals die in de repo staat,
niet naar het net: hij hoort ook te draaien als het register onbereikbaar is.
"""

import csv
import sys
import tempfile
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "adapters"))

from afm_register import (  # noqa: E402
    GEEN_ACCOUNTANTSORGANISATIE,
    OOB_AFWIJKINGEN,
    OOB_VERWACHT,
    ExportOnvolledig,
    alias_rijen,
    export_lijkt_compleet,
    onverwachte_oob,
    vergelijk,
    verdwenen_oob,
    ververs_seed,
    vervallen_rijen,
)

SEED = Path(__file__).resolve().parent / "seed" / "kantoren.csv"
VERVALLEN = Path(__file__).resolve().parent / "seed" / "kantoren_vervallen.csv"

goed = 0
fout = 0


def check(omschrijving: str, voorwaarde: bool) -> None:
    global goed, fout
    if voorwaarde:
        goed += 1
    else:
        fout += 1
        print(f"  FOUT: {omschrijving}")


with SEED.open(encoding="utf-8") as f:
    kantoren = list(csv.DictReader(f))

check("de seed-CSV is niet leeg", len(kantoren) > 200)

oob = [k for k in kantoren if k["oob_vergunning"] == "ja"]
onbekend = onverwachte_oob(kantoren)
check(
    "geen onbekend kantoor met een OOB-vergunning; staat er wel een, kijk hem na "
    "en zet hem in OOB_VERWACHT of OOB_AFWIJKINGEN: "
    + ", ".join(f"{k['afm_nummer']} {k['naam']}" for k in onbekend),
    not onbekend,
)

weg = verdwenen_oob(kantoren)
check(
    "geen kantoor uit OOB_VERWACHT is uit het register verdwenen: " + ", ".join(weg),
    not weg,
)

check(
    "de zes bekende OOB-kantoren staan er allemaal in",
    {k["afm_nummer"] for k in oob} >= set(OOB_VERWACHT),
)

# De namen moeten ook kloppen: een vergunningnummer dat van eigenaar wisselt is
# iets anders dan hetzelfde kantoor onder een nieuwe naam, en dat wil je zien.
per_nummer = {k["afm_nummer"]: k["naam"] for k in kantoren}
for nummer, naam in OOB_VERWACHT.items():
    check(
        f"{nummer} heet nog steeds {naam} (nu: {per_nummer.get(nummer, 'afwezig')})",
        per_nummer.get(nummer) == naam,
    )

# Een afwijking is een handtekening, geen manier om de test stil te krijgen.
for nummer, notitie in OOB_AFWIJKINGEN.items():
    check(
        f"de afwijking voor {nummer} heeft een toelichting die uitlegt wat er nagekeken is",
        len(notitie) > 80,
    )
check(
    "een afwijking staat niet óók in OOB_VERWACHT",
    not (set(OOB_AFWIJKINGEN) & set(OOB_VERWACHT)),
)

# Wat de test bewaakt moet ook echt in de data zitten, anders bewaakt hij niets.
check(
    "elk nummer in OOB_VERWACHT komt voor in de seed-CSV",
    set(OOB_VERWACHT) <= set(per_nummer),
)

# ---------- geen kantoor, en vervallen kantoren ----------
#
# De AFM stond van 15-8 tot 31-8-2026 zelf in haar register. Komt ze terug, dan
# moet dat opvallen; staat ze ergens in de matchlijsten, dan kan een verklaring
# haar als accountant krijgen.
for nummer, notitie in GEEN_ACCOUNTANTSORGANISATIE.items():
    check(f"{nummer} uit GEEN_ACCOUNTANTSORGANISATIE heeft een toelichting", len(notitie) > 80)
    check(f"{nummer} uit GEEN_ACCOUNTANTSORGANISATIE staat niet (meer) in de seed",
          nummer not in per_nummer)

with VERVALLEN.open(encoding="utf-8") as f:
    vervallen = list(csv.DictReader(f))
for rij in vervallen:
    check(f"vervallen {rij['afm_nummer']} staat niet ook nog in het register",
          rij["afm_nummer"] not in per_nummer)
    check(f"vervallen {rij['afm_nummer']} is geen GEEN_ACCOUNTANTSORGANISATIE",
          rij["afm_nummer"] not in GEEN_ACCOUNTANTSORGANISATIE)
    check(f"vervallen {rij['afm_nummer']} heeft een datum en een toelichting",
          bool(rij["afwezig_sinds"]) and len(rij["toelichting"]) > 20)

# ---------- de ondergrens ----------
check("233 na 233 is geloofwaardig", export_lijkt_compleet(233, 233))
check("twee vermeldingen eraf is geloofwaardig", export_lijkt_compleet(231, 233))
check("een tiende eraf is het niet", not export_lijkt_compleet(209, 233))
check("onder de 200 nooit, ook zonder vorige snapshot", not export_lijkt_compleet(150, 0))

# ---------- mutaties tussen twee snapshots (verzonnen kantoren) ----------


def kantoor(nummer: str, naam: str, oob: str = "nee") -> dict:
    return {
        "afm_nummer": nummer, "naam": naam, "rechtsvorm": "Besloten Vennootschap",
        "plaats": "Ergens", "oob_vergunning": oob, "vergunning_sinds": "2008-09-29",
        "website": "", "status": "Verleend",
    }


# Opvulling tot boven de ondergrens; de mutaties zitten in de eerste vijf.
vulsel = [kantoor(str(91000000 + i), f"Vulkantoor {i} Audit B.V.") for i in range(220)]
oud = [
    kantoor("90000001", "Zandloper Accountants + Adviseurs B.V."),
    kantoor("90000002", "Maatschap Duinroos Accountants"),
    kantoor("90000003", "Klaproos Audit B.V."),
    kantoor("90000009", "Stichting Toezicht Op Iedereen", oob="ja"),
] + vulsel
nieuw = [
    kantoor("90000001", "Zandloper Audit B.V."),
    kantoor("90000003", "Klaproos Audit B.V."),
    kantoor("90000004", "Duinroos Accountants B.V."),
] + vulsel

mutaties = vergelijk(oud, nieuw)
check("hernoemd: zelfde nummer, andere naam",
      [(o["afm_nummer"], n["naam"]) for o, n in mutaties["hernoemd"]]
      == [("90000001", "Zandloper Audit B.V.")])
check("verdwenen: de nummers die er niet meer zijn",
      [k["afm_nummer"] for k in mutaties["verdwenen"]] == ["90000002", "90000009"])
check("erbij: een nieuw nummer, nooit gekoppeld aan het verdwenen nummer",
      [k["afm_nummer"] for k in mutaties["erbij"]] == ["90000004"])

dag = date(2026, 10, 5)
rijen = vervallen_rijen(mutaties["verdwenen"], dag)
check("vervallen rij draagt het eigen nummer en de datum van de snapshot",
      rijen[0]["afm_nummer"] == "90000002" and rijen[0]["afwezig_sinds"] == "2026-10-05")
check("een nummer uit GEEN_ACCOUNTANTSORGANISATIE wordt nooit een vervallen kantoor",
      vervallen_rijen([kantoor(n, "x") for n in GEEN_ACCOUNTANTSORGANISATIE], dag) == [])

# Een alias die al naar een ánder kantoor wijst, gaat er niet in.
anders = {"zandloper accountants adviseurs": {"afm_nummer": "90000077", "naam": "Ander B.V."}}
rijen, gemeld = alias_rijen(mutaties["hernoemd"], anders, dag)
check("botsende oude naam: alleen de volle naam als alias, de korte gemeld",
      [r["alias"] for r in rijen] == ["Zandloper Accountants + Adviseurs B.V."]
      and len(gemeld) == 1 and "Ander B.V." in gemeld[0])

# Het geheel, op tijdelijke bestanden.
with tempfile.TemporaryDirectory() as map_:
    map_ = Path(map_)
    seed, alias, verv = map_ / "kantoren.csv", map_ / "alias.csv", map_ / "vervallen.csv"
    alias.write_text("alias,afm_nummer,toelichting\n", encoding="utf-8")
    with seed.open("w", newline="", encoding="utf-8") as f:
        schrijver = csv.DictWriter(f, fieldnames=list(oud[0]))
        schrijver.writeheader()
        schrijver.writerows(oud)
    voor = seed.read_bytes()

    try:
        ververs_seed(nieuw[:150], dag, seed, alias, verv, overige=[])
        geweigerd = False
    except ExportOnvolledig:
        geweigerd = True
    check("een afgekapte export wordt geweigerd", geweigerd)
    check("... en laat de seed staan zoals hij was", seed.read_bytes() == voor)
    check("... en schrijft geen vervallen-bestand", not verv.exists())

    uitkomst = ververs_seed(nieuw, dag, seed, alias, verv, overige=[])
    with alias.open(encoding="utf-8") as f:
        aliassen = list(csv.DictReader(f))
    check("de oude registernaam staat als alias bij hetzelfde nummer, voluit en kort",
          [(a["alias"], a["afm_nummer"]) for a in aliassen]
          == [("Zandloper Accountants + Adviseurs B.V.", "90000001"),
              ("zandloper accountants adviseurs", "90000001")])
    with verv.open(encoding="utf-8") as f:
        weg = list(csv.DictReader(f))
    check("de verdwenen maatschap staat in het vervallen-bestand",
          [k["afm_nummer"] for k in weg] == ["90000002", "90000009"])
    check("de mutaties komen terug voor de meldingen",
          len(uitkomst["aliassen"]) == 2 and not uitkomst["gemeld"])

    # Een week later: de maatschap staat er weer. Dan is ze niet meer vervallen.
    ververs_seed(nieuw + [kantoor("90000002", "Maatschap Duinroos Accountants")],
                 date(2026, 10, 12), seed, alias, verv, overige=[])
    with verv.open(encoding="utf-8") as f:
        weg = list(csv.DictReader(f))
    check("een nummer dat terugkomt verdwijnt uit het vervallen-bestand",
          [k["afm_nummer"] for k in weg] == ["90000009"])
    with alias.open(encoding="utf-8") as f:
        check("en een snapshot zonder hernoeming voegt geen aliassen toe",
              len(list(csv.DictReader(f))) == 2)

print(f"{goed}/{goed + fout} goed")
sys.exit(1 if fout else 0)
