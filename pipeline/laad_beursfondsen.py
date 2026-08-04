"""Jaarverslagen van beursfondsen uit het AFM-register -> opdrachten.

Uitgevende instellingen deponeren hun jaarlijkse financiële verslaggeving bij
de AFM; het openbare register (terug tot boekjaar 2006) is daarmee een
centrale vindplaats van controleverklaringen van beursfondsen. Uit elk
gedeponeerd jaarverslag halen we de verklaring, het oordeel en het
ondertekenende kantoor — met dezelfde leesregels als voor de CBF-verslagen
(extractie/verklaring.py). Vindplaatsen en leesregels van het register zelf:
adapters/afm_verslaggeving.py.

Draaien:
    python3 pipeline/laad_beursfondsen.py --droogloop --boekjaren 2016 --limiet 25
    python3 pipeline/laad_beursfondsen.py --boekjaren 2020-2025

Drie keuzes die het gedrag bepalen:

1.  **Batch per boekjaren.** Eén boekjaar is ~150-270 documenten van elk
    5-30 MB; alles in één keer is tientallen gigabytes. De workflow draait
    daarom per bereik (--boekjaren), en elk document wordt na het uitlezen
    weggegooid — alleen de uitgelezen tekst blijft in de cache, zodat een
    herstart niets opnieuw downloadt.

2.  **Bestaande rijen winnen.** Een organisatie die voor dat boekjaar al een
    opdracht heeft (bijvoorbeeld uit een transparantieverslag) wordt
    overgeslagen; deze bron vult alleen aan wat nergens anders staat. De
    winst zit vooral in de boekjaren vóór 2019, waar geen enkele andere bron
    komt.

3.  **Nooit stil gokken.** Niet elk fonds heeft een Nederlandse accountant
    (HAL Trust tekent bij PricewaterhouseCoopers Bermuda, gemeten). Een
    verklaring zonder match op het kantorenregister gaat met de gevonden
    kandidaat-namen naar de review-wachtrij.
"""

import argparse
import csv
import re
import sys
import time
import urllib.parse
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent / "adapters"))
sys.path.insert(0, str(Path(__file__).resolve().parent / "extractie"))

import afm_verslaggeving  # noqa: E402
import verklaring  # noqa: E402
from kantoor_match import bouw_index, laad_kantoren, normaliseer  # noqa: E402
from supabase_client import Supabase, SupabaseFout  # noqa: E402

CACHE = Path(__file__).resolve().parent / ".cache"

# Het register wisselt door de jaren heen van spelling: "ABN AMRO Bank N.V."
# én "ABN AMRO Bank NV". normaliseer() maakt daar "n v" respectievelijk "nv"
# van, en dan lijken het twee organisaties. Voor het herkennen van
# organisaties trekken we gespatieerde rechtsvormafkortingen daarom samen.
_LOSSE_AFKORTING = re.compile(r"\b(n v|b v|u a|s a|s e|c v)\b")


def orgsleutel(naam: str) -> str:
    return _LOSSE_AFKORTING.sub(lambda m: m.group(1).replace(" ", ""), normaliseer(naam))


def boekjaar_bereik(tekst: str) -> tuple[int, int]:
    if tekst.strip().lower() == "alle":
        return (1900, 2100)
    delen = tekst.split("-")
    eerste = int(delen[0])
    laatste = int(delen[1]) if len(delen) > 1 else eerste
    return (eerste, laatste)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--droogloop", action="store_true")
    parser.add_argument(
        "--boekjaren",
        default="2020-2025",
        help='bereik zoals "2016", "2006-2012" of "alle" (standaard 2020-2025)',
    )
    parser.add_argument("--limiet", type=int, default=0, help="alleen de eerste N (bemonstering)")
    parser.add_argument("--werkers", type=int, default=4)
    argumenten = parser.parse_args()
    eerste, laatste = boekjaar_bereik(argumenten.boekjaren)

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
            org_per_naam.setdefault(orgsleutel(rij["naam"]), []).append(rij)
        bron_id = db.invoegen(
            "bronnen",
            {
                "bron_type": "afm_verslaggeving",
                "url": afm_verslaggeving.REGISTER,
                "betrouwbaarheid": "publiek",
            },
        )["id"]

    kantoor_index = bouw_index(laad_kantoren())

    print("Register doorbladeren ...", flush=True)
    alle = afm_verslaggeving.deponeringen()
    jaarlijks = afm_verslaggeving.jaarlijkse(alle)
    te_doen = [
        rij
        for rij in jaarlijks
        if rij["boekjaar"].isdigit() and eerste <= int(rij["boekjaar"]) <= laatste
    ]
    te_doen.sort(key=lambda rij: rij["boekjaar"], reverse=True)
    if argumenten.limiet:
        te_doen = te_doen[: argumenten.limiet]
    print(
        f"{len(alle)} deponeringen, {len(jaarlijks)} jaarlijks, "
        f"{len(te_doen)} in boekjaren {eerste}-{laatste}",
        flush=True,
    )

    CACHE.mkdir(exist_ok=True)
    rapport_pad = CACHE / "resultaat_beursfondsen.csv"
    rapport = rapport_pad.open("w", newline="", encoding="utf-8")
    schrijver = csv.writer(rapport)
    schrijver.writerow(
        ["instelling", "boekjaar", "deponering", "status", "kantoor", "oordeel", "toelichting"]
    )

    def lees_deponering(rij: dict) -> tuple[dict, dict]:
        """Tekst ophalen (cache of download) en de verklaring analyseren."""
        tekst_pad = CACHE / f"fv_{rij['id']}.txt"
        try:
            if tekst_pad.exists():
                tekst = tekst_pad.read_text(encoding="utf-8")
            else:
                detail = afm_verslaggeving.haal_detail(rij["id"])
                link = afm_verslaggeving.document_link(detail)
                if link is None:
                    return rij, {"status": "afgekeurd", "reden": "geen document bij deponering"}
                tijdelijk = CACHE / f"fv_{rij['id']}.tmp"
                tijdelijk.write_bytes(afm_verslaggeving._haal(link[1]))
                tekst = afm_verslaggeving.tekst_uit_document(tijdelijk)
                # Alleen de tekst bewaren: de documenten zelf zijn samen
                # tientallen gigabytes, de teksten een paar honderd megabyte.
                # Een vrijwel lege uitkomst (scan waar ook OCR niets van
                # maakte) niet cachen, zodat een latere run het opnieuw
                # probeert in plaats van het lege resultaat te hergebruiken.
                tijdelijk.unlink()
                if len(tekst) >= 200:
                    tekst_pad.write_text(tekst, encoding="utf-8")
        except Exception as fout:  # noqa: BLE001 — één deponering mag falen
            return rij, {"status": "fout", "reden": str(fout)[:200]}

        uitkomst = verklaring.analyseer(tekst, kantoor_index)
        if uitkomst["kantoor"]:
            return rij, {
                "status": "opdracht",
                "kantoor": uitkomst["kantoor"],
                "oordeel": uitkomst["oordeel"],
                "grond_beperking": uitkomst["grond_beperking"],
                "continuiteitsonzekerheid": uitkomst["continuiteitsonzekerheid"],
            }
        if uitkomst["soort"] == "controle":
            return rij, {
                "status": "review",
                "kandidaten": uitkomst["kandidaten"],
                "oordeel": uitkomst["oordeel"],
                "reden": uitkomst.get("reden") or "",
            }
        return rij, {"status": "afgekeurd", "reden": uitkomst.get("reden") or "geen verklaring gevonden"}

    telling: dict[str, int] = {}
    per_kantoor: dict[str, int] = {}
    begin = time.time()
    with ThreadPoolExecutor(max_workers=argumenten.werkers) as pool:
        for teller, (rij, resultaat) in enumerate(pool.map(lees_deponering, te_doen), start=1):
            status = resultaat["status"]
            telling[status] = telling.get(status, 0) + 1
            if teller % 25 == 0:
                print(
                    f"--- {teller}/{len(te_doen)} | "
                    f"{telling.get('opdracht', 0)} opdrachten | "
                    f"{telling.get('review', 0)} review | "
                    f"{(time.time() - begin) / 60:.1f} min ---",
                    flush=True,
                )

            kantoor = resultaat.get("kantoor") or {}
            boekjaar = int(rij["boekjaar"])
            schrijver.writerow(
                [
                    rij["instelling"], boekjaar, rij["id"], status,
                    kantoor.get("naam", ""), resultaat.get("oordeel", "") or "",
                    resultaat.get("reden", "")
                    or ", ".join(resultaat.get("kandidaten", [])[:3]),
                ]
            )
            rapport.flush()
            if status == "opdracht":
                per_kantoor[kantoor["naam"]] = per_kantoor.get(kantoor["naam"], 0) + 1

            if db is None or status not in ("opdracht", "review"):
                continue

            sleutel = orgsleutel(rij["instelling"])
            kandidaten = org_per_naam.get(sleutel, [])
            if len(kandidaten) > 1:
                schrijver.writerow(
                    [rij["instelling"], boekjaar, rij["id"], "review (naam dubbel)", "", "", ""]
                )
                continue
            if kandidaten:
                org = kandidaten[0]
            else:
                org = db.invoegen(
                    "organisaties",
                    {"naam": rij["instelling"], "sector": "OOB", "kvk_nummer": None},
                )
                org_per_naam.setdefault(sleutel, []).append(org)

            if status == "review":
                # Verklaring zonder kantoor-match (buitenlandse accountant of
                # onherkenbare ondertekening): mens laten kijken, niet gokken.
                if not db.bestaat(
                    "review_queue",
                    "soort=eq.naam_match&status=eq.open"
                    f"&payload->>organisatie=eq.{urllib.parse.quote(rij['instelling'], safe='')}"
                    f"&payload->>boekjaar=eq.{boekjaar}",
                ):
                    db.invoegen(
                        "review_queue",
                        {
                            "soort": "naam_match",
                            "payload": {
                                "bron": "afm_verslaggeving",
                                "organisatie": rij["instelling"],
                                "boekjaar": boekjaar,
                                "deponering": rij["id"],
                                "kandidaten": resultaat.get("kandidaten", [])[:5],
                                "vindplaats": f"{afm_verslaggeving.REGISTER}/details?id={rij['id']}",
                            },
                        },
                    )
                continue

            # Bestaande rijen winnen: wat al uit een transparantieverslag of
            # andere bron bekend is, blijft staan; dit vult alleen aan.
            if db.bestaat(
                "opdrachten",
                f"organisatie_id=eq.{org['id']}&boekjaar=eq.{boekjaar}"
                "&type_opdracht=eq.wettelijke_controle",
            ):
                telling["al bekend"] = telling.get("al bekend", 0) + 1
                continue
            kantoor_id = kantoor_id_per_sleutel.get(kantoor.get("sleutel"))
            if kantoor_id is None:
                print(
                    f"  LET OP: kantoor {kantoor.get('naam')} niet in de database — "
                    "draai laad_kantoren.py",
                    flush=True,
                )
                continue
            db.upsert_met_id(
                "opdrachten",
                {
                    "organisatie_id": org["id"],
                    "kantoor_id": kantoor_id,
                    "boekjaar": boekjaar,
                    "type_opdracht": "wettelijke_controle",
                    "oordeel": resultaat.get("oordeel"),
                    "grond_beperking": resultaat.get("grond_beperking"),
                    "continuiteitsonzekerheid": resultaat.get("continuiteitsonzekerheid"),
                    "bron_id": bron_id,
                },
                "organisatie_id,boekjaar,type_opdracht",
            )

    rapport.close()
    print(f"\nUitkomst: {telling}")
    for naam, aantal in sorted(per_kantoor.items(), key=lambda kv: -kv[1])[:12]:
        print(f"  {aantal:>4}  {naam}")
    print(f"Rapport: {rapport_pad}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
