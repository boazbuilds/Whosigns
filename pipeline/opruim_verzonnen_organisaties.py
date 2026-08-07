"""Organisaties die nooit hebben bestaan uit de database halen.

    python3 pipeline/opruim_verzonnen_organisaties.py            # alleen melden
    python3 pipeline/opruim_verzonnen_organisaties.py --opruimen # ook weghalen

Waarom dit bestaat, en waarom het los staat van de laders.

De zin waarmee raadsstukken worden gelezen liet de organisatienaam over een kop
heen lopen. Een stuk van de gemeente Den Haag zet "Ons oordeel" als kopje boven
de verklaring en noemt de jaarrekening al in de regel ervóór; de naam werd dan
"Gemeente Den Haag Ons oordeel Wij hebben de jaarrekening 2016 van de gemeente
Den Haag". Dat is geen organisatie maar een stuk zin, en hij staat in de
database naast de échte gemeente Den Haag — mét een accountant eronder, dus op
de site ziet hij eruit als een gewone controleopdracht.

De leesregel is inmiddels gerepareerd (zie adapters/raadsinformatie.py), maar
dat haalt niets weg wat er al staat: de lader voegt organisaties toe en werkt
opdrachten bij, en verwijdert nooit. Een herstart van de bron laat de verzonnen
rijen dus gewoon staan. Vandaar dit losse script.

Twee regels die het voorzichtig houden:

1.  **Melden is de standaard.** Zonder --opruimen wordt er niets aangeraakt; je
    krijgt de lijst te zien en kunt hem nalopen. Weghalen is onomkeerbaar, dus
    dat hoort een aparte handeling te zijn.

2.  **Alleen wat aantoonbaar een stuk zin is.** Een naam met "wij hebben", "ons
    oordeel", "jaarrekening" of "jaarstukken" erin kan geen organisatienaam
    zijn. Namen die alléén een jaartal bevatten zijn twijfelgevallen — die
    worden apart gemeld en nooit automatisch weggehaald, want "Stichting
    Rotterdam 2018" zou echt kunnen bestaan. Gokken is hier erger dan laten
    staan.

Een organisatie mét KvK-nummer blijft altijd staan: dat nummer komt uit een
register en dan is de rij ergens aan gekoppeld.
"""

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from supabase_client import Supabase, SupabaseFout  # noqa: E402

# Woorden die alleen in een zin voorkomen, nooit in een naam.
ZINSFLARD = re.compile(
    r"\bwij\s+hebben\b|\bzij\s+hebben\b|\bons\s+oordeel\b|\boordeel\b|"
    r"\bjaarrekening\b|\bjaarstukken\b|\bgecontroleerd\b|\bhierna\b",
    re.I,
)

# Zwakker signaal: een jaartal in de naam. Wel melden, niet weghalen.
JAARTAL = re.compile(r"\b20[0-2]\d\b")


def beoordeel(naam: str) -> str:
    """'zin', 'twijfel' of 'goed'."""
    if ZINSFLARD.search(naam or ""):
        return "zin"
    if JAARTAL.search(naam or ""):
        return "twijfel"
    return "goed"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--opruimen",
        action="store_true",
        help="de gevonden rijen ook echt weghalen (zonder dit vlaggetje: alleen melden)",
    )
    argumenten = parser.parse_args()

    try:
        db = Supabase()
    except SupabaseFout as fout:
        print(fout)
        return 1

    organisaties = db.selecteer_alles(
        "organisaties", "select=id,naam,kvk_nummer,sector"
    )
    print(f"{len(organisaties)} organisaties bekeken\n")

    zin, twijfel = [], []
    for rij in organisaties:
        # Een KvK-nummer komt uit een register; die rij is ergens aan gekoppeld.
        if (rij.get("kvk_nummer") or "").strip():
            continue
        oordeel = beoordeel(rij.get("naam") or "")
        if oordeel == "zin":
            zin.append(rij)
        elif oordeel == "twijfel":
            twijfel.append(rij)

    if twijfel:
        print(f"--- {len(twijfel)} namen mét een jaartal, ter beoordeling ---")
        print("Deze blijven staan; een jaartal alleen bewijst niets.\n")
        for rij in twijfel:
            print(f"  [{rij['id']}] {rij['sector']}: {rij['naam'][:96]}")
        print()

    if not zin:
        print("Geen verzonnen organisaties gevonden.")
        return 0

    print(f"--- {len(zin)} namen die een stuk zin zijn ---")
    for rij in zin:
        print(f"  [{rij['id']}] {rij['sector']}: {rij['naam'][:96]}")

    if not argumenten.opruimen:
        print(
            f"\nNiets aangeraakt. Draai opnieuw met --opruimen om deze {len(zin)} "
            "organisaties en hun opdrachten weg te halen."
        )
        return 0

    # Eerst de opdrachten, dan de organisatie: andersom houdt een verwijzing naar
    # een rij die er niet meer is.
    opdrachten = 0
    for rij in zin:
        bestaand = db.selecteer_alles(
            "opdrachten", f"select=id&organisatie_id=eq.{rij['id']}"
        )
        opdrachten += len(bestaand)
        if bestaand:
            db.verwijderen("opdrachten", f"organisatie_id=eq.{rij['id']}")
        db.verwijderen("organisaties", f"id=eq.{rij['id']}")

    print(f"\n{len(zin)} organisaties en {opdrachten} opdrachten weggehaald.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
