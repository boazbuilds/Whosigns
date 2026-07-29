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
    """Documenten die een accountantsverklaring (kunnen) bevatten.

    Naast het losse type telt ook het verzameldocument mee: dat bundelt
    jaarrekening, bestuursverslag en verklaring in één pdf.
    """
    return [
        doc
        for doc in alle_documenten(organisatie)
        if doc.get("type", "").startswith("Accountantsverklaring")
        or doc.get("type") == "Verzameldocument"
    ]
