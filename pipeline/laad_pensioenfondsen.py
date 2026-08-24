"""Pensioenfondsen: jaarverslagen van de fondsen zelf -> opdrachten in de database.

Elk pensioenfonds publiceert zijn jaarverslag als fondsdocument op de eigen
site, inclusief de controleverklaring. De route is bewezen met het
ABP-jaarverslag 2025 (docs/bestaande-databases.md, 21-8-2026): de bestaande
extractie leest er ongewijzigd kantoor, oordeel en opdrachttype uit. Deze lader
doet dat voor elke regel in seed/pensioenfondsen.csv.

Draaien:
    python3 pipeline/laad_pensioenfondsen.py             # alles uit de seed
    python3 pipeline/laad_pensioenfondsen.py --droogloop # alleen het CSV-rapport

Spelregels, dezelfde als overal:

- **Alleen geverifieerde URL's in de seed.** Elke regel is met de hand
  gecontroleerd (HTTP 200, application/pdf) voordat hij erin ging; de lader
  gokt geen adressen.
- **Nooit gokken.** Geen betrouwbare kantoormatch -> regel in het rapport en
  op de review-queue, geen rij in de database. De tekenend accountant komt
  alleen mee als het blokoordeel gelijk is aan het documentoordeel
  (extractie/verklaring.py); leeg betekent "niet vastgesteld".
- **Bestaande rijen winnen.** Een fonds dat voor dat boekjaar al een
  wettelijke controle in de database heeft, wordt overgeslagen; herdraaien is
  dus veilig en goedkoop.
- Organisaties krijgen sector "pensioenfondsen" en geen KvK-nummer: het
  jaarverslag noemt dat niet, en een register-lookup is een aparte beslissing.
"""

import argparse
import csv
import sys
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent / "adapters"))
sys.path.insert(0, str(Path(__file__).resolve().parent / "extractie"))

from kantoor_match import bouw_index, laad_kantoren, normaliseer  # noqa: E402
from supabase_client import Supabase, SupabaseFout  # noqa: E402
from verklaring import analyseer, pdf_naar_tekst  # noqa: E402

SEED = Path(__file__).resolve().parent / "seed" / "pensioenfondsen.csv"
CACHE = Path(__file__).resolve().parent / ".cache"
KOPPEN = {"User-Agent": "Mozilla/5.0 (WhoSigns-pipeline)"}


def fondsen(seed: Path = SEED) -> list[dict]:
    with seed.open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def haal_pdf(url: str, pad: Path) -> None:
    """Downloadt één jaarverslag; wat er al ligt wordt niet opnieuw gehaald."""
    if pad.exists() and pad.stat().st_size > 100_000:
        return
    verzoek = urllib.request.Request(url, headers=KOPPEN)
    with urllib.request.urlopen(verzoek, timeout=300) as antwoord:
        pad.write_bytes(antwoord.read())


def opdracht_uit_analyse(
    analyse: dict, organisatie_id: int, kantoor_id: int, boekjaar: int, bron_id: int
) -> dict:
    """Zelfde vertaalregels als laad_zorg_rapport: leeg is null, nooit een
    lege tekst; continuïteitsonzekerheid is een echte ja/nee-bevinding."""
    return {
        "organisatie_id": organisatie_id,
        "kantoor_id": kantoor_id,
        "boekjaar": boekjaar,
        # opdrachttype None betekent: wél een controleverklaring, maar niet
        # vastgesteld waarover. Dan is "wettelijke_controle" een aanname; bij
        # een jaarverslag van een pensioenfonds is de jaarrekeningcontrole
        # echter verplicht en is de verklaring in het jaarverslag per definitie
        # die van de jaarrekening — maar dat blijft een redenering, geen
        # meting, dus we schrijven wat de extractie vond en anders
        # controle_onbepaald.
        "type_opdracht": analyse.get("opdrachttype") or "controle_onbepaald",
        "oordeel": analyse.get("oordeel") or None,
        "grond_beperking": analyse.get("grond_beperking") or None,
        "continuiteitsonzekerheid": bool(analyse.get("continuiteitsonzekerheid")),
        "tekenend_accountant": analyse.get("tekenend_accountant") or None,
        "bron_id": bron_id,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--droogloop", action="store_true")
    # Dezelfde route werkt voor elke sector met openbare jaarverslagen: geef een
    # andere seed en sectornaam mee en er verandert verder niets. De seed houdt
    # dezelfde kolommen (fonds,boekjaar,url); "fonds" is daar gewoon "de
    # organisatie waarvan dit het jaarverslag is".
    parser.add_argument("--seed", type=Path, default=SEED)
    parser.add_argument("--sector", default="pensioenfondsen")
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
        for rij in db.selecteer_alles("organisaties", "select=id,naam,kvk_nummer,sector"):
            org_per_naam.setdefault(normaliseer(rij["naam"]), []).append(rij)

    index = bouw_index(laad_kantoren())
    CACHE.mkdir(exist_ok=True)
    rapport_pad = CACHE / f"resultaat_{argumenten.sector}.csv"
    rapport = rapport_pad.open("w", newline="", encoding="utf-8")
    schrijver = csv.writer(rapport)
    schrijver.writerow(
        ["fonds", "boekjaar", "kantoor", "oordeel", "tekenend_accountant", "status"]
    )

    geschreven = overgeslagen = mislukt = 0
    for regel in fondsen(argumenten.seed):
        # "fonds" historisch; een seed van een andere sector mag "naam" gebruiken.
        fonds = (regel.get("fonds") or regel.get("naam") or "").strip()
        boekjaar = int(regel["boekjaar"])
        naamdeel = normaliseer(fonds).replace(" ", "-")[:40]
        pdf_pad = CACHE / f"jaarverslag_{naamdeel}_{boekjaar}.pdf"
        try:
            haal_pdf(regel["url"], pdf_pad)
        except Exception as fout:  # noqa: BLE001 — bron mag falen, volgende fonds
            print(f"{fonds} {boekjaar}: download mislukt: {fout}", flush=True)
            schrijver.writerow([fonds, boekjaar, "", "", "", "download mislukt"])
            mislukt += 1
            continue

        tekst = pdf_naar_tekst(str(pdf_pad))
        analyse = analyseer(tekst, index)
        kantoor = analyse.get("kantoor")
        status = "ok" if kantoor else (analyse.get("reden") or "geen kantoormatch")
        print(
            f"{fonds} {boekjaar}: "
            f"{kantoor['naam'] if kantoor else status}"
            f"{', ' + analyse['oordeel'] if analyse.get('oordeel') else ''}"
            f"{', tekenaar ' + analyse['tekenend_accountant'] if analyse.get('tekenend_accountant') else ''}",
            flush=True,
        )
        schrijver.writerow(
            [
                fonds,
                boekjaar,
                kantoor["naam"] if kantoor else "",
                analyse.get("oordeel") or "",
                analyse.get("tekenend_accountant") or "",
                "droogloop" if db is None else status,
            ]
        )
        if db is None or analyse.get("soort") != "controle":
            continue

        if kantoor is None:
            # Zelfde afspraak als de zorgoogst: een mens kijkt ernaar, wij
            # gokken niet. Kandidaten gaan mee als hint.
            if not db.bestaat(
                "review_queue",
                "soort=eq.naam_match&status=eq.open"
                f"&payload->>organisatie=eq.{urllib.parse.quote(fonds, safe='')}"
                f"&payload->>boekjaar=eq.{boekjaar}",
            ):
                db.invoegen(
                    "review_queue",
                    {
                        "soort": "naam_match",
                        "payload": {
                            "bron": "jaarverslag pensioenfonds",
                            "organisatie": fonds,
                            "boekjaar": boekjaar,
                            "kandidaten": analyse.get("kandidaten") or [],
                            "vindplaats": regel["url"],
                        },
                    },
                )
            continue

        kantoor_id = kantoor_id_per_sleutel.get(kantoor.get("sleutel"))
        if kantoor_id is None:
            print(f"  LET OP: kantoor {kantoor['naam']} niet in de database")
            continue

        sleutel = normaliseer(fonds)
        kandidaten = org_per_naam.get(sleutel, [])
        if len(kandidaten) > 1:
            print(f"  LET OP: {fonds} staat {len(kandidaten)}x in de database")
            continue
        if kandidaten:
            org = kandidaten[0]
            # Een organisatie die eerder zonder sector is aangemaakt (bijv.
            # vanuit marktonderzoek, dat alleen KvK en naam kent) hoort wel op
            # de sectorpagina. Alleen een lége sector wordt ingevuld: de seed
            # ís de sectorlijst, maar een bestaande afwijkende waarde kan een
            # bewuste keuze zijn en blijft staan.
            if not org.get("sector"):
                db.bijwerken(
                    "organisaties", f"id=eq.{org['id']}", {"sector": argumenten.sector}
                )
                org["sector"] = argumenten.sector
        else:
            org = db.invoegen(
                "organisaties",
                {"naam": fonds, "sector": argumenten.sector, "kvk_nummer": None},
            )
            org_per_naam.setdefault(sleutel, []).append(org)

        type_opdracht = analyse.get("opdrachttype") or "controle_onbepaald"
        if db.bestaat(
            "opdrachten",
            f"organisatie_id=eq.{org['id']}&boekjaar=eq.{boekjaar}"
            f"&type_opdracht=eq.{type_opdracht}",
        ):
            overgeslagen += 1
            continue
        bron = db.invoegen(
            "bronnen",
            {
                "bron_type": "jaarverslag",
                "url": regel["url"],
                "betrouwbaarheid": "publiek",
            },
        )
        db.upsert_met_id(
            "opdrachten",
            opdracht_uit_analyse(analyse, org["id"], kantoor_id, boekjaar, bron["id"]),
            "organisatie_id,boekjaar,type_opdracht",
        )
        geschreven += 1

    rapport.close()
    print(
        f"\n{geschreven} opdrachten geschreven, {overgeslagen} al bekend, "
        f"{mislukt} downloads mislukt; rapport: {rapport_pad}",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
