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
