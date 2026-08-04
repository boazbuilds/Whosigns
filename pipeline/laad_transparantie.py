"""OOB-cliëntenlijsten uit transparantieverslagen -> opdrachten in de database.

De zes kantoren met OOB-vergunning moeten jaarlijks publiceren voor welke
organisaties van openbaar belang zij wettelijke controles verrichtten
(EU-verordening 537/2014, artikel 13). Dat is de enige openbare vindplaats van
de accountant van banken, verzekeraars en beursfondsen — ASML, ABN AMRO en
Adyen staan nergens anders. Vindplaatsen en leesregels: adapters/transparantie.py
en seed/transparantieverslagen.csv.

Draaien:
    python3 pipeline/laad_transparantie.py             # alles uit de seed-lijst
    python3 pipeline/laad_transparantie.py --droogloop # alleen het CSV-rapport

Twee keuzes die het gedrag bepalen:

1.  **Boekjaar.** Een verslag over kantoorboekjaar 2024/2025 beschrijft
    controles die grotendeels jaarrekeningen over 2024 betreffen; een
    kalenderjaarverslag 2024 (BDO) betreft vooral jaarrekeningen over 2023.
    Die vertaling staat per verslag in de seed-CSV. Ze is een benadering —
    een cliënt met een gebroken boekjaar kan er een jaar naast zitten — en
    daarom geldt keuze 2.

2.  **Bestaande rijen winnen.** Een organisatie die al een opdracht voor dat
    boekjaar heeft (uit DigiMV, het CBF of de dVi — bronnen mét oordeel en
    per-jaar-precisie) wordt hier overgeslagen. Het transparantieverslag vult
    alleen aan wat nergens anders staat. Zo kan deze lader nooit een
    preciezere bron overschrijven, hoe vaak hij ook draait.

Nieuwe organisaties krijgen sector "OOB" en geen KvK-nummer: de verslagen
noemen alleen namen. Bestaande organisaties worden op genormaliseerde naam
herkend (een corporatie uit de dVi-lading die ook in de BDO-lijst staat,
wordt dus niet gedupliceerd). Is een naam niet eenduidig aan één bestaande
organisatie te koppelen, dan gaat het geval naar de review-queue — nooit
stil gokken.
"""

import argparse
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent / "adapters"))
sys.path.insert(0, str(Path(__file__).resolve().parent / "extractie"))

import transparantie  # noqa: E402
from kantoor_match import normaliseer  # noqa: E402
from supabase_client import Supabase, SupabaseFout  # noqa: E402
from verklaring import pdf_naar_tekst  # noqa: E402

SEED = Path(__file__).resolve().parent / "seed" / "transparantieverslagen.csv"
CACHE = Path(__file__).resolve().parent / ".cache"


def verslagen() -> list[dict]:
    with SEED.open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--droogloop", action="store_true")
    argumenten = parser.parse_args()

    db = None
    kantoor_id_per_sleutel: dict[str, int] = {}
    org_per_naam: dict[str, list[dict]] = {}
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
        # Alle bestaande organisaties één keer ophalen en op genormaliseerde
        # naam indexeren: zo herkennen we "Stichting Acantus" uit de dVi-lading
        # en maken we er geen tweede rij zonder KvK-nummer naast.
        for rij in db.selecteer_alles("organisaties", "select=id,naam,kvk_nummer"):
            org_per_naam.setdefault(normaliseer(rij["naam"]), []).append(rij)

    CACHE.mkdir(exist_ok=True)
    rapport_pad = CACHE / "resultaat_transparantie.csv"
    rapport = rapport_pad.open("w", newline="", encoding="utf-8")
    schrijver = csv.writer(rapport)
    schrijver.writerow(["kantoor", "boekjaar", "organisatie", "status"])

    for verslag in verslagen():
        naam_kort = verslag["kantoor"].split()[0]
        boekjaar = int(verslag["boekjaar"])
        pdf_pad = CACHE / f"transparantie_{verslag['afm_nummer']}_{verslag['verslagperiode'].replace('/', '-')}.pdf"
        try:
            transparantie.haal_verslag(verslag["url"], pdf_pad)
        except Exception as fout:  # noqa: BLE001 — bron mag falen, volgende verslag
            print(f"{naam_kort} {verslag['verslagperiode']}: download mislukt: {fout}")
            continue

        namen, afgekeurd = transparantie.namen_uit_verslag(
            pdf_naar_tekst(str(pdf_pad)), verslag["kop"]
        )
        print(
            f"{naam_kort} {verslag['verslagperiode']} -> boekjaar {boekjaar}: "
            f"{len(namen)} cliënten ({len(afgekeurd)} regels afgekeurd)",
            flush=True,
        )
        for regel in afgekeurd:
            schrijver.writerow([naam_kort, boekjaar, regel, "afgekeurd"])

        if db is None:
            for naam in namen:
                schrijver.writerow([naam_kort, boekjaar, naam, "droogloop"])
            continue

        kantoor_id = kantoor_id_per_sleutel.get(verslag["afm_nummer"])
        if kantoor_id is None:
            print(f"  LET OP: kantoor {verslag['afm_nummer']} niet in de database")
            continue
        bron = db.invoegen(
            "bronnen",
            {
                "bron_type": "transparantieverslag",
                "url": verslag["url"],
                "betrouwbaarheid": "publiek",
            },
        )

        nieuw = bestaand = overgeslagen = 0
        for naam in namen:
            sleutel = normaliseer(naam)
            kandidaten = org_per_naam.get(sleutel, [])
            if len(kandidaten) > 1:
                # Twee organisaties met dezelfde naam: een mens moet kiezen.
                if not db.bestaat(
                    "review_queue",
                    "soort=eq.naam_match&status=eq.open"
                    f"&payload->>organisatie=eq.{naam}&payload->>boekjaar=eq.{boekjaar}",
                ):
                    db.invoegen(
                        "review_queue",
                        {
                            "soort": "naam_match",
                            "payload": {
                                "bron": "transparantieverslag",
                                "organisatie": naam,
                                "boekjaar": boekjaar,
                                "kantoor": verslag["kantoor"],
                                "vindplaats": verslag["url"],
                            },
                        },
                    )
                schrijver.writerow([naam_kort, boekjaar, naam, "review (naam dubbel)"])
                continue
            if kandidaten:
                org = kandidaten[0]
            else:
                org = db.invoegen(
                    "organisaties",
                    {"naam": naam, "sector": "OOB", "kvk_nummer": None},
                )
                org_per_naam.setdefault(sleutel, []).append(org)
                nieuw += 1

            # Bestaande rijen winnen: DigiMV/CBF/dVi weten het oordeel en het
            # precieze boekjaar, het transparantieverslag alleen de relatie.
            if db.bestaat(
                "opdrachten",
                f"organisatie_id=eq.{org['id']}&boekjaar=eq.{boekjaar}"
                "&type_opdracht=eq.wettelijke_controle",
            ):
                overgeslagen += 1
                schrijver.writerow([naam_kort, boekjaar, naam, "al bekend"])
                continue
            db.upsert_met_id(
                "opdrachten",
                {
                    "organisatie_id": org["id"],
                    "kantoor_id": kantoor_id,
                    "boekjaar": boekjaar,
                    "type_opdracht": "wettelijke_controle",
                    "bron_id": bron["id"],
                },
                "organisatie_id,boekjaar,type_opdracht",
            )
            bestaand += 1
            schrijver.writerow([naam_kort, boekjaar, naam, "opdracht"])

        print(
            f"  {bestaand} opdrachten geschreven, {nieuw} nieuwe organisaties, "
            f"{overgeslagen} al bekend uit een preciezere bron",
            flush=True,
        )

    rapport.close()
    print(f"\nRapport: {rapport_pad}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
