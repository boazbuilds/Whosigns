"""Test: de geoogste csv's in de repo horen bij de kolommen die de code schrijft.

Waarom dit bestaat. Op 20-8-2026 is nagespeeld wat er gebeurt als
`RAPPORT_KOLOMMEN` een kolom erbij krijgt terwijl de vijf bestanden in
`pipeline/oogst/` nog de oude indeling hebben. Met de échte functies uit
`oogst_zorg.sh`:

    herstel_rapport : rapport in .cache opzij (andere kop)
                      repo-kopie geweigerd  (andere kop)
    daarna          : verwerkt_2019.txt tóch teruggezet, 2.211 regels
    de lader        : "alles al bekeken", schrijft alleen een kopregel
    bewaar()        : cp over de repo-kopie heen -- 942 regels worden er 1

Gecommit als "Zorgoogst 2019: 0 opdrachten, 2211 organisaties bekeken
[skip ci]", tussen honderden identieke tussenstanden. En "bekeken" betekent in
dit project "nooit meer".

Twee remmen in `oogst_zorg.sh` vangen dat nu (stoppen bij een geweigerde
repo-kopie, en nooit een korter rapport bewaren). Maar de bláard blijft dat álle
tests groen bleven: ze toetsen de code tegen de code, en het gat zat tussen de
code en de gecommitte data. Daar keek niets. Dit bestand kijkt daar wel.

Het leest de echte bestanden uit de repo. Zijn ze er niet, dan is er niets te
toetsen en slaagt de test -- een lege repo hoort geen rood te geven.
"""

import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from laad_zorg import RAPPORT_KOLOMMEN  # noqa: E402

OOGST = Path(__file__).resolve().parent / "oogst"

goed = 0
fout = 0


def check(omschrijving: str, voorwaarde: bool) -> None:
    global goed, fout
    if voorwaarde:
        goed += 1
    else:
        fout += 1
        print(f"  FOUT: {omschrijving}")


bestanden = sorted(OOGST.glob("zorg_*.csv"))
check("er zijn oogstbestanden om te toetsen (of de map is leeg)", True)

for pad in bestanden:
    with pad.open(encoding="utf-8", newline="") as f:
        kop = (f.readline() or "").rstrip("\r\n")
    check(
        f"{pad.name}: de kopregel is precies die van RAPPORT_KOLOMMEN. Wijkt hij "
        f"af, dan weigert 'Zorgoogst inladen' dit bestand en zou een nieuwe oogst "
        f"van dit boekjaar de repo-kopie overschrijven",
        kop == ",".join(RAPPORT_KOLOMMEN),
    )

    with pad.open(encoding="utf-8", newline="") as f:
        rijen = list(csv.reader(f))
    if not rijen:
        continue
    breedte = len(rijen[0])
    scheef = [i for i, r in enumerate(rijen[1:], start=2) if len(r) != breedte]
    check(
        f"{pad.name}: elke rij heeft evenveel velden als de kop "
        f"(scheef op regel {scheef[:3]})",
        not scheef,
    )

    # Eén organisatie hoort per boekjaar één keer in het rapport te staan. Een
    # dubbele KvK betekent dat er twee keer over hetzelfde is geoogst, en dan
    # bepaalt de volgorde in het bestand welke waarde in de database belandt.
    kolommen = rijen[0]
    if "kvk" in kolommen:
        i = kolommen.index("kvk")
        nummers = [r[i] for r in rijen[1:] if len(r) > i and r[i].strip()]
        check(
            f"{pad.name}: geen enkel KvK-nummer staat er twee keer in",
            len(nummers) == len(set(nummers)),
        )

    # De bekekenlijst hoort erbij: zonder die lijst begint een hervatting vooraan
    # en haalt hij alles opnieuw op.
    verwerkt = OOGST / pad.name.replace("zorg_", "verwerkt_").replace(".csv", ".txt")
    check(
        f"{pad.name}: er is een bijbehorende {verwerkt.name}",
        verwerkt.exists(),
    )

print(f"{goed}/{goed + fout} goed")
sys.exit(1 if fout else 0)
