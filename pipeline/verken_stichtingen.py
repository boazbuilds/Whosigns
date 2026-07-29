"""Meet of de goededoelensector via het CBF te oogsten is — zonder LLM.

Draaien vanuit de repo-root:

    python3 pipeline/verken_stichtingen.py dekking 2024      # is er een jaarverslag?
    python3 pipeline/verken_stichtingen.py extractie 2024 40 # komt het kantoor eruit?
    python3 pipeline/verken_stichtingen.py koppeling         # CBF ↔ ANBI op RSIN

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
import sys
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
    jaar = int(sys.argv[2]) if len(sys.argv) > 2 else 2024
    if modus == "dekking":
        raise SystemExit(dekking(jaar))
    if modus == "extractie":
        raise SystemExit(extractie(jaar, int(sys.argv[3]) if len(sys.argv) > 3 else 40))
    print(__doc__)
    raise SystemExit(1)
