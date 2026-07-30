"""Vult de extra dataset-velden bij op rijen die al in de database staan.

Waarom dit apart bestaat: `laad_zorg.py` slaat organisatie-boekjaren over die al
een opdracht hebben. Dat is precies goed voor hervatten — je wilt geen pdf's
opnieuw ophalen — maar het betekent ook dat nieuwe kolommen nooit gevuld raken
zodra een boekjaar eenmaal geladen is.

Deze velden komen uit de jaardataset, niet uit het archief. Er hoeft dus niets
gedownload te worden: het is een handvol verzoeken naar Supabase en klaar in
seconden, niet in uren.

    organisaties   subsector, rechtsvorm, omzet_eur
    opdrachten     honorarium_controle_eur, honorarium_overig_eur,
                   honorarium_fiscaal_eur, honorarium_nietcontrole_eur,
                   wissel_gerapporteerd

Draaien:
    python3 pipeline/vul_extra_velden.py --boekjaar 2023

Het boekjaar is dat van de dataset. Subsector en rechtsvorm gaan naar de
organisatie en gelden voor alle jaren; de jaarcijfers (omzet, honoraria,
wisselvlag) worden alleen aan de opdracht van dát boekjaar gehangen.

Idempotent: twee keer draaien geeft hetzelfde resultaat. Lege waarden worden
nooit weggeschreven, dus een bestaande waarde raakt niet kwijt aan een leeg veld.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent / "adapters"))

import digimv_dataset  # noqa: E402
from supabase_client import Supabase, SupabaseFout  # noqa: E402

CACHE = Path(__file__).resolve().parent / ".cache"

# csv-veld -> databasekolom, per tabel.
ORGANISATIE_VELDEN = {"subsector": "subsector", "rechtsvorm": "rechtsvorm"}
ORGANISATIE_JAARVELDEN = {"omzet": "omzet_eur"}
OPDRACHT_JAARVELDEN = {
    "honorarium_controle": "honorarium_controle_eur",
    "honorarium_overig": "honorarium_overig_eur",
    "honorarium_fiscaal": "honorarium_fiscaal_eur",
    "honorarium_nietcontrole": "honorarium_nietcontrole_eur",
    "wissel_gerapporteerd": "wissel_gerapporteerd",
    # Het oordeel zoals de bron het meldt, náást het oordeel dat wij uit de
    # gedeponeerde verklaring lezen. 97% van de tijd zijn ze het eens; de rest is
    # review-werk (v_oordeel_afwijking).
    "oordeel_gerapporteerd": "oordeel_gerapporteerd",
    "verklaring_datum": "verklaring_datum",
}


def _waarde(rij: dict, veld: str):
    """Lege tekst wordt None; 'True'/'False' uit de csv wordt een echte boolean."""
    ruw = (rij.get(veld) or "").strip()
    if not ruw:
        return None
    if ruw.lower() in ("true", "false"):
        return ruw.lower() == "true"
    return ruw


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--boekjaar", type=int, default=2023)
    argumenten = parser.parse_args()
    boekjaar = argumenten.boekjaar

    rijen = digimv_dataset.doelpopulatie_uit_cache(boekjaar, CACHE)
    print(f"{len(rijen)} organisaties in de doelpopulatie van {boekjaar}\n", flush=True)

    try:
        db = Supabase()
    except SupabaseFout as fout:
        print(fout)
        return 1

    # Alleen organisaties die al in de database staan; de rest heeft geen opdracht
    # en hoort hier niet gemaakt te worden.
    id_per_kvk = {
        rij["kvk_nummer"]: rij["id"]
        for rij in db.selecteer_alles("organisaties", "select=id,kvk_nummer")
        if rij.get("kvk_nummer")
    }
    print(f"{len(id_per_kvk)} organisaties in de database", flush=True)

    org_bijgewerkt = 0
    opdracht_bijgewerkt = 0
    overgeslagen = 0

    for rij in rijen:
        organisatie_id = id_per_kvk.get(rij["kvk_nummer"])
        if organisatie_id is None:
            overgeslagen += 1
            continue

        org_velden = {
            kolom: _waarde(rij, veld)
            for veld, kolom in {**ORGANISATIE_VELDEN, **ORGANISATIE_JAARVELDEN}.items()
            if _waarde(rij, veld) is not None
        }
        if org_velden:
            db.bijwerken("organisaties", f"id=eq.{organisatie_id}", org_velden)
            org_bijgewerkt += 1

        opdracht_velden = {
            kolom: _waarde(rij, veld)
            for veld, kolom in OPDRACHT_JAARVELDEN.items()
            if _waarde(rij, veld) is not None
        }
        if opdracht_velden:
            db.bijwerken(
                "opdrachten",
                f"organisatie_id=eq.{organisatie_id}&boekjaar=eq.{boekjaar}",
                opdracht_velden,
            )
            opdracht_bijgewerkt += 1

        if (org_bijgewerkt + overgeslagen) % 200 == 0:
            print(
                f"  {org_bijgewerkt} organisaties, {opdracht_bijgewerkt} opdrachten "
                f"bijgewerkt, {overgeslagen} niet in de database",
                flush=True,
            )

    print(
        f"\n=== {org_bijgewerkt} organisaties bijgewerkt, "
        f"{opdracht_bijgewerkt} opdrachten (boekjaar {boekjaar}), "
        f"{overgeslagen} organisaties staan niet in de database ==="
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
