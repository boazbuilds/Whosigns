"""Een oogstrapport van laad_zorg.py alsnog in de database zetten.

    rapport (csv)  ->  organisaties + opdrachten, precies zoals laad_zorg dat doet

Waarom dit bestaat: het dure deel van de zorgsector is het downloaden en lezen van
de verklaring-pdf's — ±24 seconden per organisatie, uren per boekjaar. Dat hoeft
niet op een GitHub-runner te gebeuren. laad_zorg.py --droogloop schrijft alles wat
de database nodig heeft naar resultaat_<boekjaar>.csv, en dit script zet zo'n
rapport er in een paar seconden in. Zo kost de inhaalslag vrijwel geen
Actions-minuten.

Gebruik (repo-root):

    python3 pipeline/laad_zorg_rapport.py pipeline/oogst/zorg_2019.csv
    python3 pipeline/laad_zorg_rapport.py pipeline/oogst/*.csv --droogloop

Zelfde spelregels als laad_zorg.py:
- organisatie-boekjaren die al een opdracht hebben worden overgeslagen
  (--herlaad vervangt ze);
- een kantoor dat niet in de database staat wordt gemeld, nooit stil geboekt;
- de bron-rij is dezelfde digimv-bron als bij de directe route.

Een rapport van vóór de kolomuitbreiding (zonder `type_opdracht`) wordt geweigerd
met een duidelijke melding: daarin ontbreekt het opdrachttype en dat gokken we
niet — de oogst opnieuw draaien is dan het antwoord.
"""

import argparse
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from laad_zorg import BRON_URL, RAPPORT_KOLOMMEN  # noqa: E402
from supabase_client import Supabase, SupabaseFout  # noqa: E402

# Wat de oogst schrijft is precies wat deze lader verwacht; één lijst dus, bij
# de schrijver vandaan. Zie de aantekening bij RAPPORT_KOLOMMEN in laad_zorg.py.
VERPLICHT = RAPPORT_KOLOMMEN


def lees_rapport(pad: Path) -> list[dict]:
    with pad.open(encoding="utf-8") as f:
        lezer = csv.DictReader(f)
        kolommen = lezer.fieldnames or []
        ontbreekt = [k for k in VERPLICHT if k not in kolommen]
        if ontbreekt:
            raise SystemExit(
                f"{pad}: kolommen {ontbreekt} ontbreken — dit rapport komt uit een "
                f"oudere laad_zorg.py. Draai de oogst opnieuw; het opdrachttype "
                f"wordt niet gegokt."
            )
        return [rij for rij in lezer if (rij.get("kvk") or "").strip()]


def opdracht_uit_rapportrij(
    rij: dict, organisatie_id: int, kantoor_id: int, bron_id: int
) -> dict:
    """Eén rapportregel als opdracht-rij voor de database.

    Losse functie omdat hier de vertaling zit van "wat de oogst opschreef" naar
    "wat de kolom toestaat", en dat is precies waar het misging.

    **Een leeg veld is geen waarde maar een ontbrekende waarde.** De kolom
    `oordeel` heeft een check-voorwaarde die alleen de vier echte oordelen
    toestaat; een lege string valt daarbuiten, en omdat de lader per rij schrijft
    laat één zo'n rij de hele lading omvallen. Dat gebeurde op 12-8-2026 bij de
    eerste run over de oogstrapporten: negentien rijen zonder oordeel (13 in
    2019, 6 in 2020, 5 in 2021 — verklaringen waarvan de OCR het oordeel niet
    prijsgaf), en de run stopte bij de eerste ervan met HTTP 400. Van de ruim
    duizend opdrachten kwamen er tachtig binnen. Null mag wél: een
    check-voorwaarde laat null altijd door.

    `continuiteitsonzekerheid` is bewust géén null bij leeg. De oogst schrijft
    daar "ja" als de verklaring een paragraaf over materiële
    continuïteitsonzekerheid bevat en anders niets; leeg betekent daar dus "die
    paragraaf staat er niet", en dat is onwaar, niet onbekend.
    """
    return {
        "organisatie_id": organisatie_id,
        "kantoor_id": kantoor_id,
        "boekjaar": int(rij["boekjaar"]),
        "type_opdracht": rij["type_opdracht"],
        "oordeel": (rij.get("oordeel") or "").strip() or None,
        "grond_beperking": (rij.get("grond_beperking") or "").strip() or None,
        "continuiteitsonzekerheid": rij.get("continuiteitsonzekerheid") == "ja",
        "bron_id": bron_id,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rapporten", nargs="+", help="een of meer resultaat-csv's")
    parser.add_argument("--droogloop", action="store_true")
    parser.add_argument("--herlaad", action="store_true")
    argumenten = parser.parse_args()

    rijen: list[dict] = []
    for pad in argumenten.rapporten:
        deel = lees_rapport(Path(pad))
        print(f"{pad}: {len(deel)} rijen")
        rijen.extend(deel)
    boekjaren = sorted({int(rij["boekjaar"]) for rij in rijen})
    print(f"samen {len(rijen)} rijen over boekjaren {boekjaren}\n")

    if argumenten.droogloop:
        per_kantoor: dict[str, int] = {}
        for rij in rijen:
            per_kantoor[rij["kantoor"]] = per_kantoor.get(rij["kantoor"], 0) + 1
        for naam, aantal in sorted(per_kantoor.items(), key=lambda p: -p[1])[:25]:
            print(f"  {aantal:5d}  {naam}")
        print("\ndroogloop: niets geschreven")
        return 0

    try:
        db = Supabase()
    except SupabaseFout as fout:
        print(fout)
        return 1

    # Op `sleutel`, niet op afm_nummer — zie laad_zorg.py: kantoren zonder
    # Wta-vergunning hebben afm_nummer NULL en vielen op nummer in één sleutel samen.
    kantoor_id_per_sleutel = {
        rij["sleutel"]: rij["id"]
        for rij in db.selecteer_alles("kantoren", "select=id,sleutel")
        if rij.get("sleutel")
    }
    if not kantoor_id_per_sleutel:
        print("Geen kantoren in de database — draai eerst de Pipeline-workflow.")
        return 1

    bron = db.invoegen(
        "bronnen",
        {"bron_type": "digimv", "url": BRON_URL, "betrouwbaarheid": "publiek"},
    )
    bron_id = bron["id"]

    # Wat er al staat, per boekjaar — zelfde hervat-regel als de directe route.
    al_geladen: dict[int, set] = {}
    for boekjaar in boekjaren:
        bestaand = db.selecteer_alles(
            "opdrachten",
            f"select=organisaties(kvk_nummer)&boekjaar=eq.{boekjaar}",
        )
        al_geladen[boekjaar] = set() if argumenten.herlaad else (
            {(r.get("organisaties") or {}).get("kvk_nummer") for r in bestaand}
            - {None}
        )
        print(f"boekjaar {boekjaar}: {len(al_geladen[boekjaar])} organisaties al geladen")

    geschreven = 0
    overgeslagen = 0
    zonder_kantoor: dict[str, int] = {}
    opgeruimd: set[tuple] = set()
    for rij in rijen:
        boekjaar = int(rij["boekjaar"])
        kvk = rij["kvk"].strip()
        if kvk in al_geladen[boekjaar]:
            overgeslagen += 1
            continue
        kantoor_id = kantoor_id_per_sleutel.get(rij["kantoor_sleutel"])
        if kantoor_id is None:
            # Niet stil overslaan: de seed-CSV is dan nieuwer dan de database.
            zonder_kantoor[rij["kantoor"]] = zonder_kantoor.get(rij["kantoor"], 0) + 1
            continue

        org_rij = db.upsert_met_id(
            "organisaties",
            {
                "kvk_nummer": kvk,
                "naam": rij["naam"],
                "sector": "zorg",
                "gemeente": rij["plaats"],
            },
            "kvk_nummer",
        )
        if argumenten.herlaad and (org_rij["id"], boekjaar) not in opgeruimd:
            # Eén keer per organisatie-boekjaar, ook als het rapport meer rijen
            # heeft: anders wist de tweede rij de eerste weer uit.
            db.verwijderen(
                "opdrachten",
                f"organisatie_id=eq.{org_rij['id']}&boekjaar=eq.{boekjaar}",
            )
            opgeruimd.add((org_rij["id"], boekjaar))
        db.upsert_met_id(
            "opdrachten",
            opdracht_uit_rapportrij(rij, org_rij["id"], kantoor_id, bron_id),
            "organisatie_id,boekjaar,type_opdracht",
        )
        geschreven += 1

    print(f"\n{geschreven} opdrachten geschreven, {overgeslagen} al aanwezig")
    for naam, aantal in zonder_kantoor.items():
        print(
            f"  LET OP: kantoor '{naam}' niet in de database ({aantal} rijen) — "
            f"draai eerst de Pipeline-workflow en dit rapport daarna opnieuw"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
