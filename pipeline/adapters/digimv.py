"""DigiMV-adapter: van organisatie naar een opdracht-rij in het kernmodel.

Combineert de eerder gebouwde bouwstenen:
    digimv_archief  -> zoeken in het archief, document ophalen
    kantoor_match   -> kantoornaam herkennen tegen de AFM-lijst
    verklaring      -> pdf -> soort, oordeel, continuïteitsonzekerheid

Doet één organisatie-boekjaar tegelijk (`verwerk_organisatie`) — bruikbaar voor
zowel een kleine handmatige lijst (`laad_proefdata.py`) als de latere
bulkverwerking vanuit de volledige dataset (dekkingsstrategie in `digimv.md`).

**Matchen gebeurt op KvK-nummer, niet op naam+plaats.** Naam en plaats wisselen
namelijk per boekjaar in de bron: HagaZiekenhuis staat in boekjaar 2023 als
"Stichting HagaZiekenhuis" te 's-Gravenhage, maar in 2020 als
"HagaZiekenhuis (Stichting)" te DEN HAAG. Het KvK-nummer (27268552) is over
alle jaren gelijk en is dus de enige betrouwbare sleutel. De naam dient
alleen als zoekterm om de kandidatenlijst klein te houden.

Alleen een controleverklaring met een herkend kantoor levert een resultaat op.
Samenstellings-/beoordelingsverklaringen en onherkende kantoren geven None —
de aanroeper beslist wat daarmee gebeurt (overslaan, of naar review_queue).
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "extractie"))

import digimv_archief  # noqa: E402
from verklaring import analyseer, tekst_uit_pdf  # noqa: E402

CACHE = Path(__file__).resolve().parents[1] / ".cache"

# Het archief houdt een voortschrijdend venster van zeven boekjaren aan
# (huidig jaar min 1 t/m min 7); oudere jaren geven HTTP 500. Zie digimv.md.
#
# Nagemeten op 29-7-2026: boekjaar 2018 geeft HTTP 500 (weg), 2025 is er wél al —
# 52 van de 55 organisaties met "ziekenhuis" in de naam hadden toen een verklaring
# gedeponeerd. Deponeren moest vóór 1 juni 2026, dus 2025 is grotendeels compleet.
# Beide grenzen elk jaar opnieuw controleren; ze schuiven mee.
OUDSTE_BOEKJAAR = 2019
NIEUWSTE_BOEKJAAR = 2025


def schoon_naam(naam: str) -> str:
    """Organisatienaam zoals het archief hem levert, maar zonder de rommel.

    Het archief geeft namen soms met losse spaties ("Amarant ") en één keer zelfs
    dubbel achter elkaar: "Woon & Zorgcentrum HerfstzonWoon & Zorgcentrum
    Herfstzon (Stichting)" (KvK 41032279, nagemeten 3-8-2026). Witruimte wordt
    samengevouwen; begint de rest van de naam met exact de kop ervoor (minstens
    acht tekens, tegen toeval), dan vervalt die kop en blijft de volledige
    variant met rechtsvorm over.
    """
    naam = " ".join(naam.split())
    for i in range(8, len(naam) - 7):
        if naam[i:].startswith(naam[:i]):
            return naam[i:]
    return naam


# Tussenwoorden die in een plaatsnaam klein blijven: Alphen aan den Rijn,
# Bergen op Zoom, Capelle aan den IJssel.
_PLAATS_KLEIN = {"aan", "bij", "de", "den", "der", "en", "het", "in", "op", "ter", "van"}


def _kapitaal(deel: str) -> str:
    if deel in ("'s", "'t"):
        return deel  # 's-Gravenhage, 't Zand
    if deel.startswith("ij"):
        return "IJ" + deel[2:]  # IJsselstein, niet Ijsselstein
    return deel[:1].upper() + deel[1:]


def schoon_plaats(plaats: str) -> str:
    """Plaatsnaam met normale hoofdletters in plaats van de KAPITALEN uit het archief.

    Het archief schrijft plaatsen in oudere boekjaren volledig in hoofdletters
    ("GOOR", "DEN HAAG", "CAPELLE AAN DEN IJSSEL") en in nieuwere gewoon
    ("Goor"). Alleen een naam die geheel in kapitalen staat wordt omgezet — wat
    al goed is, blijft onaangeraakt. Zonder dit stonden 394 van de ruim 1.100
    gemeenten in kapitalen op de site, en vond `gemeente=eq.` de organisaties
    in "GOOR" niet bij die in "Goor".
    """
    plaats = " ".join(plaats.split())
    if not plaats.isupper():
        return plaats
    woorden = []
    for i, woord in enumerate(plaats.lower().split(" ")):
        if i > 0 and woord in _PLAATS_KLEIN:
            woorden.append(woord)
            continue
        delen = woord.split("-")
        # "S-HERTOGENBOSCH" komt zonder apostrof binnen; die hoort er wel.
        if delen[0] == "s" and len(delen) > 1:
            delen[0] = "'s"
        woorden.append("-".join(_kapitaal(d) for d in delen))
    return " ".join(woorden)


def verwerk_organisatie(
    zoekterm: str,
    kvk_nummer: str,
    boekjaar: int,
    kantoor_index: dict,
    plaats: str = "",
    ocr: bool = True,
) -> dict | None:
    """Zoekt de organisatie op KvK-nummer en analyseert haar controleverklaring.

    `zoekterm` en `plaats` beperken alleen de kandidatenlijst; `kvk_nummer`
    bepaalt welke kandidaat we nemen. Zo blijft het werken als de bron de naam of
    plaats tussen boekjaren anders schrijft. Zoeken op alleen `plaats` is de
    terugvaloptie als de naam in de bron te veel afwijkt.
    """
    resultaten = digimv_archief.zoek(
        organisatie=zoekterm, plaats=plaats, boekjaar=boekjaar
    )
    treffers = [
        r for r in resultaten
        if (r.get("externalOrganizationId") or "").strip() == kvk_nummer
    ]
    if not treffers:
        print(f"  {boekjaar}: geen organisatie met KvK {kvk_nummer} gevonden")
        return None

    organisatie = treffers[0]
    documenten = digimv_archief.verklaringen(organisatie)
    if not documenten:
        print(f"  {boekjaar}: geen verklaring gedeponeerd")
        return None

    CACHE.mkdir(exist_ok=True)
    laatste_reden = None
    # Meerdere kandidaat-documenten: een losse verklaring lukt meestal direct,
    # een verzameldocument of de jaarrekening soms pas als de losse ontbreekt of
    # onleesbaar is (zie digimv_archief.verklaringen voor de volgorde).
    for doc in documenten:
        pdf_pad = CACHE / f"{boekjaar}_{kvk_nummer}_{doc['id']}.pdf"
        if not pdf_pad.exists():
            try:
                pdf_pad.write_bytes(digimv_archief.haal_document(doc, boekjaar))
            except Exception as fout:  # noqa: BLE001 — bron mag falen, volgende proberen
                laatste_reden = f"download mislukt: {fout}"
                continue

        # tekst_uit_pdf valt terug op OCR als er geen tekstlaag is. Kleine
        # zorgaanbieders printen, ondertekenen en scannen; zonder die terugval blijft
        # ongeveer driekwart van de organisaties zonder opdracht onzichtbaar.
        tekst, via_ocr = tekst_uit_pdf(str(pdf_pad), ocr=ocr)
        resultaat = analyseer(tekst, kantoor_index)
        resultaat["via_ocr"] = via_ocr
        if resultaat["soort"] != "controle":
            laatste_reden = f"geen controleverklaring ({resultaat['soort']})"
            # Zegt het dáárvoor bedoelde document ondubbelzinnig dat het een
            # samenstelling of beoordeling is, dan is dat het antwoord. Dan hoeven
            # we de jaarrekening niet ook nog op te halen — die is vaak tientallen
            # MB's en gaat over dezelfde opdracht. Alleen bij een onleesbare of
            # nietszeggende pdf (soort None, bijv. een aanbiedingsbrief of een scan)
            # heeft doorzoeken zin.
            if resultaat["soort"] is not None and doc.get("type", "").startswith(
                "Accountantsverklaring"
            ):
                break
            continue
        if not resultaat["kantoor"]:
            # De kandidaat-namen uit de tekst meenemen in de reden. Zonder dit gooit
            # de zorg-lader ze weg, terwijl juist dít de oogst is waarmee
            # seed/kantoren_overig.csv groeit: een naam die vaker langskomt is bijna
            # altijd een echt kantoor dat we nog niet kennen. De stichtingen-lader
            # doet dat al via de review-queue; hier stond er niets tegenover.
            laatste_reden = resultaat["reden"]
            if resultaat.get("kandidaten"):
                laatste_reden += " — kandidaten: " + ", ".join(resultaat["kandidaten"][:3])
            continue

        return {
            "kvk_nummer": kvk_nummer,
            "naam": schoon_naam(organisatie["name"]),
            "plaats": schoon_plaats(organisatie["town"]),
            "boekjaar": boekjaar,
            "opdrachttype": resultaat["opdrachttype"],
            "oordeel": resultaat["oordeel"],
            # Deze twee horen erbij omdat de lader ze wegschrijft. Ze stonden er
            # niet in toen `grond_beperking` aan `analyseer` werd toegevoegd, en
            # `laad_zorg` leest die sleutel buiten elke try: de eerstvolgende run
            # zou zijn omgevallen op een KeyError bij de eerste treffer.
            "grond_beperking": resultaat["grond_beperking"],
            "via_ocr": resultaat["via_ocr"],
            "continuiteitsonzekerheid": bool(resultaat["continuiteitsonzekerheid"]),
            "kantoor": resultaat["kantoor"],
            "bron_bestand": doc["fileName"],
        }

    print(f"  {boekjaar}: {laatste_reden}")
    return None
