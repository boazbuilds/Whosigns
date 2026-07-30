"""CBF (Centraal Bureau Fondsenwerving) — register + jaarverslagen van goede doelen.

Twee dingen komen hier vandaan, en samen zijn ze voor de goededoelensector wat
DigiMV voor de zorg is:

1. **Het register als brontabel.** Een openbare JSON-API zonder sleutel geeft alle
   erkende goede doelen mét KvK-nummer, RSIN, sector en omvangcategorie:
       GET https://apex.cbf.nl/ords/cbf/publiek/organisaties
   Gemeten 29-7-2026: 826 vermeldingen, waarvan **714 met een actieve erkenning**,
   alle 714 met KvK-nummer én RSIN. Entity resolution is dus geen probleem.

2. **De jaarverslagen als documentspoor.** Het CBF host de jaarverslaggeving zelf,
   op een voorspelbare URL — geen scraping en geen zoekfunctie nodig:
       https://static.cbf.nl/documents/<naam>/<boekjaar>/jaarverslag.pdf
   `<naam>` is het veld `naam` uit de API (url-encoded), `<boekjaar>` het verslagjaar.
   Alleen deze ene bestandsnaam bestaat; `jaarrekening.pdf` en varianten geven 404.

Waarom de erkenning zo goed uitkomt: norm 8.1.3 van de Erkenningsregeling eist een
**controleverklaring** vanaf categorie D (baten > €1 mln) — dat zijn 295 van de 714
organisaties. Daar ligt dus per definitie een accountantsverklaring, óók als de
stichting geen wettelijke controleplicht heeft. Categorie C heeft een
beoordelingsverklaring, A/B minimaal een samenstellingsverklaring: bewust géén
wettelijke controle en dus terecht geen rij in `opdrachten`.

Let op — dit is **geen open data.** Het CBF stelt voorwaarden aan hergebruik
(bronvermelding verplicht, paspoortteksten/logo's/financiële cijfers niet vrij
herbruikbaar, "Algemene Voorwaarden Gebruik CBF-data", contact data@cbf.nl). De
accountantsrelatie zelf halen we uit het jaarverslag — een openbaar stuk van de
stichting zelf — maar het register gebruiken als bronlijst is een keuze die eerst
langs de opdrachtgever moet. Zie `docs/beslissingen.md` #7.

Meetresultaten en de volledige bronverkenning: `docs/bronverkenning-stichtingen.md`.

Geen dependencies buiten de standaardbibliotheek.
"""

import json
import time
import urllib.error
import urllib.parse
import urllib.request

REGISTER_URL = "https://apex.cbf.nl/ords/cbf/publiek/organisaties"
JAARVERSLAG_URL = "https://static.cbf.nl/documents/{naam}/{boekjaar}/jaarverslag.pdf"

# Het archief is niet oneindig diep: boekjaar 2018 leverde 12 treffers op 714
# organisaties, 2019 al 514. Net als bij DigiMV geldt dus "oogsten vóór het weg is".
OUDSTE_BOEKJAAR = 2019

# Baten-grenzen uit de Normen voor de erkenning van Goede Doelen (ingaande 1-1-2026)
# en wat norm 8.1.3 per categorie eist.
CATEGORIE_EIS = {
    "A": ("< €50k", "samenstellingsverklaring of kascommissie"),
    "B": ("€50k–€200k", "samenstellingsverklaring of kascommissie"),
    "C": ("€200k–€1 mln", "samenstellingsverklaring, groeiend naar beoordeling"),
    "D": ("€1 mln–€7,5 mln", "controleverklaring"),
    "E": ("> €7,5 mln", "controleverklaring"),
}
CATEGORIE_MET_CONTROLE = ("D", "E")

USER_AGENT = "WhoSigns/0.1 (open-data-import; contact via repo)"
PAUZE_S = 0.3


def _haal(url: str, timeout: int = 60, maximum: int = 80_000_000) -> bytes:
    verzoek = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(verzoek, timeout=timeout) as antwoord:
        return antwoord.read(maximum)


def organisaties(alleen_actief: bool = True, limiet: int = 10_000) -> list[dict]:
    """Het register als lijst dicts (naam, kvknummer, rsinnummer, categorie, sectoren).

    `actieveErkenning == 1` betekent: nu erkend. Ingetrokken erkenningen blijven in
    het register staan en zijn zelf een signaal (een organisatie die de erkenning
    verliest, wisselt vaak ook van accountant) — daarom opvraagbaar met
    `alleen_actief=False`.
    """
    data = json.loads(_haal(f"{REGISTER_URL}?limit={limiet}").decode("utf-8"))
    rijen = data.get("items", [])
    if data.get("hasMore"):
        raise RuntimeError(
            "register geeft hasMore=true; verhoog `limiet` of bouw paginering"
        )
    if alleen_actief:
        rijen = [r for r in rijen if r.get("actieveErkenning") == 1]
    return rijen


def primaire_sector(organisatie: dict) -> str | None:
    """Sectornaam die het CBF als primair aanmerkt ('Welzijn', 'Dieren', …)."""
    for sector in organisatie.get("sectoren") or []:
        if str(sector.get("primair")).lower() == "true":
            return sector.get("sectornaam")
    return None


def jaarverslag_url(naam: str, boekjaar: int) -> str:
    return JAARVERSLAG_URL.format(
        naam=urllib.parse.quote(naam, safe=""), boekjaar=boekjaar
    )


def jaarverslag(naam: str, boekjaar: int) -> bytes | None:
    """De jaarverslag-pdf, of None als die er voor dit boekjaar niet is (404).

    Bewaar de bytes ongewijzigd in Storage vóór verwerking (architectuurprincipe 1:
    altijd de ruwe bron bewaren).
    """
    try:
        inhoud = _haal(jaarverslag_url(naam, boekjaar))
    except urllib.error.HTTPError as fout:
        if fout.code == 404:
            return None
        raise
    finally:
        time.sleep(PAUZE_S)  # vriendelijk voor de bron
    return inhoud if inhoud.startswith(b"%PDF") else None
