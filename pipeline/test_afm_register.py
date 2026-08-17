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
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "adapters"))

from afm_register import (  # noqa: E402
    OOB_AFWIJKINGEN,
    OOB_VERWACHT,
    onverwachte_oob,
    verdwenen_oob,
)

SEED = Path(__file__).resolve().parent / "seed" / "kantoren.csv"

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

print(f"{goed}/{goed + fout} goed")
sys.exit(1 if fout else 0)
