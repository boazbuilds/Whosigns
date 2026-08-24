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
    "q concepts": "13000773",
    "flynth": "13000519",
    "dubois": "13000044",
    "dubois co": "13000044",
    "crowe foederer": "13000413",
    "crowe peak": "13000097",
    "crowe peak audit": "13000097",
    # De merknaam tot 2019; Foederer en Peak waren toen al aparte kantoren.
    "crowe horwath foederer": "13000413",
    "crowe horwath peak": "13000097",
    "baker tilly": "13000741",
    "baker tilly netherlands": "13000741",
    "baker tilly berk": "13000741",
    # Veelvoorkomende tikfout met hoofdletter-i's in plaats van l'en.
    "baker tiiiy": "13000741",
    "eshuis": "13000144",
    "eshuis registeraccountants": "13000144",
    "verstegen": "13000147",
    "visser visser": "13000491",
    "visser and visser": "13000491",
    "share impact": "13020072",
    "share impact audit": "13020072",
    # Bewust NIET: kaal "visser" of initialen als "t visser" — dat kan een
    # persoon of een ander kantoor zijn; een mens kiest.
    # WITh heeft geen Wta-vergunning maar tekent vrijwillige controles bij
    # goede doelen; staat als overig kantoor in de database.
    "with": "overig_with_accountants",
    "with accountants": "overig_with_accountants",
    # Bewust NIET: "crowe" alleen (Foederer of Peak? een mens kiest) en
    # "crowe contour" (staat niet in het register).
}


AANLEVER = Path(__file__).resolve().parent / "aanlever"


def lees_map(map_pad: Path = AANLEVER) -> list[dict]:
    """Alle marktonderzoek_*.csv uit de aanlevermap, op bestandsnaam gesorteerd."""
    rijen: list[dict] = []
    for pad in sorted(map_pad.glob("marktonderzoek_*.csv")):
        with pad.open(encoding="utf-8") as f:
            rijen.extend(csv.DictReader(f))
    return rijen


def lees_rijen(argumenten) -> list[dict]:
    """De aangeleverde rijen: --bestand wint, dan MARKTONDERZOEK_DATA, dan de map."""
    if argumenten.bestand:
        tekst = Path(argumenten.bestand).read_text(encoding="utf-8")
        return list(csv.DictReader(io.StringIO(tekst)))
    blob = os.environ.get("MARKTONDERZOEK_DATA", "").strip()
    if blob:
        tekst = gzip.decompress(base64.b64decode(blob)).decode("utf-8")
        return list(csv.DictReader(io.StringIO(tekst)))
    return lees_map()


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

    # Eén bron-rij voor alle marktonderzoek: bestaat er al een, dan die
    # hergebruiken — anders laat elke herstart een extra rij achter.
    bron_id = None
    bezet: set[tuple[int, int]] = set()
    al_in_review: set[tuple] = set()
    review_rijen: list[dict] = []
    if db is not None:
        bestaande_bron = db.selecteer_alles(
            "bronnen", "select=id&bron_type=eq.marktonderzoek&limit=1"
        )
        if bestaande_bron:
            bron_id = bestaande_bron[0]["id"]
        # Alle organisatie-boekjaren die al een controle hebben, in één keer
        # voorgeladen: per rij naar de database vragen kost drie verzoeken per
        # rij en dat past bij duizenden rijen in geen enkele timeout.
        for r in db.selecteer_alles(
            "opdrachten",
            "select=organisatie_id,boekjaar"
            "&type_opdracht=in.(wettelijke_controle,controle_onbepaald)",
        ):
            bezet.add((r["organisatie_id"], r["boekjaar"]))
        for r in db.selecteer_alles(
            "review_queue", "select=payload&soort=eq.naam_match&status=eq.open"
        ):
            p = r.get("payload") or {}
            al_in_review.add((p.get("organisatie"), p.get("boekjaar")))

    # Eerste doorloop: herleiden, rapporteren, reviewgevallen wegschrijven.
    schoon: list[dict] = []
    geschreven = overgeslagen = review = 0
    for rij in rijen:
        kantoren, onbekend = herleid_kantoren(rij["accountant"], index)
        if len(kantoren) != 1 or onbekend:
            # Meerdere kantoren of een onherleidbaar deel: een mens kiest.
            review += 1
            schrijver.writerow(
                [rij["kvk"], rij["naam"], rij["boekjaar"], rij["accountant"], "review"]
            )
            if (rij["naam"], rij["boekjaar"]) not in al_in_review:
                al_in_review.add((rij["naam"], rij["boekjaar"]))
                review_rijen.append(
                    {
                        "soort": "naam_match",
                        "payload": {
                            "bron": "marktonderzoek",
                            "organisatie": rij["naam"],
                            "kvk": rij["kvk"],
                            "boekjaar": rij["boekjaar"],
                            "opgegeven": rij["accountant"],
                            "herleid": kantoren,
                            "onherleidbaar": onbekend,
                        },
                    }
                )
            continue
        schoon.append({**rij, "afm": kantoren[0]})
        schrijver.writerow(
            [rij["kvk"], rij["naam"], rij["boekjaar"], kantoren[0],
             "droogloop" if db is None else "ok"]
        )

    if db is not None:
        db.invoegen_bulk("review_queue", review_rijen)

    if db is not None and schoon:
        # Nieuwe organisaties in bulk, zonder bestaande te overschrijven: een
        # naam uit een documentbron is beter dan die uit een aanlevering.
        nieuw_per_kvk: dict[str, dict] = {}
        for rij in schoon:
            if rij["kvk"] not in org_per_kvk:
                nieuw_per_kvk.setdefault(
                    rij["kvk"],
                    {"naam": rij["naam"], "kvk_nummer": rij["kvk"], "sector": None},
                )
        if nieuw_per_kvk:
            db.invoegen_zonder_overschrijven(
                "organisaties", list(nieuw_per_kvk.values()), "kvk_nummer"
            )
            org_per_kvk = {
                r["kvk_nummer"]: r
                for r in db.selecteer_alles("organisaties", "select=id,kvk_nummer")
                if r.get("kvk_nummer")
            }

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

        # Opdrachten in bulk; wat al een controle heeft (of dubbel in de batch
        # zit) blijft staan — een documentbron wint altijd van een aanlevering.
        nieuwe_opdrachten: list[dict] = []
        for rij in schoon:
            org = org_per_kvk.get(rij["kvk"])
            kantoor_id = kantoor_id_per_sleutel.get(rij["afm"])
            if org is None or kantoor_id is None:
                overgeslagen += 1
                continue
            sleutel = (org["id"], rij["boekjaar"])
            if sleutel in bezet:
                overgeslagen += 1
                continue
            bezet.add(sleutel)
            nieuwe_opdrachten.append(
                {
                    "organisatie_id": org["id"],
                    "kantoor_id": kantoor_id,
                    "boekjaar": rij["boekjaar"],
                    "type_opdracht": "controle_onbepaald",
                    "bron_id": bron_id,
                }
            )
        geschreven = db.upsert(
            "opdrachten", nieuwe_opdrachten, "organisatie_id,boekjaar,type_opdracht"
        )

    rapport.close()
    print(
        f"\n{geschreven} opdrachten geschreven, {overgeslagen} al bekend, "
        f"{review} naar review; rapport: {rapport_pad}",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
