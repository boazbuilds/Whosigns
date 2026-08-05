"""Client voor het DigiMV-archief (gedeponeerde stukken per zorgorganisatie).

Het archief op digimv13.desan.nl is een JavaScript-app met een openbare JSON-API
eronder. Twee endpoints zijn relevant:

    GET /api/ArchiveSearch/GetArchiveSearchResult?organization=&town=&year=
    GET /api/ArchiveSearch/GetDocument?documentId=&year=&fileNameOption=&fileName=

Een zoekresultaat is een organisatie met:
    name, town, externalOrganizationId (= KvK-nummer), concernId,
    documents[], locations[], desaveuElements[]

en elk document heeft: id, type, fileName, fileSize, publishedDate.
Documenttypen (boekjaar 2023): Jaarrekening, Accountantsverklaring (controle-,
beoordelings- of samenstellingsverklaring), Bestuursverslag, Verslag interne
toezichthouder, Verzameldocument, Overig.

Let op het hostnummer: de app rekent het jaar om naar een subdomein
(digimv8/12/13.desan.nl). ARCHIEF_HOST hieronder is de stand van juli 2026 en moet
bij een 404 opnieuw worden vastgesteld via jaarverantwoordingzorg.nl.

Wees zuinig met de bron: PAUZE_SECONDEN tussen downloads, en resultaten cachen
(elke opgehaalde pdf gaat volgens principe 1 ruw naar Storage vóór verwerking).
"""

import json
import time
import urllib.parse
import urllib.request

ARCHIEF_HOST = "https://digimv13.desan.nl"
ZOEK_PAD = "/api/ArchiveSearch/GetArchiveSearchResult"
DOCUMENT_PAD = "/api/ArchiveSearch/GetDocument"
PAUZE_SECONDEN = 0.4
KOPPEN = {"User-Agent": "WhoSigns-pipeline", "Accept": "application/json"}


def _haal_op(url: str, timeout: int = 90) -> bytes:
    verzoek = urllib.request.Request(url, headers=KOPPEN)
    with urllib.request.urlopen(verzoek, timeout=timeout) as antwoord:
        return antwoord.read()


def zoek(organisatie: str = "", plaats: str = "", boekjaar: int = 2023) -> list[dict]:
    """Organisaties met gedeponeerde stukken. Lege zoektermen geven niets terug —
    de API vereist minstens een organisatie- of plaatsfragment."""
    query = urllib.parse.urlencode(
        {"organization": organisatie, "town": plaats, "year": boekjaar}
    )
    return json.loads(_haal_op(f"{ARCHIEF_HOST}{ZOEK_PAD}?{query}"))


def haal_document(document: dict, boekjaar: int) -> bytes:
    """Ruwe bytes van één gedeponeerd document (meestal pdf)."""
    query = urllib.parse.urlencode(
        {
            "documentId": document["id"],
            "year": boekjaar,
            "fileNameOption": "",
            "fileName": document["fileName"],
        }
    )
    data = _haal_op(f"{ARCHIEF_HOST}{DOCUMENT_PAD}?{query}")
    time.sleep(PAUZE_SECONDEN)
    return data


def alle_documenten(organisatie: dict) -> list[dict]:
    """Alle documenten van een organisatie, waar ze ook hangen.

    Let op: documenten staan niet altijd op het topniveau. Bij een deel van de
    organisaties (en systematisch in sommige boekjaren, o.a. 2022) hangen ze
    onder `locations[].documents` — per vestiging. Wie alleen naar het
    topniveau kijkt, ziet die organisaties ten onrechte als "geen stukken
    gedeponeerd". Ook `desaveuElements` kan documenten bevatten.
    """
    documenten = list(organisatie.get("documents") or [])
    for groep in ("locations", "desaveuElements"):
        for onderdeel in organisatie.get(groep) or []:
            documenten.extend(onderdeel.get("documents") or [])
    return documenten


def verklaringen(organisatie: dict) -> list[dict]:
    """Documenten die een accountantsverklaring (kunnen) bevatten, beste eerst.

    De volgorde is belangrijk, want het documenttype in de bron is een keuze van
    de indiener en klopt lang niet altijd:

    1. **Accountantsverklaring** — bedoeld als de verklaring zelf, maar in de
       praktijk uploadt een deel van de organisaties hier de *aanbiedingsbrief*
       van de accountant. Die noemt geen oordeel en soms zelfs geen kantoor.
    2. **Verzameldocument** — bundelt jaarrekening, bestuursverslag en verklaring.
    3. **Jaarrekening** — bevat de verklaring vrijwel altijd als laatste hoofdstuk.
       Dit is het vangnet voor geval 1: bij "Stichting LuciVer" (boekjaar 2023)
       stond onder Accountantsverklaring alleen een aanbiedingsbrief en zat de
       controleverklaring in de jaarrekening-pdf.

    De aanroeper (`digimv.verwerk_organisatie`) loopt deze lijst af tot er één een
    controleverklaring mét herkend kantoor oplevert. Jaarrekeningen staan achteraan
    omdat ze fors groter zijn — we halen ze alleen op als het moet.
    """
    documenten = alle_documenten(organisatie)

    def van_type(*typen: str) -> list[dict]:
        return [d for d in documenten if d.get("type", "") in typen]

    accountantsverklaring = [
        d for d in documenten if d.get("type", "").startswith("Accountantsverklaring")
    ]
    return accountantsverklaring + van_type("Verzameldocument") + van_type("Jaarrekening")


# --- de hele populatie uit het archief zelf -------------------------------
#
# De jaardataset (.ods) bestaat alleen voor 2022 t/m 2024, en voor 2019 t/m 2021
# mist hij de accountantsverklaring-velden helemaal. Voor die jaargangen leende
# `laad_zorg.py` de organisatielijst van een ánder boekjaar, met als prijs: wie
# in het lijstjaar geen controle had maar in het gescande jaar wél, viel weg.
#
# Dat blijkt de meerderheid te zijn. Het archief is namelijk zelf volledig
# doorzoekbaar. Gemeten op 5-8-2026 door de zoekfunctie op elke letter a-z los
# te bevragen en de uitkomsten samen te voegen:
#
#     boekjaar 2019   4.982 organisaties in het archief, 2.211 met een verklaring
#     boekjaar 2020   5.021                              2.351
#     boekjaar 2021   5.117                              2.471
#     boekjaar 2025  14.206                              1.146  (nog niet iedereen
#                                                                heeft gedeponeerd)
#
# Tegenover 513, 544, 580 en 640 opdrachten die er voor die jaren in de database
# stonden. Elke organisatie draagt haar KvK-nummer, dus samenvoegen is exact.
#
# Waarom a-z volstaat: de zoekfunctie doet een deelstringvergelijking op de naam,
# en elke Nederlandse organisatienaam bevat minstens één letter. De vereniging
# van alle zesentwintig uitkomsten is dus de volledige lijst. Zesentwintig
# verzoeken per boekjaar — verwaarloosbaar naast de duizenden pdf's erna.

import csv  # noqa: E402
import string  # noqa: E402
from pathlib import Path  # noqa: E402

VERKLARING_TYPE = "accountantsverklaring"
ARCHIEF_VELDEN = ["kvk_nummer", "naam", "plaats", "boekjaar"]


def alle_organisaties(boekjaar: int, pauze: float = PAUZE_SECONDEN) -> list[dict]:
    """Elke organisatie met stukken in het archief van dit boekjaar.

    Samengevoegd op KvK-nummer; organisaties zonder KvK-nummer vallen af, want
    zonder sleutel is een organisatie niet te koppelen.
    """
    gezien: dict[str, dict] = {}
    for letter in string.ascii_lowercase:
        try:
            treffers = zoek(organisatie=letter, boekjaar=boekjaar)
        except Exception:  # noqa: BLE001 — één letter mag mislukken
            continue
        for organisatie in treffers:
            kvk = str(organisatie.get("externalOrganizationId") or "").strip()
            if kvk:
                gezien.setdefault(kvk, organisatie)
        time.sleep(pauze)
    return list(gezien.values())


def heeft_verklaring(organisatie: dict) -> bool:
    return any(
        VERKLARING_TYPE in (document.get("type") or "").lower()
        for document in (organisatie.get("documents") or [])
    )


def doelpopulatie(boekjaar: int, cache: Path | None = None) -> list[dict]:
    """Organisaties met een gedeponeerde accountantsverklaring, in de vorm die
    `laad_zorg.py` verwacht (kvk_nummer, naam, plaats).

    Welke sóórt verklaring het is — controle, beoordeling of samenstelling —
    staat niet in het archief: alle drie vallen onder hetzelfde documenttype.
    Dat blijkt pas uit de pdf, en dat is precies wat de lader er daarna uit
    haalt. Hier filteren we dus ruimer dan de dataset deed; wat geen
    controleverklaring blijkt, valt verderop af.
    """
    pad = cache / f"archiefpopulatie_{boekjaar}.csv" if cache else None
    if pad is not None and pad.exists():
        with pad.open(encoding="utf-8") as bestand:
            rijen = list(csv.DictReader(bestand))
        if rijen and list(rijen[0]) == ARCHIEF_VELDEN:
            return rijen

    rijen = [
        {
            "kvk_nummer": str(organisatie.get("externalOrganizationId") or "").strip(),
            "naam": (organisatie.get("name") or "").strip(),
            "plaats": (organisatie.get("town") or "").strip(),
            "boekjaar": str(boekjaar),
        }
        for organisatie in alle_organisaties(boekjaar)
        if heeft_verklaring(organisatie)
    ]
    if pad is not None:
        pad.parent.mkdir(parents=True, exist_ok=True)
        with pad.open("w", newline="", encoding="utf-8") as bestand:
            schrijver = csv.DictWriter(bestand, fieldnames=ARCHIEF_VELDEN)
            schrijver.writeheader()
            schrijver.writerows(rijen)
    return rijen
