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
import tempfile
import time
from pathlib import Path

from kantoor_match import normaliseer

# Volgorde telt: een controleverklaring noemt vaak óók 'samengesteld'.
#
# Engelse varianten staan erbij omdat internationaal werkende stichtingen hun
# jaarverslag in het Engels publiceren: in de steekproef van 40 goede doelen
# (29-7-2026) waren dat 6 van de 38 leesbare verslagen — allemaal Nederlandse
# controles onder de COS, alleen in een andere taal opgeschreven.
#
# De kale termen "ons oordeel"/"naar ons oordeel" lijken te ruim — een
# bestuursverslag kán "naar ons oordeel was het een goed jaar" zeggen en dan
# telt een samenstellingsdossier als controle. Gemeten op 1.282 gecachte pdf's
# (3-8-2026): dat gebeurt nul keer, terwijl het schrappen van die termen 22
# échte controleverklaringen zou missen — oudere sjablonen (2019) en
# productieverantwoordingen dragen de lange kop niet. Dus: laten staan.
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

# Waar gáát een beperking over? Zonder dat erbij is "oordeel met beperking" naast de
# naam van een ziekenhuis een aanklacht, en dat is het meestal niet.
#
# Gemeten op 26 opgehaalde verklaringen met een beperking (30-7-2026): 23 gaan over
# WNT-aangelegenheden bij intragroepdetachering — de accountant kan de WNT-gegevens
# van binnen een groep gedetacheerde topfunctionarissen niet vaststellen. Dat is een
# beperking in de te verstrekken informatie, geen bevinding over de jaarrekening.
# Slechts 2 waren inhoudelijk (een niet te waarderen vordering; een productiegeschil),
# 1 had geen vindbare grond.
#
# Dat verklaart ook de sprong in de cijfers: 0,8% niet-goedkeurend in boekjaar 2022
# tegen 10,5% in 2023. Dat is geen verslechtering van de zorg maar een golf van
# WNT-beperkingen. Een site die dat verschil niet toont, laat de lezer de verkeerde
# conclusie trekken.
GROND_WNT = ("wnt", "anticumulatie", "normering topinkomens")

# De bron zegt de grond meestal zelf, in deze bewoording.
GROND_UITLEG = "beperking in ons oordeel heeft betrekking op"

# De kop van de basisparagraaf. Let op: die staat er meerdere keren, want de
# oordeelzin verwíjst ernaar ("uitgezonderd de aangelegenheid beschreven in de
# paragraaf de basis voor ons oordeel met beperking geeft de jaarrekening..."). Wie de
# eerste treffer pakt, leest de oordeelzin en niet de grond — dezelfde valkuil als bij
# het venster hierboven. Aan het vervolg is het onderscheid te maken.
GROND_KOP = "de basis voor ons oordeel met beperking"
GROND_KOP_VERWIJZING = (
    "geeft",
    "zijn wij",
    "een getrouw beeld",
    "met de jaarrekening",
    "is voldoende",
    "naar ons oordeel",
)


def _grond_beperking(genormaliseerd: str) -> str | None:
    """"wnt", "inhoudelijk", of None als de grond niet te vinden is.

    None is een echte uitkomst en geen fout: dan weten we het niet, en dat hoort de
    site ook te zeggen in plaats van "inhoudelijk" te gokken.
    """
    grond = None
    if (i := genormaliseerd.find(GROND_UITLEG)) != -1:
        grond = genormaliseerd[i + len(GROND_UITLEG) : i + len(GROND_UITLEG) + 240]
    else:
        for treffer in re.finditer(re.escape(GROND_KOP), genormaliseerd):
            vervolg = genormaliseerd[treffer.end() : treffer.end() + 240].strip()
            if not vervolg.startswith(GROND_KOP_VERWIJZING):
                grond = vervolg
                break
    if grond is None:
        return None
    return "wnt" if any(woord in grond[:200] for woord in GROND_WNT) else "inhoudelijk"


CONTINUITEIT_KENMERKEN = (
    "materiele onzekerheid over de continuiteit",
    "onzekerheid van materieel belang omtrent de continuiteit",
    "gerede twijfel over de continuiteit",
    "material uncertainty related to going concern",
)

# Een ontkenning vlak vóór een kenmerk keert de betekenis om. Het NBA-model sinds
# 2022 zegt bij een gezonde organisatie letterlijk "wij hebben geen materiële
# onzekerheid over de continuïteit geconstateerd" — met een domme substringtest
# kreeg elke organisatie met díe standaardzin een continuïteitsvlag. Engels net zo:
# "did not issue an adverse opinion" is het omgekeerde van een afkeurend oordeel.
#
# Het venster is bewust krap (32 tekens): de ontkenning staat in deze vormen pal
# voor het kenmerk ("geen materiële onzekerheid…", "geen aanwijzingen dat een
# materiële onzekerheid…", "not issue an adverse opinion"). Een ruimer venster
# keek over een zinsgrens heen en schoot echte treffers af — "niet in staat is aan
# haar verplichtingen te voldoen, waardoor gerede twijfel…" is juist wél een
# continuïteitsonzekerheid, met een "niet" een eind ervoor.
#
# Nagemeten over 1.282 gecachte pdf's (3-8-2026): deze check haalt precies de
# twee ontkende standaardzinnen weg (27 -> 25 vlaggen) en verandert verder niets.
_ONTKENNING = re.compile(r"\b(?:geen|niet|zonder|no|not|without)\b")
_ONTKENNING_VENSTER = 32


def _treffer_zonder_ontkenning(genormaliseerd: str, woord: str) -> bool:
    """Staat het kenmerk ergens in de tekst zónder ontkenning er vlak voor?"""
    for m in re.finditer(rf"(?<![a-z0-9]){re.escape(woord)}", genormaliseerd):
        voor = genormaliseerd[max(0, m.start() - _ONTKENNING_VENSTER) : m.start()]
        if not _ONTKENNING.search(voor):
            return True
    return False


# Alleen de Engelse oordeeltermen zijn gevoelig voor zo'n ontkenning: die zijn
# niet-bezittelijk, dus "adverse opinion" staat ook in "did not issue an adverse
# opinion". De Nederlandse kenmerken dragen "ons/onze" in zich en komen in
# ontkende vorm niet voor — die krijgen deze check bewust níét, want een "niet"
# van een vorige zin zou anders een echte beperking naar goedkeurend degraderen.
_ONTKENNING_GEVOELIG = {
    "adverse opinion",
    "qualified opinion",
    "disclaimer of opinion",
    "unqualified opinion",
}


def _oordeel(genormaliseerd: str) -> str | None:
    for label, sleutelwoorden in OORDEEL_KENMERKEN:
        for woord in sleutelwoorden:
            if woord in _ONTKENNING_GEVOELIG:
                if _treffer_zonder_ontkenning(genormaliseerd, woord):
                    return label
            elif re.search(rf"(?<![a-z0-9]){re.escape(woord)}", genormaliseerd):
                return label
    return None


def _continuiteitsonzekerheid(genormaliseerd: str) -> bool:
    return any(
        _treffer_zonder_ontkenning(genormaliseerd, woord)
        for woord in CONTINUITEIT_KENMERKEN
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

# Persoonsnamen zijn nooit een kántoor. Een tekenend accountant staat in de tekst
# als "J.P. van der Meulen RA" en het patroon hierboven viste "J.P. van der
# Meulen RA Accountant" dan op als kandidaat — ruis in de review-queue, want een
# persoon hoort niet in seed/kantoren_overig.csv. Initialen en beroepstitels
# verraden een persoon. Rechtsvormafkortingen (B.V., N.V., V.O.F.) tellen niet
# als initialen en worden eerst weggehaald. Prijs van deze keuze: een kantoor
# dat écht "A. Jansen Accountants" heet, sneuvelt hier ook — dat is hooguit een
# gemiste suggestie.
_RECHTSVORM_AFKORTING = re.compile(r"\b(?:B\.?V\.?|N\.?V\.?|V\.?O\.?F\.?|C\.?V\.?|LLP)\b\.?")
_INITIALEN = re.compile(r"\b[A-Z]\.")
_TITEL = re.compile(r"\b(?:RA|AA|MSc|MBA|CPA|[Dd]rs|[Mm]r|[Ii]r|[Dd]r|[Pp]rof)\b")


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
        zonder_rechtsvorm = _RECHTSVORM_AFKORTING.sub(" ", naam)
        if _INITIALEN.search(zonder_rechtsvorm) or _TITEL.search(zonder_rechtsvorm):
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
    """Lege string als de pdf geen tekstlaag heeft (gescand).

    Met tijdslimiet: één pathologische pdf mag geen werker (en daarmee de hele
    ronde) eeuwig vasthouden. Bij overschrijding doen we alsof er geen tekstlaag
    is — de OCR-route heeft zijn eigen budget. Ontbreekt pdftotext zelf, dan is
    dat een kapotte omgeving en geen kapot document: hard falen, anders wordt
    élke organisatie stilletjes "onleesbaar" en eindigt de run groen met niets.
    """
    try:
        resultaat = subprocess.run(
            ["pdftotext", "-q", pad, "-"], capture_output=True, text=True, timeout=120
        )
    except subprocess.TimeoutExpired:
        return ""
    except FileNotFoundError:
        raise RuntimeError(
            "pdftotext ontbreekt — installeer poppler-utils (zie de workflows)"
        ) from None
    return resultaat.stdout


# Tekstlaag onder deze lengte betekent: hier valt niets te lezen. Zelfde grens als
# `analyseer` gebruikt om "gescande pdf" te melden.
TEKST_ONDERGRENS = 50

# Een verklaring is kort en staat in een jaarrekening áchteraan. Meer pagina's dan
# dit renderen kost minuten zonder dat de kans op een treffer stijgt; bij een langer
# document nemen we daarom de laatste pagina's.
OCR_MAX_PAGINAS = 20

# 300 dpi is de goedkoopste stand waarop tesseract een ondertekening leest. Bij 200
# viel de kantoornaam weg, bij 400 werd het alleen langzamer.
OCR_DPI = 300

# Tijdbudget voor het OCR'en van één document, en per pagina. Waarom dit er is: bij de
# goede doelen kwam "Kracht in NL" uit op 755 seconden voor twintig pagina's — een scan
# op zeer hoge resolutie, waar tesseract per pagina veertig keer langer over doet dan
# normaal (gewoonlijk 2 à 3 seconden). De opbrengst was een samenstellingsverklaring
# zonder kantoor, dus niets. Eén zo'n document eet een kwart van het tijdbudget van een
# ronde op, en de lus draait zes blokken in drie kwartier.
#
# Bij overschrijding geven we een lege string terug en niet de helft van de pagina's:
# de verklaring staat áchteraan, dus een halve lezing mist juist het deel waar het om
# gaat en zou "geen verklaring" melden terwijl die er wel is. Liever `onleesbaar`, wat
# eerlijk is en precies het gedrag van vóór de OCR-terugval.
# Ruim gekozen, en dat is met opzet. De geslaagde lezingen kostten 47 tot 128 seconden;
# de limiet moet alleen het pathologische geval afvangen, niet een langzame ronde. Onder
# druk telt dat dubbel: de lus draait vier werkers naast elkaar, dus per pagina kan het
# een veelvoud van de 2 à 3 seconden worden die het los kost. Met een krappe grens
# (eerst 60s per pagina) leverde een document van twee pagina's dat normaal in 5 seconden
# 1.874 tekens geeft, plotseling nul tekens — een leesbaar verslag dat stil `onleesbaar`
# werd. Een limiet die data weggooit als de machine het even druk heeft is erger dan
# geen limiet.
OCR_TIJDBUDGET = 600
OCR_TIJD_PER_PAGINA = 120


def _eerste_ocr_pagina(pad: str, max_paginas: int) -> int | None:
    """Vanaf welke pagina er ge-OCR'd moet worden, of None als dat niet te bepalen is.

    Alleen een paginatelling ophalen met pdfinfo; dat kost milliseconden, terwijl een
    pagina renderen op 300 dpi tienden van seconden tot seconden kost.
    """
    try:
        uitvoer = subprocess.run(
            ["pdfinfo", pad], capture_output=True, text=True, check=True
        ).stdout
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None
    treffer = re.search(r"^Pages:\s+(\d+)", uitvoer, re.MULTILINE)
    if not treffer:
        return None
    paginas = int(treffer.group(1))
    return max(1, paginas - max_paginas + 1)


def ocr_naar_tekst(pad: str, max_paginas: int = OCR_MAX_PAGINAS) -> str:
    """Tekst uit een gescande pdf, via pdftoppm + tesseract.

    Waarom dit bestaat: van de 333 zorgorganisaties in de doelpopulatie zonder
    opdracht is ongeveer driekwart een scan zonder tekstlaag. Kleine aanbieders
    printen, ondertekenen en scannen. Zonder OCR zijn die onzichtbaar, terwijl er
    ziekenhuizen en ouderenzorg tussen zitten — Ab-Hulp Twente WLZ leverde na OCR
    een volledige rij op (controle, goedkeurend, SMK Audit B.V.).

    Duurt seconden tot een minuut per document, dus alleen aanroepen als de tekstlaag
    leeg is. Ontbreekt tesseract, dan komt er een lege string terug en gedraagt de
    pipeline zich als voorheen: geen tekstlaag, geen opdracht. Liever dat dan een run
    die omvalt op een ontbrekend hulpprogramma.
    """
    with tempfile.TemporaryDirectory() as tijdelijk:
        # Bij een lang document alleen de laatste pagina's renderen: daar staat de
        # verklaring. Het bereik vóóraf bepalen en niet achteraf weggooien, want
        # pdftoppm rendert op 300 dpi en dat is het dure deel. Een jaarverslag van een
        # goed doel is 50 tot 120 pagina's — alles renderen om er twintig te houden
        # kost daar minuten in plaats van seconden. Lukt pdfinfo niet, dan rendert hij
        # alles en snijden we na afloop; dat is de oude weg en die werkt ook.
        eerste = _eerste_ocr_pagina(pad, max_paginas)
        bereik = ["-f", str(eerste), "-l", str(eerste + max_paginas - 1)] if eerste else []
        begin = time.monotonic()
        try:
            subprocess.run(
                ["pdftoppm", "-r", str(OCR_DPI), "-png", *bereik, pad, f"{tijdelijk}/p"],
                check=True,
                capture_output=True,
                timeout=OCR_TIJDBUDGET,
            )
        except (
            subprocess.CalledProcessError,
            subprocess.TimeoutExpired,
            FileNotFoundError,
        ):
            return ""
        paginas = sorted(Path(tijdelijk).glob("p*.png"))
        if len(paginas) > max_paginas:
            paginas = paginas[-max_paginas:]
        stukken = []
        for pagina in paginas:
            if time.monotonic() - begin > OCR_TIJDBUDGET:
                # Zie OCR_TIJDBUDGET: halverwege stoppen zou de verklaring achteraan
                # missen en dat als "geen verklaring" rapporteren. Dan liever niets.
                return ""
            try:
                resultaat = subprocess.run(
                    ["tesseract", str(pagina), "-", "-l", "nld", "--psm", "3"],
                    capture_output=True,
                    text=True,
                    timeout=OCR_TIJD_PER_PAGINA,
                )
            except subprocess.TimeoutExpired:
                # Niet deze pagina overslaan en doorgaan: dan lever je een lezing
                # zonder de pagina waar de verklaring op staat, en dat komt eruit als
                # "geen verklaring". Stilte is hier gevaarlijker dan opgeven.
                return ""
            except FileNotFoundError:
                return ""
            stukken.append(resultaat.stdout)
        return "\n".join(stukken)


def tekst_uit_pdf(pad: str, ocr: bool = True) -> tuple[str, bool]:
    """De tekst én of daar OCR voor nodig was.

    Eén ingang voor alle aanroepers, zodat niemand vergeet dat een gescande pdf nog
    een tweede kans verdient. De boolean gaat mee zodat een lader kan tellen hoe vaak
    OCR nodig was — dat is een kwaliteitssignaal over de bron, geen bijzaak.

    `ocr=False` slaat die tweede kans over. Bedoeld voor organisaties waar een
    wettelijke controle niet kán spelen: OCR kost ruim twee minuten per document en
    dat is weggegooid als het stuk toch een samenstellingsverklaring blijkt.
    Gemeten op vijftien willekeurige zorgorganisaties zonder opdracht (31-7-2026):
    nul rijen, mediaan 127 seconden, en negen van de vijftien hadden aantoonbaar
    geen controleverklaring maar een samenstelling of beoordeling.
    """
    tekst = pdf_naar_tekst(pad)
    if len(tekst.strip()) >= TEKST_ONDERGRENS:
        return tekst, False
    if not ocr:
        return tekst, False
    return ocr_naar_tekst(pad), True


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
    oordeel = _oordeel(genormaliseerd) if soort == "controle" else None
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
        "oordeel": oordeel,
        # Alleen zinvol bij een beperking; bij een goedkeurend oordeel is er niets
        # om te verklaren.
        "grond_beperking": (
            _grond_beperking(genormaliseerd) if oordeel == "beperking" else None
        ),
        "continuiteitsonzekerheid": _continuiteitsonzekerheid(genormaliseerd),
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
