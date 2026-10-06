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

Guardrail: de kantoornaam, plus sinds 20-8-2026 de naam van de tekenend
accountant — mits die uit een openbare bron komt, en dat is de gedeponeerde
verklaring zelf. Zie `docs/concept.md` §9 voor de grondslag; die is níét dat
accountants buiten de AVG vallen. Andere natuurlijke personen blijven eruit, ook
in de teruggave en in logregels.

De naam wordt gezocht door `ondertekenaar.py`, op de ruwe tekst, en hij komt
alleen mee als het blok waar hij in staat hetzelfde oordeel draagt als het
document. Anders zou in een jaarverslag met zowel een jaarrekeningverklaring als
een WNT-verklaring willekeurig zijn welke naam bij welk oordeel belandt.
"""

import os
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


# ---------- getrouwheid en rechtmatigheid (decentrale overheden) ----------
#
# Een verklaring bij een gemeente, provincie, waterschap of gemeenschappelijke
# regeling draagt tot en met boekjaar 2022 twéé oordelen: of de jaarrekening een
# getrouw beeld geeft, en of de baten, lasten en balansmutaties rechtmatig tot
# stand kwamen. Het tweede gaat over aanbestedingen en begrotingsoverschrijdingen,
# niet over de cijfers. `_oordeel` hierboven ziet dat verschil niet: "Ons afkeurend
# oordeel" boven een verklaring waarvan alleen het rechtmatigheidsdeel afkeurend
# is (Smallingerland 2020 en 2021, gemeten 5-10-2026) wordt dan een afkeurend
# jaarrekeningoordeel, naast een goedgekeurde jaarrekening.
#
# Gemeten op de 4.078 ondertekende verklaringen uit Open Raadsinformatie
# (6-10-2026): 3.633 noemen de rechtmatigheid, en van de 262 waarbij `_oordeel`
# niet "goedkeurend" zegt, gaan er 172 alleen over de rechtmatigheid of de WNT.
# 78 zijn een echt niet-goedkeurend getrouwheidsoordeel (77 beperkingen, 1
# oordeelonthouding), elk met een voorbehoud in de oordeelzin of zonder
# getrouwheidszin; 12 blijven twijfel.
#
# Deze functie leest daarom alleen het getrouwheidsoordeel, op drie manieren, van
# sterk naar zwak:
#
# 1. de kop zegt het zelf: "Ons goedkeurend oordeel betreffende de getrouwheid en
#    ons oordeel met beperking betreffende de rechtmatigheid";
# 2. de oordeelzin over het getrouw beeld draagt een voorbehoud ("uitgezonderd
#    de mogelijke effecten van …", "vanwege het belang van … geen getrouw beeld")
#    — dan is dát het oordeel;
# 3. de oordeelzin over het getrouw beeld is zonder voorbehoud: dan goedkeurend,
#    maar alleen als een niet-goedkeurende kop in de tekst aantoonbaar over de
#    rechtmatigheid of de WNT gaat.
#
# Kop en oordeelzin moeten het in beide richtingen eens zijn. Een goedkeurende
# kop boven een zin met voorbehoud is een tegenspraak, en een niet-goedkeurend
# label boven een schone oordeelzin net zo goed — uit welke weg dat label ook
# komt. Tot 6-10-2026 gold alleen de eerste richting, en dan kwam er een
# onterecht oordeel uit: Stichting Begraafplaatsen en Crematorium Hilversum 2024
# werd een oordeelonthouding op de tussenkop "De basis voor onze
# oordeelonthouding" (een sjabloonfout; de oordeelzin zelf geeft een getrouw
# beeld zonder voorbehoud), en Gemeente Twenterand 2022 een beperking op één
# basiszin over "ons oordeel met beperking betreffende de getrouwheid", terwijl
# kop en oordeelzin alleen de rechtmatigheid beperken.
#
# Wat daar niet uitkomt, levert None op: niet vastgesteld. Een rechtmatigheids-
# oordeel als jaarrekeningoordeel opslaan zet een "afkeurend" naast een gemeente
# die een goedgekeurde jaarrekening had, en dat is een beschuldiging.
_GETROUWHEID_KOP = re.compile(
    r"\b(?:ons|onze)\s+(goedkeurend\s+oordeel|afkeurend\s+oordeel|"
    r"oordeel\s+met\s+beperking|oordeelonthouding)\s+(?:\w+\s+){0,4}?"
    r"(getrouwheid|rechtmatigheid)\b"
)
_KOP_LABEL = {
    "goedkeurend oordeel": "goedkeurend",
    "afkeurend oordeel": "afkeurend",
    "oordeel met beperking": "beperking",
    "oordeelonthouding": "oordeelonthouding",
}
# "Wij geven geen oordeel over de getrouwheid en rechtmatigheid van de …
# jaarrekening": de oordeelonthouding staat niet altijd als kop met "getrouwheid"
# erachter.
_ONTHOUDING_JAARREKENING = re.compile(
    r"\b(?:wij\s+geven\s+geen|geven\s+wij\s+geen)\s+oordeel\s+over\s+de\s+"
    r"(?:getrouwheid|(?:in\s+de\s+jaarstukken\s+opgenomen\s+)?jaarrekening)"
    r"|\bonthouden\s+(?:wij\s+)?ons\s+van\s+een\s+oordeel\s+over\s+de\s+"
    r"(?:getrouwheid|(?:in\s+de\s+jaarstukken\s+opgenomen\s+)?jaarrekening)"
)
# Een voorbehoud in de oordeelzin zelf. "uitgezonderd …" en "met uitzondering
# van …" is de vorm van een beperking; "vanwege het belang van … geen getrouw
# beeld" die van een afkeurend oordeel.
_VOORBEHOUD_BEPERKING = re.compile(
    r"\buitgezonderd\b|\bmet uitzondering van\b|\bbehoudens\b"
)
_VOORBEHOUD_AFKEURING = re.compile(
    r"\bgeen getrouw beeld\b|\bniet een getrouw beeld\b|\bgeeft\s+(?:\w+\s+){0,3}?niet\b"
)
# De afkeurende vorm van de rechtmatigheidszin: "… niet in alle van materieel
# belang zijnde aspecten rechtmatig tot stand gekomen", "… voldoen niet aan de
# eisen van financiële rechtmatigheid".
_VOORBEHOUD_RECHTMATIGHEID = re.compile(
    r"\bniet in alle van materieel belang\b|\bvanwege het belang van\b|"
    r"\bniet rechtmatig\b|\bvoldoen\s+(?:\w+\s+){0,3}?niet\b"
)
# Een niet-goedkeurende kop waarvan de tekst er direct achter zegt waar hij
# over gaat. Rechtmatigheid en WNT zijn allebei geen oordeel over het getrouw
# beeld van de jaarrekening (Vlist 2014: "ons afkeurend oordeel betreffende de
# WNT", met een goedgekeurde jaarrekening ernaast).
_NIET_GOEDKEUREND_KOP = re.compile(
    r"\b(?:ons\s+afkeurend\s+oordeel|ons\s+oordeel\s+met\s+beperking|"
    r"onze\s+oordeelonthouding|het\s+afkeurend\s+oordeel|het\s+oordeel\s+met\s+beperking)"
    r"(?P<vervolg>(?:\s+\w+){0,6})"
)
_ANDER_VOORWERP = re.compile(r"rechtmatig|\bwnt\b|bezoldiging|normering")
# Vanaf boekjaar 2023 is de rechtmatigheid bij gemeenten, provincies en
# gemeenschappelijke regelingen geen eigen oordeel meer. Het college legt er in
# de jaarrekening zelf verantwoording over af (de rechtmatigheidsverantwoording),
# en de accountant geeft één oordeel over die jaarrekening, die verantwoording
# inbegrepen: "… geeft een getrouw beeld van … alsmede (een getrouw beeld) van
# de financiële rechtmatigheid over 2023", of "is de in de jaarrekening
# opgenomen rechtmatigheidsverantwoording in overeenstemming met …". Een
# voorbehoud dáár is dus een voorbehoud bij het jaarrekeningoordeel, en de
# vrijstelling hieronder geldt er niet voor.
#
# Herkend aan de vorm van de zin en niet aan het boekjaar: een waterschap of
# schoolbestuur gaf in 2023 en 2024 nog een apart rechtmatigheidsoordeel
# ("zijn de … baten en lasten …, uitgezonderd …, rechtmatig tot stand gekomen";
# Waterschap Vechtstromen 2023 en 2024, Stichting Ambion 2023), en dat blijft
# een ander oordeel dan dat over de jaarrekening. Gemeten op de 4.078
# ondertekende verklaringen (6-10-2026): 153 dragen de nieuwe vorm, 141 daarvan
# over 2025 (Vechtstromen ook), en bij geen enkele staat er een voorbehoud
# alleen in het rechtmatigheidsdeel. Dit is dus een vangnet voor wat er komt.
_NIEUWE_VORM = re.compile(
    r"rechtmatigheidsverantwoording|(?:beeld|alsmede)\s+van\s+de\s+financiele\s+rechtmatigheid"
)
# Het oordeel over de rechtmatigheidsverantwoording als eigen opsommingsteken:
# "• is de in de jaarrekening opgenomen rechtmatigheidsverantwoording,
# uitgezonderd …, in alle van materieel belang zijnde aspecten in
# overeenstemming met …". Die vorm is zelf de oordeelzin; "Naar ons oordeel:"
# staat dan een heel opsommingsteken eerder, buiten het venster van 150 tekens
# dat een getrouwheidszin krijgt. Een benadrukkingsparagraaf ("Wij vestigen de
# aandacht op de rechtmatigheidsverantwoording …") heeft die vorm niet.
_RV_OORDEELZIN = re.compile(
    r"\bis\s+de\s+(?:\w+\s+){0,6}?rechtmatigheidsverantwoording\b.*\bin\s+overeenstemming\b"
)
# Het soort voorbehoud in zo'n zin. Alleen vormen die het soort oordeel
# eenduidig noemen: "uitgezonderd …" is een beperking, "niet in
# overeenstemming" of "geen getrouw beeld" een afkeuring. "Vanwege het belang
# van …" staat ook boven een oordeelonthouding; wat niet eenduidig is, wordt
# twijfel.
_NIEUWE_VORM_AFKEURING = re.compile(
    r"\bgeen getrouw beeld\b|\bniet in overeenstemming\b|\bniet in alle van materieel belang\b"
)
# Zinsgrenzen in de ruwe tekst. Ook ";" en opsommingstekens: "Naar ons oordeel:
# • geeft … een getrouw beeld …; • zijn de … baten en lasten … rechtmatig tot
# stand gekomen" is één zin met twee oordelen, en het voorbehoud van het ene
# mag niet aan het andere blijven plakken.
#
# Een punt telt alleen als zinsgrens vóór een hoofdletter: "de in de jaarstukken
# op pagina 129. tot en met pagina 161. opgenomen jaarrekening" is één zin
# (Leusden 2017, Baarle-Nassau 2020).
_ZINSGRENS = re.compile(r"(?<=;)\s+|(?<=\.)\s+(?=[A-Z])|[•●▪➢]|\n\s*\n")
# "getrouw heeld": tekstherkenning maakt van de b soms een h.
_GETROUW_BEELD = re.compile(r"\bgetrouwe?\s+[bh]eeld\b")
# Waar een voorbehoud in de getrouwheidszin ophoudt: de oordeelzin gaat verder
# ("… een getrouw beeld van …", "…, in overeenstemming met het BBV") of het
# tweede oordeel begint ("en zijn de in de jaarrekening verantwoorde baten en
# lasten …").
_VOORBEHOUD_EINDE = re.compile(
    r"\bgetrouwe?\s+[bh]eeld\b|\bin\s+overeenstemming\b|\bzijn\s+de\b|"
    r"\bverantwoorde\s+baten\b|\bbalansmutaties\b"
)


def _voorbehoud_in(zin: str) -> bool:
    """Draagt dit rechtmatigheidsdeel een voorbehoud, in welke vorm ook?"""
    return bool(
        _VOORBEHOUD_BEPERKING.search(zin)
        or _VOORBEHOUD_RECHTMATIGHEID.search(zin)
        or _NIEUWE_VORM_AFKEURING.search(zin)
    )


def _voorbehoud_nieuwe_vorm(zin: str) -> str:
    """Het soort voorbehoud in een rechtmatigheidsdeel van de nieuwe vorm."""
    beperking = bool(_VOORBEHOUD_BEPERKING.search(zin))
    afkeuring = bool(_NIEUWE_VORM_AFKEURING.search(zin))
    if beperking != afkeuring:
        return "beperking" if beperking else "afkeurend"
    return "twijfel"


def _voorbehoud_over_rechtmatigheid(zin: str, begin: int) -> bool:
    """Verwijst het voorbehoud dat op `begin` begint alleen naar de rechtmatigheid?

    "geeft de jaarrekening, uitgezonderd de gevolgen van de aangelegenheden
    beschreven in de paragraaf 'De basis voor ons oordeel met beperking inzake
    de rechtmatigheid', een getrouw beeld" (GGD West-Brabant 2019): het
    voorbehoud staat in de getrouwheidszin, maar wijst naar de
    rechtmatigheidsparagraaf. Of dat de getrouwheid raakt, zegt de tekst niet.
    Gemeente Westvoorne 2018 heeft dezelfde clausule áchter "getrouw beeld"
    ("… op 31 december 2018, uitgezonderd …, in overeenstemming met het BBV")
    en kreeg tot 6-10-2026 wél een beperking, omdat de regel alleen vóór het
    getrouw beeld keek. De clausule zelf beslist nu, waar hij ook staat: van
    het voorbehoudswoord tot waar de oordeelzin verdergaat. Noemt die ook de
    getrouwheid ("… inzake de getrouwheid en rechtmatigheid", Hof van Twente
    2021), dan is het geen twijfel.
    """
    einde = _VOORBEHOUD_EINDE.search(zin, begin)
    clausule = zin[begin : einde.start() if einde else len(zin)]
    return "rechtmatig" in clausule and "getrouwheid" not in clausule


def oordeel_getrouwheid(tekst: str) -> str | None:
    """Het oordeel over het getrouw beeld van de jaarrekening, of None.

    Voor verklaringen die naast de getrouwheid ook de rechtmatigheid
    beoordelen (decentrale overheden). Noemt de tekst de rechtmatigheid
    helemaal niet, dan is er niets te scheiden en geldt `_oordeel`.
    """
    genormaliseerd = normaliseer(tekst)

    # 1. De kop zegt het zelf.
    koppen: dict[str, set[str]] = {"getrouwheid": set(), "rechtmatigheid": set()}
    for treffer in _GETROUWHEID_KOP.finditer(genormaliseerd):
        koppen[treffer.group(2)].add(_KOP_LABEL[re.sub(r"\s+", " ", treffer.group(1))])

    # De oordeelzinnen over het getrouw beeld, elk met hun eigen voorbehoud.
    voorbehouden: set[str] = set()
    getrouw_zinnen = 0
    # Staat er een oordeelzin over de rechtmatigheid mét voorbehoud? Dan is
    # daarmee een algemene kop "Ons oordeel met beperking" verklaard.
    rechtmatigheid_voorbehoud = False
    grenzen = [0] + [m.end() for m in _ZINSGRENS.finditer(tekst)] + [len(tekst)]
    for begin, eind in zip(grenzen, grenzen[1:]):
        zin = normaliseer(tekst[begin:eind])
        beeld = _GETROUW_BEELD.search(zin)
        # Niet de alinea over wat het college moet doen of wat de accountant
        # evalueert.
        if "verantwoordelijk" in zin or "evalueren" in zin:
            continue
        if not beeld:
            if "rechtmatig" not in zin:
                continue
            if _RV_OORDEELZIN.search(zin):
                # Vanaf 2023: een deel van het jaarrekeningoordeel.
                if _voorbehoud_in(zin):
                    voorbehouden.add(_voorbehoud_nieuwe_vorm(zin))
            elif _VOORBEHOUD_BEPERKING.search(zin) or _VOORBEHOUD_RECHTMATIGHEID.search(zin):
                rechtmatigheid_voorbehoud = True
            continue
        # Een oordeelzin. Het woord "oordeel" mag ook vlak ervóór staan: "Naar
        # ons oordeel: • geeft de … jaarrekening een getrouw beeld …" is door de
        # opsomming in tweeën.
        if "oordeel" not in zin and "oordeel" not in normaliseer(
            tekst[max(0, begin - 150) : begin]
        ):
            continue
        getrouw_zinnen += 1
        # Oudere verklaringen zetten beide oordelen in één zin: "geeft … een
        # getrouw beeld …, en zijn de in de jaarrekening verantwoorde baten en
        # lasten, uitgezonderd …, rechtmatig tot stand gekomen". Het voorbehoud
        # hoort dan bij het tweede deel; alleen tot daar telt het mee. In de
        # nieuwe vorm hoort dat tweede deel juist bij het jaarrekeningoordeel.
        na_beeld = beeld.start()
        zin_vol = zin
        einden = [
            plek for plek in (
                zin.find(woord, na_beeld)
                for woord in ("rechtmatig", "verantwoorde baten", "balansmutaties")
            ) if plek != -1
        ]
        if einden:
            rest = zin[min(einden) :]
            if _NIEUWE_VORM.search(zin):
                if _voorbehoud_in(rest):
                    voorbehouden.add(_voorbehoud_nieuwe_vorm(rest))
            elif _VOORBEHOUD_BEPERKING.search(rest) or _VOORBEHOUD_RECHTMATIGHEID.search(rest):
                rechtmatigheid_voorbehoud = True
            zin = zin[: min(einden)]
        if _VOORBEHOUD_AFKEURING.search(zin):
            voorbehouden.add("afkeurend")
        if beperking := _VOORBEHOUD_BEPERKING.search(zin):
            voorbehouden.add("beperking")
            # Een voorbehoud dat naar de rechtmatigheidsparagraaf verwijst,
            # vóór of ná het getrouw beeld. Op de ongeknipte zin: de knip
            # hierboven valt bij Westvoorne 2018 precies in de aangehaalde
            # paragraaftitel ("… inzake de | rechtmatigheid").
            if _voorbehoud_over_rechtmatigheid(zin_vol, beperking.start()):
                voorbehouden.add("twijfel")

    def eens(label: str | None) -> str | None:
        """Het label, tenzij de oordeelzinnen het tegenspreken.

        Een niet-goedkeurend label terwijl er een oordeelzin over het getrouw
        beeld staat en geen enkele zo'n zin een voorbehoud draagt: dan zegt de
        tekst twee dingen, en kiezen is gokken. Zonder getrouwheidszin
        (een echte oordeelonthouding heeft er geen) blijft het label staan.
        """
        if label in (None, "goedkeurend"):
            return label
        if getrouw_zinnen and not voorbehouden:
            return None
        return label

    if koppen["getrouwheid"]:
        if len(koppen["getrouwheid"]) > 1:
            return None
        label = next(iter(koppen["getrouwheid"]))
        # Een goedkeurende kop boven een zin met voorbehoud is een tegenspraak,
        # en dan kiezen we niet; de omgekeerde richting staat in eens().
        if label == "goedkeurend" and voorbehouden:
            return None
        return eens(label)

    if _ONTHOUDING_JAARREKENING.search(genormaliseerd):
        return eens("oordeelonthouding")

    if "rechtmatig" not in genormaliseerd:
        label = _oordeel(genormaliseerd)
        if label == "goedkeurend" and voorbehouden:
            return None
        return eens(label)

    # 2. De oordeelzin draagt een voorbehoud. "twijfel" is geen oordeel maar
    # een reden om er geen te geven.
    if voorbehouden:
        if "twijfel" in voorbehouden or len(voorbehouden) > 1:
            return None
        return next(iter(voorbehouden))

    # 3. Geen voorbehoud in de oordeelzin.
    if not getrouw_zinnen:
        return None
    algemeen = _oordeel(genormaliseerd)
    if algemeen == "goedkeurend":
        return "goedkeurend"
    if algemeen is None:
        return None
    # Een niet-goedkeurende kop, en de getrouwheidszin is schoon: alleen
    # goedkeurend als die kop aantoonbaar over iets anders gaat — een
    # rechtmatigheidskop, een rechtmatigheidszin met voorbehoud, of een kop met
    # rechtmatigheid of WNT direct erachter.
    if koppen["rechtmatigheid"] and not koppen["rechtmatigheid"] <= {"goedkeurend"}:
        return "goedkeurend"
    if rechtmatigheid_voorbehoud:
        return "goedkeurend"
    for kop in _NIET_GOEDKEUREND_KOP.finditer(genormaliseerd):
        if not _ANDER_VOORWERP.search(kop.group("vervolg")):
            return None
    return "goedkeurend"


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

# Mag er in deze omgeving überhaupt ge-OCR'd worden?
#
# OCR is verreweg het duurste dat deze pipeline doet: tientallen seconden tot
# minuten per document, tegen milliseconden voor een pdf mét tekstlaag. Op een
# GitHub-runner betaal je dat in Actions-minuten, en die zijn schaars. Daarom
# draait het zware lezen buiten Actions om (zie docs/draaiboek-acties.md): daar
# oogsten we naar een csv, en de workflow schrijft alleen die csv weg.
#
# Zet WHOSIGNS_OCR op 0/nee/false om OCR uit te zetten. Wat er dan gebeurt is
# precies het gedrag van vóór de OCR-terugval: een gescande pdf levert geen
# tekst en dus geen opdracht, netjes gemeld als `onleesbaar`. Nooit een gok.
def ocr_toegestaan() -> bool:
    """Leest de omgevingsvariabele bij elke aanroep, zodat een test hem kan zetten."""
    return os.environ.get("WHOSIGNS_OCR", "1").strip().lower() not in {
        "0", "nee", "false", "off", "uit",
    }


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


# Waar de uitkomst van een OCR-lezing bewaard blijft, naast de pdf zelf.
#
# Waarom dit er is: OCR is het enige dure onderdeel van de pipeline, en de oogst
# draait in een omgeving die tussendoor opnieuw kan beginnen. Zonder bewaren
# begon elke herstart weer bij nul — blok 110-120 van boekjaar 2019 haalde tien
# keer op rij het einde niet, en gooide elke keer al het OCR-werk weg dat het tot
# dan toe had gedaan. Mét bewaren kost een herstart alleen de documenten die nog
# niet gelezen zijn, en kruipt de oogst vooruit ook als geen enkele poging het
# blok in één keer afmaakt.
#
# De kopregel houdt bij waar de tekst vandaan komt. Verandert het bestand (een
# nieuwe download onder dezelfde naam) of een OCR-instelling, dan telt de bewaarde
# tekst niet meer mee en wordt er opnieuw gelezen. Zonder die regel zou een
# verhoogde dpi of paginagrens stil genegeerd worden.
OCR_BEWAAR_VERSIE = 1


def _ocr_kop(pad: str, max_paginas: int) -> str | None:
    try:
        grootte = Path(pad).stat().st_size
    except OSError:
        return None
    return (
        f"# whosigns-ocr v{OCR_BEWAAR_VERSIE} grootte={grootte} "
        f"dpi={OCR_DPI} paginas={max_paginas}"
    )


def _ocr_uit_bewaarplaats(pad: str, kop: str | None, suffix: str = ".ocr.txt") -> str | None:
    """De eerder gelezen tekst, of None als die er niet is of niet meer klopt."""
    if kop is None:
        return None
    try:
        bewaard = Path(pad + suffix).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None
    regel, scheiding, tekst = bewaard.partition("\n")
    if not scheiding or regel != kop:
        return None
    return tekst


def _bewaar_ocr(pad: str, kop: str | None, tekst: str, suffix: str = ".ocr.txt") -> None:
    """Bewaart alleen een geslaagde lezing.

    Een lege uitkomst betekent "opgegeven" (tijdbudget op, tesseract ontbreekt) en
    niet "hier staat niets". Die bewaren zou het document voorgoed als onleesbaar
    wegzetten zonder dat het ooit nog een kans krijgt — precies de stille schade
    die dit platform niet hoort te maken. Opgeven blijft dus herhaalbaar.
    """
    if kop is None or not tekst.strip():
        return
    try:
        Path(pad + suffix).write_text(kop + "\n" + tekst, encoding="utf-8")
    except OSError:
        pass  # geen schrijfrechten of schijf vol: dan gewoon elke keer opnieuw lezen


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
    kop = _ocr_kop(pad, max_paginas)
    eerder = _ocr_uit_bewaarplaats(pad, kop)
    if eerder is not None:
        return eerder
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
        tekst = "\n".join(stukken)
        _bewaar_ocr(pad, kop, tekst)
        return tekst


# Een pdf mét tekstlaag kan de verklaring tóch als scan bevatten: de VU en
# Tilburg University plakken de ondertekende pagina's als afbeelding in een
# verder gewoon tekst-pdf. De gewone OCR-terugval ziet zo'n document nooit
# (de tekstlaag is ruim boven de ondergrens), dus de verklaring bleef
# onleesbaar: "PwC staat in de tekst, maar niet als ondertekenaar". De twee
# functies hieronder lezen alléén de tekstloze pagina's — en alleen als de
# aanroeper daarom vraagt, want dit is de uitzondering en OCR kost minuten.
OCR_LEGE_MAX = 12
LEGE_PAGINA_GRENS = 20


def lege_paginas(tekst: str, grens: int = LEGE_PAGINA_GRENS) -> list[int]:
    """Paginanummers (1-based) zonder noemenswaardige tekstlaag.

    pdftotext scheidt pagina's met een form feed, dus dit kost geen extra
    leesbeurt. Onder de grens zit in de praktijk een scan of een paginagrote
    foto; echte tekstpagina's van een jaarverslag zitten in de honderden
    tekens.
    """
    return [
        nummer
        for nummer, pagina in enumerate(tekst.split("\f"), start=1)
        if len(pagina.strip()) < grens
    ]


def _aaneengesloten(paginas: list[int]) -> list[tuple[int, int]]:
    """[3,4,5,9] -> [(3,5), (9,9)]; pdftoppm rendert per bereik."""
    reeksen: list[tuple[int, int]] = []
    for pagina in paginas:
        if reeksen and pagina == reeksen[-1][1] + 1:
            reeksen[-1] = (reeksen[-1][0], pagina)
        else:
            reeksen.append((pagina, pagina))
    return reeksen


def ocr_lege_paginas(pad: str, tekst: str, max_paginas: int = OCR_LEGE_MAX) -> str:
    """OCR van de tekstloze pagina's in een pdf die verder wél tekst heeft.

    Alleen de láátste `max_paginas` lege pagina's: de verklaring staat bij de
    overige gegevens achterin, terwijl de foto's die ook "leeg" zijn vooral
    voorin en middenin staan. Zelfde budget- en bewaarafspraken als
    ocr_naar_tekst, met een eigen bewaarbestand (.ocrlege.txt) zodat de twee
    lezingen elkaar niet overschrijven.
    """
    if not ocr_toegestaan():
        return ""
    paginas = lege_paginas(tekst)[-max_paginas:]
    if not paginas:
        return ""
    kop = _ocr_kop(pad, max_paginas)
    if kop is not None:
        kop += f" lege={','.join(map(str, paginas))}"
    eerder = _ocr_uit_bewaarplaats(pad, kop, ".ocrlege.txt")
    if eerder is not None:
        return eerder
    begin = time.monotonic()
    stukken: list[str] = []
    with tempfile.TemporaryDirectory() as tijdelijk:
        for van, tot in _aaneengesloten(paginas):
            try:
                # Prefix met het beginnummer: pdftoppm pakt de nummerbreedte per
                # bereik, en zonder prefix sorteert p-9 na p-247.
                subprocess.run(
                    [
                        "pdftoppm", "-r", str(OCR_DPI), "-png",
                        "-f", str(van), "-l", str(tot),
                        pad, f"{tijdelijk}/p{van:04d}",
                    ],
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
        for pagina in sorted(Path(tijdelijk).glob("p*.png")):
            if time.monotonic() - begin > OCR_TIJDBUDGET:
                # Zie ocr_naar_tekst: half werk zou "geen verklaring" opleveren.
                return ""
            try:
                resultaat = subprocess.run(
                    ["tesseract", str(pagina), "-", "-l", "nld", "--psm", "3"],
                    capture_output=True,
                    text=True,
                    timeout=OCR_TIJD_PER_PAGINA,
                )
            except subprocess.TimeoutExpired:
                return ""
            except FileNotFoundError:
                return ""
            stukken.append(resultaat.stdout)
    gelezen = "\n".join(stukken)
    _bewaar_ocr(pad, kop, gelezen, ".ocrlege.txt")
    return gelezen


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
    # `ocr=False` is de keuze van de aanroeper, `ocr_toegestaan()` die van de
    # omgeving. Beide moeten ja zeggen; zie de toelichting bij ocr_toegestaan.
    if not ocr or not ocr_toegestaan():
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
    from ondertekenaar import zoek_ondertekenaar

    genormaliseerd = normaliseer(tekst)
    if len(genormaliseerd) < 50:
        return {
            "soort": None,
            "oordeel": None,
            "continuiteitsonzekerheid": None,
            "kantoor": None,
            "tekenend_accountant": None,
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

    # De ondertekenaar, en alleen als hij bij hétzelfde oordeel hoort.
    #
    # `oordeel` hierboven wordt over de hele tekst bepaald: de eerste treffer
    # wint. De naam komt daarentegen uit één blok. In een jaarverslag met zowel
    # een goedkeurende jaarrekeningverklaring als een WNT-verklaring mét
    # beperking is het dan willekeurig welke naam bij welk oordeel belandt — en
    # dat zijn precies de twee stukken die de bron zelf ook door elkaar haalt
    # (zie de migratie 20260820130000). Een naam onder een oordeel dat hij niet
    # heeft afgegeven is geen leemte maar een beschuldiging, dus: komt het
    # blokoordeel niet overeen met het documentoordeel, dan geen naam.
    ondertekenaar = zoek_ondertekenaar(
        tekst, treffer["kantoor"]["naam"] if treffer else None
    )
    tekenend_accountant = None
    if ondertekenaar["naam"] and soort == "controle":
        blok = ondertekenaar["blok"]
        blokoordeel = _oordeel(normaliseer(tekst[blok[0] : blok[1]])) if blok else None
        if blokoordeel == oordeel:
            tekenend_accountant = ondertekenaar["naam"]

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
        # Zie hierboven: alleen ingevuld als de naam op een ondertekeningsplek
        # stond in een blok waarvan het oordeel gelijk is aan het documentoordeel.
        # Leeg betekent "niet vastgesteld", nooit "niet getekend".
        "tekenend_accountant": tekenend_accountant,
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
