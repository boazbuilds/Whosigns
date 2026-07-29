"""DigiMV-adapter: van organisatienaam naar een opdracht-rij in het kernmodel.

Combineert de eerder gebouwde bouwstenen:
    digimv_archief  -> zoeken in het archief, document ophalen
    kantoor_match   -> kantoornaam herkennen tegen de AFM-lijst
    verklaring      -> pdf -> soort, oordeel, continuïteitsonzekerheid

Deze module doet één organisatie tegelijk (`verwerk_organisatie`) — dat maakt
hem bruikbaar voor zowel een kleine handmatige lijst (zie `laad_proefdata.py`,
Fase 1 opstart) als de latere bulkverwerking vanuit de volledige dataset
(Fase 1, dekkingsstrategie in `digimv.md`).

Alleen een controleverklaring met een herkend kantoor levert een resultaat op.
Samenstellings-/beoordelingsverklaringen en onherkende kantoren geven None —
de aanroeper beslist wat daarmee gebeurt (overslaan, of naar review_queue).
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "extractie"))

import digimv_archief  # noqa: E402
from verklaring import analyseer, pdf_naar_tekst  # noqa: E402

CACHE = Path(__file__).resolve().parents[1] / ".cache"


def verwerk_organisatie(
    naam_fragment: str, plaats: str, boekjaar: int, kantoor_index: dict
) -> dict | None:
    """Zoekt de organisatie in het archief, analyseert haar controleverklaring.

    Geeft bij succes:
        {kvk_nummer, naam, plaats, boekjaar, oordeel,
         continuiteitsonzekerheid, kantoor: {...}, bron_url}
    of None met een reden (afgedrukt, niet teruggegeven — dit is bewust een
    kleine, leesbare functie; wie de reden geautomatiseerd nodig heeft
    (review_queue) kan `analyseer()` rechtstreeks aanroepen).
    """
    resultaten = digimv_archief.zoek(organisatie=naam_fragment, plaats=plaats, boekjaar=boekjaar)
    treffers = [r for r in resultaten if plaats.lower() in (r.get("town") or "").lower()]
    if not treffers:
        print(f"  geen archiefresultaat voor '{naam_fragment}' in {plaats}")
        return None

    organisatie = treffers[0]
    documenten = digimv_archief.verklaringen(organisatie)
    if not documenten:
        print(f"  geen verklaring-document voor {organisatie['name']}")
        return None

    CACHE.mkdir(exist_ok=True)
    doc = documenten[0]
    pdf_pad = CACHE / f"{boekjaar}_{organisatie['externalOrganizationId']}_{doc['id']}.pdf"
    if not pdf_pad.exists():
        pdf_pad.write_bytes(digimv_archief.haal_document(doc, boekjaar))

    resultaat = analyseer(pdf_naar_tekst(str(pdf_pad)), kantoor_index)
    if resultaat["soort"] != "controle":
        print(f"  {organisatie['name']}: geen controleverklaring ({resultaat['soort']})")
        return None
    if not resultaat["kantoor"]:
        print(f"  {organisatie['name']}: kantoor niet herkend ({resultaat['reden']})")
        return None

    return {
        "kvk_nummer": organisatie["externalOrganizationId"],
        "naam": organisatie["name"],
        "plaats": organisatie["town"],
        "boekjaar": boekjaar,
        "oordeel": resultaat["oordeel"],
        "continuiteitsonzekerheid": bool(resultaat["continuiteitsonzekerheid"]),
        "kantoor": resultaat["kantoor"],
        "bron_bestand": doc["fileName"],
    }
