"""Controleverklaringen uit raadsstukken (Open Raadsinformatie).

Gemeenten, provincies, waterschappen en gemeenschappelijke regelingen leggen hun
jaarstukken voor aan een raad of algemeen bestuur, en die stukken zijn openbaar.
Open Raadsinformatie ontsluit ze met een zoek-API waarin de **volledige
documenttekst al is meegeleverd** — geen pdf's downloaden, geen tekstherkenning.

    POST https://api.openraadsinformatie.nl/v1/elastic/_search

Gemeten op 5-8-2026: meer dan tienduizend documenten bevatten letterlijk de zin
"controleverklaring van de onafhankelijke accountant".

De valkuil, en waarom deze adapter leest in plaats van afleidt
-------------------------------------------------------------
Het ligt voor de hand om de organisatie te nemen die het document publiceerde.
Dat is fout. Een gemeenteraad bespreekt niet alleen de eigen jaarstukken maar
ook die van elke gemeenschappelijke regeling waarin de gemeente deelneemt. In
één zitting van een Noord-Hollandse raad kwamen de jaarstukken langs van CAW,
SSC DeSom, GGD Hollands Noorden, Veiligheidsregio NHN, WerkSaam Westfriesland,
Omgevingsdienst NHN en het Westfries Archief. Wie de publicerende raad als
gecontroleerde partij neemt, schrijft zeven controles toe aan één gemeente die
er geen enkele van heeft gehad.

Bovendien staat de term ook in inhoudsopgaven en aanbiedingsbrieven, waar
helemaal geen verklaring in staat.

Daarom leest deze adapter maar één zin, de standaardformulering waarmee elke
Nederlandse controleverklaring bij een decentrale overheid begint:

    "Wij hebben de jaarrekening 2018 van de Gemeenschappelijke regeling
     WerkSaam Westfriesland te Hoorn gecontroleerd."

Die ene zin levert alle drie de feiten die we nodig hebben — wélke organisatie,
wélk boekjaar, wélke plaats — en hij staat er alleen als er ook echt een
verklaring is. Documenten zonder die zin leveren dus niets op, en dat is de
bedoeling: liever een verklaring missen dan een controle toeschrijven aan de
verkeerde organisatie.

Het kantoor komt uit het handtekeningblok eromheen, met dezelfde matcher als de
rest van de pijplijn. Wat daar niet uit komt gaat naar de review-queue.

Geen dependencies buiten de standaardbibliotheek.
"""

import json
import re
import urllib.request

API = "https://api.openraadsinformatie.nl/v1/elastic/_search"
ZOEKZIN = "controleverklaring van de onafhankelijke accountant"
# Bovengrens voor het boekjaar. Een jaarrekening over de toekomst bestaat niet;
# staat er toch zo'n jaartal, dan is de regel verhaspeld.
HUIDIG_JAAR = 2026
KOPPEN = {
    "User-Agent": "WhoSigns/0.1 (open-data-import; contact via repo)",
    "Content-Type": "application/json",
    "Accept": "application/json",
}
VELDEN = [
    "has_organization_name",
    "name",
    "file_name",
    "original_url",
    "text",
    "last_discussed_at",
]

# De standaardzin uit de controleverklaring. Twee schrijfwijzen komen voor:
# "de jaarrekening 2018 van X te Y gecontroleerd" en dezelfde zin zonder plaats.
# Het jaartal staat er altijd, want de verklaring gaat over één jaarrekening.
_GECONTROLEERD = re.compile(
    r"jaarrekening\s+(20[0-2]\d)\s+van\s+(?:de\s+|het\s+)?"
    r"(.{3,120}?)"
    r"(?:\s+te\s+([A-Z][\w'’\- ]{2,40}?))?"
    r"\s+gecontroleerd",
    re.I | re.S,
)

# Wat nooit een organisatienaam is: een zin die is doorgelopen, of een verwijzing
# naar een bijlage. Zulke treffers laten we vallen in plaats van op te slaan.
_GEEN_ORGANISATIE = re.compile(
    r"\b(?:pagina|bijlage|hoofdstuk|bladzijde|zie |welke |die |dat |deze )\b", re.I
)


def _plat(waarde) -> str:
    """De tekst van een document; de API levert die soms als lijst per pagina."""
    if isinstance(waarde, list):
        return "\n".join(str(deel) for deel in waarde)
    return str(waarde or "")


def _haal(lichaam: dict, timeout: int = 180) -> dict:
    verzoek = urllib.request.Request(
        API, data=json.dumps(lichaam).encode("utf-8"), headers=KOPPEN, method="POST"
    )
    with urllib.request.urlopen(verzoek, timeout=timeout) as antwoord:
        return json.loads(antwoord.read().decode("utf-8"))


def documenten(per_pagina: int = 100, maximum: int = 25_000, haal=None):
    """Alle documenten met de zoekzin, in stukjes.

    Bladeren gaat met `search_after` en niet met `from`: Elasticsearch weigert
    `from` boven de tienduizend, en dat is precies waar deze bron begint.
    """
    na = None
    opgehaald = 0
    while opgehaald < maximum:
        lichaam = {
            "query": {"match_phrase": {"text": ZOEKZIN}},
            "size": min(per_pagina, maximum - opgehaald),
            "sort": [{"_id": "asc"}],
            "_source": VELDEN,
        }
        if na:
            lichaam["search_after"] = na
        antwoord = (haal or _haal)(lichaam)
        treffers = (antwoord.get("hits") or {}).get("hits") or []
        if not treffers:
            return
        for treffer in treffers:
            yield treffer.get("_source") or {}
        opgehaald += len(treffers)
        na = treffers[-1].get("sort")
        if not na:
            return


# Aanhef die vóór de organisatienaam kan blijven hangen wanneer de verklaring
# begint met "Aan het algemeen bestuur van gemeenschappelijke regeling X" en de
# zin met "de jaarrekening ... van" daar in de tekststroom tegenaan is geplakt.
_AANHEF = re.compile(
    r"^(?:aan\s+)?(?:het\s+|de\s+)?"
    r"(?:algemeen\s+bestuur|dagelijks\s+bestuur|bestuur|gemeenteraad|raad|"
    r"provinciale\s+staten|verenigde\s+vergadering)\s+van\s+",
    re.I,
)


# "gemeenschappelijke regeling de Gemeenschappelijke Regeling Veiligheidsregio
# Utrecht" komt echt zo voor: de zin herhaalt de rechtsvorm die al in de
# statutaire naam zit.
_DUBBELE_REGELING = re.compile(
    r"^(gemeenschappelijke\s+regeling)\s+(?:de\s+|het\s+)?(?=gemeenschappelijke\s+regeling)",
    re.I,
)


def _schoon_organisatie(naam: str) -> str:
    schoon = re.sub(r"\s+", " ", naam).strip(" ,.;:-–—")
    schoon = _AANHEF.sub("", schoon)
    # Een naam die met een lidwoord begint is meestal een doorgelopen zin.
    schoon = re.sub(r"^(?:de|het|een)\s+", "", schoon, flags=re.I)
    schoon = _DUBBELE_REGELING.sub("", schoon).strip()
    # De zin schrijft de rechtsvorm nu eens met en dan weer zonder hoofdletter;
    # als weergavenaam is één schrijfwijze genoeg.
    if schoon[:1].islower():
        schoon = schoon[:1].upper() + schoon[1:]
    return schoon


def matchsleutel(naam: str) -> str:
    """Sleutel om dezelfde organisatie te herkennen ondanks tekstverschillen.

    De documenttekst komt uit een pdf, en daar sneuvelen koppeltekens en
    spaties: "Veiligheidsregio Noord-Holland Noord" en "Veiligheidsregio
    NoordHolland Noord" staan allebei in de bron, net als "Regio West-Brabant"
    naast "Regio WestBrabant". Op de gewone normalisatie zijn dat verschillende
    organisaties, en dan splitst de geschiedenis van één veiligheidsregio zich
    over twee rijen — dezelfde fout die de woningcorporaties dubbel in de
    database zette.

    Daarom voor déze bron een strengere sleutel: alleen letters en cijfers.
    Bij namen van deze lengte en soortelijkheid is de kans dat twee échte
    organisaties samenvallen verwaarloosbaar.
    """
    return re.sub(r"[^a-z0-9]", "", _normaliseer_kaal(naam))


def _normaliseer_kaal(tekst: str) -> str:
    import unicodedata

    tekst = unicodedata.normalize("NFKD", tekst or "")
    tekst = "".join(teken for teken in tekst if not unicodedata.combining(teken))
    return tekst.lower()


def verklaringen_uit(tekst: str, bron: dict | None = None) -> list[dict]:
    """Alle (organisatie, boekjaar, plaats) uit de standaardzin in dit document.

    Eén document kan meerdere verklaringen bevatten — een raadsbundel met de
    jaarstukken van drie gemeenschappelijke regelingen achter elkaar. Elke zin
    telt apart; dubbele combinaties vallen weg.
    """
    ruw: list[dict] = []
    for treffer in _GECONTROLEERD.finditer(tekst):
        boekjaar = int(treffer.group(1))
        # Een jaartal buiten dit bereik komt uit een verhaspelde regel, niet uit
        # een verklaring. Gemeten op 4.000 documenten: één keer "2077".
        if not (2000 <= boekjaar <= HUIDIG_JAAR):
            continue
        organisatie = _schoon_organisatie(treffer.group(2) or "")
        plaats = _schoon_organisatie(treffer.group(3) or "") if treffer.group(3) else ""
        if len(organisatie) < 4 or _GEEN_ORGANISATIE.search(organisatie):
            continue
        if not re.search(r"[A-Za-zÀ-ÿ]{3}", organisatie):
            continue
        ruw.append(
            {
                "organisatie": organisatie,
                "boekjaar": boekjaar,
                "plaats": plaats,
                "positie": treffer.start(),
                "documentnaam": (bron or {}).get("name") or "",
                "url": (bron or {}).get("original_url") or "",
            }
        )

    # Waar mag het handtekeningblok van déze verklaring staan? Tot aan de
    # volgende verklaring in hetzelfde document, en niet verder.
    #
    # Dat is de hele reden dat dit veld bestaat. Een raadsbundel zet de
    # jaarstukken van vijf gemeenschappelijke regelingen achter elkaar in één
    # pdf. Met een vast venster van een paar duizend tekens vindt de matcher de
    # handtekening van de búúr, en dan krijgt SSC DeSom de accountant van
    # Omgevingsdienst Noord-Holland Noord. De volgende "…gecontroleerd"-zin is
    # de natuurlijke grens: daar begint een andere verklaring.
    for index, verklaring in enumerate(ruw):
        volgende = ruw[index + 1]["positie"] if index + 1 < len(ruw) else len(tekst)
        verklaring["venster"] = (max(0, verklaring["positie"] - 800), volgende)

    # Dezelfde organisatie en hetzelfde boekjaar twee keer in één document is
    # een herhaling (bijlage plus samenvatting); één regel volstaat.
    uit: list[dict] = []
    gezien: set[tuple[str, int]] = set()
    for verklaring in ruw:
        sleutel = (verklaring["organisatie"].lower(), verklaring["boekjaar"])
        if sleutel in gezien:
            continue
        gezien.add(sleutel)
        uit.append(verklaring)
    return uit
