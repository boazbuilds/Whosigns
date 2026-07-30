"""Stichtingen-adapter: van een goed doel naar een opdracht-rij in het kernmodel.

Combineert de bouwstenen zoals `digimv.py` dat voor de zorg doet:

    cbf              -> register (wie zijn het) + jaarverslag-pdf (voorspelbare URL)
    anbi_publicatie  -> terugval: het jaarstuk op de eigen site van de stichting
    kantoor_match    -> kantoornaam herkennen (AFM-lijst én kantoren zonder Wta)
    verklaring       -> tekst -> soort, oordeel, continuïteit, kantoor

Twee dingen werken hier anders dan in de zorg.

**1. Het opdrachttype is standaard `vrijwillige_controle`.** Bij een goed doel komt
de controleplicht uit norm 8.1.3 van de CBF-Erkenningsregeling en niet uit Titel 9
BW — een stichting deponeert pas bij €7,5 mln omzet uit onderneming, en donaties
zijn geen omzet uit onderneming. "Wettelijke controle" zou dus een aanname zijn.
Alleen als de verklaring zelf naar de Wet toezicht accountantsorganisaties verwijst
én het kantoor een Wta-vergunning heeft, noemen we het een wettelijke controle: dan
is er tekstueel bewijs. Gemeten: die verwijzing is zeldzaam (in de zorg 3 van 24
controleverklaringen), dus verwacht vooral `vrijwillige_controle` — en dat is
precies wat deze sector is.

**2. Een onherkend kantoor is hier niet altijd een fout.** Kantoren zonder
Wta-vergunning staan in `seed/kantoren_overig.csv`, met bewijs erbij. Wat ook daar
niet in staat, komt met de kandidaat-namen uit de tekst in de review-queue —
nooit stil gokken.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "extractie"))

import anbi_publicatie  # noqa: E402
import cbf  # noqa: E402
from kantoor_match import normaliseer  # noqa: E402
from verklaring import analyseer, pdf_naar_tekst  # noqa: E402

CACHE = Path(__file__).resolve().parents[1] / ".cache"


def _bestandsnaam(sleutel: str, boekjaar: int, achtervoegsel: str = "") -> Path:
    veilig = "".join(c if c.isalnum() else "_" for c in sleutel)[:60]
    return CACHE / f"cbf_{boekjaar}_{veilig}{achtervoegsel}.pdf"


def _opdrachttype(resultaat: dict) -> str:
    """Vaststellen in plaats van aannemen; zie de moduletoelichting."""
    kantoor = resultaat["kantoor"]
    if not kantoor.get("wta_vergunning"):
        # Zonder vergunning mág het geen wettelijke controle zijn.
        return "vrijwillige_controle"
    if resultaat.get("wta_kenmerk"):
        return "wettelijke_controle"
    return "vrijwillige_controle"


def bevat_boekjaar(tekst: str, boekjaar: int) -> bool:
    """Gaat dit stuk over het gevraagde boekjaar?

    Bij het CBF zit het verslagjaar in de URL en is dat de bron van waarheid. Op de
    eigen site van een organisatie niet: daar staan alle jaargangen door elkaar en
    de best scorende pdf bleek in de meting geregeld een oudere jaargang
    ("gewaarmerkte-jaarverslag-2023" terwijl we 2024 zochten). Zonder deze controle
    boeken we de accountant van 2023 op boekjaar 2024 — een verzonnen feit dat
    daarna niet meer van een echt feit te onderscheiden is.
    """
    genormaliseerd = normaliseer(tekst)
    return any(
        kenmerk in genormaliseerd
        for kenmerk in (
            f"31 december {boekjaar}",
            f"boekjaar {boekjaar}",
            f"jaarrekening {boekjaar}",
            f"jaarverslag {boekjaar}",
            f"december 31 {boekjaar}",
            f"financial statements {boekjaar}",
        )
    )


def _uit_tekst(tekst: str, kantoor_index: dict, vindplaats: str) -> dict | None:
    resultaat = analyseer(tekst, kantoor_index)
    if resultaat["soort"] != "controle":
        return None
    return {
        "soort": resultaat["soort"],
        "opdrachttype": _opdrachttype(resultaat) if resultaat["kantoor"] else None,
        "voorwerp": resultaat["opdrachttype"],
        "oordeel": resultaat["oordeel"],
        "continuiteitsonzekerheid": bool(resultaat["continuiteitsonzekerheid"]),
        "kantoor": resultaat["kantoor"],
        "kandidaten": resultaat["kandidaten"],
        "vindplaats": vindplaats,
    }


def verwerk_organisatie(
    organisatie: dict,
    boekjaar: int,
    kantoor_index: dict,
    terugval: bool = False,
    website: str = "",
    bewaar_pdf: bool = True,
) -> dict:
    """Eén goed doel, één boekjaar. Geeft altijd een dict met `status`.

    `status`:
      - `opdracht`      kantoor herleid; `kantoor`, `oordeel` enz. zijn gevuld
      - `review`        controleverklaring gevonden, kantoor onbekend (met `kandidaten`)
      - `geen_controle` wel een verslag, maar geen controleverklaring erin
      - `geen_verslag`  niets te vinden bij het CBF, en ook niet op de eigen site
      - `onleesbaar`    pdf zonder tekstlaag (gescand)

    `terugval=True` zoekt bij een leeg of onbruikbaar CBF-bestand ook op de eigen
    website van de organisatie (`website`, uit het ANBI-bestand). Dat kost extra
    verzoeken, dus het staat standaard uit.
    """
    naam = organisatie["naam"]
    basis = {"naam": naam, "boekjaar": boekjaar, "kvk_nummer": organisatie.get("kvknummer")}
    CACHE.mkdir(exist_ok=True)

    tekstloos = False
    pad = _bestandsnaam(naam, boekjaar)
    if not pad.exists():
        try:
            inhoud = cbf.jaarverslag(naam, boekjaar)
        except Exception as fout:  # noqa: BLE001 — bron mag falen, run gaat door
            inhoud = None
            basis["reden"] = f"download mislukt: {fout}"
        if inhoud:
            pad.write_bytes(inhoud)

    if pad.exists():
        tekst = pdf_naar_tekst(str(pad))
        if not bewaar_pdf:
            pad.unlink(missing_ok=True)
        if len(tekst.strip()) < 50:
            tekstloos = True
        else:
            gevonden = _uit_tekst(tekst, kantoor_index, cbf.jaarverslag_url(naam, boekjaar))
            if gevonden and gevonden["kantoor"]:
                return {**basis, "status": "opdracht", **gevonden}
            if gevonden:
                return {**basis, "status": "review", **gevonden}
            basis["reden"] = "jaarverslag zonder controleverklaring"

    if terugval and website:
        for document in anbi_publicatie.zoek_documenten(website, boekjaar):
            inhoud = anbi_publicatie.haal_document(document)
            if not inhoud:
                continue
            if document["soort"] == "html":
                tekst = anbi_publicatie.tekst_uit_html(inhoud)
            else:
                eigen_pad = _bestandsnaam(naam, boekjaar, "_eigen")
                eigen_pad.write_bytes(inhoud)
                tekst = pdf_naar_tekst(str(eigen_pad))
                if not bewaar_pdf:
                    eigen_pad.unlink(missing_ok=True)
            if not bevat_boekjaar(tekst, boekjaar):
                basis["reden"] = (
                    f"stuk op de eigen site gaat niet over boekjaar {boekjaar}"
                )
                continue
            gevonden = _uit_tekst(tekst, kantoor_index, document["url"])
            if gevonden and gevonden["kantoor"]:
                return {**basis, "status": "opdracht", **gevonden}
            if gevonden:
                return {**basis, "status": "review", **gevonden}

    if tekstloos:
        return {**basis, "status": "onleesbaar",
                "reden": basis.get("reden") or "geen tekstlaag (gescande pdf)"}
    if "reden" in basis and basis["reden"].startswith("jaarverslag"):
        return {**basis, "status": "geen_controle"}
    return {**basis, "status": "geen_verslag",
            "reden": basis.get("reden") or "geen jaarverslag bij het CBF"}
