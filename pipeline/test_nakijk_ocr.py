"""Wat het nakijken van bewaarde OCR-teksten wel en niet mag opleveren.

Draaien vanuit de repo-root (geen testframework nodig, geen netwerk):

    python3 pipeline/test_nakijk_ocr.py

Waarom dit bestand bestaat: nakijk_ocr.py schrijft regels bij in de
oogstrapporten, en die gaan via "Zorgoogst inladen" regelrecht de database in.
De extractie zelf (analyseer, zoek_kantoor) heeft haar eigen tests; hier staat
het loodgieterswerk eromheen dat net zo goed stuk kan: bestandsnamen ontleden
zonder voorloopnullen te verliezen, de bewaarkop herkennen, de vertaalslag
naar een rapportrij, en de regel dat tegenspraak tussen documenten een melding
wordt en nooit een rij.
"""

import csv
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from nakijk_ocr import (  # noqa: E402
    RAPPORT_KOLOMMEN,
    lees_bewaarde_tekst,
    ontleed_bestandsnaam,
    rij_uit_analyse,
    verzoen,
)

fouten = 0
gedaan = 0


def controleer(omschrijving: str, goed: bool, detail: str = "") -> None:
    global fouten, gedaan
    gedaan += 1
    fouten += not goed
    print(f"{'✓' if goed else '✗'} {omschrijving}")
    if not goed and detail:
        print(f"    {detail}")


# --- bestandsnamen ------------------------------------------------------------

controleer(
    "een gewone bewaarnaam wordt ontleed",
    ontleed_bestandsnaam("2019_59684380_11260.pdf.ocr.txt") == (2019, "59684380"),
)

controleer(
    "een voorloopnul in het KvK-nummer blijft staan",
    ontleed_bestandsnaam("2020_01129943_8028.pdf.ocr.txt") == (2020, "01129943"),
    "als string; als int wordt 01129943 het nummer van een ander bedrijf",
)

controleer(
    "een ander achtervoegsel is geen bewaarde lezing",
    ontleed_bestandsnaam("2019_59684380_11260.pdf") is None,
)

controleer(
    "te veel of te weinig delen is geen bewaarnaam",
    ontleed_bestandsnaam("2019_59684380.pdf.ocr.txt") is None
    and ontleed_bestandsnaam("2019_59684380_11260_2.pdf.ocr.txt") is None,
)

controleer(
    "niet-numerieke delen vallen af",
    ontleed_bestandsnaam("jaar_59684380_11260.pdf.ocr.txt") is None,
)

controleer(
    "een onmogelijk boekjaar valt af",
    ontleed_bestandsnaam("2077_59684380_11260.pdf.ocr.txt") is None,
    "dezelfde grens als de databasevoorwaarde opdrachten_boekjaar_plausibel",
)

# --- de bewaarkop -------------------------------------------------------------

with tempfile.TemporaryDirectory() as map_:
    goed_pad = Path(map_) / "a.pdf.ocr.txt"
    goed_pad.write_text(
        "# whosigns-ocr v2 grootte=123 dpi=300 paginas=20\nDe echte tekst.\n",
        encoding="utf-8",
    )
    controleer(
        "de tekst achter de bewaarkop komt terug, zonder de kop",
        lees_bewaarde_tekst(goed_pad) == "De echte tekst.\n",
    )

    kaal_pad = Path(map_) / "b.pdf.ocr.txt"
    kaal_pad.write_text("Zomaar een tekstbestand.\n", encoding="utf-8")
    controleer(
        "een bestand zonder bewaarkop telt niet als bewaarde lezing",
        lees_bewaarde_tekst(kaal_pad) is None,
    )

    leeg_pad = Path(map_) / "c.pdf.ocr.txt"
    leeg_pad.write_text("# whosigns-ocr v2 grootte=1 dpi=300 paginas=20\n \n",
                        encoding="utf-8")
    controleer(
        "een lege lezing levert niets op",
        lees_bewaarde_tekst(leeg_pad) is None,
    )

    controleer(
        "een bestand dat er niet is levert niets op",
        lees_bewaarde_tekst(Path(map_) / "bestaat_niet.txt") is None,
    )

# --- van analyse naar rapportrij ----------------------------------------------


def analyse(**velden) -> dict:
    basis = {
        "soort": "controle",
        "opdrachttype": "wettelijke_controle",
        "oordeel": "goedkeurend",
        "grond_beperking": None,
        "continuiteitsonzekerheid": False,
        "kantoor": {
            "naam": "Voorbeeld Audit B.V.",
            "sleutel": "13000999",
            "afm_nummer": "13000999",
            "wta_vergunning": True,
        },
    }
    basis.update(velden)
    return basis


controleer(
    "een sterke controleverklaring wordt een complete rij",
    rij_uit_analyse("01234567", "Zorg B.V.", "Utrecht", 2019, analyse())
    == {
        "kvk": "01234567", "naam": "Zorg B.V.", "plaats": "Utrecht",
        "boekjaar": "2019", "kantoor": "Voorbeeld Audit B.V.",
        "kantoor_sleutel": "13000999", "afm_nummer": "13000999",
        "type_opdracht": "wettelijke_controle", "oordeel": "goedkeurend",
        "grond_beperking": "", "continuiteitsonzekerheid": "",
    },
)

controleer(
    "geen controleverklaring: geen rij",
    rij_uit_analyse("1", "X", "Y", 2019, analyse(soort="samenstelling")) is None,
)

controleer(
    "geen vastgesteld kantoor: geen rij",
    rij_uit_analyse("1", "X", "Y", 2019, analyse(kantoor=None)) is None,
    "een zwakke treffer heeft analyseer() dan al op None gezet",
)

controleer(
    "opdrachttype onbekend wordt controle_onbepaald, geen gok naar het zwaarste",
    rij_uit_analyse("1", "X", "Y", 2019, analyse(opdrachttype=None))["type_opdracht"]
    == "controle_onbepaald",
)

zonder_wta = analyse()
zonder_wta["kantoor"] = dict(zonder_wta["kantoor"], wta_vergunning=False,
                             afm_nummer=None)
rij = rij_uit_analyse("1", "X", "Y", 2019, zonder_wta)
controleer(
    "wettelijke controle bij een kantoor zonder Wta-vergunning wordt vrijwillig",
    rij["type_opdracht"] == "vrijwillige_controle" and rij["afm_nummer"] == "",
    "dezelfde vertaalslag als in laad_zorg.py",
)

controleer(
    "geen oordeel wordt een lege cel, geen None-tekst",
    rij_uit_analyse("1", "X", "Y", 2019, analyse(oordeel=None))["oordeel"] == "",
    "de kolom kent alleen echte oordelen of leeg; 'None' als tekst zou de "
    "lading van #54 opnieuw laten omvallen",
)

controleer(
    "continuiteitsonzekerheid wordt alleen 'ja' als hij er is",
    rij_uit_analyse("1", "X", "Y", 2019,
                    analyse(continuiteitsonzekerheid=True))["continuiteitsonzekerheid"]
    == "ja",
)

# --- tegenspraak tussen documenten --------------------------------------------

een = rij_uit_analyse("1", "X", "Y", 2019, analyse())
nog_een = rij_uit_analyse("1", "X", "Y", 2019, analyse())
ander_kantoor = analyse()
ander_kantoor["kantoor"] = dict(ander_kantoor["kantoor"],
                                naam="Ander Kantoor", sleutel="13000111")
tegenspraak = rij_uit_analyse("1", "X", "Y", 2019, ander_kantoor)

controleer("niets gelezen: geen rij en geen melding", verzoen([]) == (None, None))

controleer(
    "één sterke lezing: die rij",
    verzoen([een]) == (een, None),
)

controleer(
    "twee lezingen die elkaar bevestigen: één rij",
    verzoen([een, nog_een]) == (een, None),
)

uit, reden = verzoen([een, tegenspraak])
controleer(
    "twee lezingen die elkaar tegenspreken: geen rij, wel uitleg",
    uit is None and reden is not None and "Ander Kantoor" in reden,
    "liever een melding dan een gok die de database in gaat",
)

# --- aansluiting op het echte rapport -----------------------------------------

with (Path(__file__).resolve().parent / "oogst" / "zorg_2019.csv").open(
    encoding="utf-8"
) as bestand:
    kop = next(csv.reader(bestand))
controleer(
    "de kolommen zijn exact die van het oogstrapport",
    kop == RAPPORT_KOLOMMEN,
    f"rapport: {kop}",
)

print(f"\n{gedaan - fouten}/{gedaan} goed")
raise SystemExit(1 if fouten else 0)
