"""Test: sector aanvullen uit de KvK-dataset, zonder netwerk en zonder database.

De API staat één verzoek per minuut toe en een Actions-job duurt hooguit zes
uur. Wat hier bewaakt wordt: dat het script die minuut aanhoudt, op tijd
stopt, alleen lege velden vult, en bijhoudt wat het al vroeg — zodat de
volgende run verder gaat in plaats van opnieuw begint. Verzonnen namen en
KvK-nummers; een nep-klok in plaats van echt wachten.
"""

import http.client
import sys
import tempfile
import urllib.request
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import vul_sector  # noqa: E402
from vul_sector import (  # noqa: E402
    INTERVAL,
    MAX_FOUTEN_OP_RIJ,
    draai,
    hoofdactiviteit,
    is_bv_nv,
    lees_voortgang,
    schrijf_voortgang,
    te_doen,
)

goed = 0
fout = 0


def check(omschrijving: str, voorwaarde: bool) -> None:
    global goed, fout
    if voorwaarde:
        goed += 1
    else:
        fout += 1
        print(f"  FOUT: {omschrijving}")


class Klok:
    """Nep-tijd: slapen schuift de klok op, en een verzoek kost een seconde."""

    def __init__(self):
        self.nu = 0.0
        self.verzoeken: list[float] = []

    def tijd(self) -> float:
        return self.nu

    def slaap(self, seconden: float) -> None:
        self.nu += seconden


class NepDb:
    def __init__(self):
        self.updates: list[tuple[str, str, dict]] = []

    def bijwerken(self, tabel: str, filter: str, velden: dict) -> None:
        self.updates.append((tabel, filter, velden))


def nep_haal(antwoorden: dict, klok: Klok):
    def haal(kvk: str):
        klok.verzoeken.append(klok.nu)
        klok.nu += 1
        return antwoorden.get(kvk, (404, None))

    return haal


VANDAAG = date(2026, 10, 6)
ORGS = [
    {"id": 1, "naam": "Stichting Testhuis", "kvk_nummer": "90000001", "sector": None},
    {"id": 2, "naam": "Testhandel B.V.", "kvk_nummer": "90000002", "sector": None},
    {"id": 3, "naam": "Testholding N.V. in liquidatie", "kvk_nummer": "90000003", "sector": None},
    {"id": 4, "naam": "Testbouw BV", "kvk_nummer": "90000004", "sector": None},
    {"id": 5, "naam": "Al Ingedeeld B.V.", "kvk_nummer": "90000005", "sector": "handel"},
    {"id": 6, "naam": "Kapot Nummer B.V.", "kvk_nummer": "9000", "sector": None},
    {"id": 7, "naam": "Testschool B.V.", "kvk_nummer": "90000007", "sector": None},
]
ANTWOORDEN = {
    "90000002": (200, {"rechtsvormCode": "BV", "activiteiten": [
        {"sbiCode": "46900", "soortActiviteit": "Nevenactiviteit"},
        {"sbiCode": "47.11.0", "soortActiviteit": "Hoofdactiviteit"}]}),
    "90000003": (200, {"rechtsvormCode": "NV", "actief": "N", "activiteiten": [
        {"sbiCode": "6420", "soortActiviteit": "Hoofdactiviteit"}]}),
    "90000004": (200, {"rechtsvormCode": "BV", "activiteiten": []}),
    "90000007": (200, {"rechtsvormCode": "BV", "activiteiten": [
        {"sbiCode": "85310", "soortActiviteit": "Hoofdactiviteit"}]}),
}

check("B.V. achteraan", is_bv_nv("Testhandel B.V.") and is_bv_nv("Testbouw BV"))
check("N.V. in liquidatie", is_bv_nv("Testholding N.V. in liquidatie"))
check("een stichting is geen BV", not is_bv_nv("Stichting Bevolkingsonderzoek Test"))
check(
    "de hoofdactiviteit, niet de nevenactiviteit, en zonder punten",
    hoofdactiviteit(ANTWOORDEN["90000002"][1]) == "47110",
)
check("zonder hoofdactiviteit: niets", hoofdactiviteit({"activiteiten": []}) is None)

lijst = te_doen(ORGS, {"uitkomsten": {}}, VANDAAG)
check(
    "BV's en NV's eerst, wat al een sector heeft of geen geldig nummer niet",
    [o["id"] for o in lijst] == [2, 3, 4, 7, 1],
)
oud = {"uitkomsten": {
    "1": {"uitkomst": "niet_in_dataset", "op": "2026-09-01"},
    "4": {"uitkomst": "geen_sbi", "op": "2025-01-01"},
}}
check(
    "een recente 404 slaan we over, een oude 'geen SBI' vragen we opnieuw",
    [o["id"] for o in te_doen(ORGS, oud, VANDAAG)] == [2, 3, 4, 7],
)

klok = Klok()
db = NepDb()
voortgang = {"uitkomsten": {}}
bewaard = []
telling = draai(
    ORGS, voortgang, db,
    haal=nep_haal(ANTWOORDEN, klok), klok=klok.tijd, slaap=klok.slaap,
    vandaag=VANDAAG, schoolbesturen={"90000007"},
    bewaar=lambda v: bewaard.append(len(v["uitkomsten"])),
)
check(
    "vijf gevraagd: drie gevuld, één zonder SBI, één niet in de dataset",
    telling["gevraagd"] == 5 and telling["gevuld"] == 3
    and telling["geen_sbi"] == 1 and telling["niet_in_dataset"] == 1,
)
tussenpozen = [b - a for a, b in zip(klok.verzoeken, klok.verzoeken[1:])]
check(
    "tussen twee verzoeken zit minstens een interval",
    all(t >= INTERVAL for t in tussenpozen),
)
check(
    "alleen lege velden: elke update filtert op is.null",
    db.updates and all("=is.null" in f for _, f, _ in db.updates),
)
check(
    "SBI 47.11 wordt handel, een holding financiële dienstverlening",
    ("organisaties", "id=eq.2&sector=is.null", {"sector": "handel"}) in db.updates
    and ("organisaties", "id=eq.3&sector=is.null", {"sector": "financiële dienstverlening"})
    in db.updates,
)
check(
    "een schoolbestuur uit DUO wordt onderwijs",
    ("organisaties", "id=eq.7&sector=is.null", {"sector": "onderwijs"}) in db.updates,
)
check(
    "de voortgang wordt na elk antwoord bewaard, op organisatie-id",
    bewaard == [1, 2, 3, 4, 5] and set(voortgang["uitkomsten"]) == {"1", "2", "3", "4", "7"},
)
check(
    "geen KvK-nummers in de voortgang",
    not any(o["kvk_nummer"] in str(voortgang) for o in ORGS),
)

# Tijdbudget: met 150 seconden past alleen het eerste verzoek plus één interval.
klok = Klok()
telling = draai(
    ORGS, {"uitkomsten": {}}, None,
    haal=nep_haal(ANTWOORDEN, klok), klok=klok.tijd, slaap=klok.slaap,
    vandaag=VANDAAG, schoolbesturen=set(), tijdbudget_s=150,
)
check(
    "het tijdbudget stopt de run vóór het volgende verzoek het niet meer haalt",
    telling["gevraagd"] == 2 and telling["reden"] == "tijdbudget op" and klok.nu <= 150,
)
check("droogloop schrijft niets (db is None) maar telt wel", telling["gevuld"] == 2)

# Een reeks 429's: stoppen, en niets als uitkomst vastleggen.
klok = Klok()
voortgang = {"uitkomsten": {}}
telling = draai(
    ORGS, voortgang, None,
    haal=lambda kvk: (429, None), klok=klok.tijd, slaap=klok.slaap,
    vandaag=VANDAAG, schoolbesturen=set(),
)
check(
    "na een paar keer 429 stopt de run, zonder uitkomsten te verzinnen",
    telling["gevraagd"] == MAX_FOUTEN_OP_RIJ and telling["fout"] == MAX_FOUTEN_OP_RIJ
    and voortgang["uitkomsten"] == {},
)

# Een verbinding die ná het verzoek wegvalt, gooit urllib niet als URLError
# maar als RemoteDisconnected, IncompleteRead of ConnectionResetError. Dat is
# "geen verbinding" (status 0, de volgende run vraagt opnieuw), geen crash
# die de hele run stopt. Een nep-urlopen, zonder netwerk.
class KapotAntwoord:
    status = 200

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def read(self):
        return b'{"activiteiten": ['


def gooi(fout_object):
    def urlopen(*_args, **_kwargs):
        raise fout_object

    return urlopen


echte_urlopen = urllib.request.urlopen
uitkomsten = []
try:
    for nep_urlopen in (
        gooi(http.client.RemoteDisconnected("verbinding verbroken")),
        gooi(http.client.IncompleteRead(b"")),
        gooi(ConnectionResetError()),
        gooi(TimeoutError()),
        lambda *_args, **_kwargs: KapotAntwoord(),
    ):
        urllib.request.urlopen = nep_urlopen
        uitkomsten.append(vul_sector.haal("90000002"))
finally:
    urllib.request.urlopen = echte_urlopen
check(
    "een verbroken verbinding of half antwoord telt als fout (status 0)",
    uitkomsten == [(0, None)] * 5,
)
klok = Klok()
voortgang = {"uitkomsten": {}}
telling = draai(
    ORGS, voortgang, None,
    haal=lambda kvk: (0, None), klok=klok.tijd, slaap=klok.slaap,
    vandaag=VANDAAG, schoolbesturen=set(),
)
check(
    "drie verbroken verbindingen op rij: stoppen, niets vastgelegd",
    telling["fout"] == MAX_FOUTEN_OP_RIJ and voortgang["uitkomsten"] == {}
    and "HTTP 0" in telling["reden"],
)

# Een 404 vóór de eerste 200 wacht: pas als de run ook een 200 ziet, is een
# 404 "geen BV of NV" en geen verhuisd endpoint. Twee BV's, de laagste id
# geeft 404, de volgende 200.
EERST_404 = [
    {"id": 1, "naam": "Testvierhonderdvier B.V.", "kvk_nummer": "90000001", "sector": None},
    {"id": 2, "naam": "Testhandel B.V.", "kvk_nummer": "90000002", "sector": None},
]
klok = Klok()
voortgang = {"uitkomsten": {}}
bewaard = []
telling = draai(
    EERST_404, voortgang, None,
    haal=nep_haal(ANTWOORDEN, klok), klok=klok.tijd, slaap=klok.slaap,
    vandaag=VANDAAG, schoolbesturen=set(),
    bewaar=lambda v: bewaard.append(sorted(v["uitkomsten"])),
)
check(
    "een 404 vóór de eerste 200 wordt pas met die 200 vastgelegd, en dan wel",
    bewaard == [["1", "2"]] and telling["niet_in_dataset"] == 1 and telling["fout"] == 0
    and voortgang["uitkomsten"]["1"]["uitkomst"] == "niet_in_dataset",
)
# Alleen maar 404: een verhuisd endpoint. Niets vastleggen, alles telt als fout
# (dan wordt de run rood) en de reden zegt waarom.
klok = Klok()
voortgang = {"uitkomsten": {}}
telling = draai(
    ORGS, voortgang, None,
    haal=lambda kvk: (404, None), klok=klok.tijd, slaap=klok.slaap,
    vandaag=VANDAAG, schoolbesturen=set(),
)
check(
    "alleen 404's zonder één 200: niets 'niet in de dataset', alles fout",
    telling["gevraagd"] == 5 and telling["fout"] == 5 and telling["niet_in_dataset"] == 0
    and voortgang["uitkomsten"] == {} and "zonder één 200" in telling["reden"],
)
# Een 200 met iets anders dan een JSON-object: fout, geen crash, niets vastgelegd.
klok = Klok()
voortgang = {"uitkomsten": {}}
telling = draai(
    ORGS[:2], voortgang, None,
    haal=lambda kvk: (200, [{"activiteiten": []}]), klok=klok.tijd, slaap=klok.slaap,
    vandaag=VANDAAG, schoolbesturen=set(),
)
check(
    "een 200 met een lijst in plaats van een object telt als fout",
    telling["fout"] == 2 and telling["gevuld"] == 0 and voortgang["uitkomsten"] == {},
)
check(
    "een vreemde vorm van 'activiteiten' geeft geen hoofdactiviteit, geen crash",
    hoofdactiviteit({"activiteiten": "geen lijst"}) is None
    and hoofdactiviteit({"activiteiten": [None, "x", {"soortActiviteit": "Hoofdactiviteit",
                                                       "sbiCode": 6420}]}) == "6420",
)

# Het voortgangsbestand overleeft een rondje schrijven en lezen.
with tempfile.TemporaryDirectory() as map_:
    pad = Path(map_) / "sector_kvk.json"
    check("zonder bestand begint de voortgang leeg", lees_voortgang(pad)["uitkomsten"] == {})
    schrijf_voortgang({"bron": "x", "uitkomsten": {"2": {"uitkomst": "gevuld", "op": "2026-10-06"}}}, pad)
    check("en komt terug zoals hij is weggeschreven", lees_voortgang(pad)["uitkomsten"]["2"]["uitkomst"] == "gevuld")

print(f"{goed}/{goed + fout} goed")
sys.exit(1 if fout else 0)
