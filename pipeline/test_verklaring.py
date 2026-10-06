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
import tempfile
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

# --- de bewaarplaats voor OCR-tekst -----------------------------------------
#
# Waarom dit ertoe doet: de zorgoogst draait in een omgeving die ongeveer elk uur
# opnieuw begint. Zonder bewaren begon elke herstart weer bij nul en kwam blok
# 110-120 van boekjaar 2019 tien keer op rij niet af. Mét bewaren telt elke
# gelezen pdf mee, ook als de poging waarin hij gelezen werd het niet haalde.
with tempfile.TemporaryDirectory() as tijdelijk:
    nep_pdf = Path(tijdelijk) / "verslag.pdf"
    nep_pdf.write_bytes(b"%PDF-1.4 net genoeg bytes om een grootte te hebben")
    pad = str(nep_pdf)
    kop = verklaring._ocr_kop(pad, verklaring.OCR_MAX_PAGINAS)

    controleer(
        "zonder eerdere lezing valt er niets terug te halen",
        verklaring._ocr_uit_bewaarplaats(pad, kop) is None,
    )

    verklaring._bewaar_ocr(pad, kop, "Zwolle, 14 maart 2024 Countus Audit B.V.")
    controleer(
        "een geslaagde lezing komt er onveranderd weer uit",
        verklaring._ocr_uit_bewaarplaats(pad, kop)
        == "Zwolle, 14 maart 2024 Countus Audit B.V.",
        f"gevonden: {verklaring._ocr_uit_bewaarplaats(pad, kop)!r}",
    )

    # Opgeven mag nooit blijvend zijn. `ocr_naar_tekst` geeft "" terug als het
    # tijdbudget op is; zou dat bewaard worden, dan was het document voorgoed
    # onleesbaar zonder dat het ooit nog een kans kreeg.
    (Path(pad + ".ocr.txt")).unlink()
    verklaring._bewaar_ocr(pad, kop, "")
    verklaring._bewaar_ocr(pad, kop, "   \n  ")
    controleer(
        "een mislukte lezing wordt niet bewaard, dus blijft herhaalbaar",
        not Path(pad + ".ocr.txt").exists(),
    )

    # De kopregel is de houdbaarheidsdatum. Verandert het bestand of een
    # OCR-instelling, dan hoort de oude tekst niet meer mee te tellen.
    verklaring._bewaar_ocr(pad, kop, "oude lezing")
    nep_pdf.write_bytes(b"%PDF-1.4 een andere download onder dezelfde naam, langer")
    controleer(
        "een gewijzigde pdf maakt de bewaarde tekst ongeldig",
        verklaring._ocr_uit_bewaarplaats(
            pad, verklaring._ocr_kop(pad, verklaring.OCR_MAX_PAGINAS)
        ) is None,
    )

    nep_pdf.write_bytes(b"%PDF-1.4 net genoeg bytes om een grootte te hebben")
    controleer(
        "een andere paginagrens maakt de bewaarde tekst ongeldig",
        verklaring._ocr_uit_bewaarplaats(
            pad, verklaring._ocr_kop(pad, verklaring.OCR_MAX_PAGINAS + 5)
        ) is None,
    )
    controleer(
        "met dezelfde pdf en dezelfde instellingen telt hij weer mee",
        verklaring._ocr_uit_bewaarplaats(pad, kop) == "oude lezing",
    )

    # Een tekst met meerdere regels mag niet halveren op de scheiding met de kop.
    verklaring._bewaar_ocr(pad, kop, "eerste regel\ntweede regel\nderde regel")
    controleer(
        "tekst met meerdere regels blijft heel",
        verklaring._ocr_uit_bewaarplaats(pad, kop)
        == "eerste regel\ntweede regel\nderde regel",
    )

controleer(
    "een pdf die niet bestaat levert geen kopregel op (en dus geen bewaarplaats)",
    verklaring._ocr_kop("/bestaat/niet.pdf", verklaring.OCR_MAX_PAGINAS) is None,
)

# --- Mengvorm-pdf's: tekstlaag mét gescande verklaringspagina's -------------
#
# De VU en Tilburg University plakken de ondertekende verklaring als afbeelding
# in een verder gewoon tekst-pdf. De paginakeuze moet dan precies de tekstloze
# pagina's aanwijzen — en niets renderen als die er niet zijn.

from verklaring import _aaneengesloten, lege_paginas, ocr_lege_paginas  # noqa: E402

controleer(
    "lege pagina's worden op de form feed geteld, 1-gebaseerd",
    lege_paginas("volle pagina met ruim voldoende tekst erin\f\f  \fnog een volle pagina met ruim voldoende tekst") == [2, 3],
)
controleer(
    "een pagina onder de grens telt als leeg, erboven niet",
    lege_paginas("x" * 19 + "\f" + "x" * 20) == [1],
)
controleer(
    "zonder form feed is er één pagina en beslist de grens",
    lege_paginas("") == [1] and lege_paginas("x" * 500) == [],
)
controleer(
    "aaneengesloten reeksen worden bereiken voor pdftoppm",
    _aaneengesloten([3, 4, 5, 9]) == [(3, 5), (9, 9)] and _aaneengesloten([]) == [],
)
controleer(
    "zonder lege pagina's wordt er niets ge-OCR'd (geen subprocess, meteen leeg)",
    ocr_lege_paginas("/bestaat/niet.pdf", "x" * 500) == "",
)
os.environ["WHOSIGNS_OCR"] = "0"
controleer(
    "OCR uit betekent ook voor de mengvormlezing: uit",
    ocr_lege_paginas("/bestaat/niet.pdf", "\f\f") == "",
)
os.environ.pop("WHOSIGNS_OCR", None)

# --- Getrouwheid en rechtmatigheid (decentrale overheden) --------------------
#
# Een verklaring bij een gemeente draagt tot en met 2022 twee oordelen. Alleen
# het oordeel over het getrouw beeld is het jaarrekeningoordeel; een afkeurend
# rechtmatigheidsoordeel naast een goedgekeurde jaarrekening mag geen
# "afkeurend" worden. De zinnen hieronder volgen de vorm van echte verklaringen
# uit Open Raadsinformatie (5-10-2026), met verzonnen gemeenten.

from verklaring import oordeel_getrouwheid  # noqa: E402

GETROUW = (
    "geeft de in de jaarstukken opgenomen jaarrekening een getrouw beeld van de "
    "grootte en de samenstelling van zowel de baten en lasten over 2020 als van "
    "de activa en passiva van de gemeente Testdam op 31 december 2020 in "
    "overeenstemming met het Besluit begroting en verantwoording provincies en "
    "gemeenten (BBV);"
)
RECHTMATIG_SCHOON = (
    "zijn de in de jaarrekening verantwoorde baten en lasten alsmede de "
    "balansmutaties over 2020 in alle van materieel belang zijnde aspecten "
    "rechtmatig tot stand gekomen in overeenstemming met de begroting."
)
RECHTMATIG_AFGEKEURD = (
    "zijn de in de jaarrekening verantwoorde baten en lasten alsmede de "
    "balansmutaties over 2020, vanwege het belang van de aangelegenheden zoals "
    "beschreven in de paragraaf “De basis voor ons afkeurend oordeel”, niet in "
    "alle van materieel belang zijnde aspecten rechtmatig tot stand gekomen."
)

for omschrijving, tekst, verwacht in [
    (
        "de kop noemt beide oordelen: getrouwheid telt",
        "Ons goedkeurend oordeel betreffende de getrouwheid en ons oordeel met "
        "beperking betreffende de rechtmatigheid\nWij hebben de jaarrekening 2020 "
        "van de gemeente Testdam gecontroleerd.\nNaar ons oordeel:\n• " + GETROUW
        + "\n• " + RECHTMATIG_SCHOON,
        "goedkeurend",
    ),
    (
        "algemene kop 'Ons afkeurend oordeel', alleen de rechtmatigheid is afgekeurd",
        "Ons afkeurend oordeel\nWij hebben de jaarrekening 2020 van de gemeente "
        "Testdam gecontroleerd.\nNaar ons oordeel:\n• " + GETROUW + "\n• "
        + RECHTMATIG_AFGEKEURD + "\nDe basis voor ons afkeurend oordeel\nIn de "
        "jaarrekening 2020 is sprake van rechtmatigheidsfouten.",
        "goedkeurend",
    ),
    (
        "een voorbehoud in de getrouwheidszin is een beperking",
        "Ons oordeel met beperking\nNaar ons oordeel:\n• geeft de in de jaarstukken "
        "opgenomen jaarrekening uitgezonderd de effecten van de aangelegenheden "
        "beschreven in de paragraaf ‘De basis voor ons oordeel met beperking’ een "
        "getrouw beeld van de grootte en de samenstelling van zowel de baten en "
        "lasten als van de activa en passiva;\n• " + RECHTMATIG_SCHOON,
        "beperking",
    ),
    (
        "geen getrouw beeld is een afkeurend oordeel",
        "Naar ons oordeel geeft de jaarrekening van de gemeente Testdam, vanwege "
        "het belang van de aangelegenheid beschreven in de paragraaf ‘De basis "
        "voor ons afkeurend oordeel’, geen getrouw beeld van de grootte en de "
        "samenstelling van de baten en lasten.\nVoorts zijn wij van oordeel dat de "
        "baten en lasten rechtmatig tot stand zijn gekomen.",
        "afkeurend",
    ),
    (
        "een afkeurend WNT-oordeel naast een schone jaarrekening",
        "Wij zijn van mening dat de verkregen controle-informatie een basis biedt "
        "voor ons oordeel betreffende de jaarrekening en voor ons afkeurend oordeel "
        "betreffende de WNT.\nOordeel betreffende de jaarrekening\nNaar ons oordeel "
        "geeft de jaarrekening van de gemeente Testdam een getrouw beeld van de "
        "grootte en de samenstelling van de baten en lasten. Voorts zijn wij van "
        "oordeel dat de baten en lasten rechtmatig tot stand zijn gekomen.",
        "goedkeurend",
    ),
    (
        "geen oordeel over getrouwheid en rechtmatigheid is een oordeelonthouding",
        "Onze oordeelonthouding\nWij hebben de jaarrekening 2025 van de "
        "gemeenschappelijke regeling Testpark te Testdam gecontroleerd. Wij geven "
        "geen oordeel over de getrouwheid en rechtmatigheid van de in de jaarstukken "
        "opgenomen jaarrekening.",
        "oordeelonthouding",
    ),
    (
        "zonder rechtmatigheid geldt gewoon de oordeelregel",
        "Ons oordeel met beperking\nNaar ons oordeel geeft de jaarrekening, "
        "uitgezonderd de mogelijke effecten van de aangelegenheid, een getrouw "
        "beeld van het vermogen van Stichting Testhuis.",
        "beperking",
    ),
    (
        "oudere opmaak: beide oordelen in één zin, het voorbehoud hoort bij de "
        "rechtmatigheid",
        "Oordeel met beperking\nNaar ons oordeel geeft de jaarrekening van de "
        "gemeente Testdam een getrouw beeld van de grootte en de samenstelling van "
        "zowel de baten en lasten als van de activa en passiva, en zijn de in de "
        "jaarrekening verantwoorde baten en lasten, uitgezonderd de aangelegenheid "
        "beschreven in de paragraaf onderbouwing, rechtmatig tot stand gekomen.",
        "goedkeurend",
    ),
    (
        "een voorbehoud ná het getrouw beeld, met een kop over de getrouwheid",
        "Ons oordeel met beperking inzake de getrouwheid\nNaar ons oordeel:\n• geeft "
        "de in de jaarstukken opgenomen jaarrekening een getrouw beeld van de "
        "grootte en de samenstelling van de baten en lasten over 2018 en van de "
        "activa en passiva van de gemeente Testdam op 31 december 2018, "
        "uitgezonderd de gevolgen van de aangelegenheden beschreven in de paragraaf "
        "‘De basis voor ons oordeel met beperking inzake de rechtmatigheid’, in "
        "overeenstemming met het BBV;\n• " + RECHTMATIG_SCHOON,
        "beperking",
    ),
    (
        "het voorbehoud verwijst naar een paragraaf over getrouwheid én "
        "rechtmatigheid",
        "Ons oordeel\nNaar ons oordeel:\n• geeft de in de jaarstukken opgenomen "
        "jaarrekening een getrouw beeld van de grootte en de samenstelling van de "
        "baten en lasten over 2021 en van de activa en passiva van de gemeente "
        "Testdam op 31 december 2021, in overeenstemming met het BBV, uitgezonderd "
        "de gevolgen van de aangelegenheden beschreven in de paragraaf ‘De basis "
        "voor ons oordeel met beperking inzake de getrouwheid en rechtmatigheid’;\n• "
        + RECHTMATIG_SCHOON,
        "beperking",
    ),
    (
        "een punt na een paginanummer is geen zinsgrens",
        "Ons oordeel met beperking inzake de rechtmatigheid\nNaar ons oordeel geeft "
        "de in de jaarstukken op pagina 129. tot en met pagina 161. opgenomen "
        "jaarrekening een getrouw beeld van de grootte en de samenstelling van de "
        "baten en lasten.",
        "goedkeurend",
    ),
]:
    controleer(
        f"getrouwheid: {omschrijving}",
        oordeel_getrouwheid(tekst) == verwacht,
        f"kreeg {oordeel_getrouwheid(tekst)!r}, verwacht {verwacht!r}",
    )

# Wat níét vast te stellen is, blijft leeg.
for omschrijving, tekst in [
    (
        "een algemene beperkingskop zonder aanwijzing waar hij over gaat",
        "Ons oordeel met beperking\nNaar ons oordeel geeft de jaarrekening van de "
        "gemeente Testdam een getrouw beeld van de grootte en de samenstelling van "
        "de baten en lasten. Het college is verantwoordelijk voor het rechtmatig "
        "tot stand komen van de baten en lasten.",
    ),
    (
        "een voorbehoud bij de getrouwheid dat naar de rechtmatigheid verwijst",
        "Naar ons oordeel:\n• geeft de in de jaarstukken opgenomen jaarrekening "
        "uitgezonderd de gevolgen van de aangelegenheden beschreven in de paragraaf "
        "‘De basis voor ons oordeel met beperking inzake de rechtmatigheid’ een "
        "getrouw beeld van de grootte en samenstelling van de baten en lasten;\n• "
        + RECHTMATIG_SCHOON,
    ),
    (
        "kop goedkeurend, maar de oordeelzin draagt een voorbehoud",
        "Ons goedkeurend oordeel betreffende de getrouwheid\nNaar ons oordeel geeft "
        "de jaarrekening, met uitzondering van de mogelijke effecten, een getrouw "
        "beeld van de baten en lasten. De baten en lasten zijn rechtmatig.",
    ),
    # Dezelfde verwijzing, maar dan áchter het getrouw beeld (een gemeente,
    # 2018). Tot 6-10-2026 werd dit een beperking: de twijfelregel keek alleen
    # tussen het voorbehoud en "getrouw beeld", en de knip op het tweede
    # oordeel viel midden in de aangehaalde paragraaftitel.
    (
        "een voorbehoud ná het getrouw beeld dat naar de rechtmatigheid verwijst",
        "Ons oordeel met beperking\nNaar ons oordeel:\n• geeft de in de jaarstukken "
        "opgenomen jaarrekening een getrouw beeld van de grootte en de samenstelling "
        "van zowel de baten en lasten over 2018 als van de activa en passiva van de "
        "gemeente Testdam op 31 december 2018, uitgezonderd de gevolgen van de "
        "aangelegenheden beschreven in de paragraaf ‘De basis voor ons oordeel met "
        "beperking inzake de rechtmatigheid’, in overeenstemming met het BBV;\n• "
        "zijn de in deze jaarrekening verantwoorde baten en lasten alsmede de "
        "balansmutaties over 2018, uitgezonderd de gevolgen van de aangelegenheden "
        "beschreven in de paragraaf ‘De basis voor ons oordeel met beperking inzake "
        "de rechtmatigheid’, in alle van materieel belang zijnde aspecten rechtmatig "
        "tot stand gekomen in overeenstemming met de begroting.\nDe basis voor ons "
        "oordeel voor getrouwheid en ons oordeel met beperking inzake de "
        "rechtmatigheid\nIn de jaarrekening zijn lasten verantwoord die niet "
        "rechtmatig tot stand zijn gekomen.",
    ),
    # De omgekeerde tegenspraak: een niet-goedkeurend label boven een schone
    # oordeelzin. Zo werd een begraafplaatsstichting (2024) een
    # oordeelonthouding op een sjabloonfout in één tussenkop …
    (
        "'basis voor onze oordeelonthouding' boven een schone oordeelzin",
        "Ons oordeel\nWij hebben de jaarrekening 2024 van Stichting Testrust te "
        "Testdam gecontroleerd. Naar ons oordeel geeft de jaarrekening een getrouw "
        "beeld van de grootte en de samenstelling van het vermogen van Stichting "
        "Testrust op 31 december 2024.\nDe basis voor onze oordeelonthouding\nWij "
        "hebben onze controle uitgevoerd volgens het Nederlands recht. Wij vinden "
        "dat de door ons verkregen controle-informatie voldoende en geschikt is "
        "als basis voor ons oordeel.",
    ),
    # … en een gemeente (2022) een beperking op één basiszin, terwijl kop en
    # oordeelzin alleen de rechtmatigheid beperken.
    (
        "beperking 'betreffende de getrouwheid' alleen in een basiszin",
        "Ons oordeel betreffende de getrouwheid van de jaarrekening en ons oordeel "
        "met beperking betreffende de rechtmatigheid\nWij hebben de jaarrekening "
        "2022 van de gemeente Testdam gecontroleerd.\nNaar ons oordeel:\n• "
        + GETROUW + "\n• " + RECHTMATIG_SCHOON + "\nDe basis voor ons oordeel\n"
        "Wij vinden dat de verkregen controle-informatie voldoende en geschikt is "
        "als basis voor ons oordeel met beperking betreffende de getrouwheid en de "
        "rechtmatigheid.",
    ),
    # Zonder "ons" in de kop leest de gewone regel "naar ons oordeel" als
    # goedkeurend, terwijl de oordeelzin een voorbehoud draagt (een bibliotheek,
    # 2012). Ook dat is een tegenspraak, in de andere richting.
    (
        "kop zonder 'ons', en de oordeelzin draagt een voorbehoud",
        "Oordeel met beperking betreffende de jaarrekening\nNaar ons oordeel geeft "
        "de jaarrekening uitgezonderd de gevolgen van de aangelegenheid beschreven "
        "in de paragraaf 'Onderbouwing van het oordeel met beperking' een getrouw "
        "beeld van de grootte en samenstelling van het vermogen van Stichting "
        "Testboek per 31 december 2012.",
    ),
]:
    controleer(
        f"getrouwheid niet vast te stellen: {omschrijving}",
        oordeel_getrouwheid(tekst) is None,
        f"kreeg {oordeel_getrouwheid(tekst)!r}",
    )

# Een echte oordeelonthouding heeft geen oordeelzin over het getrouw beeld, en
# blijft dus een oordeelonthouding (zo'n regeling in 2025).
controleer(
    "getrouwheid: een oordeelonthouding zonder getrouwheidszin blijft staan",
    oordeel_getrouwheid(
        "Onze oordeelonthouding\nWij hebben de opdracht gekregen om de jaarrekening "
        "2025 van de gemeenschappelijke regeling Testpark te Testdam te controleren. "
        "Wij geven geen oordeel over de in de jaarstukken opgenomen jaarrekening. "
        "Vanwege de significantie van de aangelegenheid zijn wij niet in staat "
        "geweest voldoende en geschikte controle-informatie te verkrijgen."
    ) == "oordeelonthouding",
)

# --- Vanaf 2023: de rechtmatigheid als deel van het jaarrekeningoordeel -------
#
# Bij gemeenten, provincies en gemeenschappelijke regelingen legt het college
# sinds boekjaar 2023 zelf verantwoording af over de rechtmatigheid, ín de
# jaarrekening. Een voorbehoud bij die verantwoording is een voorbehoud bij het
# jaarrekeningoordeel, en mag dus niet als "alleen rechtmatigheid" goedkeurend
# worden. Herkend aan de vorm, niet aan het jaartal: de oude vorm ("… rechtmatig
# tot stand gekomen") blijft vrijgesteld, ook in 2023 (zie de tests hierboven).
GETROUW_2024 = (
    "geeft de in de jaarstukken opgenomen jaarrekening een getrouw beeld van de "
    "grootte en de samenstelling van de baten en lasten over 2024 en van het "
    "vermogen van de gemeente Testdam op 31 december 2024 in overeenstemming met "
    "het BBV;"
)
for omschrijving, tekst, verwacht in [
    (
        "een beperking op de rechtmatigheidsverantwoording",
        "Ons oordeel met beperking\nWij hebben de jaarrekening 2024 van de gemeente "
        "Testdam gecontroleerd.\nNaar ons oordeel:\n• " + GETROUW_2024 + "\n• is de "
        "in de jaarrekening opgenomen rechtmatigheidsverantwoording, uitgezonderd "
        "de gevolgen van de aangelegenheid beschreven in de paragraaf ‘De basis "
        "voor ons oordeel met beperking’, in alle van materieel belang zijnde "
        "aspecten in overeenstemming met de vereisten van het BBV.",
        "beperking",
    ),
    (
        "een afkeurende rechtmatigheidsverantwoording",
        "Ons afkeurend oordeel\nWij hebben de jaarrekening 2024 van de gemeente "
        "Testdam gecontroleerd.\nNaar ons oordeel:\n• " + GETROUW_2024 + "\n• is de "
        "in de jaarrekening opgenomen rechtmatigheidsverantwoording, vanwege het "
        "belang van de aangelegenheid beschreven in de paragraaf ‘De basis voor ons "
        "afkeurend oordeel’, niet in overeenstemming met de vereisten van het BBV.",
        "afkeurend",
    ),
    (
        "een afkeuring die alleen 'niet in overeenstemming' zegt",
        "Ons afkeurend oordeel\nNaar ons oordeel:\n• " + GETROUW_2024 + "\n• is de "
        "in de jaarrekening opgenomen rechtmatigheidsverantwoording niet in "
        "overeenstemming met de vereisten van het BBV.",
        "afkeurend",
    ),
    (
        "het voorbehoud bij 'een getrouw beeld van de financiële rechtmatigheid'",
        "Ons oordeel met beperking\nNaar ons oordeel geeft de in de jaarstukken "
        "opgenomen jaarrekening een getrouw beeld van de grootte en de samenstelling "
        "van de baten en lasten over 2025 en van het vermogen van Recreatieschap "
        "Testplas op 31 december 2025 alsmede een getrouw beeld van de financiële "
        "rechtmatigheid over 2025, uitgezonderd de gevolgen van de aangelegenheid "
        "beschreven in de paragraaf ‘De basis voor ons oordeel met beperking’, in "
        "overeenstemming met het BBV.",
        "beperking",
    ),
    (
        "het college meldt zelf fouten in de verantwoording; het oordeel is schoon",
        "Ons oordeel\nNaar ons oordeel geeft de in de jaarstukken opgenomen "
        "jaarrekening een getrouw beeld van de grootte en de samenstelling van de "
        "baten en lasten over 2024 en van het vermogen op 31 december 2024 alsmede "
        "een getrouw beeld van de financiële rechtmatigheid over 2024 in "
        "overeenstemming met het BBV.\nParagraaf ter benadrukking van bepaalde "
        "aangelegenheden – rechtmatigheidsverantwoording\nWij vestigen de aandacht "
        "op de rechtmatigheidsverantwoording. Het dagelijks bestuur heeft daarin "
        "toegelicht dat een deel van de lasten niet rechtmatig tot stand is "
        "gekomen. Ons oordeel is niet aangepast als gevolg van deze aangelegenheid.",
        "goedkeurend",
    ),
]:
    controleer(
        f"nieuwe vorm: {omschrijving}",
        oordeel_getrouwheid(tekst) == verwacht,
        f"kreeg {oordeel_getrouwheid(tekst)!r}, verwacht {verwacht!r}",
    )

print(f"\n{gedaan - fouten}/{gedaan} goed")
raise SystemExit(1 if fouten else 0)
