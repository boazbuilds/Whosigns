"""Zet de kantorenlijsten en de aliassen in Supabase.

Drie lijsten, één tabel:

- `seed/kantoren.csv` — de Wta-vergunninghouders uit het AFM-register
  (`wta_vergunning = true`).
- `seed/kantoren_vervallen.csv` — vergunninghouders die uit dat register zijn
  verdwenen. Hun rij blijft bestaan (er hangen opdrachten aan), maar wordt
  inactief en verliest haar vergunningsvlaggen.
- `seed/kantoren_overig.csv` — kantoren zónder Wta-vergunning die wél
  controleverklaringen tekenen bij organisaties zonder controleplicht
  (`wta_vergunning = false`). Zonder deze rijen mist WhoSigns bijna een derde van
  de goededoelensector; zie docs/bronverkenning-stichtingen.md.

Een AFM-nummer dat in de database staat maar in geen van de twee AFM-lijsten,
wordt ook inactief: het register kent het niet meer, ook als niemand het in
kantoren_vervallen.csv heeft gezet. Behalve als de seed ineens veel korter is
dan wat de database actief heeft — dan is de seed verdacht en niet het register.

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
    laad_vervallen_kantoren,
)
from supabase_client import Supabase, SupabaseFout  # noqa: E402

REGISTER_URL = (
    "https://www.afm.nl/nl-nl/sector/registers/vergunningenregisters/"
    "accountantsorganisaties"
)


def afm_rijen(kantoren: list[dict]) -> list[dict]:
    return [
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
    ]


def vervallen_rijen(vervallen: list[dict]) -> list[dict]:
    """Verdwenen vergunninghouders: zelfde rij, maar niets meer actief aan.

    Zelfde sleutel als toen ze nog in het register stonden, dus de upsert raakt
    de bestaande rij en de opdrachten die eraan hangen blijven waar ze zijn (de
    maatschap Steens & Partners, 13000055, tekende er een over 2024). Alle drie
    de vlaggen gaan uit: `oob_vergunning` en `wta_vergunning` beschrijven wat het
    register vandaag zegt, en vandaag zegt het niets meer over dit nummer.
    """
    return [
        {
            "sleutel": k["afm_nummer"],
            "afm_nummer": k["afm_nummer"],
            "naam": k["naam"],
            "wta_vergunning": False,
            "oob_vergunning": False,
            "actief": False,
            "website": k.get("website") or None,
            "plaats": k.get("plaats") or None,
            "rechtsvorm": k.get("rechtsvorm") or None,
            "vergunning_sinds": k.get("vergunning_sinds") or None,
            "toelichting": " — ".join(
                deel
                for deel in (
                    "uit het AFM-vergunningenregister accountantsorganisaties "
                    f"verdwenen (eerste snapshot zonder dit nummer: "
                    f"{_datum_nl(k.get('afwezig_sinds'))})",
                    k.get("toelichting"),
                )
                if (deel or "").strip()
            ),
        }
        for k in vervallen
    ]


def _datum_nl(iso: str | None) -> str:
    """'2026-09-28' -> '28-9-2026', zoals de toelichtingen elders; anders as-is."""
    try:
        jaar, maand, dag = (int(deel) for deel in (iso or "").split("-"))
    except ValueError:
        return iso or "onbekend"
    return f"{dag}-{maand}-{jaar}"


def overige_rijen(overige: list[dict]) -> list[dict]:
    return [
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
    ]


def te_deactiveren(db_rijen: list[dict], bekend: set[str]) -> list[dict]:
    """AFM-rijen uit de database die het register niet meer kent.

    Het vangnet naast kantoren_vervallen.csv. 'Stichting Autoriteit Financiële
    Markten' (13020232) verdween op 31-8-2026 uit de export en stond vijf weken
    later nog als OOB-kantoor op de site, omdat deze lader alleen kon toevoegen.
    Wat in geen enkele AFM-lijst meer staat gaat nu uit, ook als niemand het als
    vervallen heeft opgeschreven.

    Alleen rijen waar nog iets aan staat: wat al inactief is en geen vlag meer
    heeft, hoeft niet elke run opnieuw bijgewerkt.
    """
    return [
        rij
        for rij in db_rijen
        if rij.get("afm_nummer")
        and rij["afm_nummer"] not in bekend
        and (rij.get("actief") or rij.get("oob_vergunning") or rij.get("wta_vergunning"))
    ]


def main(offline: bool = False, db: Supabase | None = None) -> int:
    if not offline:
        print("AFM-register ophalen…")
        try:
            kantoren_bron = afm_register.parse_register(afm_register.haal_register_op())
            afm_register.ververs_seed(kantoren_bron)
            print(f"  seed bijgewerkt: {len(kantoren_bron)} kantoren")
        except Exception as fout:  # noqa: BLE001 — bron mag falen, seed blijft bruikbaar
            print(f"  ophalen mislukt ({fout}); ik gebruik de bestaande seed")

    kantoren = laad_kantoren()
    in_register = {k["afm_nummer"] for k in kantoren}
    vervallen = [k for k in laad_vervallen_kantoren() if k["afm_nummer"] not in in_register]
    overige = laad_overige_kantoren()
    aliassen = laad_aliassen()
    print(
        f"seed: {len(kantoren)} AFM-kantoren, {len(vervallen)} uit het register "
        f"verdwenen, {len(overige)} kantoren zonder Wta-vergunning, "
        f"{len(aliassen)} aliassen"
    )

    if db is None:
        try:
            db = Supabase()
        except SupabaseFout as fout:
            print(f"\n{fout}")
            print("De seed-bestanden zijn wel bijgewerkt; alleen het wegschrijven sloeg over.")
            return 1

    # Vóór de upserts: de ondergrens hieronder vergelijkt de seed met wat de
    # database tot nu toe actief had, niet met wat deze run er zelf van maakt.
    db_afm = db.selecteer_alles(
        "kantoren",
        "select=id,afm_nummer,naam,actief,oob_vergunning,wta_vergunning"
        "&afm_nummer=not.is.null",
    )

    # Elke run legt vast wanneer we het register raadpleegden; die datum tonen we
    # later op kantoorpagina's als "stand per …".
    bron = db.invoegen(
        "bronnen",
        {"bron_type": "afm_register", "url": REGISTER_URL, "betrouwbaarheid": "publiek"},
    )
    print(f"bron geregistreerd (id {bron['id']})")

    db.upsert("kantoren", afm_rijen(kantoren), "sleutel")
    print(f"AFM-kantoren weggeschreven: {len(kantoren)}")

    if vervallen:
        db.upsert("kantoren", vervallen_rijen(vervallen), "sleutel")
        print(f"uit het register verdwenen, op inactief gezet: {len(vervallen)}")

    if overige:
        db.upsert("kantoren", overige_rijen(overige), "sleutel")
        print(f"kantoren zonder Wta-vergunning weggeschreven: {len(overige)}")

    status = 0
    bekend = in_register | {k["afm_nummer"] for k in vervallen}
    weg = te_deactiveren(db_afm, bekend)
    actief_in_db = sum(1 for rij in db_afm if rij.get("actief"))
    if weg and not afm_register.export_lijkt_compleet(len(kantoren), actief_in_db):
        # Een seed die ineens een tiende korter is dan wat de database actief
        # heeft, is eerder kapot dan dat de AFM een tiende van de markt intrekt.
        # Dan liever niets uitzetten en rood worden dan een massale intrekking
        # op de site.
        print(
            f"::error::de seed telt {len(kantoren)} AFM-kantoren, de database had er "
            f"{actief_in_db} actief; {len(weg)} kantoren blijven daarom actief tot "
            "iemand de seed heeft nagekeken"
        )
        status = 1
    elif weg:
        for rij in weg:
            print(f"  niet meer in het register, op inactief gezet: {rij['afm_nummer']} {rij['naam']}")
        db.bijwerken(
            "kantoren",
            f"id=in.({','.join(str(rij['id']) for rij in weg)})",
            {"actief": False, "oob_vergunning": False, "wta_vergunning": False},
        )

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
        f"\nklaar — {len(kantoren) + len(vervallen) + len(overige)} kantoren in de "
        f"database ({aantal_oob} met OOB-vergunning, {len(vervallen)} vervallen, "
        f"{len(overige)} zonder Wta-vergunning)"
    )
    return status


if __name__ == "__main__":
    raise SystemExit(main(offline="--offline" in sys.argv))
