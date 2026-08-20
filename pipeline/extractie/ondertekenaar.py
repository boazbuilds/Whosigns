"""De naam van de accountant die de verklaring ondertekende.

Mag sinds 20-8-2026 worden vastgelegd, mits hij uit een openbare bron komt: de
gedeponeerde verklaring zelf. Zie `docs/concept.md` §9 — inclusief de grondslag,
die *niet* is dat accountants buiten de AVG vallen maar gerechtvaardigd belang
bij een al openbaar gegeven. Andere natuurlijke personen horen hier niet in, ook
niet in de teruggave en niet in een logregel.

Waarom een eigen module en niet een regel in `kantoor_match.py`
--------------------------------------------------------------
`kantoor_match` kent al `_ONDERTEKENAAR_NA`: die kijkt of er ná een kantoornaam
een persoonsnaam met beroepstitel staat, en gebruikt dat als bewijs dat de
kantoornaam op een ondertekeningsplek staat. Verleidelijk om daar de naam uit te
plukken, maar dat gaat op drie punten mis, en alle drie zijn ze gemeten
(20-8-2026, op 1.084 gecachte documenten met tekstlaag):

- **Het bewijs is circulair.** `DREMPEL_ONDERTEKENING` is 2 en de
  ondertekenaar-regel keert precies +2 uit. De vraag "staat hier een
  handtekening?" wordt dan beantwoord door de vondst die je juist wilt toetsen.
  Een zin als "<kantoor>, vertegenwoordigd door <naam> RA" in een verslag van de
  raad van toezicht haalt de drempel zo, en levert een naam op die niets heeft
  ondertekend.
- **Het blok hoeft geen verklaring te zijn.** 25 van 603 namen (4,1%) kwamen uit
  iets anders: de begeleidende brief bij een accountantsverslag ("Hoogachtend,
  <kantoor> <naam> RA"), een rapport bij een productieverantwoording, en twee
  assurance-rapporten uit transparantieverslagen van kantoren zelf. Die naam zou
  in de database komen mét het oordeel van het hele document.
- **Het werkt op de genormaliseerde tekst.** Daar zijn de punten weg, en dan is
  OCR-schade onzichtbaar: 8 van 58 namen uit OCR-tekst waren beschadigd, één met
  een weggevallen voorletter. Dat is geen spelfout maar een andere persoon.

Deze module leest daarom de rúwe tekst, en eist onafhankelijk bewijs dat er een
verklaring ligt: een kop én een oordeelzin. Wat overblijft is smal en dat is de
bedoeling. Leeg is gratis; een verkeerde naam onder een niet-goedkeurend oordeel
is een beschuldiging.
"""

import re

# --------------------------------------------------------------- de naam zelf

# Op de RUWE tekst, met punten. Verplichte initialen met punt, hooguit drie
# tussenvoegsels, een achternaam, en een beroepstitel. De titel is niet optioneel:
# zonder titel is een hoofdletterwoord in een jaarverslag te vaak een plaatsnaam,
# een productnaam of een kop.
_NAAM = re.compile(
    # De naam moet zijn eigen regel beginnen, eventueel na "was getekend" of
    # "w.g.". Zonder die eis slokt het initialenpatroon de rechtsvorm van de
    # regel erbóven op: "Voorbeeld Accountants B.V.\n\nA.B. van der Meer RA"
    # werd "B.V. A.B. van der Meer RA", want "B." en "V." zijn geldige
    # initialen. Dat is geen gemiste naam maar een verkeerde naam, en die zijn
    # hier duurder dan lege velden.
    r"^[ \t]*"
    r"(?:(?:was\s+)?getekend(?:\s+door)?|w\.?\s?g\.?|validsigned(?:\s+door)?"
    r"|origineel\s+getekend(?:\s+door)?)?[:\s]*"
    r"(?P<aanhef>(?:drs|mr|ir|ing|prof|dr|mw|dhr)\.?\s+){0,2}"
    r"(?P<initialen>(?:[A-Z]\.\s*){1,5})"
    r"(?P<tussen>(?:(?:van|de|den|der|ten|ter|op|in|het|te|'t)\s+){0,3})"
    r"(?P<achternaam>[A-Z][A-Za-zÀ-ÿ'’-]{1,30}"
    r"(?:\s+[A-Z][A-Za-zÀ-ÿ'’-]{1,30}){0,2})"
    r"(?P<graad>(?:\s+(?:MSc|MSC|BSc|LLM|MBA|MA|MS))?)"
    r"(?P<titel>(?:\s+(?:RA|AA|RB|RE|RC))+)"
    r"(?![A-Za-z])",
    re.M,
)

# De kop van een controleverklaring. Alleen deze kop telt: "assurance-rapport",
# "samenstellingsverklaring" en "beoordelingsverklaring" zijn andere opdrachten
# en horen niet in dit veld.
_KOP = re.compile(
    r"controleverklaring\s+van\s+de\s+onafhankelijke\s+accountant",
    re.I,
)

# Onafhankelijk bewijs dat er in dit blok een oordeel wordt uitgesproken.
_OORDEELZIN = re.compile(
    r"naar\s+ons\s+oordeel|ons\s+oordeel\s+met\s+beperking|wij\s+onthouden\s+ons"
    r"|geven\s+wij\s+geen\s+oordeel|in\s+our\s+opinion|ons\s+oordeel\b",
    re.I,
)

# Waar een handtekening begint. De plaats-en-datumregel is het sterkste anker:
# die staat in vrijwel elke verklaring vlak boven de ondertekening.
_PLAATS_DATUM = re.compile(
    r"^[ \t]*[A-Z][A-Za-zÀ-ÿ'’ .-]{2,40},\s*\d{1,2}\s+"
    r"(?:januari|februari|maart|april|mei|juni|juli|augustus|september|oktober"
    r"|november|december)\s+(?:19|20)\d{2}[ \t]*$",
    re.M,
)
_WAS_GETEKEND = re.compile(r"was\s+getekend|w\.?\s?g\.?\s|origineel\s+getekend"
                           r"|validsigned|getekend\s+door", re.I)

# Hoe ver ná een anker een naam nog een handtekening kan zijn. Ruim genoeg voor
# "<kantoor> B.V.\n\nwas getekend\n\n<naam> RA", krap genoeg om het colofon twee
# alinea's verderop buiten te sluiten.
VENSTER_NA_ANKER = 170

# Hoe ver een blok maximaal doorloopt als er geen volgende kop is. Een
# controleverklaring is zelden langer dan een paar duizend tekens; ruimer maken
# betekent dat bijlage, colofon en dankwoord meetellen, en dat is precies waar de
# verkeerde namen staan.
BLOKLENGTE = 12000

# Rollen die iemand tot iets anders maken dan de ondertekenaar. Als deelwoord en
# niet met woordgrenzen, want het Nederlands plakt: "auditcommissie",
# "kascommissie", "raadscommissie", "adviesraad", "ledenraad",
# "verantwoordingsorgaan" en "bestuurssecretaris" glippen allemaal door een
# \b-filter heen.
_ROLDELEN = (
    "commissie", "raad", "toezicht", "bestuur", "secretar", "voorzitter",
    "penningmeester", "directeur", "directie", "notaris", "controller",
    "manager", "vaktechniek", "behandeld door", "colofon", "redactie",
    "orgaan", "verantwoordingsorgaan", "toezichthoud", "lid ", "leden",
)

# Woorden die geen achternaam zijn. Ze duiken op in afkortingenlijsten, waar
# "RA x Registeraccountant" het naampatroon kan halen.
_GEEN_ACHTERNAAM = (
    "registeraccountant", "accountant", "kwaliteitsmanagementsysteem",
    "assurance", "audit", "controle", "jaarrekening", "verklaring",
)


def _rol_in_de_buurt(tekst: str, positie: int) -> str | None:
    """Staat er op of vlak boven deze regel een rolaanduiding?

    Op régels en niet op een venster van zoveel tekens, en dat is niet
    cosmetisch. Elke controleverklaring begint met een adresregel: "Aan: het
    bestuur van ..." of "Aan de raad van toezicht van ...". Een venster van
    tweehonderd tekens pikt dat in een kort blok gewoon op, en dan wijst het
    filter precies de goede naam af — dat gebeurde bij de eerste versie hiervan.
    De aanhef staat bovenaan, de handtekening onderaan; een venster van drie
    regels haalt ze uit elkaar.

    Ook de regel erbóven meekijken is met opzet: een kop als "Colofon" of "Raad
    van toezicht" staat vóór de naam, niet erachter.
    """
    regelstart = tekst.rfind("\n", 0, positie) + 1
    vorige_start = tekst.rfind("\n", 0, max(0, regelstart - 1)) + 1
    regeleind = tekst.find("\n", positie)
    regeleind = len(tekst) if regeleind < 0 else regeleind
    venster = tekst[vorige_start:regeleind].lower()
    for deel in _ROLDELEN:
        if deel in venster:
            return deel
    return None


def _blokken(tekst: str) -> list[tuple[int, int]]:
    """De stukken tekst die een controleverklaring zijn."""
    koppen = [m.start() for m in _KOP.finditer(tekst)]
    uit = []
    for i, start in enumerate(koppen):
        volgende = koppen[i + 1] if i + 1 < len(koppen) else len(tekst)
        uit.append((start, min(volgende, start + BLOKLENGTE)))
    return uit


def _ankers(blok: str) -> list[int]:
    """Posities waar een ondertekening kan beginnen, binnen dit blok."""
    plekken = [m.end() for m in _PLAATS_DATUM.finditer(blok)]
    plekken += [m.end() for m in _WAS_GETEKEND.finditer(blok)]
    return sorted(plekken)


def _schoon(match: re.Match) -> str:
    """De naam zoals hij in het stuk staat, met de witruimte gladgestreken.

    Uit de benoemde groepen en niet uit `group(0)`: die begint bij het begin van
    de regel en bevat dus ook "was getekend" of "w.g.". Dat hoort niet in een
    naam en al helemaal niet in de sleutel waarop de accountantspagina groepeert.
    """
    delen = "".join(
        match.group(naam) or ""
        for naam in ("aanhef", "initialen", "tussen", "achternaam", "graad", "titel")
    )
    return re.sub(r"\s+", " ", delen).strip()


def zoek_ondertekenaar(tekst: str, kantoornaam: str | None = None) -> dict:
    """Zoekt de ondertekenaar van de controleverklaring in de ruwe tekst.

    Geeft altijd hetzelfde dict terug:

        naam        de naam, of None
        reden       waarom er geen naam is (leeg bij een treffer)
        kandidaten  wat er is afgewezen, zodat de review-queue iets heeft
        blok        (start, eind) van het blok waar de naam uit komt, of None

    `kantoornaam` is optioneel en maakt de eis strenger: staat hij in het blok,
    dan moet hij tussen het anker en de naam liggen. Dat sluit het geval uit
    waarin de naam wel bij een handtekening staat maar bij die van een ánder
    kantoor — een verzameldocument met twee verklaringen erin.
    """
    blokken = _blokken(tekst)
    if not blokken:
        return {"naam": None, "reden": "geen controleverklaring-kop gevonden",
                "kandidaten": [], "blok": None}

    afgewezen: list[str] = []
    treffers: list[tuple[str, tuple[int, int]]] = []

    for start, eind in blokken:
        blok = tekst[start:eind]
        if not _OORDEELZIN.search(blok):
            continue
        ankers = _ankers(blok)
        if not ankers:
            continue
        in_dit_blok: list[str] = []
        for match in _NAAM.finditer(blok):
            # Het dichtstbijzijnde anker vóór de naam, en niet zomaar een anker
            # ergens in het blok: anders telt een kop bovenaan als bewijs voor
            # een naam duizend tekens verderop.
            eerder = [a for a in ankers if a <= match.start()]
            if not eerder:
                continue
            anker = eerder[-1]
            if match.start() - anker > VENSTER_NA_ANKER:
                continue
            naam = _schoon(match)
            achter = match.group("achternaam").lower()
            if any(w in achter for w in _GEEN_ACHTERNAAM):
                afgewezen.append(naam)
                continue
            rol = _rol_in_de_buurt(blok, match.start())
            if rol:
                afgewezen.append(naam)
                continue
            if kantoornaam:
                kern = kantoornaam.split()[0].lower()
                tussenin = blok[anker : match.start()].lower()
                voor_anker = blok[max(0, anker - 300) : anker].lower()
                if kern not in tussenin and kern not in voor_anker:
                    afgewezen.append(naam)
                    continue
            in_dit_blok.append(naam)
        # Twee namen in hetzelfde handtekeningblok worden niet tot één gegokt.
        uniek = list(dict.fromkeys(in_dit_blok))
        if len(uniek) == 1:
            treffers.append((uniek[0], (start, eind)))
        elif len(uniek) > 1:
            afgewezen.extend(uniek)

    unieke_namen = list(dict.fromkeys(n for n, _ in treffers))
    if len(unieke_namen) == 1:
        return {"naam": unieke_namen[0], "reden": "",
                "kandidaten": [], "blok": treffers[0][1]}
    if len(unieke_namen) > 1:
        return {"naam": None,
                "reden": f"{len(unieke_namen)} verschillende ondertekenaars in het stuk",
                "kandidaten": unieke_namen[:5], "blok": None}
    return {"naam": None,
            "reden": "geen naam op een ondertekeningsplek",
            "kandidaten": list(dict.fromkeys(afgewezen))[:5], "blok": None}
