"""De ondertekenaar bijvullen in rapporten die er al liggen.

Draaien vanuit de repo-root:

    python3 pipeline/vul_ondertekenaar.py                    # droogloop
    python3 pipeline/vul_ondertekenaar.py --schrijf          # invullen
    python3 pipeline/vul_ondertekenaar.py --boekjaren 2023   # één jaar

Waarom dit bestaat
------------------
`tekenend_accountant` is op 20-8-2026 aan het rapport toegevoegd, ná vijf
geoogste boekjaren. Die 4.646 rijen opnieuw oogsten kost tientallen uren: elke
organisatie betekent een zoekopdracht in het archief, een download en meestal
OCR. Maar het dure deel ligt er al. `oogst_zorg.sh` bewaart de gelezen tekst van
elke gescande verklaring in `pipeline/oogst/ocr/` — 3.604 bestanden over vijf
boekjaren — en in `.cache` staan bovendien de pdf's van de laatste oogst.

Dit script leest die teksten opnieuw, zoekt de ondertekenaar, en vult hem in bij
de rij die er al staat. Geen download, geen OCR, geen archiefverzoek.

Wat het bewust niet doet
------------------------
- **Rijen toevoegen.** Dat is het werk van `nakijk_ocr.py`. Hier wordt alleen een
  leeg veld gevuld bij een rij die er al is.
- **Een bestaande naam overschrijven.** Wat er staat komt uit een oogst met de
  volledige tekst; deze bijvulling werkt met wat er toevallig bewaard is.
- **Gokken.** Dezelfde eis als in `analyseer()`: het oordeel van het blok waar de
  naam uit komt moet gelijk zijn aan het oordeel dat in de rij staat. Anders is
  het willekeurig welke naam bij welk oordeel hoort — in een jaarverslag met een
  jaarrekeningverklaring én een WNT-verklaring is dat een echt risico.
"""

import argparse
import csv
import subprocess
import sys
from pathlib import Path

WORTEL = Path(__file__).resolve().parent
sys.path.insert(0, str(WORTEL))
sys.path.insert(0, str(WORTEL / "extractie"))

from laad_zorg import RAPPORT_KOLOMMEN  # noqa: E402
from ondertekenaar import zoek_ondertekenaar  # noqa: E402
from verklaring import _oordeel, normaliseer  # noqa: E402

OOGST = WORTEL / "oogst"
OCR = OOGST / "ocr"
CACHE = WORTEL / ".cache"


def tekst_van(boekjaar: str, kvk: str) -> tuple[str, str] | None:
    """De tekst van de verklaring, en waar hij vandaan komt.

    Volgorde: de bewaarde OCR-tekst in de repo eerst, want die overleeft een
    herstart van de omgeving. Daarna wat er toevallig in .cache ligt.
    """
    for pad in sorted(OCR.glob(f"{boekjaar}_{kvk}_*.ocr.txt")):
        return pad.read_text(encoding="utf-8", errors="replace"), "bewaarde ocr"
    for pad in sorted(CACHE.glob(f"{boekjaar}_{kvk}_*.ocr.txt")):
        return pad.read_text(encoding="utf-8", errors="replace"), "ocr in cache"
    for pad in sorted(CACHE.glob(f"{boekjaar}_{kvk}_*.pdf")):
        try:
            uit = subprocess.run(
                ["pdftotext", "-q", str(pad), "-"], capture_output=True, timeout=120
            ).stdout.decode("utf-8", "replace")
        except Exception:
            continue
        if len(uit.strip()) >= 200:
            return uit, "pdf in cache"
    return None


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--boekjaren", default="", help="komma-lijst, leeg = alle")
    p.add_argument("--schrijf", action="store_true")
    argumenten = p.parse_args()

    jaren = [j.strip() for j in argumenten.boekjaren.split(",") if j.strip()]
    bestanden = sorted(OOGST.glob("zorg_*.csv"))
    if jaren:
        bestanden = [b for b in bestanden if b.stem.split("_")[1] in jaren]

    totaal_bij = 0
    for pad in bestanden:
        boekjaar = pad.stem.split("_")[1]
        with pad.open(encoding="utf-8", newline="") as f:
            rijen = list(csv.DictReader(f))
        if not rijen:
            continue

        leeg = [r for r in rijen if not (r.get("tekenend_accountant") or "").strip()]
        gevuld = 0
        geen_tekst = 0
        geen_naam = 0
        oordeel_wijkt_af = 0
        herkomst: dict[str, int] = {}

        for rij in leeg:
            gevonden = tekst_van(boekjaar, rij["kvk"])
            if gevonden is None:
                geen_tekst += 1
                continue
            tekst, waarvandaan = gevonden
            uit = zoek_ondertekenaar(tekst, rij.get("kantoor") or None)
            if not uit["naam"] or not uit["blok"]:
                geen_naam += 1
                continue
            blok = tekst[uit["blok"][0] : uit["blok"][1]]
            if (_oordeel(normaliseer(blok)) or "") != (rij.get("oordeel") or ""):
                oordeel_wijkt_af += 1
                continue
            rij["tekenend_accountant"] = uit["naam"]
            gevulde_herkomst = herkomst.get(waarvandaan, 0)
            herkomst[waarvandaan] = gevulde_herkomst + 1
            gevuld += 1

        print(
            f"boekjaar {boekjaar}: {len(rijen)} rijen, {len(leeg)} zonder naam -> "
            f"{gevuld} ingevuld"
            + (f" ({', '.join(f'{k}: {v}' for k, v in herkomst.items())})" if herkomst else "")
        )
        print(
            f"    niet gelukt: {geen_tekst} zonder bewaarde tekst, "
            f"{geen_naam} geen naam op een ondertekeningsplek, "
            f"{oordeel_wijkt_af} blokoordeel wijkt af van de rij"
        )
        totaal_bij += gevuld

        if argumenten.schrijf and gevuld:
            with pad.open("w", encoding="utf-8", newline="") as f:
                schrijver = csv.DictWriter(f, fieldnames=RAPPORT_KOLOMMEN)
                schrijver.writeheader()
                schrijver.writerows(rijen)

    if not argumenten.schrijf:
        print(f"\ndroogloop: er is niets geschreven; met --schrijf worden er "
              f"{totaal_bij} namen ingevuld")
    else:
        print(f"\n{totaal_bij} namen ingevuld")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
