"""Meet hoe goed we de kantoornaam uit zorgverklaringen halen — zonder LLM.

Draaien vanuit de repo-root:
    python3 pipeline/valideer_extractie.py            # standaard: 'ziekenhuis', 2023
    python3 pipeline/valideer_extractie.py stichting 2023 40

Downloadt een steekproef verklaring-pdf's uit het DigiMV-archief, analyseert ze en
rapporteert de trefkans, uitgesplitst naar soort verklaring. De maat die telt is de
laatste regel: het percentage CONTROLEverklaringen dat aan een AFM-vergunninghouder
is gekoppeld — alleen die zijn wettelijke controles.

Pdf's worden gecachet in pipeline/.cache/ (niet in git) zodat herhaald draaien de
bron niet opnieuw belast.
"""

import collections
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "adapters"))
sys.path.insert(0, str(Path(__file__).resolve().parent / "extractie"))

import digimv_archief  # noqa: E402
from kantoor_match import bouw_index, laad_kantoren  # noqa: E402
from verklaring import analyseer, pdf_naar_tekst  # noqa: E402

CACHE = Path(__file__).resolve().parent / ".cache"


def main(zoekterm: str = "ziekenhuis", boekjaar: int = 2023, maximum: int = 15) -> int:
    CACHE.mkdir(exist_ok=True)
    index = bouw_index(laad_kantoren())
    print(f"zoeksleutels (kantoren + aliassen): {len(index)}")
    print(f"zoeken: '{zoekterm}', boekjaar {boekjaar}, max {maximum} organisaties\n")

    organisaties = digimv_archief.zoek(organisatie=zoekterm, boekjaar=boekjaar)
    kandidaten = [
        (org, docs[0])
        for org in organisaties
        if (docs := digimv_archief.verklaringen(org))
    ]
    if not kandidaten:
        print("geen verklaringen gevonden voor deze zoekterm")
        return 1

    # Gespreide steekproef in plaats van de eerste N (die zijn alfabetisch geclusterd).
    stap = max(1, len(kandidaten) // maximum)
    steekproef = kandidaten[::stap][:maximum]
    print(f"{len(kandidaten)} organisaties met een verklaring; {len(steekproef)} bekeken\n")

    telling: collections.Counter = collections.Counter()
    for org, doc in steekproef:
        pad = CACHE / f"{boekjaar}_{org['externalOrganizationId']}_{doc['id']}.pdf"
        if not pad.exists():
            try:
                pad.write_bytes(digimv_archief.haal_document(doc, boekjaar))
            except Exception as fout:  # noqa: BLE001 — bron mag falen, meting gaat door
                print(f"  downloadfout {org['name'][:38]}: {fout}")
                continue

        resultaat = analyseer(pdf_naar_tekst(str(pad)), index)
        soort = resultaat["soort"] or "geen tekstlaag"
        telling[(soort, bool(resultaat["kantoor"]))] += 1
        kantoor = (
            resultaat["kantoor"]["naam"][:34]
            if resultaat["kantoor"]
            else f"— {resultaat['reden']}"
        )
        vlag = "!" if resultaat["continuiteitsonzekerheid"] else " "
        print(
            f"{'✓' if resultaat['kantoor'] else '✗'}{vlag} {org['name'][:38]:38s} "
            f"{soort:14s} {str(resultaat['oordeel'] or ''):16s} {kantoor}"
        )

    print("\nsoort verklaring × kantoor gevonden:")
    for (soort, gevonden), aantal in sorted(telling.items()):
        print(f"  {soort:16s} {'gevonden' if gevonden else 'GEEN':9s} {aantal:3d}")

    totaal = sum(a for (s, _), a in telling.items() if s == "controle")
    raak = sum(a for (s, g), a in telling.items() if s == "controle" and g)
    if totaal:
        print(f"\nCONTROLEVERKLARINGEN: {raak}/{totaal} = {100 * raak // totaal}% herleid")
    return 0


if __name__ == "__main__":
    zoekterm = sys.argv[1] if len(sys.argv) > 1 else "ziekenhuis"
    jaar = int(sys.argv[2]) if len(sys.argv) > 2 else 2023
    maximum = int(sys.argv[3]) if len(sys.argv) > 3 else 15
    raise SystemExit(main(zoekterm, jaar, maximum))
