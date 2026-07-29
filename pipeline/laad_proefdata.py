"""Laadt een kleine, herkenbare steekproef zorginstellingen in de database.

Doel: iets echts te bekijken hebben zodra de website er is — voor Fase 2
("klik-machine") is 10 herkenbare organisaties een veel bruikbaardere basis
om feedback op te geven dan een lege database of 6.000 onbekende namen.

Dit is bewust een handmatige lijst, geen bulk-import (die komt in Fase 1
verderop, met de dekkingsstrategie uit adapters/digimv.md). Bekende, grote
ziekenhuizen zijn gekozen omdat readers ze herkennen en omdat ze vrijwel
altijd een echte controleverklaring hebben (geen samenstellingsverklaring).

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

from digimv import verwerk_organisatie  # noqa: E402
from kantoor_match import bouw_index, laad_kantoren  # noqa: E402
from supabase_client import Supabase, SupabaseFout  # noqa: E402

BOEKJAAR = 2023
BRON_URL = "https://digimv13.desan.nl/archive/search"

# (naam-fragment voor de archiefzoekfunctie, plaats — ter ontdubbeling van gelijknamige
# organisaties). Groter dan 10 gekozen zodat een enkele misser (bijv. gescande pdf)
# nog steeds op ≥ 10 geladen organisaties uitkomt.
ORGANISATIES = [
    ("HagaZiekenhuis", "'s-Gravenhage"),  # officiële plaatsnaam in het archief, niet "Den Haag"
    ("Catharina Ziekenhuis", "Eindhoven"),
    ("Maasstad Ziekenhuis", "Rotterdam"),
    ("Bravis ziekenhuis", "Roosendaal"),
    ("Flevoziekenhuis", "Almere"),
    ("IJsselland Ziekenhuis", "Capelle"),
    ("Wilhelmina Ziekenhuis Assen", "Assen"),
    ("Sint Antonius Ziekenhuis", "Nieuwegein"),
    ("Laurentius Ziekenhuis", "Roermond"),
    ("Albert Schweitzer Ziekenhuis", "Dordrecht"),
    ("Christelijk Ziekenhuis St Jansdal", "Harderwijk"),
    ("Ziekenhuis Gelderse Vallei", "Ede"),
    ("Rode Kruis Ziekenhuis", "Beverwijk"),
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

    bron = db.invoegen(
        "bronnen",
        {"bron_type": "digimv", "url": BRON_URL, "betrouwbaarheid": "publiek"},
    )
    print(f"bron geregistreerd (id {bron['id']})")

    geladen = []
    for naam_fragment, plaats in ORGANISATIES:
        print(f"\n{naam_fragment} ({plaats})")
        resultaat = verwerk_organisatie(naam_fragment, plaats, BOEKJAAR, kantoor_index)
        if not resultaat:
            continue

        kantoor_id = kantoor_id_per_nummer.get(resultaat["kantoor"]["afm_nummer"])
        if kantoor_id is None:
            print(f"  kantoor {resultaat['kantoor']['naam']} niet gevonden in Supabase "
                  f"— eerst laad_kantoren.py draaien?")
            continue

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
        db.upsert_met_id(
            "opdrachten",
            {
                "organisatie_id": organisatie["id"],
                "kantoor_id": kantoor_id,
                "boekjaar": resultaat["boekjaar"],
                "type_opdracht": "wettelijke_controle",
                "oordeel": resultaat["oordeel"],
                "continuiteitsonzekerheid": resultaat["continuiteitsonzekerheid"],
                "bron_id": bron["id"],
            },
            "organisatie_id,boekjaar,type_opdracht",
        )
        geladen.append((resultaat["naam"], resultaat["kantoor"]["naam"], resultaat["oordeel"]))
        print(f"  OK -> {resultaat['kantoor']['naam']} ({resultaat['oordeel']})")

    print(f"\n{len(geladen)} organisaties geladen:")
    for naam, kantoor, oordeel in geladen:
        print(f"  - {naam} -> {kantoor} ({oordeel})")

    if len(geladen) < 10:
        print(f"\nLet op: {len(geladen)} van de {len(ORGANISATIES)} kandidaten geladen "
              f"(< 10). Uitbreiden van ORGANISATIES kan als dat te weinig is.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
