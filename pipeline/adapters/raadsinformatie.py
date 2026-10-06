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

Twee zoekvragen
---------------
De eerste vraagt om de kop "controleverklaring van de onafhankelijke
accountant". De tweede (sinds 5-10-2026) om dezelfde standaardzin zónder die
kop: accountantsverslagen aan de raad ("Wij hebben de jaarrekening 2018 van de
gemeente X gecontroleerd. …") en verklaringen in een oudere opmaak zonder die
kop. Gemeten op 5-10-2026: 21.339
documenten voor de eerste vraag, 4.283 voor de tweede, geen overlap. Wat de
lader met die tweede soort wel en niet doet staat in laad_raadsinformatie.py.

Geen dependencies buiten de standaardbibliotheek.
"""

import datetime
import json
import re
import time
import urllib.request

API = "https://api.openraadsinformatie.nl/v1/elastic/_search"
ZOEKZIN = "controleverklaring van de onafhankelijke accountant"

# De twee zoekvragen, op naam. `documenten()` en `totaal_documenten()` lezen
# allebei uit deze ene tabel: de vervang-stand in de lader vergelijkt het aantal
# gelezen documenten met het opgegeven totaal, en als die twee niet over
# precies dezelfde vraag gaan, wist hij op een vergelijking die niets zegt.
#
# De tweede vraag sluit de eerste uit (must_not), zodat geen document twee keer
# wordt gelezen en de totalen gewoon optellen. "opgenomen jaarrekening" staat
# erbij voor de oudere gemeenteformulering "Wij hebben de in dit document
# opgenomen jaarrekening 2011 van de gemeente X, opgesteld onder
# verantwoordelijkheid van het college, gecontroleerd" — zonder die frase vond
# de vraag 2.927 documenten, met 4.283 (5-10-2026).
ZOEKVRAGEN = {
    "controleverklaring": {"match_phrase": {"text": ZOEKZIN}},
    "accountantsverslag": {
        "bool": {
            "must": [
                {
                    "bool": {
                        "should": [
                            {"match_phrase": {"text": "wij hebben de jaarrekening"}},
                            {"match_phrase": {"text": "opgenomen jaarrekening"}},
                        ],
                        "minimum_should_match": 1,
                    }
                },
                {"match": {"text": "gecontroleerd"}},
            ],
            "must_not": [{"match_phrase": {"text": ZOEKZIN}}],
        }
    },
}

# Bovengrens voor het boekjaar. Een jaarrekening over de toekomst bestaat niet;
# staat er toch zo'n jaartal, dan is de regel verhaspeld.
#
# Uit de kalender en niet als vast getal: hier stond 2026, en vanaf 2028 zou
# elke jaarrekening over 2027 dan stil wegvallen als "verhaspeld". Het lopende
# jaar zelf mag (een gebroken boekjaar of een tussentijdse jaarrekening), het
# jaar erna niet.
HUIDIG_JAAR = datetime.date.today().year
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

# De kop van een controleverklaring, en hoe ver vóór de standaardzin hij mag
# staan om nog bij dezelfde verklaring te horen. Gemeten op een derde van de
# bron (5-10-2026, 4.257 vermeldingen met een kop ervóór): mediaan 214 tekens,
# 97% binnen de 800 van het kantoorvenster. De rest is vooral het sjabloon
# waarin het hele oordeel tussen kop en standaardzin staat; 49 keer lag de
# laatste kop verder dan 4.000 tekens terug, en dan is het meestal een
# inhoudsopgave en niet de kop van deze verklaring.
_KOP = re.compile(r"controleverklaring\s+van\s+de\s+onafhankelijke\s+accountant", re.I)
KOP_AFSTAND = 4000

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


def totaal_documenten(haal=None, zoekvraag: str = "controleverklaring") -> int | None:
    """Hoeveel documenten vallen onder deze zoekvraag? `None` als de API het niet zegt.

    Eén verzoek met `size: 0`, dus zonder de documenten zelf op te halen.
    Bestaat om te kunnen controleren of een doorloop echt de hele bron heeft
    gezien — zie de vervang-stand in laad_raadsinformatie.py. Gemeten
    11-8-2026: 21.339, met relation "eq" (een exact getal, geen ondergrens).
    """
    antwoord = (haal or _haal)(
        {
            "query": ZOEKVRAGEN[zoekvraag],
            "size": 0,
            "track_total_hits": True,
        }
    )
    totaal = ((antwoord.get("hits") or {}).get("total") or {})
    waarde = totaal.get("value")
    return int(waarde) if isinstance(waarde, int) else None


def documenten(
    per_pagina: int = 100,
    maximum: int = 25_000,
    haal=None,
    zoekvraag: str = "controleverklaring",
    pauze: float = 0.0,
):
    """Alle documenten onder deze zoekvraag, in stukjes.

    Bladeren gaat met `search_after` en niet met `from`: Elasticsearch weigert
    `from` boven de tienduizend, en dat is precies waar deze bron begint.

    `pauze` is de wachttijd tussen twee verzoeken. Open Raadsinformatie is een
    publieke voorziening zonder sleutel of quotum; één lader die er een
    halfuur lang zo snel mogelijk pagina's van honderd volle documenten uit
    trekt, hoort daar niet. Een vijfde seconde per pagina kost over de hele
    bron anderhalve minuut.
    """
    na = None
    opgehaald = 0
    while opgehaald < maximum:
        if pauze and opgehaald:
            time.sleep(pauze)
        lichaam = {
            "query": ZOEKVRAGEN[zoekvraag],
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
            # Het documentnummer van Open Raadsinformatie gaat mee: daarmee is
            # het stuk terug te vinden zonder de titel of de url te bewaren
            # (zie verklaringen_uit).
            yield {**(treffer.get("_source") or {}), "_id": treffer.get("_id")}
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


# Staarten die de zin achter de naam hangt en die niets over de identiteit
# zeggen: een afkorting voor de rest van de tekst, of de bijzin over wie de
# jaarrekening opstelde.
#
#   Gemeente Meppel (hierna te noemen: 'gemeente')
#   Gemeente Venlo (‘de gemeente’)
#   Gemeenschappelijke Regeling GGD West-Brabant (verder genoemd: GGD West-Brabant)
#   Gemeente Voorst, opgesteld onder verantwoordelijkheid van het college van
#     burgemeester en wethouders
#   GBLT, opgesteld ender verantwoordelijkheid van het dagelijks bestuur  (OCR)
#
# Zonder deze schoonmaak matcht de naam niet met de organisatie die er al staat,
# en ontstaat er een tweede gemeente naast de eerste: op 5-10-2026 stonden er 36
# organisatienamen met "hierna", 34 met een aanhalingsteken-alias tussen haakjes
# en 8 met "opgesteld" in de database. In de tweede zoekvraag droeg ruim een
# derde van de namen zo'n staart (208 van de 585, gemeten vóór deze
# schoonmaak) — de oudere gemeenteverklaring schrijft de opsteller standaard in
# de zin.
#
# Een afkorting tússen haakjes zonder aanhalingstekens blijft staan: "(AGV)" en
# "(OLCT)" horen bij de statutaire naam.
_STAART = re.compile(
    r"\s*\(\s*(?:hierna|hiema|verder)\b.*$"
    r"|,?\s+(?:hierna|hiema)\b.*$"
    r"|,?\s+verder\s+(?:te\s+noemen|genoemd)\b.*$"
    r"|\s*\(\s*[\"'‘’“”„][^()]{1,40}\)\s*$"
    r"|,?\s*opgesteld\s+(?:onder|ender|door)\b.*$"
    r"|,?\s+zoals\s+opgenomen\b.*$"
    r"|\s*[\"'‘’“”]?\s*in\s+liquidatie\s*[\"'‘’“”]?\s*$",
    re.I | re.S,
)

# "Uw gemeente Kapelle", "Uw gemeenschappelijke regeling WVS Groep": de
# aanspreekvorm van een accountantsverslag aan de raad, niet het begin van een
# naam. Alleen vóór een soortnaam, want "Uw" en "Onze" kunnen óók het begin van
# een echte naam zijn: "Onze Huisartsen B.V.", "UW Werkmaatschappij B.V." (beide
# met KvK-nummer) en "Uw Toekomst N.V." stonden op 6-10-2026 in de database, en
# zonder die rem viel een lezing "Werkmaatschappij B.V." op de strenge sleutel
# samen met die van de KvK-organisatie. Gemeten over beide zoekvragen: de
# standaardzin zet "uw" alleen vóór organisatie (377), gemeente (189),
# gemeenschappelijke regeling (97), onderneming (9), veiligheidsregio (4),
# stichting (2), GGD en milieudienst; "onze" komt er niet in voor.
_AANSPREEKVORM = re.compile(
    r"^(?:uw|onze)\s+(?=(?:gemeente|gemeenschappelijke\s+regeling|regeling|"
    r"organisatie|onderneming|stichting|vereniging|holding|veiligheidsregio|"
    r"omgevingsdienst|milieudienst|ggd|provincie|waterschap)\b)",
    re.I,
)


def _zonder_staart(naam: str) -> str:
    schoon = re.sub(r"\s+", " ", naam).strip(" ,.;:-–—")
    vorige = None
    while vorige != schoon:
        vorige = schoon
        schoon = _STAART.sub("", schoon).strip(" ,.;:-–—")
        schoon = _AANSPREEKVORM.sub("", schoon)
    # "Gemeente Gemeente Barendrecht": de aanhef en de naam plakken aan elkaar.
    return re.sub(r"^(\w+)\s+(?=\1\b)", "", schoon, flags=re.I)


def _schoon_organisatie(naam: str) -> str:
    schoon = re.sub(r"\s+", " ", naam).strip(" ,.;:-–—")
    schoon = _AANHEF.sub("", schoon)
    # Een naam die met een lidwoord begint is meestal een doorgelopen zin.
    schoon = re.sub(r"^(?:de|het|een)\s+", "", schoon, flags=re.I)
    schoon = _DUBBELE_REGELING.sub("", schoon).strip()
    schoon = _zonder_staart(schoon)
    # De zin schrijft de rechtsvorm nu eens met en dan weer zonder hoofdletter;
    # als weergavenaam is één schrijfwijze genoeg.
    if schoon[:1].islower():
        schoon = schoon[:1].upper() + schoon[1:]
    return schoon


# Een plaats die na het afknippen van de staart achteraan de naam blijft
# hangen: "Permar Energiek B.V. te Ede ('de vennootschap')" wordt eerst
# "Permar Energiek B.V. te Ede", en "Ede" hoort dan in het plaatsveld, net als
# bij de zin die direct na de plaats "gecontroleerd" zegt. De plaats moet met
# een hoofdletter beginnen; "te gemeente De Wolden" is geen plaats.
_PLAATS_ACHTERAAN = re.compile(
    r"^(?P<naam>.*?\S)\s*,?\s+(?:statutair\s+)?(?:gevestigd\s+)?te\s+"
    r"(?P<plaats>(?:'s[-\s]|’s[-\s])?[A-Z][\w'’\-]+"
    r"(?:\s+(?:[A-Z][\w'’\-]*|aan|den|de|der|op|bij|en|in))*"
    r"(?:\s*\([A-Za-z.]{1,5}\))?)$"
)


def plaats_achteraan(naam: str) -> str | None:
    """De plaats achter een organisatienaam ("… te Hoorn"), of None.

    Voor namen die al in de database staan: de lader vergelijkt er de plaats
    van twee organisaties mee die op de strenge sleutel samenvallen.
    """
    treffer = _PLAATS_ACHTERAAN.match(_zonder_staart(naam or ""))
    return treffer["plaats"] if treffer else None


# "Wij hebben de jaarrekening 2019 van de gemeente Tilburg Tilburg
# gecontroleerd": het woord "te" is uit de zin gevallen. Alleen bij een
# gemeente waarvan de hele naam zich herhaalt, want "Brum Brum" is een echte
# organisatienaam (KvK) en een herhaald woord op zich bewijst niets.
_GEMEENTE_ZONDER_TE = re.compile(r"^(?P<naam>gemeente\s+(?P<plaats>.+?))\s+(?P=plaats)$", re.I)

# Een naam die alleen uit de soort organisatie bestaat, zonder eigennaam. Komt
# uit "Uw gemeenschappelijke regeling, opgesteld onder …" of "Gemeente (hierna
# te noemen 'gemeente')" zodra de staart eraf is, en zou anders als organisatie
# "Gemeente" de database in gaan. "Onderneming" en "Milieudienst" komen uit
# "Uw onderneming" en "Uw milieudienst, opgesteld onder …" (6-10-2026: tien
# keer, toen nog zonder ondertekening in het venster).
_ALLEEN_SOORT = re.compile(
    r"^(?:de\s+|het\s+)?(?:gemeente|provincie|waterschap|hoogheemraadschap|"
    r"wetterskip|gemeenschappelijke\s+regeling|regeling|veiligheidsregio|"
    r"omgevingsdienst|stichting|vereniging|organisatie|openbaar\s+lichaam|gr|"
    r"bedrijfsvoeringsorganisatie|samenwerkingsverband|onderneming|milieudienst)$",
    re.I,
)

# Een zin die is doorgelopen en daarom geen naam is. Gemeten in de tweede
# zoekvraag (5-10-2026): "Gemeente Nieuwkoop afgerond. Bijgevoegd" uit "Wij
# hebben de controle van de jaarrekening 2023 van de gemeente Nieuwkoop
# afgerond", "Kredietbank Limburg is door ons" en "Gemeente Weesp voor de
# laatste keer". En "OPOPS is" wat overblijft van "OPOPS is opgesteld door …".
_DOORGELOPEN_ZIN = re.compile(
    r"\b(?:afgerond|bijgevoegd|is\s+door\s+ons|voor\s+de\s+laatste\s+keer)\b"
    r"|\s(?:is|zijn|wordt|werd)$",
    re.I,
)


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
    # Eerst dezelfde staarten eraf als bij het lezen van de naam. Hier is dat
    # geen opmaak maar herkenning: de database bevat nog namen van vóór die
    # schoonmaak ("Gemeente Venlo (‘de gemeente’)"), en de schone naam uit een
    # nieuwe lezing moet daar op dezelfde sleutel uitkomen.
    kaal = _normaliseer_kaal(_zonder_staart(naam))
    # "… te Hoofddorp", "…, te Meerkerk", "… te gemeente De Wolden",
    # "…, gevestigd te Roosendaal", "… statutair gevestigd te Rotterdam"
    #
    # De spatie vóór "te" mag ook ontbreken. In de pdf-tekst plakt de staart
    # soms direct achter de afkorting tussen haakjes: "Waterschap Amstel, Gooi
    # en Vecht (AGV)te Amsterdam", "… Crematoria Twente (OLCT)te Enschede".
    # Zonder de ")" in dit tekenklasje bleven dat aparte organisaties naast de
    # versie zonder plaatsnaam. Gemeten over de 1.770 overheidsorganisaties in
    # de database (11-8-2026): twee namen erbij die samenvallen, allebei goed,
    # geen enkele verkeerde samenvoeging.
    kaal = re.sub(
        r"[,.\s)]+(?:statutair\s+)?(?:gevestigd\s+)?te\s+[a-z'\-. ]+$", "", kaal
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
        if not plaats and (achteraan := _PLAATS_ACHTERAAN.match(organisatie)):
            organisatie, plaats = achteraan["naam"].rstrip(" ,"), achteraan["plaats"]
        if not plaats and (zonder_te := _GEMEENTE_ZONDER_TE.match(organisatie)):
            organisatie, plaats = zonder_te["naam"], zonder_te["plaats"]
        if len(organisatie) < 4 or _GEEN_ORGANISATIE.search(organisatie):
            continue
        if _ALLEEN_SOORT.match(organisatie) or _DOORGELOPEN_ZIN.search(organisatie):
            continue
        if not re.search(r"[A-Za-zÀ-ÿ]{3}", organisatie):
            continue
        ruw.append(
            {
                "organisatie": organisatie,
                "boekjaar": boekjaar,
                "plaats": plaats,
                "positie": treffer.start(),
                # Het documentnummer en niet de titel: een titel noemt soms een
                # wethouder ("Mededeling wethouder … jaarverslag 2021 …"), en
                # een deel van de raadsinformatiesystemen zet de bestandsnaam
                # ook in de url (bij parlaeus 278 van de 326 urls, gemeten
                # 6-10-2026). De url blijft voor wie het stuk zelf ophaalt; in
                # een rapport of de review-queue hoort het nummer.
                "document_id": str((bron or {}).get("_id") or ""),
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
        # Voor oordeel en ondertekenaar: vanaf de kop van déze verklaring. Een
        # deel van de verklaringen zet de oordeelzin vóór de standaardzin ("Ons
        # oordeel — Naar ons oordeel: • geeft … een getrouw beeld …; • zijn …
        # rechtmatig … Wij hebben de jaarrekening 2019 van X gecontroleerd"),
        # en dan valt die net buiten de 800 tekens van het kantoorvenster —
        # en de kop, die de naamzoeker nodig heeft, ook. De kop moet wel ná de
        # vorige vermelding staan, anders hoort hij bij de buurman.
        vorige = ruw[index - 1]["positie"] if index else 0
        koppen = [
            kop.start()
            for kop in _KOP.finditer(
                tekst, max(vorige, verklaring["positie"] - KOP_AFSTAND),
                verklaring["positie"],
            )
        ]
        verklaring["oordeelvenster"] = (
            koppen[-1] if koppen else verklaring["venster"][0], volgende
        )

    # Dezelfde organisatie en hetzelfde boekjaar twee keer in één document is
    # een herhaling: een raadsbundel noemt de jaarrekening eerst in de
    # aanbiedingsbrief en dan nog eens in de bijgevoegde verklaring zelf. Beide
    # vermeldingen gaan hier tóch mee terug, en dat is een bewuste keuze.
    #
    # Hier stond eerder een ontdubbeling die de vermelding met het langste
    # venster hield. De redenering klopte — het venster van de eerste vermelding
    # eindigt waar de tweede begint, dus vlák vóór het handtekeningblok — maar de
    # maatstaf niet. Gemeten op de volle bron (13-8-2026, uit het rapport van run
    # 31580465246): bij "Gemeenschappelijke regeling Werk en Inkomen Baarn" won
    # venster 2987-9840 (6.853 tekens) van 9040-15535 (6.495), terwijl de
    # handtekening juist in dat kórtere zit. Lengte zegt niets over waar de
    # handtekening staat.
    #
    # Alleen wie de handtekening kán zien, kan kiezen — en dat is deze functie
    # niet. Zij leest tekst en kent geen kantoren. De lader eromheen wél: die
    # loopt de vermeldingen op volgorde af, slaat een venster zonder
    # ondertekening over zónder het als afgehandeld te merken, en schrijft pas
    # een opdracht bij een echte handtekening. Alles teruggeven legt de keuze dus
    # bij de enige laag die hem kan maken.
    #
    # Opbrengst, gemeten op dertig afgewezen verklaringen uit datzelfde rapport:
    # zes leveren alsnog een opdracht op, twintig procent. Over de 315 afgewezen
    # verklaringen zonder bestaand organisatie-boekjaarpaar gaat het om
    # ordegrootte zestig opdrachten.
    return ruw
