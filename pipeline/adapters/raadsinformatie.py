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

# Woorden waarmee een nieuwe zin of een kop begint. Een organisatienaam loopt daar
# nooit doorheen, dus de naam mag ze niet bevatten.
#
# Waarom dit er is: zonder deze rem sprong de naam over een kop heen. Een stuk van
# de gemeente Den Haag zet "Ons oordeel" als kopje boven de verklaring, en de
# regel ervóór noemt de jaarrekening al. De naam werd dan "Gemeente Den Haag Ons
# oordeel Wij hebben de jaarrekening 2016 van de gemeente Den Haag" — een tweede,
# verzonnen organisatie naast de echte, mét een accountant eronder. Gemeten op
# 4.000 documenten (7-8-2026): 26 van de 2.335 namen waren zo opgerekt, en Den
# Haag raakte er vijf echte jaren door kwijt, want de opgerekte match at de goede
# zin op. Met de rem verdwijnen alle 26 en komen die vijf terug; geen enkele
# schone naam valt weg.
_HERSTART = r"\bjaarrekening\b|\bjaarstukken\b|\boordeel\b|\bwij\s+hebben\b|20[0-2]\d"

# Wat er tussen "jaarrekening 2020" en "van" mag staan.
#
# Alleen een aanduiding van de reikwijdte: "(inclusief erratum)", "inclusief de
# SISA bijlage (bijlage 7.1)", "en de daarbij behorende bijlagen". Bewust géén vrij
# gat, en de tussenzin mag zelf het woord "van" niet bevatten. Dat is gemeten en
# het was geen theorie: met een vrij gat sloeg de zoeker het échte "van" over en
# haakte hij aan het "van" binnenín de naam. "Vereniging van Nederlandse
# Gemeenten" werd dan "Nederlandse Gemeenten", "Regio Hart van Brabant" werd
# "Brabant" en "Stichting Openbaar Onderwijs Land van Altena" werd "Altena" —
# 113 gehalveerde namen op 4.000 documenten. Nederlandse organisatienamen zitten
# vol "van", dus dit is geen randgeval.
#
# "opdracht" en "verantwoordelijk" horen er om dezelfde reden niet in: "is
# opgesteld onder verantwoordelijkheid van het bestuur" en "in opdracht van het
# GR-bestuur" zijn ándere zinnen, en die leverden "het bestuur" als organisatie.
_AANVULLING = (
    r"(?:"
    r"\((?:(?!\bvan\b)[^()]){1,45}\)"
    r"|(?:inclusief|incl\.|en\s+(?:de\s+)?daarbij\s+behorende)"
    r"(?:(?!\bvan\b|opdracht|verantwoordelijk)[^.;:!?()]){0,45}"
    r")"
)

# De standaardzin uit de controleverklaring. Twee schrijfwijzen komen voor:
# "de jaarrekening 2018 van X te Y gecontroleerd" en dezelfde zin zonder plaats.
# Het jaartal staat er altijd, want de verklaring gaat over één jaarrekening.
_GECONTROLEERD = re.compile(
    r"jaarrekening\s+(20[0-2]\d)\s+"
    r"(?:" + _AANVULLING + r"(?:\s+" + _AANVULLING + r")?\s+)?"
    r"van\s+(?:de\s+|het\s+)?"
    r"((?:(?!" + _HERSTART + r").){3,120}?)"
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

    Twee dingen worden er vooraf afgehaald, allebei omdat ze niets over
    identiteit zeggen. Ze zijn gemeten over de volle oogst (8-8-2026, 1.575
    namen) en voegden daar 22 namen samen tot 14 organisaties, zonder één
    verkeerde samenvoeging:

    * een plaatsaanduiding achteraan — "Gemeenschappelijke Regeling Cocensus"
      en "Gemeenschappelijke Regeling Cocensus, te Hoofddorp" zijn hetzelfde;
    * een per ongeluk verdubbeld eerste woord — "Gemeente Gemeente De Ronde
      Venen", "Stichting Stichting Openbaar Onderwijs Rijn- en Heuvelland".

    Wat hier bewust NIET gebeurt is het wegstrepen van woorden als "gemeente",
    "provincie" of "gemeenschappelijke regeling". Dat lijkt dezelfde soort
    opschoning, maar die woorden zíjn de identiteit: zonder "gemeente" en
    "provincie" vallen Gemeente Utrecht en Provincie Utrecht samen, en Gemeente
    Groningen en Provincie Groningen ook. Beide zijn echte, verschillende
    gecontroleerde partijen.

    Wat er dan nog overblijft is tekstschade uit de pdf: "Gemeenschappeiijke
    Regeling Senzer", "Omgevingsdienst Veluwe I]ssel", "GGD Gelderand-Zuid".
    Daar is geen veilige regel voor te schrijven — één letter verschil is ook
    precies wat EMCO-groep van Felua-groep onderscheidt — dus die blijven staan
    als aparte organisatie. Zie docs/bronverkenning-raadsinformatie.md.
    """
    kaal = _normaliseer_kaal(naam)
    # "… te Hoofddorp", "…, te Meerkerk", "… te gemeente De Wolden",
    # "…, gevestigd te Roosendaal", "… statutair gevestigd te Rotterdam"
    kaal = re.sub(
        r"[,.\s]+(?:statutair\s+)?(?:gevestigd\s+)?te\s+[a-z'\-. ]+$", "", kaal
    )
    # "gemeente gemeente de ronde venen" -> "gemeente de ronde venen"
    kaal = re.sub(r"^(\w+)\s+\1\b", r"\1", kaal)
    return re.sub(r"[^a-z0-9]", "", kaal)


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
    # een herhaling (bijlage plus samenvatting); één regel volstaat. Maar wélke
    # van de twee je houdt maakt uit, en dat is niet vanzelfsprekend.
    #
    # Een raadsbundel noemt de jaarrekening vaak eerst in de aanbiedingsbrief en
    # dan nog eens in de bijgevoegde verklaring zelf. Het venster van elke
    # vermelding loopt tot aan de vólgende vermelding, dus het venster van die
    # eerste eindigt precies waar de échte verklaring begint — vlák vóór het
    # handtekeningblok. Wie simpelweg de eerste houdt, houdt dus de vermelding
    # zónder handtekening over.
    #
    # Daarom de vermelding met het langste venster. Dat blijft veilig: elk
    # venster is al begrensd door de eerstvolgende verklaring in het document,
    # welke organisatie die ook betreft, dus een langer venster kan nooit de
    # handtekening van de buurman opslokken.
    #
    # Eerlijk over de omvang: het geval staat in de tests (zonder deze regel valt
    # de handtekening buiten het venster), maar corpusbreed is het níet
    # doorgemeten. De meting stond op 3.000 van de 21.339 documenten — daar nul
    # verschil, in beide richtingen — toen hij is afgebroken omdat hij processor
    # wegnam van de zorgoogst, en dáár kost dat blijvend gegevens: het
    # OCR-tijdbudget is kloktijd, dus een document dat door drukte niet op tijd
    # gelezen wordt, gaat als "bekeken" de lijst in en komt niet terug. De regel
    # is dus goed onderbouwd en aantoonbaar onschadelijk op het gemeten deel,
    # maar de opbrengst over de volle bron is onbekend.
    beste: dict[tuple[str, int], dict] = {}
    for verklaring in ruw:
        sleutel = (verklaring["organisatie"].lower(), verklaring["boekjaar"])
        vorige = beste.get(sleutel)
        if vorige is None or _vensterlengte(verklaring) > _vensterlengte(vorige):
            # dict houdt de invoegvolgorde aan, dus vervangen laat de plaats
            # van de eerste vermelding in het document intact.
            beste[sleutel] = verklaring
    return list(beste.values())


def _vensterlengte(verklaring: dict) -> int:
    begin, eind = verklaring["venster"]
    return eind - begin
