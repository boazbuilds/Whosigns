"""Bewaarde OCR-teksten opnieuw nakijken met de kantorenlijst van nu.

Draaien vanuit de repo-root:

    python3 pipeline/nakijk_ocr.py                  # droogloop: alleen tellen
    python3 pipeline/nakijk_ocr.py --schrijf        # rijen bijschrijven
    python3 pipeline/nakijk_ocr.py --boekjaren 2019 # één jaar

Waarom dit bestaat
------------------
De zorgoogst leest per organisatie de verklaring-pdf en gooit de pdf daarna
weg; alleen van gescande documenten blijft de gelezen tekst bewaard in
pipeline/oogst/ocr/ (zie oogst_zorg.sh). Een organisatie waar toen geen
kantoor uit kwam is afgeschreven als "bekeken" — en bekeken betekent nooit
meer.

Maar de kantorenlijst groeit. Boekjaar 2019 en 2020 zijn geoogst met 35
kantoren in seed/kantoren_overig.csv; op 12-8-2026 waren het er 55, plus zeven
nieuwe aliassen in seed/kantoor_alias.csv — juist gevonden dóór die mislukte
gevallen na te lezen. Elke naam die toen onbekend was en nu in de seed staat,
is een verklaring die alsnog leesbaar is zonder één download of één minuut
OCR: de tekst ligt er al.

Dit script loopt de bewaarde teksten langs voor organisaties die nog geen
regel in pipeline/oogst/zorg_<jaar>.csv hebben, haalt ze door exact dezelfde
`analyseer()` als de oogst zelf, en schrijft wat nu wél een vastgesteld
kantoor oplevert als extra rapportregels bij. Die gaan daarna met de gewone
knop "Zorgoogst inladen" de database in — zelfde route, zelfde controles.

Wat dit script bewust níét doet
-------------------------------
- Niets verwijderen of overschrijven: het schrijft alleen regels bíj.
- Niet gokken: dezelfde drempels als de oogst (soort=controle én een naam op
  een ondertekeningsplek). Twee documenten van dezelfde organisatie die elkaar
  tegenspreken leveren géén rij maar een melding.
- Niet aan een boekjaar komen waarvan de oogst nú draait: de oogst kopieert
  zijn eigen rapport over de repo-kopie heen (oogst_zorg.sh, bewaar), dus
  bijschrijven zou daar stilletjes verloren gaan. Welk jaar draait staat niet
  in een statusbestand; het staat wél in /proc, dus daar kijken we.
"""

import argparse
import csv
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent / "adapters"))
sys.path.insert(0, str(Path(__file__).resolve().parent / "extractie"))

import digimv_archief  # noqa: E402
from digimv import schoon_naam, schoon_plaats  # noqa: E402
from kantoor_match import bouw_index, laad_kantoren  # noqa: E402
from verklaring import analyseer  # noqa: E402

CACHE = Path(__file__).resolve().parent / ".cache"
OOGST = Path(__file__).resolve().parent / "oogst"

RAPPORT_KOLOMMEN = [
    "kvk", "naam", "plaats", "boekjaar", "kantoor", "kantoor_sleutel",
    "afm_nummer", "type_opdracht", "oordeel", "grond_beperking",
    "continuiteitsonzekerheid",
]


def ontleed_bestandsnaam(naam: str) -> tuple[int, str] | None:
    """`2019_01087507_3375.pdf.ocr.txt` -> (2019, "01087507"), anders None.

    Het KvK-nummer blijft een string: voorloopnullen zijn betekenisvol en de
    rapporten en populatielijsten schrijven ze ook zo.
    """
    if not naam.endswith(".pdf.ocr.txt"):
        return None
    delen = naam[: -len(".pdf.ocr.txt")].split("_")
    if len(delen) != 3 or not all(d.isdigit() for d in delen):
        return None
    jaar = int(delen[0])
    if not 1990 <= jaar <= 2035:
        return None
    return jaar, delen[1]


def lees_bewaarde_tekst(pad: Path) -> str | None:
    """De tekst achter de bewaarkop, of None als het bestand er niet uitziet
    zoals _bewaar_ocr (extractie/verklaring.py) hem schrijft.

    De kop zelf valideren kan hier niet — die bevat de bestandsgrootte van een
    pdf die allang is opgeruimd. Dat hij er stáát is genoeg: het scheidt een
    bewaarde lezing van een willekeurig tekstbestand.
    """
    try:
        inhoud = pad.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None
    kop, scheiding, tekst = inhoud.partition("\n")
    if not scheiding or not kop.startswith("# whosigns-ocr"):
        return None
    return tekst if tekst.strip() else None


def rij_uit_analyse(kvk: str, naam: str, plaats: str, boekjaar: int,
                    resultaat: dict) -> dict | None:
    """Eén rapportrij, of None als de analyse niet aan de oogst-drempels komt.

    De vertaalslag is dezelfde als in laad_zorg.py: een controleverklaring
    zonder vast te stellen voorwerp heet "controle_onbepaald" (geen zwaarste
    type gokken), en een kantoor zonder Wta-vergunning kan geen wettelijke
    controle tekenen, dus dan is het een vrijwillige.
    """
    if resultaat.get("soort") != "controle" or not resultaat.get("kantoor"):
        return None
    kantoor = resultaat["kantoor"]
    type_opdracht = resultaat.get("opdrachttype") or "controle_onbepaald"
    if type_opdracht == "wettelijke_controle" and not kantoor.get("wta_vergunning", True):
        type_opdracht = "vrijwillige_controle"
    return {
        "kvk": kvk,
        "naam": schoon_naam(naam),
        "plaats": schoon_plaats(plaats),
        "boekjaar": str(boekjaar),
        "kantoor": kantoor["naam"],
        "kantoor_sleutel": kantoor["sleutel"],
        "afm_nummer": kantoor.get("afm_nummer") or "",
        "type_opdracht": type_opdracht,
        "oordeel": resultaat.get("oordeel") or "",
        "grond_beperking": resultaat.get("grond_beperking") or "",
        "continuiteitsonzekerheid": "ja" if resultaat.get("continuiteitsonzekerheid") else "",
    }


def verzoen(rijen: list[dict]) -> tuple[dict | None, str | None]:
    """Meerdere documenten van dezelfde organisatie: één rij, of uitleg waarom niet.

    De oogst zelf verwerkt documenten in de volgorde van digimv_archief en stopt
    bij de eerste sterke treffer. Die volgorde is hier weg — er liggen alleen nog
    losse tekstbestanden — dus kiezen op volgorde zou schijnzekerheid zijn. In
    plaats daarvan: spreken alle sterke lezingen elkaar niet tegen op kantoor,
    opdrachttype en oordeel, dan is dát de rij. Anders geen rij; liever een
    melding dan een gok die de database in gaat.
    """
    if not rijen:
        return None, None
    kernen = {
        (r["kantoor_sleutel"], r["type_opdracht"], r["oordeel"]) for r in rijen
    }
    if len(kernen) > 1:
        omschrijving = "; ".join(
            f"{r['kantoor']} ({r['type_opdracht']}, {r['oordeel'] or 'geen oordeel'})"
            for r in rijen
        )
        return None, f"documenten spreken elkaar tegen: {omschrijving}"
    return rijen[0], None


def jaren_in_bedrijf() -> set[int]:
    """Boekjaren waarvoor nú een oogst of lader draait, gelezen uit /proc.

    Er is geen statusbestand dat dit bijhoudt en het bezig-vlaggetje van
    oogst_zorg.sh draagt geen jaartal. De commandoregel van het draaiende
    proces wel: `laad_zorg.py --boekjaar N` of `oogst_zorg.sh N`.
    """
    jaren: set[int] = set()
    for cmdline in Path("/proc").glob("[0-9]*/cmdline"):
        try:
            delen = cmdline.read_bytes().split(b"\0")
        except OSError:
            continue
        tekst = [d.decode(errors="replace") for d in delen]
        for i, deel in enumerate(tekst):
            if deel.endswith("laad_zorg.py") and "--boekjaar" in tekst:
                try:
                    jaren.add(int(tekst[tekst.index("--boekjaar") + 1]))
                except (ValueError, IndexError):
                    pass
            elif deel.endswith("oogst_zorg.sh") and i + 1 < len(tekst):
                try:
                    jaren.add(int(tekst[i + 1]))
                except ValueError:
                    pass
    return jaren


def bestaande_kvks(rapport_pad: Path) -> set[str]:
    if not rapport_pad.exists():
        return set()
    with rapport_pad.open(encoding="utf-8") as bestand:
        return {rij["kvk"] for rij in csv.DictReader(bestand)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--boekjaren", type=int, nargs="+", default=[2019, 2020])
    parser.add_argument("--schrijf", action="store_true",
                        help="rijen echt bijschrijven (anders alleen tellen)")
    argumenten = parser.parse_args()

    bezet = jaren_in_bedrijf()
    index = bouw_index(laad_kantoren())
    totaal_bij = 0

    for jaar in argumenten.boekjaren:
        if jaar in bezet:
            print(f"boekjaar {jaar}: de oogst draait er nu — overgeslagen; "
                  f"draai dit opnieuw als hij klaar is")
            continue

        rapport_pad = OOGST / f"zorg_{jaar}.csv"
        al_geboekt = bestaande_kvks(rapport_pad)
        populatie = {
            o["kvk_nummer"]: o
            for o in digimv_archief.doelpopulatie(jaar, cache=CACHE)
        }

        # Alle bewaarde teksten van dit jaar, gegroepeerd per organisatie.
        per_kvk: dict[str, list[Path]] = {}
        for pad in sorted(OOGST.glob(f"ocr/{jaar}_*.pdf.ocr.txt")):
            ontleed = ontleed_bestandsnaam(pad.name)
            if ontleed is None:
                continue
            _, kvk = ontleed
            if kvk in al_geboekt:
                continue
            per_kvk.setdefault(kvk, []).append(pad)

        nieuw: list[dict] = []
        tegenstrijdig = 0
        onbekende_org = 0
        per_kantoor: Counter[str] = Counter()
        for kvk, paden in per_kvk.items():
            organisatie = populatie.get(kvk)
            if organisatie is None:
                # Wel tekst bewaard, maar de organisatie staat niet (meer) in de
                # archieflijst van dit jaar. Zonder naam en plaats is een rij
                # niet compleet; melden en overslaan.
                onbekende_org += 1
                continue
            kandidaten = []
            for pad in paden:
                tekst = lees_bewaarde_tekst(pad)
                if tekst is None:
                    continue
                rij = rij_uit_analyse(
                    kvk, organisatie["naam"], organisatie["plaats"], jaar,
                    analyseer(tekst, index),
                )
                if rij is not None:
                    kandidaten.append(rij)
            rij, reden = verzoen(kandidaten)
            if reden is not None:
                tegenstrijdig += 1
                print(f"  {jaar} {kvk} {organisatie['naam'][:40]}: {reden}")
            elif rij is not None:
                nieuw.append(rij)
                per_kantoor[rij["kantoor"]] += 1

        print(f"\nboekjaar {jaar}: {len(per_kvk)} organisaties zonder rij hebben "
              f"bewaarde tekst; {len(nieuw)} leveren nu een kantoor op"
              + (f", {tegenstrijdig} tegenstrijdig" if tegenstrijdig else "")
              + (f", {onbekende_org} niet in de archieflijst" if onbekende_org else ""))
        for naam, aantal in per_kantoor.most_common():
            print(f"  {aantal:3d}  {naam}")

        if argumenten.schrijf and nieuw:
            with rapport_pad.open("a", newline="", encoding="utf-8") as bestand:
                schrijver = csv.DictWriter(bestand, fieldnames=RAPPORT_KOLOMMEN)
                schrijver.writerows(nieuw)
            print(f"  {len(nieuw)} rijen bijgeschreven in {rapport_pad}")
        totaal_bij += len(nieuw)

    if not argumenten.schrijf:
        print(f"\ndroogloop: er is niets geschreven; met --schrijf komen er "
              f"{totaal_bij} rijen bij")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
