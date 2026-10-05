"""Test: een rare link op de eigen site laat de terugval niet meer struikelen.

Draaien vanuit de repo-root (geen netwerk; urlopen en _haal worden vervangen):

    python3 pipeline/test_anbi_publicatie.py

Waarom dit bestaat. Een href met een spatie gaf http.client.InvalidURL, en die erft
niet van URLError of OSError, dus geen van de except-blokken ving hem. Een letter
buiten ASCII gaf een UnicodeEncodeError. Allebei gingen ze dwars door
`zoek_documenten()` heen: de rest van die site werd niet meer bekeken. Nu wordt
het adres eerst gecodeerd, en valt bij een fout alleen dat ene stuk af.
De adressen hieronder zijn verzonnen.
"""

import http.client
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "adapters"))

import anbi_publicatie  # noqa: E402

goed = 0
fout = 0


def check(omschrijving: str, voorwaarde: bool) -> None:
    global goed, fout
    if voorwaarde:
        goed += 1
    else:
        fout += 1
        print(f"  FOUT: {omschrijving}")


anbi_publicatie.PAUZE_S = 0
veilig = anbi_publicatie.veilige_url

# --- coderen -------------------------------------------------------------------
check("spaties worden %20",
      veilig("https://fictief.invalid/docs/12 - Bijlage - Brief controleverklaring.pdf")
      == "https://fictief.invalid/docs/12%20-%20Bijlage%20-%20Brief%20controleverklaring.pdf")
check("wat al gecodeerd is blijft zoals het is",
      veilig("https://fictief.invalid/a%20b.pdf?x=1&y=2#p")
      == "https://fictief.invalid/a%20b.pdf?x=1&y=2#p")
check("letters buiten ASCII in het pad worden UTF-8 gecodeerd",
      veilig("https://fictief.invalid/jaarverslag-ü.pdf")
      == "https://fictief.invalid/jaarverslag-%C3%BC.pdf")
check("een domeinnaam buiten ASCII gaat via IDNA",
      veilig("https://bücher.invalid/anbi").startswith("https://xn--bcher-kva.invalid/"))
check("een gewoon adres verandert niet",
      veilig("https://www.fictief.invalid/anbi?jaar=2025") ==
      "https://www.fictief.invalid/anbi?jaar=2025")
check("witruimte eromheen gaat eraf",
      veilig("  https://fictief.invalid/a.pdf \n") == "https://fictief.invalid/a.pdf")


# --- _haal codeert vóór urlopen -------------------------------------------------
class NepAntwoord:
    headers = {"Content-Type": "application/pdf"}

    def __init__(self, url: str):
        self.url = url

    def geturl(self) -> str:
        return self.url

    def read(self, maximum: int) -> bytes:
        return b"%PDF-1.4"

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False


gevraagd: list[str] = []


def nep_urlopen(verzoek, timeout=None):
    gevraagd.append(verzoek.full_url)
    return NepAntwoord(verzoek.full_url)


echte_urlopen = urllib.request.urlopen
urllib.request.urlopen = nep_urlopen
try:
    inhoud = anbi_publicatie.haal_document(
        {"url": "https://fictief.invalid/docs/brief controleverklaring.pdf", "soort": "pdf"}
    )
finally:
    urllib.request.urlopen = echte_urlopen
check("een document met een spatie in de naam wordt gewoon opgehaald",
      inhoud == b"%PDF-1.4"
      and gevraagd == ["https://fictief.invalid/docs/brief%20controleverklaring.pdf"])


# --- een fout bij één stuk is een gemist stuk, geen gemiste site ----------------
echte_haal = anbi_publicatie._haal
# Eén pdf op de homepage: dan probeert zoek_documenten ook de vaste paden.
HOMEPAGE = (
    b'<a href="/jaarverslag">Jaarverslag</a>'
    b'<a href="/docs/jaarrekening 2025.pdf">Jaarrekening 2025</a>'
)
opgehaald: list[str] = []


def nep_haal(url, maximum, timeout=25):
    opgehaald.append(url)
    if url.rstrip("/") == "https://fictief.invalid":
        return url, "text/html", HOMEPAGE
    if url.endswith("/jaarverslag"):
        raise http.client.InvalidURL("URL can't contain control characters")
    if url.endswith("/anbi"):
        raise UnicodeEncodeError("ascii", "ü", 0, 1, "ordinal not in range")
    if url.endswith(".pdf"):
        raise http.client.IncompleteRead(b"")
    raise OSError("niet gevonden")


anbi_publicatie._haal = nep_haal
try:
    documenten = anbi_publicatie.zoek_documenten("https://fictief.invalid", 2025)
    check("een pagina met InvalidURL of UnicodeEncodeError breekt de zoektocht niet af",
          [d["url"] for d in documenten] == ["https://fictief.invalid/docs/jaarrekening 2025.pdf"])
    check("en de pagina's daarna worden nog bekeken",
          "https://fictief.invalid/jaarverslag" in opgehaald
          and "https://fictief.invalid/anbi" in opgehaald
          and opgehaald.index("https://fictief.invalid/anbi") < len(opgehaald) - 1)
    check("een document dat halverwege afbreekt is None, geen uitzondering",
          anbi_publicatie.haal_document(documenten[0]) is None)
finally:
    anbi_publicatie._haal = echte_haal

print(f"{goed}/{goed + fout} goed")
sys.exit(1 if fout else 0)
