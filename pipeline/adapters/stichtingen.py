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

import hashlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "extractie"))

import anbi_publicatie  # noqa: E402
import cbf  # noqa: E402
from kantoor_match import normaliseer  # noqa: E402
from verklaring import analyseer, pdf_naar_tekst, tekst_uit_pdf  # noqa: E402

CACHE = Path(__file__).resolve().parents[1] / ".cache"


def _bestandsnaam(sleutel: str, boekjaar: int, achtervoegsel: str = "") -> Path:
    # Kappen op 60 tekens hield de bestandsnamen leesbaar, maar twee lange namen
    # met dezelfde eerste 60 tekens deelden dan één cachebestand — en dan wordt
    # organisatie B beoordeeld op het jaarverslag van organisatie A. De korte
    # vingerafdruk van de vólledige naam maakt de naam alsnog uniek.
    veilig = "".join(c if c.isalnum() else "_" for c in sleutel)[:60]
    vingerafdruk = hashlib.sha1(sleutel.encode()).hexdigest()[:8]
    return CACHE / f"cbf_{boekjaar}_{veilig}_{vingerafdruk}{achtervoegsel}.pdf"


def _opdrachttype(resultaat: dict) -> str:
    """Vaststellen in plaats van aannemen; zie de moduletoelichting."""
    soort = resultaat.get("soort")
    if soort != "controle":
        # Een beoordeling (Standaard 2400) of samenstelling is een ander soort
        # opdracht, geen jaarrekeningcontrole. Het type is dus wat er staat — de
        # views in supabase/migrations/ tellen alleen de twee controlevormen mee,
        # en web/lib/paden.ts kent deze labels al.
        return soort
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


def _uit_tekst(
    tekst: str,
    kantoor_index: dict,
    vindplaats: str,
    soorten: tuple[str, ...] = ("controle",),
) -> dict | None:
    resultaat = analyseer(tekst, kantoor_index)
    if resultaat["soort"] not in soorten:
        return None
    return {
        "soort": resultaat["soort"],
        "opdrachttype": _opdrachttype(resultaat) if resultaat["kantoor"] else None,
        "voorwerp": resultaat["opdrachttype"],
        "oordeel": resultaat["oordeel"],
        # Waar een beperking over gaat (wnt | inhoudelijk | None). In de zorg bleek
        # dat het verschil tussen een golf WNT-formaliteiten en een echte bevinding
        # over de jaarrekening; hier is het net zo belangrijk, want "oordeel met
        # beperking" naast de naam van een goed doel leest als een aanklacht.
        "grond_beperking": resultaat["grond_beperking"],
        "continuiteitsonzekerheid": bool(resultaat["continuiteitsonzekerheid"]),
        "kantoor": resultaat["kantoor"],
        "kandidaten": resultaat["kandidaten"],
        "vindplaats": vindplaats,
    }


def _lees_pdf(pad: str, ocr: bool) -> tuple[str, bool]:
    """De tekst van een pdf, met OCR als tweede kans wanneer `ocr` aan staat.

    Waarom dit een keuze per populatie is en niet altijd aan: het hangt af van wie het
    verslag inscande. Gemeten op boekjaar 2024, de gescande verslagen (tekstlaag nul):

      D/E  9 scans, en dat zijn Open Doors, KNGF Geleidehonden, Feyenoord Foundation,
           voordekunst — organisaties van een omvang waarbij een controle hoort. OCR
           haalt daar echte controleverklaringen uit, met kantoor en al.
      A/B  33 scans, en bij vier daarvan nagekeken had er drie géén verklaring en de
           vierde een samenstelling zonder herleidbaar kantoor. Wie print, ondertekent
           en scant is daar juist de stichting die zich niet laat controleren. OCR
           bewijst dan dat het stuk leeg is: een minuut rekenwerk per document om te
           bevestigen wat de basiskans al zei (201 van de 262 zonder controle).

    Dus aan waar een verklaring te verwachten is, uit waar de scan zelf het signaal is
    dat er niets te vinden valt.
    """
    if ocr:
        return tekst_uit_pdf(pad)
    return pdf_naar_tekst(pad), False


def verwerk_organisatie(
    organisatie: dict,
    boekjaar: int,
    kantoor_index: dict,
    terugval: bool = False,
    website: str = "",
    bewaar_pdf: bool = True,
    soorten: tuple[str, ...] = ("controle",),
    ocr: bool = True,
) -> dict:
    """Eén goed doel, één boekjaar. Geeft altijd een dict met `status`.

    `status`:
      - `opdracht`      kantoor herleid; `kantoor`, `oordeel` enz. zijn gevuld
      - `review`        gezochte verklaring gevonden, kantoor onbekend (met `kandidaten`)
      - `geen_controle` wel een verslag, maar niet de gezochte verklaring erin
      - `geen_verslag`  niets te vinden bij het CBF, en ook niet op de eigen site
      - `onleesbaar`    pdf zonder tekstlaag (gescand)

    `soorten` zijn de verklaringsoorten die een opdracht-rij mogen worden. Voor
    categorie D/E is dat `controle`; voor categorie C ook `beoordeling`, want daar
    eist de Erkenningsregeling geen controle. Wat er niet in staat, levert bewust
    niets op: een samenstellingsverklaring per ongeluk als controle boeken is
    precies het soort stille aanname dat dit project niet doet.

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
        # Let op de volgorde: eerst lezen, dán de pdf weggooien, want OCR heeft het
        # bestand nog nodig.
        tekst, via_ocr = _lees_pdf(str(pad), ocr)
        if not bewaar_pdf:
            pad.unlink(missing_ok=True)
        if via_ocr:
            basis["via_ocr"] = True
        if len(tekst.strip()) < 50:
            tekstloos = True
        else:
            gevonden = _uit_tekst(
                tekst, kantoor_index, cbf.jaarverslag_url(naam, boekjaar), soorten
            )
            if gevonden and gevonden["kantoor"]:
                return {**basis, "status": "opdracht", **gevonden}
            if gevonden:
                return {**basis, "status": "review", **gevonden}
            basis["reden"] = f"jaarverslag zonder {'/'.join(soorten)}verklaring"

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
                tekst, via_ocr = _lees_pdf(str(eigen_pad), ocr)
                if not bewaar_pdf:
                    eigen_pad.unlink(missing_ok=True)
                if via_ocr:
                    basis["via_ocr"] = True
            if not bevat_boekjaar(tekst, boekjaar):
                basis["reden"] = (
                    f"stuk op de eigen site gaat niet over boekjaar {boekjaar}"
                )
                continue
            gevonden = _uit_tekst(tekst, kantoor_index, document["url"], soorten)
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
