"""Bulk-lader stichtingen/NGO's: van het CBF-register naar opdrachten in de database.

Werkwijze (de route uit docs/bronverkenning-stichtingen.md):

    CBF-register            ->  714 erkende goede doelen, met KvK-nummer en sector
      categorie D/E         ->  295 waar een controleverklaring een harde norm is
      jaarverslag-pdf       ->  static.cbf.nl/documents/<naam>/<boekjaar>/jaarverslag.pdf
      tekst                 ->  kantoornaam (AFM-lijst + kantoren zonder Wta)
      geen kantoor?         ->  review_queue met de kandidaat-namen uit de tekst
      geen verslag?         ->  optioneel de eigen website (--terugval)

Draaien:
    python3 pipeline/laad_stichtingen.py --boekjaar 2024
    python3 pipeline/laad_stichtingen.py --boekjaar 2024 --categorieen C,D,E --terugval
    python3 pipeline/laad_stichtingen.py --boekjaar 2024 --droogloop

**Eén boekjaar is bijna niets waard**: zonder een tweede jaar is er geen wisseling
te zien. Draai dus 2019 t/m 2025 (`cbf.OUDSTE_BOEKJAAR` is de ondergrens die de
bron aanhoudt).

Opties:
    --boekjaar N       welk boekjaar (= verslagjaar in de CBF-URL)
    --categorieen L    CBF-omvangcategorieën, komma's ertussen (standaard D,E:
                       daar is een controleverklaring een harde norm)
    --soorten L        welke verklaringsoorten een opdracht-rij mogen worden
                       (standaard `controle`; voor categorie C ook `beoordeling`)
    --erkenning W      actief (standaard), ingetrokken of alle. Ingetrokken
                       erkenningen hebben nog jaarverslagen bij het CBF staan
    --vanaf N          sla de eerste N organisaties over (voor het opknippen)
    --aantal N         verwerk er hoogstens N
    --rapport-json P   schrijf de tellingen als JSON naar P (voor `lus.py`)
    --terugval         zoek bij een leeg CBF-bestand ook op de eigen website
                       (ANBI-publicatieplicht); kost extra verzoeken
    --droogloop        niets naar de database schrijven, alleen een CSV-rapport
    --werkers N        hoeveel organisaties tegelijk ophalen (standaard 4)
    --herlaad          organisaties die al een opdracht hebben opnieuw beoordelen
    --bewaar-pdf       jaarverslagen in pipeline/.cache/ laten staan (standaard
                       worden ze na het lezen weggegooid: 295 verslagen is ruim 1 GB)

Idempotent: upsert op (organisatie_id, boekjaar, type_opdracht). Hervatten is
veilig — organisatie-boekjaren die al een opdracht hebben, worden overgeslagen.

`--vanaf`/`--aantal` snijden in een lijst met een vaste volgorde (`cbf.selecteer`
sorteert op KvK-nummer), zodat blok 3 volgende week nog dezelfde organisaties
betekent. Daar leunt `lus.py` op.

Opdrachttype: standaard `vrijwillige_controle`, want bij een goed doel komt de
controleplicht uit de Erkenningsregeling en niet uit Titel 9 BW. Zie
`adapters/stichtingen.py` voor de onderbouwing.
"""

import argparse
import csv
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent / "adapters"))
sys.path.insert(0, str(Path(__file__).resolve().parent / "extractie"))

import anbi  # noqa: E402
import cbf  # noqa: E402
import stichtingen  # noqa: E402
from kantoor_match import bouw_index, laad_kantoren  # noqa: E402
from supabase_client import Supabase, SupabaseFout  # noqa: E402

CACHE = Path(__file__).resolve().parent / ".cache"
SECTOR = "goede doelen"


def _websites(organisaties: list[dict]) -> dict[str, str]:
    """RSIN -> website uit het ANBI-bestand; leeg als het ophalen niet lukt."""
    try:
        rijen = anbi.lees(anbi.download_xml())
    except Exception as fout:  # noqa: BLE001 — terugval is optioneel
        print(f"ANBI-bestand niet beschikbaar ({fout}); terugval zonder websites")
        return {}
    op_rsin = anbi.index_op_rsin(rijen)
    uit = {}
    for organisatie in organisaties:
        rij = op_rsin.get((organisatie.get("rsinnummer") or "").zfill(9))
        if rij and rij.get("webSite"):
            uit[organisatie["naam"]] = rij["webSite"]
    print(f"websites uit het ANBI-bestand: {len(uit)} van {len(organisaties)}")
    return uit


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--boekjaar", type=int, default=2024)
    parser.add_argument("--categorieen", default=",".join(cbf.CATEGORIE_MET_CONTROLE))
    parser.add_argument("--soorten", default="controle")
    parser.add_argument(
        "--erkenning", default="actief", choices=("actief", "ingetrokken", "alle")
    )
    parser.add_argument("--vanaf", type=int, default=0)
    parser.add_argument("--aantal", type=int, default=0)
    parser.add_argument("--rapport-json", default="", dest="rapport_json")
    parser.add_argument("--terugval", action="store_true")
    parser.add_argument("--droogloop", action="store_true")
    parser.add_argument("--werkers", type=int, default=4)
    parser.add_argument("--herlaad", action="store_true")
    parser.add_argument("--bewaar-pdf", action="store_true", dest="bewaar_pdf")
    argumenten = parser.parse_args()
    boekjaar = argumenten.boekjaar

    if boekjaar < cbf.OUDSTE_BOEKJAAR:
        print(
            f"boekjaar {boekjaar} ligt vóór {cbf.OUDSTE_BOEKJAAR}; het CBF-archief "
            "gaat niet verder terug (gemeten: 12 treffers in 2018 tegen 514 in 2019)"
        )
        return 1

    categorieen = [c.strip().upper() for c in argumenten.categorieen.split(",") if c.strip()]
    soorten = tuple(s.strip() for s in argumenten.soorten.split(",") if s.strip())
    print(
        f"CBF-register ophalen (categorieën {', '.join(categorieen)}, "
        f"erkenning {argumenten.erkenning}, soorten {', '.join(soorten)})…",
        flush=True,
    )
    organisaties = cbf.selecteer(categorieen, argumenten.erkenning)
    print(
        f"{len(organisaties)} organisaties in de doelpopulatie; boekjaar {boekjaar}",
        flush=True,
    )
    if not organisaties:
        return 1

    werklijst = organisaties[argumenten.vanaf:]
    if argumenten.aantal:
        werklijst = werklijst[: argumenten.aantal]
    if not werklijst:
        print(f"blok begint voorbij het einde van de lijst ({argumenten.vanaf})")
        return 1
    print(
        f"blok: organisatie {argumenten.vanaf + 1} t/m "
        f"{argumenten.vanaf + len(werklijst)} van {len(organisaties)}",
        flush=True,
    )

    websites = _websites(werklijst) if argumenten.terugval else {}
    kantoor_index = bouw_index(laad_kantoren())

    db = None
    bron_id = None
    kantoor_id_per_sleutel: dict[str, int] = {}
    al_geladen: set[str] = set()
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
        # "Al geladen" alleen vragen voor de KvK-nummers van dít blok. Zonder dat
        # filter komen alle opdrachten van een boekjaar mee — inclusief de duizenden
        # zorgrijen die er niets mee te maken hebben. `selecteer_alles` pagineert dus
        # door tabellen heen waar we niets aan hebben, elke ronde opnieuw. Een
        # `in.(…)` op ten hoogste een blok is één verzoek van vijftig rijen.
        kvks = [o["kvknummer"] for o in werklijst if o.get("kvknummer")]
        if kvks and not argumenten.herlaad:
            try:
                bestaand = db.selecteer_alles(
                    "opdrachten",
                    f"select=organisaties!inner(kvk_nummer)&boekjaar=eq.{boekjaar}"
                    f"&organisaties.kvk_nummer=in.({','.join(kvks)})",
                )
            except SupabaseFout as fout:
                # Filteren op een kolom van een gekoppelde tabel vraagt om `!inner`
                # en een PostgREST dat dat aankan. Struikelt hij erover, dan is de
                # brede vraag nog altijd goed — alleen duurder. Dit mag een lus die
                # onbeheerd draait niet op zijn eerste blok laten stranden.
                print(f"  gerichte vraag mislukt ({fout}); alle opdrachten opvragen")
                bestaand = db.selecteer_alles(
                    "opdrachten",
                    f"select=organisaties(kvk_nummer)&boekjaar=eq.{boekjaar}",
                )
            al_geladen = {
                (r.get("organisaties") or {}).get("kvk_nummer") for r in bestaand
            } - {None}
        bron = db.invoegen(
            "bronnen",
            {"bron_type": "cbf", "url": cbf.REGISTER_URL, "betrouwbaarheid": "publiek"},
        )
        bron_id = bron["id"]
        print(
            f"bron {bron_id}; {len(al_geladen)} van {len(werklijst)} al geladen",
            flush=True,
        )

    te_doen = [o for o in werklijst if (o.get("kvknummer") or "") not in al_geladen]

    CACHE.mkdir(exist_ok=True)
    rapport_pad = CACHE / f"resultaat_stichtingen_{boekjaar}.csv"
    rapport = rapport_pad.open("a", newline="", encoding="utf-8")
    schrijver = csv.writer(rapport)
    if rapport.tell() == 0:
        schrijver.writerow(
            ["kvk", "naam", "categorie", "sector", "boekjaar", "status",
             "kantoor", "wta", "opdrachttype", "oordeel", "grond_beperking",
             "vindplaats"]
        )

    telling: dict[str, int] = {}
    per_kantoor: dict[str, int] = {}
    # Kandidaat-namen uit de review-gevallen, geteld. Dit is de oogst waarmee
    # seed/kantoren_overig.csv en kantoor_alias.csv groeien: een naam die vijf keer
    # langskomt is bijna altijd een echt kantoor dat we nog niet kennen.
    onbekend: dict[str, int] = {}
    begin = time.time()

    def haal_op(organisatie: dict):
        try:
            return organisatie, stichtingen.verwerk_organisatie(
                organisatie,
                boekjaar,
                kantoor_index,
                terugval=argumenten.terugval,
                website=websites.get(organisatie["naam"], ""),
                bewaar_pdf=argumenten.bewaar_pdf,
                soorten=soorten,
            )
        except Exception as fout:  # noqa: BLE001 — bron mag falen, run gaat door
            print(f"  {organisatie['naam'][:50]}: fout {fout}", flush=True)
            return organisatie, {"status": "fout", "reden": str(fout)}

    with ThreadPoolExecutor(max_workers=argumenten.werkers) as pool:
        for teller, (organisatie, resultaat) in enumerate(
            pool.map(haal_op, te_doen), start=1
        ):
            status = resultaat["status"]
            telling[status] = telling.get(status, 0) + 1
            if teller % 25 == 0:
                print(
                    f"--- {teller}/{len(te_doen)} | "
                    f"{telling.get('opdracht', 0)} opdrachten | "
                    f"{telling.get('review', 0)} review | "
                    f"{(time.time()-begin)/60:.1f} min ---",
                    flush=True,
                )

            kvk = organisatie.get("kvknummer")
            kantoor = resultaat.get("kantoor") or {}
            schrijver.writerow([
                kvk, organisatie["naam"], organisatie["categorie"],
                cbf.primaire_sector(organisatie) or "", boekjaar, status,
                kantoor.get("naam", ""),
                "" if not kantoor else ("ja" if kantoor["wta_vergunning"] else "nee"),
                resultaat.get("opdrachttype", ""), resultaat.get("oordeel", ""),
                resultaat.get("grond_beperking", "") or "",
                resultaat.get("vindplaats", resultaat.get("reden", "")),
            ])
            rapport.flush()

            if status == "opdracht":
                per_kantoor[kantoor["naam"]] = per_kantoor.get(kantoor["naam"], 0) + 1
            elif status == "review":
                for kandidaat in resultaat.get("kandidaten", [])[:3]:
                    onbekend[kandidaat] = onbekend.get(kandidaat, 0) + 1

            if db is None or not kvk:
                continue

            if status in ("opdracht", "review"):
                org_rij = db.upsert_met_id(
                    "organisaties",
                    {
                        "kvk_nummer": kvk,
                        "naam": organisatie["naam"],
                        "rechtsvorm": "stichting",
                        "sector": SECTOR,
                        "subsector": cbf.primaire_sector(organisatie),
                        "gemeente": (organisatie.get("plaats_statutair") or "").title() or None,
                        "grootteklasse": f"CBF-categorie {organisatie['categorie']}",
                    },
                    "kvk_nummer",
                )

            if status == "opdracht":
                kantoor_id = kantoor_id_per_sleutel.get(kantoor["sleutel"])
                if kantoor_id is None:
                    print(
                        f"  {organisatie['naam'][:40]}: kantoor {kantoor['naam']} staat "
                        "nog niet in de database — draai laad_kantoren.py",
                        flush=True,
                    )
                    continue
                if argumenten.herlaad:
                    db.verwijderen(
                        "opdrachten",
                        f"organisatie_id=eq.{org_rij['id']}&boekjaar=eq.{boekjaar}",
                    )
                db.upsert_met_id(
                    "opdrachten",
                    {
                        "organisatie_id": org_rij["id"],
                        "kantoor_id": kantoor_id,
                        "boekjaar": boekjaar,
                        "type_opdracht": resultaat["opdrachttype"],
                        "oordeel": resultaat["oordeel"],
                        "grond_beperking": resultaat["grond_beperking"],
                        "continuiteitsonzekerheid": resultaat["continuiteitsonzekerheid"],
                        "bron_id": bron_id,
                    },
                    "organisatie_id,boekjaar,type_opdracht",
                )
            elif status == "review":
                # Nooit stil gokken: wél een controleverklaring, maar het kantoor
                # staat in geen van beide lijsten. De kandidaat-namen uit de tekst
                # gaan mee zodat iemand het in één oogopslag kan afhandelen —
                # en zo groeit seed/kantoren_overig.csv met bewijs.
                db.invoegen(
                    "review_queue",
                    {
                        "soort": "naam_match",
                        "payload": {
                            "bron": "cbf",
                            "organisatie": organisatie["naam"],
                            "kvk_nummer": kvk,
                            "boekjaar": boekjaar,
                            "soort": resultaat.get("soort"),
                            "vindplaats": resultaat.get("vindplaats"),
                            "kandidaten": resultaat.get("kandidaten", []),
                            "oordeel": resultaat.get("oordeel"),
                        },
                    },
                )

    rapport.close()
    print(f"\n=== boekjaar {boekjaar} ({(time.time()-begin)/60:.0f} min) ===")
    for status, aantal in sorted(telling.items(), key=lambda p: -p[1]):
        print(f"  {status:14s} {aantal:4d}")
    print("\nKantoren in deze run:")
    for naam, aantal in sorted(per_kantoor.items(), key=lambda p: -p[1])[:25]:
        print(f"  {aantal:4d}  {naam}")
    print(f"\nRapport: {rapport_pad}")

    if argumenten.rapport_json:
        # Voor `lus.py`: dezelfde uitkomst, maar zonder stdout te hoeven lezen.
        # `overgeslagen` staat erbij omdat een blok dat al geladen was geen
        # mislukking is maar een geslaagde no-op.
        Path(argumenten.rapport_json).write_text(
            json.dumps(
                {
                    "boekjaar": boekjaar,
                    "categorieen": categorieen,
                    "soorten": list(soorten),
                    "erkenning": argumenten.erkenning,
                    "vanaf": argumenten.vanaf,
                    "in_blok": len(werklijst),
                    "overgeslagen": len(werklijst) - len(te_doen),
                    "minuten": round((time.time() - begin) / 60, 1),
                    "telling": telling,
                    "per_kantoor": per_kantoor,
                    "onbekende_kantoren": onbekend,
                },
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        print(f"JSON-rapport: {argumenten.rapport_json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
