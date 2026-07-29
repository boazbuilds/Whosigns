"""Bulk-lader zorgsector: van de DigiMV-dataset naar opdrachten in de database.

Werkwijze (de dekkingsstrategie uit adapters/digimv.md):

    dataset (.ods)  ->  wie heeft een CONTROLEverklaring?   ~1.010 van 6.131
                    ->  archief: verklaring-pdf per organisatie
                    ->  tekst -> kantoornaam tegen de AFM-lijst
                    ->  opdracht-rij in Supabase

Draaien:
    python3 pipeline/laad_zorg.py --boekjaar 2023
    python3 pipeline/laad_zorg.py --boekjaar 2023 --droogloop --kantoor qconcepts

Opties:
    --boekjaar N    welk boekjaar (standaard 2023)
    --vanaf N       sla de eerste N organisaties over (voor het opknippen van
                    een lange run over meerdere jobs)
    --aantal N      verwerk er hoogstens N
    --droogloop     niets naar de database schrijven; alleen een CSV-rapport.
                    Werkt zonder Supabase-sleutels.
    --kantoor TEKST toon aan het eind alleen de cliënten van dit kantoor

Hervatten is veilig: organisatie-boekjaren die al een opdracht in de database
hebben, worden overgeslagen. Wat niets opleverde (geen deponering, gescande pdf)
wordt bij een herstart wél opnieuw geprobeerd — dat is bewust, want zulke
gevallen kunnen later alsnog gevuld raken. Wordt dat te duur, dan is een
verwerkingslog-tabel de volgende stap.

Wees vriendelijk voor de bron: er zit een pauze tussen downloads
(digimv_archief.PAUZE_SECONDEN) en de run hoort als achtergrondtaak te draaien,
niet interactief.
"""

import argparse
import csv
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent / "adapters"))
sys.path.insert(0, str(Path(__file__).resolve().parent / "extractie"))

import digimv_archief  # noqa: E402
import digimv_dataset  # noqa: E402
from digimv import verwerk_organisatie  # noqa: E402
from kantoor_match import bouw_index, laad_kantoren, normaliseer  # noqa: E402
from supabase_client import Supabase, SupabaseFout  # noqa: E402

CACHE = Path(__file__).resolve().parent / ".cache"
BRON_URL = "https://digimv13.desan.nl/archive/search"

# Woorden die in honderden zorgnamen voorkomen en dus niets onderscheiden.
# Alleen gebruikt om een bétere zoekterm te kiezen, niet om iets weg te gooien.
GENERIEK = {
    "stichting", "holding", "besloten", "vennootschap", "naamloze", "maatschap",
    "cooperatie", "groep", "group", "nederland", "nederlandse", "zorg", "care",
    "ziekenhuis", "centrum", "center", "medisch", "medische", "academisch",
    "kliniek", "praktijk", "thuis", "thuiszorg", "wonen", "welzijn", "jeugd",
    "zorggroep", "zorgcentrum", "zorgcentra", "instelling", "regionaal",
    "regionale", "algemeen", "algemene", "nieuwe", "voor", "van", "den", "der",
    "het", "een", "and", "the",
}


def zoekfragment(naam: str) -> str:
    """Eén onderscheidend wóórd uit de naam om mee te zoeken.

    Het archief zoekt op deelstring. Twee woorden aan elkaar plakken werkt dus
    niet zodra er iets tussen staat: "Admiraal De Ruyter Ziekenhuis" bevat wel
    "Admiraal" maar niet "Admiraal Ziekenhuis". Eén woord is altijd een
    aaneengesloten stuk en dus veilig.

    Generieke zorgwoorden worden vermeden omdat ze duizenden treffers geven;
    ze blijven wel bruikbaar als er niets onderscheidends over is. Te veel
    treffers is overigens niet erg — het KvK-nummer beslist alsnog.
    """
    schoon = re.sub(r"[\"'()./,]", " ", naam)
    schoon = re.sub(r"[^A-Za-z0-9\s&-]", " ", schoon)
    woorden = [w for w in schoon.split() if len(w) >= 3]
    if not woorden:
        return re.sub(r"[^A-Za-z0-9\s]", " ", naam).strip()[:40] or naam[:40]
    onderscheidend = [w for w in woorden if w.lower() not in GENERIEK]
    kandidaten = onderscheidend or woorden
    return max(kandidaten, key=len)


def zoek_met_terugval(organisatie: dict, boekjaar: int, kantoor_index: dict):
    """Probeer op naamfragment; lukt dat niet, dan op plaatsnaam.

    In beide gevallen beslist het KvK-nummer welke treffer we nemen — namen en
    plaatsen wisselen per boekjaar, het KvK-nummer niet (zie adapters/digimv.py).
    """
    kvk = organisatie["kvk_nummer"]
    resultaat = verwerk_organisatie(
        zoekfragment(organisatie["naam"]), kvk, boekjaar, kantoor_index
    )
    if resultaat or not organisatie.get("plaats"):
        return resultaat
    treffers = digimv_archief.zoek(plaats=organisatie["plaats"], boekjaar=boekjaar)
    if not any((t.get("externalOrganizationId") or "").strip() == kvk for t in treffers):
        return None
    # Wél op plaats te vinden: nog een keer, nu met de plaats als ingang en een
    # lege naam — de plaatsnaam hoort in het plaats-veld, niet in het naam-veld.
    return verwerk_organisatie(
        "", kvk, boekjaar, kantoor_index, plaats=organisatie["plaats"]
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--boekjaar", type=int, default=2023)
    parser.add_argument("--vanaf", type=int, default=0)
    parser.add_argument("--aantal", type=int, default=0)
    parser.add_argument("--droogloop", action="store_true")
    parser.add_argument("--kantoor", default="")
    argumenten = parser.parse_args()
    boekjaar = argumenten.boekjaar

    print(f"dataset boekjaar {boekjaar} ophalen...", flush=True)
    ods = digimv_dataset.download(boekjaar, CACHE)
    lijst_pad = CACHE / f"doelpopulatie_{boekjaar}.csv"
    if lijst_pad.exists():
        organisaties = digimv_dataset.lees_csv(lijst_pad)
    else:
        print("doelpopulatie bepalen (dit duurt een paar minuten)...", flush=True)
        organisaties = digimv_dataset.doelpopulatie(ods, boekjaar)
        digimv_dataset.schrijf_csv(organisaties, lijst_pad)
    print(f"{len(organisaties)} organisaties met een controleverklaring\n", flush=True)

    kantoor_index = bouw_index(laad_kantoren())

    db = None
    bron_id = None
    kantoor_id_per_nummer: dict[str, int] = {}
    al_geladen: set[str] = set()
    if not argumenten.droogloop:
        try:
            db = Supabase()
        except SupabaseFout as fout:
            print(fout)
            return 1
        kantoor_id_per_nummer = {
            rij["afm_nummer"]: rij["id"]
            for rij in db.selecteer("kantoren", "select=id,afm_nummer")
        }
        if not kantoor_id_per_nummer:
            print("Geen kantoren in de database — draai eerst de Pipeline-workflow.")
            return 1
        bestaand = db.selecteer(
            "opdrachten",
            f"select=organisaties(kvk_nummer)&boekjaar=eq.{boekjaar}",
        )
        al_geladen = {
            (rij.get("organisaties") or {}).get("kvk_nummer")
            for rij in bestaand
        } - {None}
        bron = db.invoegen(
            "bronnen",
            {"bron_type": "digimv", "url": BRON_URL, "betrouwbaarheid": "publiek"},
        )
        bron_id = bron["id"]
        print(f"bron {bron_id}; {len(al_geladen)} organisaties al geladen\n", flush=True)

    werklijst = organisaties[argumenten.vanaf:]
    if argumenten.aantal:
        werklijst = werklijst[: argumenten.aantal]

    rapport_pad = CACHE / f"resultaat_{boekjaar}.csv"
    rapport = rapport_pad.open("a", newline="", encoding="utf-8")
    schrijver = csv.writer(rapport)
    if rapport.tell() == 0:
        schrijver.writerow(["kvk", "naam", "plaats", "boekjaar", "kantoor", "afm_nummer", "oordeel"])

    gevonden = 0
    mislukt = 0
    per_kantoor: dict[str, int] = {}
    begin = time.time()

    for teller, organisatie in enumerate(werklijst, start=1):
        kvk = organisatie["kvk_nummer"]
        if kvk in al_geladen:
            continue
        if teller % 25 == 0:
            verstreken = time.time() - begin
            print(
                f"--- {teller}/{len(werklijst)} | {gevonden} gevonden | "
                f"{mislukt} zonder kantoor | {verstreken/60:.1f} min ---",
                flush=True,
            )

        try:
            resultaat = zoek_met_terugval(organisatie, boekjaar, kantoor_index)
        except Exception as fout:  # noqa: BLE001 — bron mag falen, run gaat door
            print(f"  {organisatie['naam'][:50]}: fout {fout}", flush=True)
            mislukt += 1
            continue

        if not resultaat:
            mislukt += 1
            continue

        kantoor = resultaat["kantoor"]
        gevonden += 1
        per_kantoor[kantoor["naam"]] = per_kantoor.get(kantoor["naam"], 0) + 1
        schrijver.writerow([
            kvk, resultaat["naam"], resultaat["plaats"], boekjaar,
            kantoor["naam"], kantoor["afm_nummer"], resultaat["oordeel"],
        ])
        rapport.flush()

        if db is not None:
            kantoor_id = kantoor_id_per_nummer.get(kantoor["afm_nummer"])
            if kantoor_id is None:
                continue
            org_rij = db.upsert_met_id(
                "organisaties",
                {
                    "kvk_nummer": kvk,
                    "naam": resultaat["naam"],
                    "sector": "zorg",
                    "gemeente": resultaat["plaats"],
                },
                "kvk_nummer",
            )
            db.upsert_met_id(
                "opdrachten",
                {
                    "organisatie_id": org_rij["id"],
                    "kantoor_id": kantoor_id,
                    "boekjaar": boekjaar,
                    "type_opdracht": "wettelijke_controle",
                    "oordeel": resultaat["oordeel"],
                    "continuiteitsonzekerheid": resultaat["continuiteitsonzekerheid"],
                    "bron_id": bron_id,
                },
                "organisatie_id,boekjaar,type_opdracht",
            )

    rapport.close()
    print(f"\n=== boekjaar {boekjaar}: {gevonden} opdrachten, "
          f"{mislukt} zonder herleidbaar kantoor "
          f"({(time.time()-begin)/60:.0f} min) ===\n")

    print("Marktaandeel in deze run:")
    for naam, aantal in sorted(per_kantoor.items(), key=lambda p: -p[1])[:25]:
        print(f"  {aantal:5d}  {naam}")

    if argumenten.kantoor:
        gezocht = normaliseer(argumenten.kantoor)
        print(f"\n=== cliënten van '{argumenten.kantoor}' ===")
        with rapport_pad.open(encoding="utf-8") as f:
            treffers = [r for r in csv.DictReader(f)
                        if gezocht in normaliseer(r["kantoor"])]
        for rij in sorted(treffers, key=lambda r: r["naam"]):
            print(f"  {rij['naam']} ({rij['plaats']}) — {rij['oordeel']}")
        print(f"\n{len(treffers)} cliënten")

    print(f"\nRapport: {rapport_pad}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
