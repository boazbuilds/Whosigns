"""Laadt een kleine, herkenbare steekproef zorginstellingen in de database.

Doel: iets echts te bekijken hebben zodra de website er is. Voor Fase 2
("klik-machine") zijn 13 herkenbare organisaties mét meerdere boekjaren een
veel bruikbaardere basis om feedback op te geven dan een lege database of
6.000 onbekende namen — je ziet meteen relatieduur en wisselingen.

Dit is bewust een handmatige lijst, geen bulk-import (die komt verderop in
Fase 1, met de dekkingsstrategie uit adapters/digimv.md). Bekende, grote
ziekenhuizen zijn gekozen omdat lezers ze herkennen en omdat ze vrijwel altijd
een echte controleverklaring hebben (geen samenstellingsverklaring).

Organisaties staan op **KvK-nummer**, niet op naam+plaats: de bron schrijft
namen en plaatsen per boekjaar anders (zie adapters/digimv.py).

Draaien:
    python3 pipeline/laad_proefdata.py

Vereist SUPABASE_URL en SUPABASE_SERVICE_ROLE_KEY als omgevingsvariabelen
(gezet door de GitHub Action; zie .github/workflows/proefdata.yml).
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent / "adapters"))
sys.path.insert(0, str(Path(__file__).resolve().parent / "extractie"))

from digimv import OUDSTE_BOEKJAAR, verwerk_organisatie  # noqa: E402
from kantoor_match import bouw_index, laad_kantoren  # noqa: E402
from supabase_client import Supabase, SupabaseFout  # noqa: E402

# Nieuwste eerst, zodat een afgebroken run altijd de meest actuele jaren heeft.
BOEKJAREN = list(range(2024, OUDSTE_BOEKJAAR - 1, -1))
BRON_URL = "https://digimv13.desan.nl/archive/search"

# (zoekterm om de kandidatenlijst te beperken, KvK-nummer als echte sleutel)
ORGANISATIES = [
    ("HagaZiekenhuis", "27268552"),
    ("Catharina Ziekenhuis", "41087385"),
    ("Maasstad Ziekenhuis", "24299846"),
    ("Bravis ziekenhuis", "62350080"),
    ("Flevoziekenhuis", "41023790"),
    ("IJsselland Ziekenhuis", "41128994"),
    ("Wilhelmina Ziekenhuis Assen", "41017323"),
    ("Sint Antonius Ziekenhuis", "41177415"),
    ("Laurentius Ziekenhuis", "41066359"),
    ("Albert Schweitzer Ziekenhuis", "23091362"),
    ("Jansdal", "41035024"),
    ("Gelderse Vallei", "41049860"),
    ("Rode Kruis Ziekenhuis", "41222777"),
]


def main() -> int:
    try:
        db = Supabase()
    except SupabaseFout as fout:
        print(fout)
        return 1

    kantoor_index = bouw_index(laad_kantoren())
    kantoor_id_per_nummer = {
        rij["afm_nummer"]: rij["id"]
        for rij in db.selecteer("kantoren", "select=id,afm_nummer")
    }
    if not kantoor_id_per_nummer:
        print("Geen kantoren in de database — draai eerst de Pipeline-workflow.")
        return 1

    bron = db.invoegen(
        "bronnen",
        {"bron_type": "digimv", "url": BRON_URL, "betrouwbaarheid": "publiek"},
    )
    print(f"bron geregistreerd (id {bron['id']})\n")

    opdrachten_geladen = 0
    # Sleutel op KvK, niet op naam: de bron schrijft de naam per boekjaar anders
    # ("Stichting Flevoziekenhuis" vs. "Flevoziekenhuis (Stichting)"), waardoor
    # groeperen op naam één organisatie in tweeën zou splitsen — en dus een
    # wisseling zou verbergen.
    per_organisatie: dict[str, dict] = {}

    for zoekterm, kvk in ORGANISATIES:
        print(f"{zoekterm} (KvK {kvk})")
        organisatie_id = None

        for boekjaar in BOEKJAREN:
            resultaat = verwerk_organisatie(zoekterm, kvk, boekjaar, kantoor_index)
            if not resultaat:
                continue

            kantoor_id = kantoor_id_per_nummer.get(resultaat["kantoor"]["afm_nummer"])
            if kantoor_id is None:
                print(f"  {boekjaar}: kantoor {resultaat['kantoor']['naam']} "
                      f"niet in de database")
                continue

            if organisatie_id is None:
                organisatie = db.upsert_met_id(
                    "organisaties",
                    {
                        "kvk_nummer": resultaat["kvk_nummer"],
                        "naam": resultaat["naam"],
                        "sector": "zorg",
                        "gemeente": resultaat["plaats"],
                    },
                    "kvk_nummer",
                )
                organisatie_id = organisatie["id"]

            db.upsert_met_id(
                "opdrachten",
                {
                    "organisatie_id": organisatie_id,
                    "kantoor_id": kantoor_id,
                    "boekjaar": boekjaar,
                    "type_opdracht": "wettelijke_controle",
                    "oordeel": resultaat["oordeel"],
                    "continuiteitsonzekerheid": resultaat["continuiteitsonzekerheid"],
                    "bron_id": bron["id"],
                },
                "organisatie_id,boekjaar,type_opdracht",
            )
            opdrachten_geladen += 1
            regel = per_organisatie.setdefault(kvk, {"naam": resultaat["naam"], "jaren": []})
            regel["jaren"].append(
                (boekjaar, resultaat["kantoor"]["naam"], resultaat["oordeel"])
            )
            print(f"  {boekjaar}: {resultaat['kantoor']['naam']} "
                  f"({resultaat['oordeel']})")
        print()

    print(f"=== {len(per_organisatie)} organisaties, {opdrachten_geladen} opdrachten ===\n")
    wisselingen = 0
    for regel in per_organisatie.values():
        jaren = regel["jaren"]
        kantoren = {k for _, k, _ in jaren}
        wissel = "  ← WISSELING" if len(kantoren) > 1 else ""
        if len(kantoren) > 1:
            wisselingen += 1
        print(f"{regel['naam']} ({len(jaren)} boekjaren){wissel}")
        for boekjaar, kantoor, oordeel in sorted(jaren):
            print(f"    {boekjaar}  {kantoor:42s} {oordeel}")
    print(f"\n{wisselingen} organisaties wisselden van accountant in deze periode.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
