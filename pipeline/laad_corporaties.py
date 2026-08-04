"""Bulk-lader woningcorporaties: van de dVi-open data naar opdrachten in de database.

De goedkoopste vertical die we hebben. De Autoriteit woningcorporaties publiceert de
verantwoordingsinformatie als open data (CC-0) en hoofdstuk 1 bevat per corporatie een
kolom `Accountant`, met KvK-nummer, naam en gemeente ernaast:

    dVi<jaar> hoofdstuk 1 (xlsx)  ->  kolom Accountant  ->  naam normaliseren
                                  ->  opdracht-rij in Supabase

Geen archief, geen pdf's, geen OCR — één bestand per boekjaar. Zie
`docs/bestaande-databases.md` en `adapters/aw_dvi.py`.

Draaien:
    python3 pipeline/laad_corporaties.py --boekjaar 2024
    python3 pipeline/laad_corporaties.py --boekjaar 2024 --droogloop
    python3 pipeline/laad_corporaties.py --boekjaar 2015 --bestand ~/dvi2015.xlsx

Opties:
    --boekjaar N   welk boekjaar (2014 t/m 2024 staan los per hoofdstuk online)
    --droogloop    niets naar de database schrijven, alleen een CSV-rapport
    --herlaad      bestaande opdrachten van dit boekjaar opnieuw beoordelen
    --bestand PAD  een al gedownload xlsx gebruiken; handig als data.overheid.nl traag
                   is (dat gebeurt) of als je een jaargang met de hand hebt opgehaald

Idempotent: upsert op (organisatie_id, boekjaar, type_opdracht).

Opdrachttype: `wettelijke_controle`. Een toegelaten instelling is op grond van de
Woningwet controleplichtig, dus dit is geen vrijwillige controle zoals bij de goede
doelen. Komt er onverwacht een kantoor zonder Wta-vergunning uit, dan kán het geen
wettelijke controle zijn en boeken we `vrijwillige_controle` — met een regel in het
rapport, want dan is er iets aan de hand.

Herkomst per feit: dit veld is **zelfgerapporteerd** door de corporatie in haar
verantwoording aan de toezichthouder. Dat is een ander soort bewijs dan een
ondertekende verklaring; de bronrij (`bron_type = 'aw_dvi'`) legt dat vast.
"""

import argparse
import collections
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent / "adapters"))
sys.path.insert(0, str(Path(__file__).resolve().parent / "extractie"))

import aw_dvi  # noqa: E402
from kantoor_match import bouw_index, laad_kantoren, zoek_kantoor  # noqa: E402
from supabase_client import Supabase, SupabaseFout  # noqa: E402

CACHE = Path(__file__).resolve().parent / ".cache"
SECTOR = "woningcorporaties"


def _kantoor(naam: str, index: dict) -> dict | None:
    """Kantoornaam uit een veld matchen.

    We plakken er een plaats en datum bij, omdat `zoek_kantoor` sinds de goededoelenrun
    eist dat een naam op een ondertekeningsplek staat. Dat is de juiste regel voor
    verklaringteksten, maar hier is de naam zelf het veld — er ís geen ondertekening om
    naar te kijken.
    """
    treffer = zoek_kantoor(f"Rotterdam, 1 juni 2026 {naam}", index)
    return treffer["kantoor"] if treffer and not treffer["zwak"] else None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--boekjaar", type=int, default=2024)
    parser.add_argument("--droogloop", action="store_true")
    parser.add_argument("--herlaad", action="store_true")
    parser.add_argument("--bestand", default="")
    argumenten = parser.parse_args()
    boekjaar = argumenten.boekjaar

    if not (aw_dvi.OUDSTE_BOEKJAAR <= boekjaar <= aw_dvi.NIEUWSTE_BOEKJAAR):
        print(
            f"boekjaar {boekjaar} valt buiten {aw_dvi.OUDSTE_BOEKJAAR}–"
            f"{aw_dvi.NIEUWSTE_BOEKJAAR}; oudere jaargangen staan als één bundel online "
            "en zijn nog niet uitgezocht"
        )
        return 1

    print(f"dVi{boekjaar} ophalen…", flush=True)
    try:
        if argumenten.bestand:
            rijen = aw_dvi.corporaties_uit_bestand(Path(argumenten.bestand), boekjaar)
        else:
            rijen = aw_dvi.corporaties(boekjaar, cache=CACHE)
    except Exception as fout:  # noqa: BLE001 — bron mag falen, meld het netjes
        print(f"ophalen mislukt: {type(fout).__name__}: {fout}")
        print("Tip: download het xlsx met de hand en geef het mee met --bestand.")
        return 1
    print(f"{len(rijen)} corporaties met een accountantsnaam", flush=True)

    index = bouw_index(laad_kantoren())

    db = None
    bron_id = None
    kantoor_id_per_sleutel: dict[str, int] = {}
    al_geladen: set[str] = set()
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
        if not kantoor_id_per_sleutel:
            print("Geen kantoren in de database — draai eerst de Pipeline-workflow.")
            return 1
        bestaand = db.selecteer_alles(
            "opdrachten", f"select=organisaties(kvk_nummer)&boekjaar=eq.{boekjaar}"
        )
        al_geladen = (
            set()
            if argumenten.herlaad
            else {(r.get("organisaties") or {}).get("kvk_nummer") for r in bestaand} - {None}
        )
        bron = db.invoegen(
            "bronnen",
            {
                "bron_type": "aw_dvi",
                "url": rijen[0]["bron_url"],
                "betrouwbaarheid": "publiek",
            },
        )
        bron_id = bron["id"]
        print(f"bron {bron_id}; {len(al_geladen)} organisaties al geladen", flush=True)

    CACHE.mkdir(exist_ok=True)
    rapport_pad = CACHE / f"resultaat_corporaties_{boekjaar}.csv"
    with rapport_pad.open("w", newline="", encoding="utf-8") as rapport:
        schrijver = csv.writer(rapport)
        schrijver.writerow(
            ["kvk", "naam", "gemeente", "boekjaar", "status",
             "accountant_ruw", "kantoor", "wta", "opdrachttype"]
        )

        telling: collections.Counter = collections.Counter()
        per_kantoor: collections.Counter = collections.Counter()
        for rij in rijen:
            kantoor = _kantoor(rij["accountant"], index)
            status = "opdracht" if kantoor else "review"
            wta = bool(kantoor and kantoor["wta_vergunning"])
            # Een corporatie is controleplichtig; een kantoor zonder vergunning mág die
            # controle dus niet doen. Komt dat voor, dan is er iets aan de hand en
            # noemen we het niet wettelijk.
            type_opdracht = "wettelijke_controle" if wta else "vrijwillige_controle"
            if not rij["kvk_nummer"]:
                status = "geen_kvk"
            telling[status] += 1
            if kantoor:
                per_kantoor[kantoor["naam"]] += 1
            schrijver.writerow([
                rij["kvk_nummer"], rij["naam"], rij["gemeente"], boekjaar, status,
                rij["accountant_ruw"], kantoor["naam"] if kantoor else "",
                "ja" if wta else ("nee" if kantoor else ""),
                type_opdracht if kantoor else "",
            ])

            if db is None or status == "geen_kvk":
                continue
            if rij["kvk_nummer"] in al_geladen:
                continue

            org = db.upsert_met_id(
                "organisaties",
                {
                    "kvk_nummer": rij["kvk_nummer"],
                    "naam": rij["naam"] or rij["kvk_nummer"],
                    "rechtsvorm": "toegelaten instelling",
                    "sector": SECTOR,
                    "gemeente": rij["gemeente"] or None,
                },
                "kvk_nummer",
            )
            if kantoor:
                kantoor_id = kantoor_id_per_sleutel.get(kantoor["sleutel"])
                if kantoor_id is None:
                    print(f"  {rij['naam'][:40]}: kantoor {kantoor['naam']} nog niet in "
                          "de database — draai laad_kantoren.py", flush=True)
                    continue
                if argumenten.herlaad:
                    db.verwijderen(
                        "opdrachten",
                        f"organisatie_id=eq.{org['id']}&boekjaar=eq.{boekjaar}",
                    )
                db.upsert_met_id(
                    "opdrachten",
                    {
                        "organisatie_id": org["id"],
                        "kantoor_id": kantoor_id,
                        "boekjaar": boekjaar,
                        "type_opdracht": type_opdracht,
                        "bron_id": bron_id,
                    },
                    "organisatie_id,boekjaar,type_opdracht",
                )
            else:
                # Nooit stil gokken: de opgegeven naam past op geen enkel kantoor uit
                # onze lijsten. Meestal een typefout of een historische naam.
                #
                # Maar niet nóg een keer: dit geval krijgt geen opdracht-rij en
                # wordt bij elke herstart opnieuw verwerkt — zonder deze check
                # groeide de wachtrij met hetzelfde geval per run.
                if db.bestaat(
                    "review_queue",
                    "soort=eq.naam_match&status=eq.open"
                    f"&payload->>kvk_nummer=eq.{rij['kvk_nummer']}"
                    f"&payload->>boekjaar=eq.{boekjaar}",
                ):
                    continue
                db.invoegen(
                    "review_queue",
                    {
                        "soort": "naam_match",
                        "payload": {
                            "bron": "aw_dvi",
                            "organisatie": rij["naam"],
                            "kvk_nummer": rij["kvk_nummer"],
                            "boekjaar": boekjaar,
                            "opgegeven_naam": rij["accountant_ruw"],
                            "vindplaats": rij["bron_url"],
                        },
                    },
                )

    print(f"\n=== boekjaar {boekjaar} ===")
    for status, aantal in telling.most_common():
        print(f"  {status:12s} {aantal:4d}")
    print("\nMarktaandeel corporaties in deze run:")
    for naam, aantal in per_kantoor.most_common(15):
        print(f"  {aantal:4d}  {naam}")
    print(f"\nRapport: {rapport_pad}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
