"""Controleverklaringen uit raadsstukken -> opdrachten in de database.

    Open Raadsinformatie  ->  documenten met "controleverklaring van de
                              onafhankelijke accountant"
                          ->  de zin "Wij hebben de jaarrekening JJJJ van X
                              te Y gecontroleerd"
                          ->  kantoor uit het handtekeningblok eróver
                          ->  opdracht-rij

Vindplaats en leesregels: adapters/raadsinformatie.py.

Draaien:
    python3 pipeline/laad_raadsinformatie.py --droogloop
    python3 pipeline/laad_raadsinformatie.py --maximum 5000

Drie keuzes die het gedrag bepalen:

1.  **De gecontroleerde organisatie komt uit de verklaring, niet uit de
    vindplaats.** Een gemeenteraad bespreekt ook de jaarstukken van elke
    gemeenschappelijke regeling waarin de gemeente deelneemt. Wie de
    publicerende raad als gecontroleerde partij neemt, schrijft die controles
    toe aan de verkeerde organisatie. Zie de toelichting in de adapter.

2.  **Het handtekeningblok houdt op bij de volgende verklaring.** Een
    raadsbundel zet meerdere jaarstukken achter elkaar in één pdf; zonder die
    grens vindt de matcher de accountant van de buurorganisatie. Het venster
    per verklaring komt daarom uit de adapter.

3.  **Alleen een ondertekening telt.** `zoek_kantoor` markeert een treffer als
    zwak wanneer die niet in de buurt van een datum, plaats of
    ondertekeningsformule staat — dan is de kantoornaam eerder een vermelding
    dan een handtekening. Zwakke treffers en niet-herkende namen komen in het
    rapport terecht, niet in de database.

Deze organisaties zijn overheden: gemeenten, provincies, waterschappen,
gemeenschappelijke regelingen, omgevingsdiensten, veiligheidsregio's. Ze
krijgen sector "overheid" en geen KvK-nummer (de verklaring noemt dat niet), en
worden op genormaliseerde naam herkend zodat dezelfde organisatie niet twee
keer ontstaat — ook niet naast een organisatie die al uit de TED-gunningen
kwam.

Een decentrale overheid is op grond van de Gemeentewet (of de Waterschapswet,
of de eigen gemeenschappelijke regeling) controleplichtig, dus dit zijn
wettelijke controles.
"""

import argparse
import collections
import csv
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent / "adapters"))
sys.path.insert(0, str(Path(__file__).resolve().parent / "extractie"))

import raadsinformatie  # noqa: E402
from kantoor_match import (  # noqa: E402
    bouw_index,
    laad_aliassen,
    laad_kantoren,
    laad_overige_kantoren,
    normaliseer,
    zoek_kantoor,
)
from supabase_client import Supabase, SupabaseFout  # noqa: E402

CACHE = Path(__file__).resolve().parent / ".cache"
SECTOR = "overheid"
TYPE_OPDRACHT = "wettelijke_controle"

# Namen die geen organisatie zijn maar een restant van de zin eromheen. Gemeten
# op de eerste tweehonderd documenten; zonder deze rem komen er rijen binnen
# als "onze controle" of "het onderdeel".
_GEEN_ORGANISATIE = re.compile(
    r"^(?:onze|onze\s|het\s|deze\s|die\s|welke\s|bovengenoemde\s)|"
    r"^(?:controle|jaarstukken|jaarrekening|begroting|bijlage)\b",
    re.I,
)


def bruikbaar(naam: str) -> bool:
    if len(naam) < 5 or len(naam) > 110:
        return False
    if _GEEN_ORGANISATIE.search(naam):
        return False
    # Een organisatienaam draagt minstens twee woorden of een hoofdletter.
    return bool(re.search(r"[A-ZÀ-Ý]", naam) or " " in naam)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--droogloop", action="store_true")
    parser.add_argument(
        "--maximum", type=int, default=25_000, help="hoogstens zoveel documenten lezen"
    )
    parser.add_argument(
        "--per-pagina", type=int, default=100, dest="per_pagina",
        help="documenten per verzoek aan de zoek-API",
    )
    argumenten = parser.parse_args()

    index = bouw_index(laad_kantoren(), laad_aliassen(), laad_overige_kantoren())

    db = None
    bron_id = None
    kantoor_id_per_sleutel: dict[str, int] = {}
    org_per_naam: dict[str, list[dict]] = {}
    org_per_streng: dict[str, list[dict]] = {}
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
        for rij in db.selecteer_alles("organisaties", "select=id,naam,kvk_nummer"):
            org_per_naam.setdefault(normaliseer(rij["naam"]), []).append(rij)
            # Tweede index op de strengere sleutel: zie matchsleutel() in de
            # adapter. Alleen gebruiken als hij naar precies één organisatie
            # wijst — anders is samenvoegen een gok.
            org_per_streng.setdefault(
                raadsinformatie.matchsleutel(rij["naam"]), []
            ).append(rij)
        bron = db.invoegen(
            "bronnen",
            {
                "bron_type": "raadsinformatie",
                "url": raadsinformatie.API,
                "betrouwbaarheid": "publiek",
            },
        )
        bron_id = bron["id"]

    CACHE.mkdir(exist_ok=True)
    rapport_pad = CACHE / "resultaat_raadsinformatie.csv"
    rapport = rapport_pad.open("w", newline="", encoding="utf-8")
    schrijver = csv.writer(rapport)
    schrijver.writerow(
        ["organisatie", "plaats", "boekjaar", "kantoor", "status", "document", "url"]
    )

    telling: collections.Counter = collections.Counter()
    afgekeurd: collections.Counter = collections.Counter()
    gezien: set[tuple[str, int]] = set()
    documenten = 0

    for document in raadsinformatie.documenten(
        per_pagina=argumenten.per_pagina, maximum=argumenten.maximum
    ):
        documenten += 1
        if documenten % 500 == 0:
            print(
                f"  {documenten} documenten, {telling['opdracht']} controles",
                flush=True,
            )
        tekst = raadsinformatie._plat(document.get("text"))
        for verklaring in raadsinformatie.verklaringen_uit(tekst, document):
            naam = verklaring["organisatie"]
            if not bruikbaar(naam):
                afgekeurd[naam[:60]] += 1
                telling["naam onbruikbaar"] += 1
                continue

            sleutel = (raadsinformatie.matchsleutel(naam), verklaring["boekjaar"])
            if sleutel in gezien:
                telling["al gezien"] += 1
                continue

            begin, eind = verklaring["venster"]
            treffer = zoek_kantoor(tekst[begin:eind], index)
            if treffer is None:
                status, kantoornaam = "geen kantoor", ""
            elif treffer.get("zwak"):
                status, kantoornaam = "geen ondertekening", treffer["kantoor"]["naam"]
            else:
                status, kantoornaam = "opdracht", treffer["kantoor"]["naam"]
            telling[status] += 1
            schrijver.writerow(
                [
                    naam, verklaring["plaats"], verklaring["boekjaar"], kantoornaam,
                    status, verklaring["documentnaam"], verklaring["url"],
                ]
            )
            if status != "opdracht":
                continue
            gezien.add(sleutel)

            if db is None:
                continue
            kantoor_id = kantoor_id_per_sleutel.get(treffer["kantoor"]["sleutel"])
            if kantoor_id is None:
                print(
                    f"  LET OP: {treffer['kantoor']['naam']} staat niet in de "
                    "database — draai laad_kantoren.py"
                )
                continue

            streng = raadsinformatie.matchsleutel(naam)
            kandidaten = org_per_naam.get(normaliseer(naam), [])
            if not kandidaten:
                # Koppeltekens en spaties sneuvelen in de pdf-tekst; op de
                # strengere sleutel is "Regio West-Brabant" hetzelfde als
                # "Regio WestBrabant". Alleen bij precies één treffer.
                streng_kandidaten = org_per_streng.get(streng, [])
                if len(streng_kandidaten) == 1:
                    kandidaten = streng_kandidaten
                    telling["op strenge sleutel herkend"] += 1
            if kandidaten:
                org = kandidaten[0]
            else:
                org = db.invoegen(
                    "organisaties",
                    {
                        "naam": naam,
                        "kvk_nummer": None,
                        "sector": SECTOR,
                        "gemeente": verklaring["plaats"] or None,
                    },
                )
                org_per_naam.setdefault(normaliseer(naam), []).append(org)
                org_per_streng.setdefault(streng, []).append(org)
                telling["nieuwe organisatie"] += 1

            db.upsert(
                "opdrachten",
                [
                    {
                        "organisatie_id": org["id"],
                        "kantoor_id": kantoor_id,
                        "boekjaar": verklaring["boekjaar"],
                        "type_opdracht": TYPE_OPDRACHT,
                        "bron_id": bron_id,
                    }
                ],
                "organisatie_id,boekjaar,type_opdracht",
            )

    rapport.close()
    print(f"\n{documenten} documenten gelezen")
    print(f"Uitkomst: {dict(telling)}")
    if afgekeurd:
        print("\nNamen die geen organisatie bleken (top 10):")
        for naam, aantal in afgekeurd.most_common(10):
            print(f"  {aantal:4d}x  {naam}")
    print(f"\nRapport: {rapport_pad}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
