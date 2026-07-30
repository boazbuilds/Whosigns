"""Uit een gedeponeerde pdf halen: soort verklaring + welk kantoor tekende.

Geen LLM. Twee deterministische stappen:
1. `pdftotext` (poppler) haalt de tekstlaag eruit.
2. Trefwoorden bepalen het soort verklaring; `kantoor_match` zoekt de kantoornaam
   op in de gesloten AFM-lijst.

Alleen een controleverklaring is een wettelijke controle. Samenstellings- en
beoordelingsverklaringen komen vaak van kantoren zónder Wta-vergunning — die horen
niet in `opdrachten` als wettelijke controle, en dat er geen match is, is dan juist
correct gedrag.

Gemeten op een steekproef van 41 zorg-pdf's (juli 2026, boekjaar 2023):
26 van de 27 controleverklaringen correct herleid tot een AFM-vergunninghouder
(96%), zonder valse matches. De rest: gescande pdf's zonder tekstlaag en één
verklaring waarin de kantoornaam alleen als logo staat — die gaan naar de
review-queue.

Guardrail: we halen uitsluitend de kantoornaam op. De naam van de tekenend
accountant staat wel in de tekst, maar wordt niet gezocht, niet teruggegeven en
niet gelogd.
"""

import re
import subprocess

from kantoor_match import normaliseer

# Volgorde telt: een controleverklaring noemt vaak óók 'samengesteld'.
#
# Engelse varianten staan erbij omdat internationaal werkende stichtingen hun
# jaarverslag in het Engels publiceren: in de steekproef van 40 goede doelen
# (29-7-2026) waren dat 6 van de 38 leesbare verslagen — allemaal Nederlandse
# controles onder de COS, alleen in een andere taal opgeschreven.
SOORT_KENMERKEN = [
    (
        "controle",
        (
            "controleverklaring van de onafhankelijke accountant",
            "naar ons oordeel",
            "ons oordeel",
            "independent auditor s report",
            "audit of the financial statements",
            "in our opinion",
        ),
    ),
    ("beoordeling", ("beoordelingsverklaring", "standaard 2400", "review report")),
    (
        "samenstelling",
        (
            "samenstellingsverklaring",
            "standaard 4410",
            "samengesteld",
            "compilation report",
        ),
    ),
]

# Bezittelijke vorm, want dat is de kop van de oordeelparagraaf ("Ons oordeel met
# beperking", "Onze oordeelonthouding") en niet iets dat je in een beschouwing
# tegenkomt. Losse termen als "oordeelonthouding" of "oordeel met beperking"
# stonden ook in bestuursverslagen die het over de sector in het algemeen hadden —
# dat leverde twee onterechte oordeelonthoudingen op in de proefrit van boekjaar
# 2023 (Jeugdbescherming Brabant en Veilig Thuis Oost-Brabant, allebei in de zin
# "een hausse van verklaringen met beperking of oordeelonthoudingen").
#
# De Engelse termen kunnen niet met een gewone substringtest: 'qualified opinion'
# zit letterlijk in 'unqualified opinion', en dat is precies het omgekeerde
# oordeel. `_eerste_treffer` eist daarom een woordgrens vóór het kenmerk.
OORDEEL_KENMERKEN = [
    ("afkeurend", ("ons afkeurend oordeel", "adverse opinion")),
    (
        "oordeelonthouding",
        (
            "onze oordeelonthouding",
            "wij geven geen oordeel",
            "disclaimer of opinion",
            "we do not express an opinion",
        ),
    ),
    ("beperking", ("ons oordeel met beperking", "qualified opinion")),
    (
        "goedkeurend",
        ("naar ons oordeel", "ons oordeel", "unqualified opinion", "in our opinion"),
    ),
]

# Ook geprobeerd en verworpen: het oordeel alleen zoeken in het stuk tekst vanaf de
# kop "controleverklaring van de onafhankelijke accountant". Klinkt logischer, maar
# die kop komt in een jaarrekening meerdere keren voor (inhoudsopgave, de
# verwijzing "de verklaring is opgenomen op pagina 69", en de verklaring zelf).
# Welke je ook kiest, je landt regelmatig ná de oordeelparagraaf: bij
# HagaZiekenhuis 2023 begon het venster middenin de fraudeparagraaf, waardoor een
# echt oordeel met beperking als goedkeurend uit de bus kwam. 38 oordelen sloegen
# op die manier de verkeerde kant op. De kopvorm hierboven doet het werk al.

# Waar gáát de controle over? "Controleverklaring van de onafhankelijke accountant"
# staat óók boven een verklaring bij een WNT-verantwoording of een financiële
# productieverantwoording, en dat zijn andere opdrachten dan de controle van de
# jaarrekening. Zonder dit onderscheid boeken we die als wettelijke controle en
# tellen ze mee in marktaandelen waar ze niet horen.
#
# Gemeten op de 686 geladen rijen van boekjaar 2023: 622 noemen de jaarrekening,
# 34 alleen WNT, 26 alleen productieverantwoording, 4 geen enkel kenmerk. Dus
# ongeveer één op de elf was verkeerd getypeerd.
#
# Let op de volgorde: een verzameldocument noemt vaak zowel de jaarrekening als de
# WNT-verantwoording. De jaarrekening is dan het zwaarste voorwerp en die wint.
VOORWERP_KENMERKEN = [
    (
        "wettelijke_controle",
        (
            "in de jaarverslaggeving opgenomen jaarrekening",
            "controle van de jaarrekening",
            "verklaring over de jaarrekening",
            "audit of the financial statements",
        ),
    ),
    (
        "wnt_verantwoording",
        (
            "wnt verantwoording",
            "verantwoordingsmodel wnt",
            "controleverklaring wnt",
            "wnt gegevens",
            "bezoldiging topfunctionarissen",
        ),
    ),
    (
        "productieverantwoording",
        (
            "financiele productieverantwoording",
            "productieverantwoording",
            "nacalculatie",
            "gerealiseerde productie",
        ),
    ),
    ("subsidieverklaring", ("subsidieverantwoording", "verantwoording subsidie")),
]

CONTINUITEIT_KENMERKEN = (
    "materiele onzekerheid over de continuiteit",
    "onzekerheid van materieel belang omtrent de continuiteit",
    "gerede twijfel over de continuiteit",
    "material uncertainty related to going concern",
)

# Verwijst de verklaring naar de Wta? Bij een wettelijke controle hoort de
# onafhankelijkheidsparagraaf naar de Wet toezicht accountantsorganisaties te
# verwijzen; bij een vrijwillige controle staat daar de ViO. Het is een
# aanwijzing, geen bewijs — daarom een apart veld en geen conclusie.
WTA_KENMERKEN = (
    "wet toezicht accountantsorganisaties",
    "wta",
    "verordening eu nr 537 2014",
)

# Namen die op een accountantskantoor lijken. Bedoeld om kandidaten aan te dragen
# voor de review-queue en voor het uitbreiden van de kantorenlijst — nooit om
# automatisch een kantoor vast te stellen: dat blijft een match tegen een lijst.
_KANDIDAAT = re.compile(
    r"([A-Z][A-Za-z&'’\.\- ]{2,45}?\s?"
    r"(?:Accountants?|Audit|Assurance|Registeraccountants|Accountancy)"
    r"(?:\s(?:&|en)\s[A-Z][A-Za-z]+)?"
    r"(?:\s(?:B\.?V\.?|N\.?V\.?|LLP))?)"
)
# Wat het patroon óók opvist: commissies, wetteksten en kostenposten uit de
# jaarrekening ("Bestuurskosten Accountants", "De Auditcommissie", "Verordening
# Gedrags- en Beroepsregels Accountants").
_KANDIDAAT_RUIS = re.compile(
    r"auditcommissie|audit commissie|auditcomite|standards on auditing|"
    r"beroepsregels|verordening|nba|code of ethics|raad van|\blid\b|commissie|"
    r"kosten|lonen|salaris|vergoeding|bespreking|rapportage|verslag|overleg|"
    r"international standards|dutch standards|final audit|internal audit|"
    r"chartered|expenses|allowance|advice|opdrachten|verricht|"
    r"algemene voorwaarden|gedeponeerd",
    re.I,
)


def kantoorkandidaten(tekst: str) -> list[str]:
    """Namen uit de tekst die op een accountantskantoor lijken, meest genoemd eerst.

    Gebruikt door de review-queue (welk kantoor stond er dan wél?) en door
    `verken_stichtingen.py oogst`, dat hiermee de kantorenlijst buiten het
    AFM-register opbouwt.
    """
    telling: dict[str, int] = {}
    for treffer in _KANDIDAAT.finditer(tekst):
        naam = re.sub(r"\s+", " ", treffer.group(1)).strip(" .-&")
        if len(naam) < 6 or _KANDIDAAT_RUIS.search(naam):
            continue
        # Losse beroepsaanduidingen zonder eigennaam zeggen niets.
        if normaliseer(naam) in {
            "accountants", "accountant", "audit", "assurance", "accountancy",
            "registeraccountants", "audit assurance",
        }:
            continue
        telling[naam] = telling.get(naam, 0) + 1

    # Dezelfde naam komt vaak in twee lengtes voorbij ("Op alle door Kaap Hoorn
    # Audit & Assurance B.V." naast "Kaap Hoorn Audit & Assurance B.V."). Houd de
    # kortste vorm en tel de langere daarbij op.
    namen = sorted(telling, key=len)
    beknopt: dict[str, int] = {}
    for naam in sorted(telling, key=lambda n: -len(n)):
        korter = next(
            (k for k in namen if k != naam and normaliseer(naam).endswith(normaliseer(k))),
            None,
        )
        if korter:
            telling[korter] += telling[naam]
        else:
            beknopt[naam] = telling[naam]
    return sorted(beknopt, key=lambda n: (-telling[n], n))


def pdf_naar_tekst(pad: str) -> str:
    """Lege string als de pdf geen tekstlaag heeft (gescand)."""
    resultaat = subprocess.run(
        ["pdftotext", "-q", pad, "-"], capture_output=True, text=True
    )
    return resultaat.stdout


def _eerste_treffer(genormaliseerd: str, kenmerken: list[tuple]) -> str | None:
    """Eerste label waarvan een kenmerk als woord in de tekst staat.

    Woordgrens alléén aan de voorkant: dat vangt 'unqualified opinion' weg bij
    het zoeken naar 'qualified opinion', terwijl meervouden aan de achterkant
    ('productieverantwoordingen', 'nacalculaties') blijven meetellen.
    """
    for label, sleutelwoorden in kenmerken:
        if any(
            re.search(rf"(?<![a-z0-9]){re.escape(woord)}", genormaliseerd)
            for woord in sleutelwoorden
        ):
            return label
    return None




def analyseer(tekst: str, index: dict) -> dict:
    """Geeft soort, oordeel, continuïteitsonzekerheid en kantoor.

    `kantoor` is None wanneer er geen betrouwbare match is; de aanroeper zet zo'n
    geval in de review_queue in plaats van te gokken.
    """
    from kantoor_match import zoek_kantoor

    genormaliseerd = normaliseer(tekst)
    if len(genormaliseerd) < 50:
        return {
            "soort": None,
            "oordeel": None,
            "continuiteitsonzekerheid": None,
            "kantoor": None,
            "kandidaten": [],
            "wta_kenmerk": None,
            "reden": "geen tekstlaag (gescande pdf)",
        }

    soort = _eerste_treffer(genormaliseerd, SOORT_KENMERKEN)
    treffer = zoek_kantoor(tekst, index)
    # Een naam die niet op een ondertekeningsplek staat, is geen vastgesteld kantoor.
    # Hij gaat wél als suggestie mee naar de review-queue: iemand die het stuk erbij
    # pakt, is er in tien seconden uit.
    zwakke_treffer = treffer["kantoor"]["naam"] if treffer and treffer["zwak"] else None
    if zwakke_treffer:
        treffer = None
    return {
        "soort": soort,
        # Waar de controle over gaat. None betekent: het is wél een
        # controleverklaring, maar we hebben niet kunnen vaststellen waarover —
        # dan is "wettelijke controle" een aanname en geen bevinding.
        "opdrachttype": (
            _eerste_treffer(genormaliseerd, VOORWERP_KENMERKEN)
            if soort == "controle"
            else None
        ),
        "oordeel": _eerste_treffer(genormaliseerd, OORDEEL_KENMERKEN)
        if soort == "controle"
        else None,
        "continuiteitsonzekerheid": any(
            woord in genormaliseerd for woord in CONTINUITEIT_KENMERKEN
        ),
        "kantoor": treffer["kantoor"] if treffer else None,
        # Aanwijzing dat het om een wettelijke controle gaat; de aanroeper beslist
        # wat hij ermee doet (zie laad_stichtingen.py).
        "wta_kenmerk": _eerste_treffer(genormaliseerd, [("wta", WTA_KENMERKEN)]) == "wta",
        # Wat er dan wél in de tekst stond. Alleen gevuld als er geen match is,
        # zodat de review-queue een aanknopingspunt heeft. Een naam die alleen buiten
        # de ondertekening voorkwam, staat vooraan — dat is de sterkste aanwijzing.
        "kandidaten": (
            []
            if treffer
            else ([zwakke_treffer] if zwakke_treffer else []) + kantoorkandidaten(tekst)[:5]
        ),
        "reden": (
            None
            if treffer
            else (
                f"'{zwakke_treffer}' staat in de tekst, maar niet als ondertekenaar"
                if zwakke_treffer
                else "kantoornaam niet gevonden in de tekst"
            )
        ),
    }
