"""Aanbestede accountantsdiensten uit TED (Tenders Electronic Daily).

Gemeenten, provincies, waterschappen, veiligheidsregio's en onderwijsbesturen
moeten hun accountantscontrole Europees aanbesteden. De gunning noemt de
opdrachtgever, het gekozen kantoor en de datum van contractsluiting — en dat is
precies één helft van wat WhoSigns bijhoudt.

Gemeten op 4-8-2026:

    api        POST https://api.ted.europa.eu/v3/notices/search geeft HTTP 200
               zonder sleutel en zonder inlog (GET geeft 405)
    volume     403 gunningen in de CPV-familie 79200000 met buyer-country NLD
               sinds 1-1-2024; ruim 2.900 over 2016-2026
    winnaar    onder eForms (berichten vanaf ~2023) staat winner-name
               gestructureerd in het antwoord; oudere berichten hebben dat veld
               niet — die leveren wel een opdrachtgever maar geen kantoor op

Twee valkuilen die gemeten zijn en waar de code op is ingericht:

1.  **De oudercode is nodig, en vervuilt.** De meeste gemeentelijke
    accountantsaanbestedingen staan onder 79200000 ("boekhoudkundige, audit- en
    fiscale diensten"), niet onder de specifieke 79212*-codes. Filteren op
    alleen 79212* kost meer dan de helft van de populatie. Maar 79200000 vangt
    óók WOZ-software, salarisadministratie en organisatieadvies: in de eerste
    acht treffers van 2024 zaten "xxllnc Belastingen B.V.", "ANG B.V." en
    "Boer & Croon Management Solutions".

2.  **De kantorenlijst is het filter.** In plaats van op de titel te raden,
    leggen we de winnaar langs het AFM-register en de lijst met kantoren zonder
    Wta-vergunning. Wat daar niet in staat is geen accountantskantoor en gaat
    niet mee. Dat is dezelfde toets die de rest van de pipeline gebruikt, dus
    het kan niet uit de pas lopen — en wat afvalt komt in het rapport terecht,
    zodat een echt kantoor dat we nog niet kenden opvalt in plaats van
    stilletjes te verdwijnen.
"""

import json
import re
import urllib.request

API = "https://api.ted.europa.eu/v3/notices/search"

# De hele familie boekhoud-, audit- en fiscale diensten. Bewust de oudercode:
# zie valkuil 1 in de moduletekst.
CPV_FAMILIE = "79200000"

VELDEN = [
    "publication-number",
    "buyer-name",
    "winner-name",
    "contract-conclusion-date",
    "notice-title",
]


def _plat(waarde) -> list[str]:
    """TED levert meertalige velden als {"nld": [...]}, soms als lijst, soms kaal."""
    if waarde is None:
        return []
    if isinstance(waarde, str):
        return [waarde]
    if isinstance(waarde, list):
        uit = []
        for deel in waarde:
            uit.extend(_plat(deel))
        return uit
    if isinstance(waarde, dict):
        # Nederlands eerst; anders de eerste taal die er is.
        for taal in ("nld", "eng", "MUL"):
            if taal in waarde:
                return _plat(waarde[taal])
        for deel in waarde.values():
            return _plat(deel)
    return [str(waarde)]


def _eerste(waarde) -> str | None:
    plat = _plat(waarde)
    return plat[0] if plat else None


# Soms staat er in het winnaarsveld geen naam maar een rubriekaanduiding uit het
# formulier ("Gegunde opdrachten", tien keer in 2024). Dat is geen partij.
_GEEN_NAAM = re.compile(
    r"(?:gegunde\s+opdracht\w*|niet\s+van\s+toepassing|n\.?v\.?t\.?|onbekend|"
    r"geen\s+\w+)",
    re.I,
)


def _datum(waarde) -> str | None:
    """TED schrijft "2024-01-08+01:00"; wij willen "2024-01-08"."""
    ruw = _eerste(waarde)
    if not ruw:
        return None
    treffer = re.match(r"(\d{4}-\d{2}-\d{2})", ruw)
    return treffer.group(1) if treffer else None


def zoek(
    vanaf: str = "20160101",
    tot: str | None = None,
    per_pagina: int = 100,
    max_paginas: int = 60,
    haal=None,
) -> list[dict]:
    """Alle gunningsberichten van Nederlandse aanbesteders in de audit-familie.

    `vanaf` en `tot` zijn publicatiedatums als JJJJMMDD. `haal` is er voor de
    tests: een functie die een verzoeklichaam krijgt en het antwoord teruggeeft.
    """
    voorwaarden = [
        "buyer-country=NLD",
        f"classification-cpv={CPV_FAMILIE}",
        "notice-type=can-standard",
        f"publication-date>={vanaf}",
    ]
    if tot:
        voorwaarden.append(f"publication-date<={tot}")
    vraag = " AND ".join(voorwaarden)

    berichten: list[dict] = []
    for pagina in range(1, max_paginas + 1):
        lichaam = {
            "query": vraag,
            "fields": VELDEN,
            "page": pagina,
            "limit": per_pagina,
            "scope": "ALL",
        }
        antwoord = (haal or _haal)(lichaam)
        deel = antwoord.get("notices") or []
        berichten.extend(deel)
        if len(deel) < per_pagina:
            break
    return berichten


def _haal(lichaam: dict) -> dict:
    verzoek = urllib.request.Request(
        API,
        data=json.dumps(lichaam).encode("utf-8"),
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(verzoek, timeout=180) as antwoord:
        return json.loads(antwoord.read().decode("utf-8"))


def gunningen_uit(berichten: list[dict]) -> list[dict]:
    """Berichten -> platte gunningsregels (opdrachtgever, winnaar, datum).

    Eén bericht kan meerdere percelen aan meerdere partijen gunnen; die worden
    hier uit elkaar getrokken tot één regel per (opdrachtgever, winnaar). Een
    bericht zonder winnaarsveld — alles van vóór eForms — levert niets op: we
    weten dan wél dat er aanbesteed is, maar niet aan wie, en een gunning zonder
    kantoor heeft in dit model geen betekenis.
    """
    regels = []
    for bericht in berichten:
        nummer = _eerste(bericht.get("publication-number"))
        koper = _eerste(bericht.get("buyer-name"))
        winnaars = _plat(bericht.get("winner-name"))
        if not nummer or not koper or not winnaars:
            continue
        datum = _datum(bericht.get("contract-conclusion-date"))
        titel = _eerste(bericht.get("notice-title"))
        gezien = set()
        for winnaar in winnaars:
            schoon = re.sub(r"\s+", " ", winnaar).strip()
            if not schoon or schoon.lower() in gezien or _GEEN_NAAM.fullmatch(schoon):
                continue
            gezien.add(schoon.lower())
            regels.append(
                {
                    "publicatienummer": nummer,
                    "opdrachtgever": re.sub(r"\s+", " ", koper).strip(),
                    "winnaar": schoon,
                    "gunningsdatum": datum,
                    "titel": (titel or "")[:300] or None,
                    "url": f"https://ted.europa.eu/nl/notice/-/detail/{nummer}",
                }
            )
    return regels


# Aanbesteders schrijven hun eigen naam rommelig op: "Afdeling Inkoop, Gemeente
# Nijmegen", "Gemeente Kerkrade, Raadhuis", "gemeentehuis Borsele". Voor het
# koppelen aan een organisatie halen we die aanhangsels eraf; de ruwe naam
# blijft in het rapport staan.
_AANHANGSEL = re.compile(
    r"^(?:afdeling\s+\w+,\s*|gemeentehuis\s+|bureau\s+inkoop\s+)|"
    r"(?:,\s*(?:raadhuis|stadhuis|gemeentehuis|inkoop|afdeling\s+\w+))$",
    re.I,
)


def schoon_opdrachtgever(naam: str) -> str:
    schoon = _AANHANGSEL.sub("", naam).strip(" ,")
    # "gemeente Nijmegen" en "Gemeente Nijmegen" horen dezelfde te zijn; de
    # rest van de pipeline normaliseert toch, maar de weergavenaam ook netjes.
    # Hetzelfde geldt voor waterschap, provincie en veiligheidsregio, die in TED
    # net zo vaak met een kleine letter beginnen.
    for woord in ("gemeente", "waterschap", "provincie", "veiligheidsregio",
                  "hoogheemraadschap", "stichting"):
        if schoon[: len(woord) + 1].lower() == f"{woord} ":
            schoon = woord.capitalize() + schoon[len(woord) :]
            break
    return schoon or naam


# --- Berichten van vóór eForms: de winnaar staat in de XML -------------------
#
# Het zoekantwoord heeft alleen een winner-name voor eForms-berichten (ruwweg
# vanaf december 2023). Voor 2016 t/m 2023 blijft dat veld leeg, en dat is
# precies de periode waarin de meeste gemeenten hun accountant hebben
# aanbesteed. De winnaar staat er wél in, maar dan in het XML-bericht zelf.
#
# Gemeten op 5-8-2026: 788 gunningsberichten in de audit-familie tussen
# 1-1-2016 en 30-11-2023, in twee verschillende schema's.
#
#     2016-2017  <AWARD_OF_CONTRACT> met <ECONOMIC_OPERATOR_NAME_ADDRESS>
#                en de datum in losse <DAY>/<MONTH>/<YEAR>
#     2018-2023  <AWARD_CONTRACT> met <AWARDED_CONTRACT><CONTRACTORS>
#                <CONTRACTOR><ADDRESS_CONTRACTOR>, datum als <DATE_CONCLUSION_CONTRACT>
#
# Beide schema's gebruiken <OFFICIALNAME>, en dat is precies de valkuil: die tag
# staat óók om de aanbesteder en om de rechtbank waar je bezwaar maakt. Alleen
# de naam binnen het contractor-element telt, en daarom knippen we eerst het
# gunningsblok uit en zoeken we daarbinnen alleen in het juiste omhulsel.

_XML_BERICHT = "https://ted.europa.eu/en/notice/{}/xml"

_BLOK_NIEUW = re.compile(r"<AWARD_CONTRACT\b.*?</AWARD_CONTRACT>", re.S)
_BLOK_OUD = re.compile(r"<AWARD_OF_CONTRACT\b.*?</AWARD_OF_CONTRACT>", re.S)
_CONTRACTOR = re.compile(r"<ADDRESS_CONTRACTOR\b.*?</ADDRESS_CONTRACTOR>", re.S)
_OPERATOR = re.compile(
    r"<ECONOMIC_OPERATOR_NAME_ADDRESS\b.*?</ECONOMIC_OPERATOR_NAME_ADDRESS>", re.S
)
_OFFICIEEL = re.compile(r"<OFFICIALNAME[^>]*>(.*?)</OFFICIALNAME>", re.S)
_DATUM_NIEUW = re.compile(
    r"<DATE_CONCLUSION_CONTRACT[^>]*>\s*(\d{4}-\d{2}-\d{2})", re.S
)
_DATUM_OUD = re.compile(
    r"<CONTRACT_AWARD_DATE[^>]*>\s*<DAY>(\d{1,2})</DAY>\s*"
    r"<MONTH>(\d{1,2})</MONTH>\s*<YEAR>(\d{4})</YEAR>",
    re.S,
)
_TITEL = re.compile(r"<(?:CONTRACT_)?TITLE[^>]*>\s*<P>(.*?)</P>", re.S)


def _tekst(ruw: str) -> str:
    """Tags eruit, entiteiten terug, witruimte samengetrokken."""
    kaal = re.sub(r"<[^>]+>", " ", ruw)
    for entiteit, teken in (("&amp;", "&"), ("&quot;", '"'), ("&apos;", "'"),
                            ("&lt;", "<"), ("&gt;", ">")):
        kaal = kaal.replace(entiteit, teken)
    return re.sub(r"\s+", " ", kaal).strip()


def bericht_xml(nummer: str, haal=None) -> str:
    if haal:
        return haal(nummer)
    verzoek = urllib.request.Request(
        _XML_BERICHT.format(nummer),
        headers={"User-Agent": "Mozilla/5.0 (WhoSigns-pipeline)"},
    )
    with urllib.request.urlopen(verzoek, timeout=120) as antwoord:
        return antwoord.read().decode("utf-8", "replace")


def gunningen_uit_xml(xml: str, nummer: str, opdrachtgever: str) -> list[dict]:
    """Gunningsregels uit het XML-bericht, voor beide TED-schema's.

    De opdrachtgever komt uit het zoekantwoord meegereisd: die staat in het
    zoekresultaat al netjes per taal uitgesplitst, terwijl hij in de XML tussen
    dezelfde OFFICIALNAME-tags staat als de winnaar en de rechtbank.
    """
    regels: list[dict] = []
    gezien: set[str] = set()
    blokken = [(b, True) for b in _BLOK_NIEUW.findall(xml)]
    blokken += [(b, False) for b in _BLOK_OUD.findall(xml)]
    for blok, nieuw in blokken:
        omhulsels = (_CONTRACTOR if nieuw else _OPERATOR).findall(blok)
        if not omhulsels:
            # Aanbesteding zonder gunning (ingetrokken of niets ontvangen).
            continue
        if nieuw:
            treffer = _DATUM_NIEUW.search(blok)
            datum = treffer.group(1) if treffer else None
        else:
            treffer = _DATUM_OUD.search(blok)
            datum = (
                f"{treffer.group(3)}-{int(treffer.group(2)):02d}-{int(treffer.group(1)):02d}"
                if treffer
                else None
            )
        titel_treffer = _TITEL.search(blok)
        titel = _tekst(titel_treffer.group(1)) if titel_treffer else None
        for omhulsel in omhulsels:
            for ruwe_naam in _OFFICIEEL.findall(omhulsel):
                winnaar = _tekst(ruwe_naam)
                if not winnaar or _GEEN_NAAM.fullmatch(winnaar):
                    continue
                sleutel = winnaar.lower()
                if sleutel in gezien:
                    continue
                gezien.add(sleutel)
                regels.append(
                    {
                        "publicatienummer": nummer,
                        "opdrachtgever": re.sub(r"\s+", " ", opdrachtgever).strip(),
                        "winnaar": winnaar,
                        "gunningsdatum": datum,
                        "titel": (titel or "")[:300] or None,
                        "url": f"https://ted.europa.eu/nl/notice/-/detail/{nummer}",
                    }
                )
    return regels


def berichten_zonder_winnaar(berichten: list[dict]) -> list[tuple[str, str]]:
    """(publicatienummer, opdrachtgever) van berichten die de XML-route nodig hebben."""
    open_staand = []
    for bericht in berichten:
        if _plat(bericht.get("winner-name")):
            continue
        nummer = _eerste(bericht.get("publication-number"))
        koper = _eerste(bericht.get("buyer-name"))
        if nummer and koper:
            open_staand.append((nummer, koper))
    return open_staand
