"""Aanbestede accountantsdiensten uit TED -> tabel `gunningen`.

Gemeenten, provincies, waterschappen, veiligheidsregio's en onderwijsbesturen
besteden hun accountantscontrole Europees aan. De gunning noemt opdrachtgever,
kantoor en datum. Vindplaats en leesregels: adapters/tenderned.py.

Draaien:
    python3 pipeline/laad_gunningen.py --droogloop
    python3 pipeline/laad_gunningen.py --vanaf 20240101

Drie keuzes die het gedrag bepalen:

1.  **Een gunning is geen opdracht.** Het is een benoeming vooraf, voor
    doorgaans vier jaar; of die controle er kwam en met welk oordeel staat er
    niet in. Daarom een eigen tabel (migratie 20260804180000) en niet
    `opdrachten` — anders zou de database vier boekjaren controle beweren die
    niemand heeft waargenomen.

2.  **De kantorenlijst is het filter.** De CPV-oudercode die nodig is om de
    gemeenten te vangen, sleept ook WOZ-software, salarisadministratie en
    organisatieadvies mee. In plaats van op de titel te raden leggen we elke
    winnaar langs het AFM-register en de lijst kantoren zonder Wta-vergunning.
    Wat daar niet in staat, is geen accountantskantoor. Wat afvalt komt in het
    rapport, zodat een échte accountant die wij nog niet kenden opvalt in
    plaats van stilletjes te verdwijnen.

3.  **Opdrachtgevers zijn nieuwe organisaties.** Gemeenten en waterschappen
    staan nog nergens in deze database. Ze krijgen sector "overheid" en geen
    KvK-nummer (TED noemt dat niet), en worden op genormaliseerde naam herkend
    zodat dezelfde gemeente niet twee keer ontstaat.
"""

import argparse
import time
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent / "adapters"))
sys.path.insert(0, str(Path(__file__).resolve().parent / "extractie"))

import tenderned  # noqa: E402
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


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--droogloop", action="store_true")
    parser.add_argument("--vanaf", default="20160101", help="publicatiedatum vanaf (JJJJMMDD)")
    parser.add_argument("--tot", default="", help="publicatiedatum tot en met (JJJJMMDD)")
    parser.add_argument(
        "--geen-xml",
        action="store_true",
        help="sla de XML-route voor oudere berichten over (sneller, veel minder data)",
    )
    argumenten = parser.parse_args()

    print(f"TED raadplegen vanaf {argumenten.vanaf} ...", flush=True)
    try:
        berichten = tenderned.zoek(vanaf=argumenten.vanaf, tot=argumenten.tot or None)
    except Exception as fout:  # noqa: BLE001 — bron mag falen, dan stoppen we netjes
        print(f"TED niet bereikbaar: {fout}")
        return 1
    regels = tenderned.gunningen_uit(berichten)
    print(f"{len(berichten)} gunningsberichten, {len(regels)} regels met een winnaar", flush=True)

    # Berichten van vóór eForms dragen geen winner-name in het zoekantwoord.
    # Dat is niet een handjevol randgevallen maar de hele periode 2016-2023,
    # waarin juist de meeste gemeenten hun accountant hebben aanbesteed. Voor
    # die berichten halen we het XML-bericht op, waar de winnaar wél in staat.
    # Eén verzoek per bericht, dus alleen voor wat anders niets zou opleveren.
    open_staand = tenderned.berichten_zonder_winnaar(berichten)
    if open_staand and not argumenten.geen_xml:
        print(f"{len(open_staand)} berichten zonder winnaar in het zoekantwoord; "
              f"XML erbij halen ...", flush=True)
        mislukt = 0
        for teller, (nummer, koper) in enumerate(open_staand, 1):
            try:
                xml = tenderned.bericht_xml(nummer)
            except Exception:  # noqa: BLE001 — één bericht mag falen
                mislukt += 1
                continue
            regels.extend(tenderned.gunningen_uit_xml(xml, nummer, koper))
            if teller % 100 == 0:
                print(f"  {teller}/{len(open_staand)} — {len(regels)} regels", flush=True)
            time.sleep(0.2)
        print(f"na de XML-route: {len(regels)} regels met een winnaar "
              f"({mislukt} berichten onbereikbaar)", flush=True)

    # Het filter: alleen winnaars die een accountantskantoor blijken te zijn.
    # `overige` erbij, want een gemeente kan ook aan een kantoor zonder
    # Wta-vergunning gunnen (dat mag voor andere diensten dan de controle).
    index = bouw_index(laad_kantoren(), laad_aliassen(), laad_overige_kantoren())

    db = None
    kantoor_id_per_sleutel: dict[str, int] = {}
    org_per_naam: dict[str, list[dict]] = {}
    bron_id = None
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
        for rij in db.selecteer_alles("organisaties", "select=id,naam,kvk_nummer"):
            org_per_naam.setdefault(normaliseer(rij["naam"]), []).append(rij)
        bron_id = db.invoegen(
            "bronnen",
            {
                "bron_type": "tenderned",
                "url": "https://ted.europa.eu/",
                "betrouwbaarheid": "publiek",
            },
        )["id"]

    CACHE.mkdir(exist_ok=True)
    rapport_pad = CACHE / "resultaat_gunningen.csv"
    rapport = rapport_pad.open("w", newline="", encoding="utf-8")
    schrijver = csv.writer(rapport)
    schrijver.writerow(
        ["opdrachtgever", "winnaar", "kantoor", "gunningsdatum", "status", "publicatienummer", "url"]
    )

    telling: dict[str, int] = {}
    geen_kantoor: dict[str, int] = {}
    for regel in regels:
        treffer = zoek_kantoor(regel["winnaar"], index)
        # Een zwakke treffer is een naam die ergens in de tekst stond maar niet
        # als ondertekenaar; bij een winnaarsveld van één naam is dat onderscheid
        # betekenisloos, dus die accepteren we hier wel.
        kantoor = treffer["kantoor"] if treffer else None
        if kantoor is None:
            telling["geen kantoor"] = telling.get("geen kantoor", 0) + 1
            geen_kantoor[regel["winnaar"]] = geen_kantoor.get(regel["winnaar"], 0) + 1
            schrijver.writerow(
                [regel["opdrachtgever"], regel["winnaar"], "", regel["gunningsdatum"],
                 "geen accountantskantoor", regel["publicatienummer"], regel["url"]]
            )
            continue

        opdrachtgever = tenderned.schoon_opdrachtgever(regel["opdrachtgever"])
        telling["gunning"] = telling.get("gunning", 0) + 1
        schrijver.writerow(
            [opdrachtgever, regel["winnaar"], kantoor["naam"], regel["gunningsdatum"],
             "gunning", regel["publicatienummer"], regel["url"]]
        )

        if db is None:
            continue

        kantoor_id = kantoor_id_per_sleutel.get(kantoor["sleutel"])
        if kantoor_id is None:
            print(f"  LET OP: {kantoor['naam']} staat niet in de database — draai laad_kantoren.py")
            continue

        sleutel = normaliseer(opdrachtgever)
        kandidaten = org_per_naam.get(sleutel, [])
        if kandidaten:
            org = kandidaten[0]
        else:
            org = db.invoegen(
                "organisaties",
                {"naam": opdrachtgever, "kvk_nummer": None, "sector": SECTOR},
            )
            org_per_naam.setdefault(sleutel, []).append(org)
            telling["nieuwe organisatie"] = telling.get("nieuwe organisatie", 0) + 1

        db.upsert(
            "gunningen",
            [
                {
                    "organisatie_id": org["id"],
                    "kantoor_id": kantoor_id,
                    "gunningsdatum": regel["gunningsdatum"],
                    "publicatienummer": regel["publicatienummer"],
                    "titel": regel["titel"],
                    "bron_id": bron_id,
                }
            ],
            "publicatienummer,organisatie_id,kantoor_id",
        )

    rapport.close()
    print(f"\nUitkomst: {telling}")
    if geen_kantoor:
        # Deze lijst is het nuttigste deel van het rapport: staat hier een naam
        # die wél een accountantskantoor is, dan hoort die in
        # seed/kantoren_overig.csv en levert een volgende run hem alsnog op.
        print("\nWinnaars die geen accountantskantoor bleken (top 12):")
        for naam, aantal in sorted(geen_kantoor.items(), key=lambda kv: -kv[1])[:12]:
            print(f"  {aantal:>3}x  {naam}")
    print(f"\nRapport: {rapport_pad}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
