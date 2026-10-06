"""Cliënten van een kantoor uit losse openbare jaarstukken -> opdrachten.

Voor kantoren zonder OOB-vergunning bestaat er geen cliëntenlijst: die hoeven
geen transparantieverslag te publiceren, en hun cliënten deponeren hun
jaarrekening bij de Kamer van Koophandel — die voor dit project is uitgesloten.
Wat overblijft is per organisatie een openbaar jaarstuk zoeken waarin de
accountant met naam staat. Zie adapters/kantoorclienten.py voor het waarom.

Draaien:
    python3 pipeline/laad_kantoorclienten.py --droogloop
    python3 pipeline/laad_kantoorclienten.py --kantoor 13020070

De seed (seed/kantoorclienten.csv) is een lijst BEWERINGEN, geen lijst feiten:
per regel "in dit document staat dat kantoor X tekende bij organisatie Y over
boekjaar Z". Deze lader haalt het document erbij en controleert die bewering
vóór er iets in de database komt. Drie uitkomsten:

    bevestigd   het document is opgehaald en noemt het kantoor -> opdracht
    onbevestigd het document is er wel, maar noemt het kantoor niet -> niets
    onbereikbaar het document is weg, of achter een inlog -> niets

Alleen "bevestigd" schrijft. Dat is strenger dan bij de andere bronnen, en met
reden: daar staat een centrale uitgever garant voor de inhoud, hier is het
document zelf de enige garantie. Een seed-regel die verouderd raakt (het
jaarverslag wordt van de site gehaald) verdwijnt zo vanzelf uit beeld in plaats
van stilletjes een onbewijsbaar feit in de database te houden.

Bestaande rijen winnen: een organisatie die voor dat boekjaar al een opdracht
heeft uit een preciezere bron wordt overgeslagen.
"""

import argparse
import csv
import sys
import urllib.parse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent / "adapters"))
sys.path.insert(0, str(Path(__file__).resolve().parent / "extractie"))

import kantoorclienten  # noqa: E402
from kantoor_match import laad_aliassen, laad_kantoren, normaliseer  # noqa: E402
from supabase_client import Supabase, SupabaseFout  # noqa: E402

SEED = Path(__file__).resolve().parent / "seed" / "kantoorclienten.csv"
CACHE = Path(__file__).resolve().parent / ".cache"

# Wat er in de seed mag staan bij type_opdracht. Een samenstellings- of
# beoordelingsopdracht is géén controle en telt dus niet mee in marktaandelen;
# de views in SQL filteren daarop. Ze worden wél vastgelegd, want ze zeggen iets
# over de relatie.
TYPEN = {
    "controle": "wettelijke_controle",
    "vrijwillige_controle": "vrijwillige_controle",
    "beoordeling": "beoordeling",
    "samenstelling": "samenstelling",
}


def regels() -> list[dict]:
    if not SEED.exists():
        return []
    with SEED.open(encoding="utf-8") as f:
        return [r for r in csv.DictReader(f) if r.get("organisatie")]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--droogloop", action="store_true")
    parser.add_argument("--kantoor", default="", help="alleen deze kantoorsleutel (AFM-nummer)")
    argumenten = parser.parse_args()

    te_doen = regels()
    if argumenten.kantoor:
        te_doen = [r for r in te_doen if r["kantoor_sleutel"] == argumenten.kantoor]
    if not te_doen:
        print("Geen regels in seed/kantoorclienten.csv (of niets voor dit kantoor).")
        print("Dat is geen fout: deze bron groeit met de hand, per bewezen document.")
        return 0

    # Naam en aliassen per kantoorsleutel, om in het document op te zoeken.
    naam_per_sleutel = {k["afm_nummer"]: k["naam"] for k in laad_kantoren()}
    aliassen_per_sleutel: dict[str, list[str]] = {}
    for alias in laad_aliassen():
        aliassen_per_sleutel.setdefault(alias["afm_nummer"], []).append(alias["alias"])

    db = None
    kantoor_id_per_sleutel: dict[str, int] = {}
    org_per_naam: dict[str, list[dict]] = {}
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
        for rij in db.selecteer_alles("organisaties", "select=id,naam,kvk_nummer"):
            org_per_naam.setdefault(normaliseer(rij["naam"]), []).append(rij)

    CACHE.mkdir(exist_ok=True)
    rapport_pad = CACHE / "resultaat_kantoorclienten.csv"
    rapport = rapport_pad.open("w", newline="", encoding="utf-8")
    schrijver = csv.writer(rapport)
    schrijver.writerow(["kantoor", "organisatie", "boekjaar", "status", "gevonden_citaat", "url"])

    telling: dict[str, int] = {}
    for nummer, regel in enumerate(te_doen, start=1):
        sleutel = regel["kantoor_sleutel"]
        kantoornaam = naam_per_sleutel.get(sleutel, sleutel)
        organisatie = regel["organisatie"].strip()
        boekjaar = int(regel["boekjaar"])
        url = regel["url"].strip()

        pad = CACHE / f"kc_{sleutel}_{nummer:03d}"
        try:
            kantoorclienten.haal_document(url, pad)
            tekst = kantoorclienten.tekst_uit_document(pad)
        except kantoorclienten.BronGeweigerd as fout:
            print(f"  GEWEIGERD {organisatie} {boekjaar}: {fout}", flush=True)
            telling["geweigerd"] = telling.get("geweigerd", 0) + 1
            schrijver.writerow([kantoornaam, organisatie, boekjaar, "bron geweigerd", str(fout), url])
            continue
        except Exception as fout:  # noqa: BLE001 — één document mag falen
            print(f"  ONBEREIKBAAR {organisatie} {boekjaar}: {str(fout)[:120]}", flush=True)
            telling["onbereikbaar"] = telling.get("onbereikbaar", 0) + 1
            schrijver.writerow([kantoornaam, organisatie, boekjaar, "onbereikbaar", str(fout)[:200], url])
            continue

        citaat = kantoorclienten.noemt_kantoor(
            tekst, kantoornaam, aliassen_per_sleutel.get(sleutel, [])
        )
        if not citaat:
            # Het document bestaat, maar noemt dit kantoor niet. Dat is precies
            # het geval waarvoor deze controle er is: niet schrijven.
            print(f"  ONBEVESTIGD {organisatie} {boekjaar}: {kantoornaam} niet in het document", flush=True)
            telling["onbevestigd"] = telling.get("onbevestigd", 0) + 1
            schrijver.writerow([kantoornaam, organisatie, boekjaar, "onbevestigd", "", url])
            continue

        print(f"  bevestigd  {organisatie} {boekjaar} — {citaat[:80]}", flush=True)
        telling["bevestigd"] = telling.get("bevestigd", 0) + 1
        schrijver.writerow([kantoornaam, organisatie, boekjaar, "bevestigd", citaat[:300], url])

        if db is None:
            continue

        kantoor_id = kantoor_id_per_sleutel.get(sleutel)
        if kantoor_id is None:
            print(f"  LET OP: kantoor {sleutel} staat niet in de database — draai laad_kantoren.py")
            continue

        bron = db.invoegen(
            "bronnen",
            {"bron_type": "openbaar_jaarstuk", "url": url, "betrouwbaarheid": "publiek"},
        )

        kvk = (regel.get("kvk_nummer") or "").strip() or None
        naamsleutel = normaliseer(organisatie)
        kandidaten = org_per_naam.get(naamsleutel, [])
        if len(kandidaten) > 1:
            # Twee organisaties met dezelfde naam: een mens moet kiezen.
            if not db.bestaat(
                "review_queue",
                "soort=eq.naam_match&status=eq.open"
                f"&payload->>organisatie=eq.{urllib.parse.quote(organisatie, safe='')}"
                f"&payload->>boekjaar=eq.{boekjaar}",
            ):
                db.invoegen(
                    "review_queue",
                    {
                        "soort": "naam_match",
                        "payload": {
                            "bron": "openbaar_jaarstuk",
                            "organisatie": organisatie,
                            "boekjaar": boekjaar,
                            "kantoor": kantoornaam,
                            "vindplaats": url,
                        },
                    },
                )
            schrijver.writerow([kantoornaam, organisatie, boekjaar, "review (naam dubbel)", "", url])
            continue

        if kandidaten:
            org = kandidaten[0]
        else:
            org = db.upsert_met_id(
                "organisaties",
                {"naam": organisatie, "kvk_nummer": kvk, "sector": regel.get("sector") or None},
                "kvk_nummer" if kvk else "naam",
            ) if kvk else db.invoegen(
                "organisaties",
                {"naam": organisatie, "kvk_nummer": None, "sector": regel.get("sector") or None},
            )
            org_per_naam.setdefault(naamsleutel, []).append(org)

        type_opdracht = TYPEN.get(regel.get("type_opdracht", "").strip(), "wettelijke_controle")

        # Bestaande rijen winnen: een preciezere bron wordt nooit overschreven.
        if db.bestaat(
            "opdrachten",
            f"organisatie_id=eq.{org['id']}&boekjaar=eq.{boekjaar}"
            f"&type_opdracht=eq.{type_opdracht}",
        ):
            telling["al bekend"] = telling.get("al bekend", 0) + 1
            continue

        db.upsert_met_id(
            "opdrachten",
            {
                "organisatie_id": org["id"],
                "kantoor_id": kantoor_id,
                "boekjaar": boekjaar,
                "type_opdracht": type_opdracht,
                "bron_id": bron["id"],
            },
            "organisatie_id,boekjaar,type_opdracht",
        )

    rapport.close()
    print(f"\nUitkomst: {telling}")
    print(f"Rapport: {rapport_pad}")
    # Onbevestigde regels zijn geen crash, maar wel iets om naar te kijken.
    if telling.get("onbevestigd") or telling.get("onbereikbaar"):
        print(
            "\nLet op: regels met status 'onbevestigd' of 'onbereikbaar' hebben "
            "niets weggeschreven. Controleer de vindplaats in de seed."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
