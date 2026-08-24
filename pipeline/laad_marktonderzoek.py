"""Aangeleverd marktonderzoek -> opdrachten in de database.

De eigenaar levert exportbestanden aan met per rij een organisatie
(KvK-nummer), boekjaar en accountantsnaam. De bestanden zelf blijven buiten
de repository — die is openbaar — en bereiken de lader als omgevingsvariabele
(gzip+base64, zie workflow marktonderzoek.yml) of als los csv-pad.

Draaien:
    python3 pipeline/laad_marktonderzoek.py --bestand pad/naar/export.csv
    python3 pipeline/laad_marktonderzoek.py --bestand ... --droogloop

    # of met de data in een omgevingsvariabele (workflow-route):
    MARKTONDERZOEK_DATA="$(gzip -c export.csv | base64 -w0)" \
        python3 pipeline/laad_marktonderzoek.py

Csv-kolommen: kvk,naam,boekjaar,accountant.

Spelregels:

- **`controle_onbepaald`, geen wettelijke controle.** De aanlevering bewijst
  de accountantsrelatie, niet het soort opdracht. Daardoor telt dit ook niet
  mee in v_marktaandeel (die filtert op wettelijke_controle) en vervuilt een
  aanlevering per kantoor de marktaandelen niet.
- **Nooit gokken.** De accountantsnaam wordt herleid tot een kantoor uit de
  AFM-lijst via een expliciete verkorte-namenlijst plus de bestaande matcher;
  onherleidbaar of meerdere kantoren in één veld -> review-queue.
- **Bestaande rijen winnen.** Heeft een organisatie voor dat boekjaar al een
  wettelijke controle (uit een document-bron), dan slaan we de rij over.
- Bronregistratie: bron_type "marktonderzoek", betrouwbaarheid
  "zelf_aangeleverd", zonder url. Het colofon van de site benoemt deze
  categorie.
- Organisaties worden op KvK-nummer herkend of aangemaakt (zonder sector —
  liever leeg dan een gok uit een SBI-code).
"""

import argparse
import base64
import csv
import gzip
import io
import os
import re
import sys
import urllib.parse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent / "adapters"))
sys.path.insert(0, str(Path(__file__).resolve().parent / "extractie"))

from kantoor_match import bouw_index, laad_kantoren, normaliseer, zoek_kantoor  # noqa: E402
from supabase_client import Supabase, SupabaseFout  # noqa: E402

CACHE = Path(__file__).resolve().parent / ".cache"

# Verkorte namen zoals aanleveringen ze schrijven -> AFM-nummer. Alleen namen
# die ondubbelzinnig één Wta-vergunninghouder aanduiden; al het andere loopt
# via de gewone matcher of de review-queue.
VERKORT: dict[str, str] = {
    "kpmg": "13000121",
    "pwc": "13000291",
    "deloitte": "13000015",
    "ey": "13020186",
    "e y": "13020186",
    "bdo": "13000311",
    "mazars": "13000408",
    "forvis mazars": "13000408",
    "confinant": "13020070",
    "confinant audit": "13020070",
    "confinant audit assurance": "13020070",
}


def lees_rijen(argumenten) -> list[dict]:
    """De aangeleverde rijen, uit --bestand of uit MARKTONDERZOEK_DATA."""
    if argumenten.bestand:
        tekst = Path(argumenten.bestand).read_text(encoding="utf-8")
    else:
        blob = os.environ.get("MARKTONDERZOEK_DATA", "").strip()
        if not blob:
            print("geen --bestand en geen MARKTONDERZOEK_DATA; niets te doen")
            return []
        tekst = gzip.decompress(base64.b64decode(blob)).decode("utf-8")
    return list(csv.DictReader(io.StringIO(tekst)))


def herleid_kantoren(veld: str, index: dict) -> tuple[list[str], list[str]]:
    """Accountantsveld -> (AFM-nummers, onherleidbare delen).

    Een veld kan meerdere namen bevatten ("A; B", "a/b"); elk deel wordt los
    herleid. Dubbele treffers vouwen samen.
    """
    delen = [d for d in re.split(r"[;/]", veld) if d.strip()]
    gevonden: list[str] = []
    onbekend: list[str] = []
    for deel in delen:
        sleutel = normaliseer(deel)
        afm = VERKORT.get(sleutel)
        if afm is None:
            # Zelfde kunstgreep als laad_corporaties: de naam op een
            # ondertekeningsplek aanbieden zodat de positiescontrole van de
            # matcher niet in de weg zit.
            treffer = zoek_kantoor(f"Rotterdam, 1 juni 2026 {deel.strip()}", index)
            if treffer and not treffer["zwak"]:
                afm = treffer["kantoor"].get("sleutel")
        if afm:
            if afm not in gevonden:
                gevonden.append(afm)
        else:
            onbekend.append(deel.strip())
    return gevonden, onbekend


def geldige_rij(rij: dict) -> dict | None:
    kvk = re.sub(r"\D", "", rij.get("kvk") or "")
    naam = (rij.get("naam") or "").strip()
    boekjaar = (rij.get("boekjaar") or "").strip()
    accountant = (rij.get("accountant") or "").strip()
    if len(kvk) != 8 or not naam or not boekjaar.isdigit() or not accountant:
        return None
    return {"kvk": kvk, "naam": naam, "boekjaar": int(boekjaar), "accountant": accountant}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bestand", help="csv met kolommen kvk,naam,boekjaar,accountant")
    parser.add_argument("--droogloop", action="store_true")
    argumenten = parser.parse_args()

    rijen = [g for r in lees_rijen(argumenten) if (g := geldige_rij(r))]
    print(f"{len(rijen)} geldige rijen aangeleverd", flush=True)
    if not rijen:
        return 0

    index = bouw_index(laad_kantoren())

    db = None
    kantoor_id_per_sleutel: dict[str, int] = {}
    org_per_kvk: dict[str, dict] = {}
    if not argumenten.droogloop:
        try:
            db = Supabase()
        except SupabaseFout as fout:
            print(fout)
            return 1
        kantoor_id_per_sleutel = {
            rij["sleutel"]: rij["id"]
            for rij in db.selecteer_alles("kantoren", "select=id,sleutel")
            if rij.get("sleutel")
        }
        for rij in db.selecteer_alles("organisaties", "select=id,kvk_nummer"):
            if rij.get("kvk_nummer"):
                org_per_kvk[rij["kvk_nummer"]] = rij

    CACHE.mkdir(exist_ok=True)
    rapport_pad = CACHE / "resultaat_marktonderzoek.csv"
    rapport = rapport_pad.open("w", newline="", encoding="utf-8")
    schrijver = csv.writer(rapport)
    schrijver.writerow(["kvk", "naam", "boekjaar", "kantoor", "status"])

    bron_id = None
    geschreven = overgeslagen = review = 0
    for rij in rijen:
        kantoren, onbekend = herleid_kantoren(rij["accountant"], index)
        if len(kantoren) != 1 or onbekend:
            # Meerdere kantoren of een onherleidbaar deel: een mens kiest.
            review += 1
            schrijver.writerow(
                [rij["kvk"], rij["naam"], rij["boekjaar"], rij["accountant"], "review"]
            )
            if db is not None and not db.bestaat(
                "review_queue",
                "soort=eq.kantoor_match&status=eq.open"
                f"&payload->>organisatie=eq.{urllib.parse.quote(rij['naam'], safe='')}"
                f"&payload->>boekjaar=eq.{rij['boekjaar']}",
            ):
                db.invoegen(
                    "review_queue",
                    {
                        "soort": "kantoor_match",
                        "payload": {
                            "bron": "marktonderzoek",
                            "organisatie": rij["naam"],
                            "kvk": rij["kvk"],
                            "boekjaar": rij["boekjaar"],
                            "opgegeven": rij["accountant"],
                            "herleid": kantoren,
                            "onherleidbaar": onbekend,
                        },
                    },
                )
            continue

        afm = kantoren[0]
        schrijver.writerow(
            [rij["kvk"], rij["naam"], rij["boekjaar"], afm, "droogloop" if db is None else "ok"]
        )
        if db is None:
            continue

        kantoor_id = kantoor_id_per_sleutel.get(afm)
        if kantoor_id is None:
            print(f"  LET OP: kantoor {afm} niet in de database")
            continue

        org = org_per_kvk.get(rij["kvk"])
        if org is None:
            org = db.invoegen(
                "organisaties",
                {"naam": rij["naam"], "kvk_nummer": rij["kvk"], "sector": None},
            )
            org_per_kvk[rij["kvk"]] = org

        # Een document-bron met het soort opdracht en het oordeel wint altijd
        # van een aanlevering die alleen de relatie kent.
        if db.bestaat(
            "opdrachten",
            f"organisatie_id=eq.{org['id']}&boekjaar=eq.{rij['boekjaar']}"
            "&type_opdracht=eq.wettelijke_controle",
        ):
            overgeslagen += 1
            continue
        if db.bestaat(
            "opdrachten",
            f"organisatie_id=eq.{org['id']}&boekjaar=eq.{rij['boekjaar']}"
            "&type_opdracht=eq.controle_onbepaald",
        ):
            overgeslagen += 1
            continue

        if bron_id is None:
            bron = db.invoegen(
                "bronnen",
                {
                    "bron_type": "marktonderzoek",
                    "url": None,
                    "betrouwbaarheid": "zelf_aangeleverd",
                },
            )
            bron_id = bron["id"]
        db.upsert_met_id(
            "opdrachten",
            {
                "organisatie_id": org["id"],
                "kantoor_id": kantoor_id,
                "boekjaar": rij["boekjaar"],
                "type_opdracht": "controle_onbepaald",
                "bron_id": bron_id,
            },
            "organisatie_id,boekjaar,type_opdracht",
        )
        geschreven += 1

    rapport.close()
    print(
        f"\n{geschreven} opdrachten geschreven, {overgeslagen} al bekend, "
        f"{review} naar review; rapport: {rapport_pad}",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
