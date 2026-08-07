"""Zet de kantorenlijsten en de aliassen in Supabase.

Twee lijsten, één tabel:

- `seed/kantoren.csv` — de Wta-vergunninghouders uit het AFM-register
  (`wta_vergunning = true`).
- `seed/kantoren_overig.csv` — kantoren zónder Wta-vergunning die wél
  controleverklaringen tekenen bij organisaties zonder controleplicht
  (`wta_vergunning = false`). Zonder deze rijen mist WhoSigns bijna een derde van
  de goededoelensector; zie docs/bronverkenning-stichtingen.md.

Draaien:
    python3 pipeline/laad_kantoren.py            # ververst eerst bij de AFM
    python3 pipeline/laad_kantoren.py --offline  # gebruikt alleen de seed-bestanden

Idempotent: upsert op `sleutel` (kantoren) en `alias` (kantoor_alias), dus twee keer
draaien geeft hetzelfde resultaat zonder duplicaten. `sleutel` is het AFM-nummer, of
"overig_…" voor een kantoor zonder vergunning.

Herkomst per feit: er komt één rij in `bronnen` met bron_type 'afm_register' en de
registerlink, waar de kantoorrijen aan hangen.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent / "adapters"))
sys.path.insert(0, str(Path(__file__).resolve().parent / "extractie"))

import afm_register  # noqa: E402
from kantoor_match import (  # noqa: E402
    laad_aliassen,
    laad_kantoren,
    laad_overige_kantoren,
)
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
    overige = laad_overige_kantoren()
    aliassen = laad_aliassen()
    print(
        f"seed: {len(kantoren)} AFM-kantoren, {len(overige)} kantoren zonder "
        f"Wta-vergunning, {len(aliassen)} aliassen"
    )

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
                "sleutel": k["afm_nummer"],
                "afm_nummer": k["afm_nummer"],
                "naam": k["naam"],
                "wta_vergunning": True,
                "oob_vergunning": k["oob_vergunning"] == "ja",
                "actief": k["status"] == "Verleend",
                "website": k["website"] or None,
                # Profielvelden voor de kantoorpagina; stonden al in de seed maar
                # bleven eerder liggen. vergunning_sinds is de datum waarop de AFM
                # de vergunning verleende, niet de oprichtingsdatum.
                "plaats": k.get("plaats") or None,
                "rechtsvorm": k.get("rechtsvorm") or None,
                "vergunning_sinds": k.get("vergunning_sinds") or None,
                "toelichting": "AFM-vergunningenregister accountantsorganisaties",
            }
            for k in kantoren
        ],
        "sleutel",
    )
    print(f"AFM-kantoren weggeschreven: {len(kantoren)}")

    if overige:
        db.upsert(
            "kantoren",
            [
                {
                    "sleutel": k["sleutel"],
                    "afm_nummer": None,
                    "naam": k["naam"],
                    "wta_vergunning": False,
                    "oob_vergunning": False,
                    "actief": True,
                    "website": k.get("website") or None,
                    "kvk_nummer": k.get("kvk_nummer") or None,
                    "plaats": k.get("plaats") or None,
                    # De reden dat een vergunning is vervallen hoort mee de
                    # database in. Anders staat er op de site een kantoor zónder
                    # vergunning onder een wettelijke controle, zonder dat er
                    # ergens uit blijkt waarom dat klopt.
                    "toelichting": " — ".join(
                        deel for deel in (k.get("toelichting"), k.get("wta_vervallen"))
                        if (deel or "").strip()
                    ) or None,
                }
                for k in overige
            ],
            "sleutel",
        )
        print(f"kantoren zonder Wta-vergunning weggeschreven: {len(overige)}")

    # kantoor_alias verwijst naar kantoren.id, dus eerst de nummers ophalen.
    id_per_nummer = {
        rij["afm_nummer"]: rij["id"]
        for rij in db.selecteer_alles("kantoren", "select=id,afm_nummer")
        if rij.get("afm_nummer")
    }
    alias_rijen = [
        {"alias": a["alias"], "kantoor_id": id_per_nummer[a["afm_nummer"]]}
        for a in aliassen
        if a["afm_nummer"] in id_per_nummer
    ]
    db.upsert("kantoor_alias", alias_rijen, "alias")
    print(f"aliassen weggeschreven: {len(alias_rijen)}")

    aantal_oob = sum(1 for k in kantoren if k["oob_vergunning"] == "ja")
    print(
        f"\nklaar — {len(kantoren) + len(overige)} kantoren in de database "
        f"({aantal_oob} met OOB-vergunning, {len(overige)} zonder Wta-vergunning)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(offline="--offline" in sys.argv))
