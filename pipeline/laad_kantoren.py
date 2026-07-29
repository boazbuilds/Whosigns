"""Zet de AFM-kantorenlijst en de aliassen in Supabase.

Draaien:
    python3 pipeline/laad_kantoren.py            # ververst eerst bij de AFM
    python3 pipeline/laad_kantoren.py --offline  # gebruikt alleen de seed-bestanden

Idempotent: upsert op `afm_nummer` (kantoren) en `alias` (kantoor_alias), dus twee
keer draaien geeft hetzelfde resultaat zonder duplicaten.

Herkomst per feit: er komt één rij in `bronnen` met bron_type 'afm_register' en de
registerlink, waar de kantoorrijen aan hangen.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent / "adapters"))
sys.path.insert(0, str(Path(__file__).resolve().parent / "extractie"))

import afm_register  # noqa: E402
from kantoor_match import laad_aliassen, laad_kantoren  # noqa: E402
from supabase_client import Supabase, SupabaseFout  # noqa: E402

REGISTER_URL = (
    "https://www.afm.nl/nl-nl/sector/registers/vergunningenregisters/"
    "accountantsorganisaties"
)


def main(offline: bool = False) -> int:
    if not offline:
        print("AFM-register ophalen…")
        try:
            kantoren_bron = afm_register.parse_register(afm_register.haal_register_op())
            afm_register.schrijf_seed(kantoren_bron)
            print(f"  seed bijgewerkt: {len(kantoren_bron)} kantoren")
        except Exception as fout:  # noqa: BLE001 — bron mag falen, seed blijft bruikbaar
            print(f"  ophalen mislukt ({fout}); ik gebruik de bestaande seed")

    kantoren = laad_kantoren()
    aliassen = laad_aliassen()
    print(f"seed: {len(kantoren)} kantoren, {len(aliassen)} aliassen")

    try:
        db = Supabase()
    except SupabaseFout as fout:
        print(f"\n{fout}")
        print("De seed-bestanden zijn wel bijgewerkt; alleen het wegschrijven sloeg over.")
        return 1

    # Elke run legt vast wanneer we het register raadpleegden; die datum tonen we
    # later op kantoorpagina's als "stand per …".
    bron = db.invoegen(
        "bronnen",
        {"bron_type": "afm_register", "url": REGISTER_URL, "betrouwbaarheid": "publiek"},
    )
    print(f"bron geregistreerd (id {bron['id']})")

    db.upsert(
        "kantoren",
        [
            {
                "afm_nummer": k["afm_nummer"],
                "naam": k["naam"],
                "oob_vergunning": k["oob_vergunning"] == "ja",
                "actief": k["status"] == "Verleend",
                "website": k["website"] or None,
            }
            for k in kantoren
        ],
        "afm_nummer",
    )
    print(f"kantoren weggeschreven: {len(kantoren)}")

    # kantoor_alias verwijst naar kantoren.id, dus eerst de nummers ophalen.
    id_per_nummer = {
        rij["afm_nummer"]: rij["id"]
        for rij in db.selecteer("kantoren", "select=id,afm_nummer")
    }
    alias_rijen = [
        {"alias": a["alias"], "kantoor_id": id_per_nummer[a["afm_nummer"]]}
        for a in aliassen
        if a["afm_nummer"] in id_per_nummer
    ]
    db.upsert("kantoor_alias", alias_rijen, "alias")
    print(f"aliassen weggeschreven: {len(alias_rijen)}")

    aantal_oob = sum(1 for k in kantoren if k["oob_vergunning"] == "ja")
    print(f"\nklaar — {len(kantoren)} kantoren in de database, {aantal_oob} met OOB-vergunning")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(offline="--offline" in sys.argv))
