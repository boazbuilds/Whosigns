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
    python3 pipeline/laad_raadsinformatie.py --vervang

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

Waarom `--vervang` bestaat
--------------------------
De naam-extractie is na de eerste volledige lading (6-8-2026, 3.940 opdrachten)
vier keer verbeterd: de naam mag niet meer over een kop heen lopen, een
herhaalde verklaring houdt de vermelding mét handtekeningblok, en de
matchsleutel herkent de plaatsstaart nu ook zonder spatie. Elke verbetering
levert schónere namen op — maar een blinde herdraai zet die schone namen als
nieuwe organisaties naast de oude verhaspelde, want de upsert-sleutel is de
organisatie en die matcht dan niet. Gemeten op 11-8-2026: er stonden ~195
naamfragmenten te veel in sector overheid ("…Utrechtte Soest", "…('de
vennootschap')" als organisatienaam).

`--vervang` herleest daarom eerst de volledige bron met de huidige leesregels.
Elke verklaring die opnieuw wordt gezien krijgt door de upsert
(merge-duplicates) vanzelf het nieuwe bron_id; wat er ná de doorloop nog aan
een oud raadsinformatie-bron_id hangt is dus precies wat alleen de oude
leesregels zagen, en dát wordt gewist. Tot slot gaan de organisaties weg die
daardoor nergens meer aan hangen — alleen die zonder KvK-nummer en zonder
resterende opdrachten, gunningen of signalen, zodat een organisatie uit een
register of met geschiedenis uit een andere bron nooit mee wordt gegrepen.

Die volgorde — eerst laden, dan pas wissen — is bewust: crasht de run
halverwege, dan is er niets verwijderd en draai je hem gewoon opnieuw. En is de
doorloop afgekapt op --maximum, dan wordt er óók niets gewist, want wat niet
herlezen is kan niet voor verouderd doorgaan. De bron is klein genoeg (21.339
documenten, een half uur) om dit per run volledig te doen.

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
    parser.add_argument(
        "--vervang", action="store_true",
        help="wis eerst de eerdere raadsinformatie-uitkomst en laad opnieuw "
        "(zie de toelichting bovenin dit bestand)",
    )
    argumenten = parser.parse_args()
    if argumenten.vervang and argumenten.droogloop:
        print("--vervang en --droogloop gaan niet samen: vervangen raakt de database.")
        return 1

    index = bouw_index(laad_kantoren(), laad_aliassen(), laad_overige_kantoren())

    db = None
    bron_id = None
    kantoor_id_per_sleutel: dict[str, int] = {}
    org_per_naam: dict[str, list[dict]] = {}
    org_per_streng: dict[str, list[dict]] = {}
    kvk_per_id: dict[int, str | None] = {}
    geraakt: set[int] = set()
    oude_bronnen: list[int] = []
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
            kvk_per_id[rij["id"]] = rij.get("kvk_nummer")
            org_per_naam.setdefault(normaliseer(rij["naam"]), []).append(rij)
            # Tweede index op de strengere sleutel: zie matchsleutel() in de
            # adapter. Alleen gebruiken als hij naar precies één organisatie
            # wijst — anders is samenvoegen een gok.
            org_per_streng.setdefault(
                raadsinformatie.matchsleutel(rij["naam"]), []
            ).append(rij)

        if argumenten.vervang:
            # Nog niets wissen — alleen onthouden wat er nu staat. De upsert
            # werkt met resolution=merge-duplicates, dus elke verklaring die de
            # verbeterde leesregels opnieuw opleveren krijgt vanzelf het nieuwe
            # bron_id. Wat er ná de volledige doorloop nog aan een oud bron_id
            # hangt, is dus precies de uitkomst die de oude leesregels te veel
            # zagen — en pas dán wordt er gewist. Crasht de run halverwege, dan
            # is er niets verwijderd en draai je hem gewoon opnieuw.
            oude_bronnen = [
                rij["id"]
                for rij in db.selecteer_alles("bronnen", "select=id,bron_type")
                if rij["bron_type"] == "raadsinformatie"
            ]
            for oude_bron in oude_bronnen:
                geraakt.update(
                    rij["organisatie_id"]
                    for rij in db.selecteer_alles(
                        "opdrachten",
                        f"select=id,organisatie_id&bron_id=eq.{oude_bron}",
                    )
                )
            print(
                f"vervang: {len(oude_bronnen)} eerdere ladingen gevonden, "
                f"{len(geraakt)} organisaties; opruiming volgt na de doorloop",
                flush=True,
            )

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

    if db is not None and argumenten.vervang:
        if documenten >= argumenten.maximum:
            # De doorloop is afgekapt op --maximum, dus een deel van de bron is
            # niet herlezen. Wat daar nog aan oude bron_id's hangt is dan geen
            # verouderde uitkomst maar gewoon niet-bezocht werk. Niets wissen.
            print(
                f"vervang: doorloop afgekapt op {argumenten.maximum} documenten; "
                "de oude uitkomst blijft staan. Draai zonder krappe --maximum."
            )
        else:
            # Alles wat de verbeterde leesregels opnieuw zagen draagt nu het
            # nieuwe bron_id (merge-duplicates). De rest is de oude uitkomst.
            gewist = 0
            for oude_bron in oude_bronnen:
                rijen = db.selecteer_alles(
                    "opdrachten", f"select=id&bron_id=eq.{oude_bron}"
                )
                if not rijen:
                    continue
                db.verwijderen("opdrachten", f"bron_id=eq.{oude_bron}")
                gewist += len(rijen)
            # Wezen: organisaties die alleen voor zo'n gewiste rij bestonden.
            # Alleen zonder KvK-nummer (mét nummer komt ze uit een register) en
            # zonder resterende opdrachten, gunningen of signalen.
            met_rij: set[int] = set()
            for tabel in ("opdrachten", "gunningen", "signalen"):
                met_rij.update(
                    rij["organisatie_id"]
                    for rij in db.selecteer_alles(tabel, "select=organisatie_id")
                )
            wezen = [
                organisatie_id
                for organisatie_id in sorted(geraakt)
                if organisatie_id not in met_rij
                and not kvk_per_id.get(organisatie_id)
            ]
            for organisatie_id in wezen:
                db.verwijderen("organisaties", f"id=eq.{organisatie_id}")
            print(
                f"vervang: {gewist} verouderde opdrachten gewist, "
                f"{len(wezen)} organisaties zonder resterende rijen opgeruimd"
            )

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
