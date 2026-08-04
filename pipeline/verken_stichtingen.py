"""Meet of de goededoelensector via het CBF te oogsten is — zonder LLM.

Draaien vanuit de repo-root:

    python3 pipeline/verken_stichtingen.py dekking 2024      # is er een jaarverslag?
    python3 pipeline/verken_stichtingen.py extractie 2024 40 # komt het kantoor eruit?
    python3 pipeline/verken_stichtingen.py koppeling         # CBF ↔ ANBI op RSIN
    python3 pipeline/verken_stichtingen.py oogst 2024        # welke kantoren missen we?
    python3 pipeline/verken_stichtingen.py wisselingen 2023 2024   # wie wisselde?

Dit is het zusje van `valideer_extractie.py` (dat hetzelfde doet voor de zorg): een
herhaalbare meting die de cijfers in `docs/bronverkenning-stichtingen.md` reproduceert.
Pdf's worden gecachet in `pipeline/.cache/` (niet in git).

De maat die telt bij `extractie` is de laatste regel: hoeveel controleverklaringen we
aan een AFM-vergunninghouder konden koppelen. Dat percentage blijft in deze sector
bewust onder de 100: een flink deel van de goede doelen laat vrijwillig controleren
door een kantoor zónder Wta-vergunning (dat mag, want er is geen wettelijke
controleplicht). Zulke kantoren staan terecht niet in het AFM-register — zie de
bronverkenning voor wat dat voor het datamodel betekent.
"""

import collections
import csv
import os
import sys
import tempfile
import urllib.error
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "adapters"))
sys.path.insert(0, str(Path(__file__).resolve().parent / "extractie"))

import anbi  # noqa: E402
import cbf  # noqa: E402
from kantoor_match import bouw_index, laad_kantoren  # noqa: E402
from verklaring import analyseer, pdf_naar_tekst  # noqa: E402

CACHE = Path(__file__).resolve().parent / ".cache"
WERKERS = 5


def _bestandsnaam(naam: str, boekjaar: int) -> Path:
    veilig = "".join(c if c.isalnum() else "_" for c in naam)[:60]
    return CACHE / f"cbf_{boekjaar}_{veilig}.pdf"


def _steekproef(organisaties: list[dict], maximum: int) -> list[dict]:
    """Gespreide steekproef; de eerste N zijn alfabetisch geclusterd."""
    stap = max(1, len(organisaties) // maximum)
    return organisaties[::stap][:maximum]


def dekking(boekjaar: int) -> int:
    """Voor hoeveel erkende goede doelen staat er een jaarverslag klaar?"""
    organisaties = cbf.organisaties()
    print(f"{len(organisaties)} organisaties met een actieve CBF-erkenning\n")

    def aanwezig(organisatie: dict) -> tuple[str, bool]:
        try:
            inhoud = cbf.jaarverslag(organisatie["naam"], boekjaar)
        except (urllib.error.URLError, TimeoutError):
            inhoud = None
        return organisatie["categorie"], inhoud is not None

    with ThreadPoolExecutor(max_workers=WERKERS * 2) as pool:
        uitkomsten = list(pool.map(aanwezig, organisaties))

    gevonden: collections.Counter = collections.Counter()
    totaal: collections.Counter = collections.Counter()
    for categorie, ok in uitkomsten:
        totaal[categorie] += 1
        gevonden[categorie] += ok
    print(f"boekjaar {boekjaar}: {sum(gevonden.values())}/{len(uitkomsten)} jaarverslag")
    for categorie in "ABCDE":
        baten, eis = cbf.CATEGORIE_EIS[categorie]
        print(
            f"  categorie {categorie} ({baten:16s} {eis:44s}): "
            f"{gevonden[categorie]:3d}/{totaal[categorie]:3d}"
        )
    return 0


def extractie(boekjaar: int, maximum: int) -> int:
    """Haal kantoor + oordeel uit de jaarverslagen van categorie D en E."""
    index = bouw_index(laad_kantoren())
    CACHE.mkdir(exist_ok=True)
    organisaties = [
        o for o in cbf.organisaties() if o["categorie"] in cbf.CATEGORIE_MET_CONTROLE
    ]
    steekproef = _steekproef(organisaties, maximum)
    print(f"zoeksleutels (kantoren + aliassen): {len(index)}")
    print(
        f"{len(organisaties)} goede doelen in categorie D/E "
        f"(controleverklaring is harde norm); {len(steekproef)} bekeken, "
        f"boekjaar {boekjaar}\n"
    )

    def meet(organisatie: dict) -> dict:
        pad = _bestandsnaam(organisatie["naam"], boekjaar)
        if not pad.exists():
            try:
                inhoud = cbf.jaarverslag(organisatie["naam"], boekjaar)
            except Exception as fout:  # noqa: BLE001 — bron mag falen, meting gaat door
                return {"organisatie": organisatie, "soort": f"downloadfout: {fout}"}
            if inhoud is None:
                return {"organisatie": organisatie, "soort": "geen jaarverslag"}
            pad.write_bytes(inhoud)
        resultaat = analyseer(pdf_naar_tekst(str(pad)), index)
        return {"organisatie": organisatie, **resultaat}

    with ThreadPoolExecutor(max_workers=WERKERS) as pool:
        uitkomsten = list(pool.map(meet, steekproef))

    telling: collections.Counter = collections.Counter()
    kantoren: collections.Counter = collections.Counter()
    for rij in uitkomsten:
        organisatie = rij["organisatie"]
        soort = rij.get("soort") or "geen tekstlaag"
        kantoor = rij.get("kantoor")
        telling[(soort, bool(kantoor))] += 1
        if kantoor:
            kantoren[kantoor["naam"]] += 1
        vlag = "!" if rij.get("continuiteitsonzekerheid") else " "
        print(
            f"{'✓' if kantoor else '✗'}{vlag} {organisatie['categorie']} "
            f"{organisatie['naam'][:34]:36s} {soort[:14]:15s} "
            f"{str(rij.get('oordeel') or ''):13s} "
            f"{kantoor['naam'][:34] if kantoor else '— ' + str(rij.get('reden'))}"
        )

    print("\nsoort verklaring × kantoor gevonden:")
    for (soort, ok), aantal in sorted(telling.items()):
        print(f"  {soort:20s} {'gevonden' if ok else 'GEEN':9s} {aantal:3d}")
    print("\nkantoren:")
    for naam, aantal in kantoren.most_common():
        print(f"  {aantal:3d}× {naam}")

    totaal = sum(a for (s, _), a in telling.items() if s == "controle")
    raak = sum(a for (s, g), a in telling.items() if s == "controle" and g)
    if totaal:
        print(
            f"\nCONTROLEVERKLARINGEN: {raak}/{totaal} = {100 * raak // totaal}% "
            "herleid tot een AFM-vergunninghouder"
        )
    return 0


def oogst(boekjaar: int, maximum: int = 0) -> int:
    """Welke kantoornamen tekenen deze verklaringen die wij nog niet kennen?

    Loopt de hele categorie D/E langs, en verzamelt bij elke misser de
    kantoorkandidaten uit de tekst. De uitvoer (gesorteerd op hoe vaak een naam
    voorkomt, met bij elke naam een voorbeeldorganisatie) is de bewijsbasis voor
    `seed/kantoren_overig.csv`. Nakijken met de hand blijft nodig: het patroon vist
    ook wel eens een kostenpost of een commissie op.

    Slaat de pdf's niet op — 295 jaarverslagen is ruim een gigabyte.
    """
    index = bouw_index(laad_kantoren())
    organisaties = [
        o for o in cbf.organisaties() if o["categorie"] in cbf.CATEGORIE_MET_CONTROLE
    ]
    if maximum:
        organisaties = _steekproef(organisaties, maximum)
    print(f"{len(organisaties)} goede doelen in categorie D/E, boekjaar {boekjaar}")
    print("(pdf's worden niet bewaard)\n", flush=True)

    def meet(organisatie: dict) -> dict:
        try:
            inhoud = cbf.jaarverslag(organisatie["naam"], boekjaar)
        except Exception as fout:  # noqa: BLE001 — bron mag falen, oogst gaat door
            return {"naam": organisatie["naam"], "status": f"downloadfout: {fout}"}
        if inhoud is None:
            return {"naam": organisatie["naam"], "status": "geen jaarverslag"}
        # mkstemp geeft ook een open bestandsdescriptor terug; die meteen sluiten,
        # anders lekt er één per gedownload verslag (295 per oogst).
        descriptor, tijdelijk = tempfile.mkstemp(suffix=".pdf")
        os.close(descriptor)
        pad = Path(tijdelijk)
        try:
            pad.write_bytes(inhoud)
            resultaat = analyseer(pdf_naar_tekst(str(pad)), index)
        finally:
            pad.unlink(missing_ok=True)
        return {
            "naam": organisatie["naam"],
            "status": "ok",
            "soort": resultaat.get("soort"),
            "kantoor": (resultaat.get("kantoor") or {}).get("naam"),
            "wta_kenmerk": resultaat.get("wta_kenmerk"),
            "kandidaten": resultaat.get("kandidaten") or [],
        }

    with ThreadPoolExecutor(max_workers=WERKERS) as pool:
        uitkomsten = []
        for teller, rij in enumerate(pool.map(meet, organisaties), start=1):
            uitkomsten.append(rij)
            if teller % 25 == 0:
                gevonden = sum(1 for r in uitkomsten if r.get("kantoor"))
                print(f"--- {teller}/{len(organisaties)} | {gevonden} met kantoor ---",
                      flush=True)

    controles = [r for r in uitkomsten if r.get("soort") == "controle"]
    met_kantoor = [r for r in controles if r.get("kantoor")]
    kandidaten: collections.Counter = collections.Counter()
    voorbeeld: dict[str, str] = {}
    for rij in controles:
        if rij.get("kantoor"):
            continue
        for naam in rij["kandidaten"]:
            kandidaten[naam] += 1
            voorbeeld.setdefault(naam, rij["naam"])

    print(f"\njaarverslagen gelezen:        {sum(1 for r in uitkomsten if r['status'] == 'ok')}")
    print(f"controleverklaringen:        {len(controles)}")
    print(f"— kantoor herleid:           {len(met_kantoor)}")
    print(f"— kantoor onbekend:          {len(controles) - len(met_kantoor)}")

    # Zegt de Wta-verwijzing iets? Kruistabel als de aanname klopt dat een
    # wettelijke controle naar de Wta verwijst en een vrijwillige naar de ViO.
    kruis: collections.Counter = collections.Counter()
    for rij in controles:
        kruis[(bool(rij.get("kantoor")), bool(rij.get("wta_kenmerk")))] += 1
    print("\nkantoor herleid × verklaring verwijst naar de Wta:")
    for (heeft_kantoor, wta), aantal in sorted(kruis.items()):
        print(f"  kantoor {'ja ' if heeft_kantoor else 'nee'} | Wta "
              f"{'ja ' if wta else 'nee'} | {aantal:3d}")

    uitvoer = CACHE / f"kantoorkandidaten_{boekjaar}.csv"
    CACHE.mkdir(exist_ok=True)
    with uitvoer.open("w", newline="", encoding="utf-8") as f:
        schrijver = csv.writer(f)
        schrijver.writerow(["kandidaat", "aantal", "voorbeeldorganisatie", "boekjaar"])
        for naam, aantal in kandidaten.most_common():
            schrijver.writerow([naam, aantal, voorbeeld[naam], boekjaar])
    print(f"\nkandidaat-kantoornamen bij de missers ({len(kandidaten)} verschillende):")
    for naam, aantal in kandidaten.most_common(25):
        print(f"  {aantal:3d}× {naam}   (bijv. {voorbeeld[naam]})")
    print(f"\nvolledige lijst: {uitvoer}")
    return 0


def wisselingen(eerste: int, tweede: int) -> int:
    """Wie wisselde van accountant tussen twee boekjaren? Uit de droogloop-rapporten.

    De database heeft hiervoor `v_wisselingen`, maar dat werkt pas ná het laden. Deze
    modus vergelijkt de CSV-rapporten van twee droogloop-runs, zodat je vóór het
    laden al ziet of de sector oplevert wat we ervan verwachten — en of een
    "wisseling" niet gewoon een extractiefout is.

        python3 pipeline/laad_stichtingen.py --boekjaar 2023 --droogloop
        python3 pipeline/laad_stichtingen.py --boekjaar 2024 --droogloop
        python3 pipeline/verken_stichtingen.py wisselingen 2023 2024
    """
    def lees(boekjaar: int) -> dict[str, dict]:
        pad = CACHE / f"resultaat_stichtingen_{boekjaar}.csv"
        if not pad.exists():
            raise SystemExit(f"geen rapport voor {boekjaar}: draai eerst de droogloop ({pad})")
        with pad.open(encoding="utf-8") as f:
            # Bij hervatten wordt aangevuld; de laatste regel per organisatie telt.
            return {r["naam"]: r for r in csv.DictReader(f)}

    oud, nieuw = lees(eerste), lees(tweede)
    beide = [n for n in nieuw if n in oud]
    met_kantoor = [
        n for n in beide if oud[n]["kantoor"] and nieuw[n]["kantoor"]
    ]
    gewisseld = [n for n in met_kantoor if oud[n]["kantoor"] != nieuw[n]["kantoor"]]

    print(f"organisaties in beide rapporten:        {len(beide)}")
    print(f"met een kantoor in beide boekjaren:     {len(met_kantoor)}")
    print(f"**ander kantoor in {tweede} dan in {eerste}: {len(gewisseld)}**\n")
    for naam in sorted(gewisseld):
        print(
            f"  {naam[:34]:36} {oud[naam]['kantoor'][:30]:32} → "
            f"{nieuw[naam]['kantoor'][:30]}"
        )
    if met_kantoor:
        deel = 100 * len(gewisseld) / len(met_kantoor)
        print(f"\nwisselpercentage: {deel:.1f}% van de vergelijkbare relaties")
    return 0


def koppeling() -> int:
    """Hebben de erkende goede doelen een ANBI-beschikking (en dus een website)?"""
    print("ANBI-bestand downloaden…")
    rijen = anbi.lees(anbi.download_xml())
    op_rsin = anbi.index_op_rsin(rijen)
    organisaties = cbf.organisaties()
    gekoppeld = [o for o in organisaties if (o.get("rsinnummer") or "").zfill(9) in op_rsin]
    met_site = [
        o
        for o in gekoppeld
        if op_rsin[(o["rsinnummer"] or "").zfill(9)].get("webSite")
    ]
    print(f"actieve ANBI's in het bestand: {len(rijen)}")
    print(f"CBF-erkend en actief:          {len(organisaties)}")
    print(f"  gevonden in het ANBI-bestand op RSIN: {len(gekoppeld)}")
    print(f"  daarvan met een websiteveld:          {len(met_site)}")
    print(f"  met KvK-nummer in het CBF-register:   "
          f"{sum(1 for o in organisaties if o.get('kvknummer'))}")
    return 0


if __name__ == "__main__":
    modus = sys.argv[1] if len(sys.argv) > 1 else "dekking"
    if modus == "koppeling":
        raise SystemExit(koppeling())
    if modus == "wisselingen":
        raise SystemExit(wisselingen(int(sys.argv[2]), int(sys.argv[3])))
    jaar = int(sys.argv[2]) if len(sys.argv) > 2 else 2024
    if modus == "dekking":
        raise SystemExit(dekking(jaar))
    if modus == "extractie":
        raise SystemExit(extractie(jaar, int(sys.argv[3]) if len(sys.argv) > 3 else 40))
    if modus == "oogst":
        raise SystemExit(oogst(jaar, int(sys.argv[3]) if len(sys.argv) > 3 else 0))
    print(__doc__)
    raise SystemExit(1)
