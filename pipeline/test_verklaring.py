"""Tests voor de leeslaag van verklaringen — de dure keuzes eromheen.

Draaien vanuit de repo-root (geen testframework nodig, geen netwerk):

    python3 pipeline/test_verklaring.py

Waarom dit bestand bestaat: OCR is verreweg het duurste dat deze pipeline doet.
Gemeten op gescande zorgverklaringen (6-8-2026): tientallen seconden tot ruim
zes minuten per document, tegen milliseconden voor een pdf mét tekstlaag. Dat
hoort niet op een GitHub-runner thuis, want daar betaal je het in
Actions-minuten. De schakelaar die dat regelt moet dus precies doen wat hij
belooft — en vooral: uit betekent uit.
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "extractie"))

import verklaring  # noqa: E402
from verklaring import ocr_toegestaan, tekst_uit_pdf  # noqa: E402

fouten = 0
gedaan = 0


def controleer(omschrijving: str, goed: bool, detail: str = "") -> None:
    global fouten, gedaan
    gedaan += 1
    fouten += not goed
    print(f"{'✓' if goed else '✗'} {omschrijving}")
    if not goed and detail:
        print(f"    {detail}")


def met_omgeving(waarde):
    """Zet WHOSIGNS_OCR op `waarde`, of haalt hem weg bij None."""
    if waarde is None:
        os.environ.pop("WHOSIGNS_OCR", None)
    else:
        os.environ["WHOSIGNS_OCR"] = waarde


# --- de schakelaar zelf ------------------------------------------------------
#
# Standaard aan: wie het script gewoon draait (hier, buiten Actions) verwacht de
# volle lezing. Alleen een expliciet "uit" zet hem uit.
met_omgeving(None)
controleer("zonder WHOSIGNS_OCR staat OCR aan", ocr_toegestaan())

for waarde in ("0", "nee", "false", "off", "uit", "UIT", " 0 "):
    met_omgeving(waarde)
    controleer(f"WHOSIGNS_OCR={waarde!r} zet OCR uit", not ocr_toegestaan())

for waarde in ("1", "ja", "true", ""):
    met_omgeving(waarde)
    controleer(f"WHOSIGNS_OCR={waarde!r} laat OCR aan", ocr_toegestaan())


# --- en wat de leeslaag ermee doet -------------------------------------------
#
# De valkuil is stilte: als de schakelaar wél gelezen wordt maar `ocr_naar_tekst`
# tóch draait, kost een run alsnog uren zonder dat iemand het ziet. Daarom hier
# geen echte pdf maar een teller op de dure functie.
opgeroepen = {"aantal": 0}
echte_ocr = verklaring.ocr_naar_tekst
echte_pdf = verklaring.pdf_naar_tekst


def _nep_ocr(pad, max_paginas=verklaring.OCR_MAX_PAGINAS):
    opgeroepen["aantal"] += 1
    return "controleverklaring van de onafhankelijke accountant, ruim boven de grens"


verklaring.ocr_naar_tekst = _nep_ocr
verklaring.pdf_naar_tekst = lambda pad: ""  # een scan: geen tekstlaag
try:
    met_omgeving("0")
    tekst, via_ocr = tekst_uit_pdf("verzonnen.pdf")
    controleer(
        "OCR uit: de dure functie wordt niet aangeroepen",
        opgeroepen["aantal"] == 0 and tekst == "" and via_ocr is False,
        f"aanroepen={opgeroepen['aantal']}, tekst={tekst!r}, via_ocr={via_ocr}",
    )

    met_omgeving("1")
    tekst, via_ocr = tekst_uit_pdf("verzonnen.pdf")
    controleer(
        "OCR aan: de dure functie wordt wél aangeroepen",
        opgeroepen["aantal"] == 1 and via_ocr is True and tekst,
        f"aanroepen={opgeroepen['aantal']}, via_ocr={via_ocr}",
    )

    # De keuze van de aanroeper blijft leidend: laad_zorg zet ocr=False voor
    # organisaties waar een wettelijke controle niet kán spelen, en die mag de
    # omgevingsvariabele niet overrulen.
    opgeroepen["aantal"] = 0
    tekst, via_ocr = tekst_uit_pdf("verzonnen.pdf", ocr=False)
    controleer(
        "ocr=False van de aanroeper wint, ook als de omgeving OCR toestaat",
        opgeroepen["aantal"] == 0 and via_ocr is False,
        f"aanroepen={opgeroepen['aantal']}, via_ocr={via_ocr}",
    )

    # Een pdf mét tekstlaag komt nooit bij OCR uit, ongeacht de schakelaar.
    verklaring.pdf_naar_tekst = lambda pad: "x" * (verklaring.TEKST_ONDERGRENS + 1)
    opgeroepen["aantal"] = 0
    tekst, via_ocr = tekst_uit_pdf("verzonnen.pdf")
    controleer(
        "een pdf mét tekstlaag komt niet bij OCR uit",
        opgeroepen["aantal"] == 0 and via_ocr is False and tekst,
    )
finally:
    verklaring.ocr_naar_tekst = echte_ocr
    verklaring.pdf_naar_tekst = echte_pdf
    met_omgeving(None)

print(f"\n{gedaan - fouten}/{gedaan} goed")
raise SystemExit(1 if fouten else 0)
