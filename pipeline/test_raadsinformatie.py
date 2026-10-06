"""Leesregels voor controleverklaringen in raadsstukken.

De tekstfragmenten hieronder komen uit echte documenten in Open
Raadsinformatie; erboven staat welk geval ze afdekken.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "adapters"))

import raadsinformatie as ori  # noqa: E402

fouten = 0
gedaan = 0


def controleer(omschrijving: str, goed: bool, detail: str = "") -> None:
    global fouten, gedaan
    gedaan += 1
    fouten += not goed
    print(f"{'✓' if goed else '✗'} {omschrijving}")
    if not goed and detail:
        print(f"    {detail}")


# --- de standaardzin ---------------------------------------------------------
TEKST = (
    "Controleverklaring van de onafhankelijke accountant\n"
    "Aan het algemeen bestuur van de Gemeenschappelijke regeling WerkSaam "
    "Westfriesland te Hoorn\n"
    "A. VERKLARING OVER DE IN DE JAARSTUKKEN OPGENOMEN JAARREKENING 2018\n"
    "Ons oordeel\n"
    "Wij hebben de jaarrekening 2018 van de Gemeenschappelijke regeling WerkSaam "
    "Westfriesland te Hoorn gecontroleerd.\n"
)
uit = ori.verklaringen_uit(TEKST)
controleer(
    "de zin levert organisatie, boekjaar en plaats",
    len(uit) == 1
    and uit[0]["organisatie"] == "Gemeenschappelijke regeling WerkSaam Westfriesland"
    and uit[0]["boekjaar"] == 2018
    and uit[0]["plaats"] == "Hoorn",
    f"gevonden: {uit}",
)

# Een document dat de term alleen in een inhoudsopgave noemt levert niets op —
# dat is de rem op aanbiedingsbrieven en jaarstukken zonder verklaring.
controleer(
    "zonder de standaardzin geen verklaring",
    ori.verklaringen_uit(
        "Controleverklaring van de onafhankelijke accountant ......... 21\n"
        "Bijlagen I Begrotingscriterium over 2018\n"
    )
    == [],
)

# --- meerdere verklaringen in één bundel -------------------------------------
#
# Dit is het geval waar de bron om vraagt: een raadsbundel met de jaarstukken
# van twee gemeenschappelijke regelingen achter elkaar. Het handtekeningblok
# van de eerste mag niet aan de tweede worden toegeschreven.
BUNDEL = (
    "Wij hebben de jaarrekening 2020 van gemeenschappelijke regeling SSC DeSom "
    "te Wognum gecontroleerd.\n"
    + "vulling " * 200
    + "Alkmaar, 12 april 2021 Deloitte Accountants B.V. was getekend\n"
    + "Wij hebben de jaarrekening 2020 van gemeenschappelijke regeling GGD "
    "Hollands Noorden te Schagen gecontroleerd.\n"
    + "vulling " * 200
    + "Zwolle, 3 mei 2021 Flynth Audit B.V. was getekend\n"
)
uit = ori.verklaringen_uit(BUNDEL)
controleer(
    "twee verklaringen in één document worden allebei gezien",
    len(uit) == 2
    and uit[0]["boekjaar"] == 2020
    and "DeSom" in uit[0]["organisatie"]
    and "GGD" in uit[1]["organisatie"],
    f"gevonden: {[(v['organisatie'], v['boekjaar']) for v in uit]}",
)
eerste_venster = BUNDEL[uit[0]["venster"][0] : uit[0]["venster"][1]]
tweede_venster = BUNDEL[uit[1]["venster"][0] : uit[1]["venster"][1]]
controleer(
    "het venster van de eerste houdt op bij de tweede verklaring",
    "Deloitte" in eerste_venster and "Flynth" not in eerste_venster,
    "het venster liep door tot in de volgende verklaring",
)
controleer(
    "het venster van de tweede bevat alleen haar eigen kantoor",
    "Flynth" in tweede_venster,
)

# --- dezelfde verklaring twee keer in één bundel -----------------------------
#
# Een raadsbundel noemt de jaarrekening vaak eerst in de aanbiedingsbrief en dan
# nog eens in de bijgevoegde verklaring zelf. Beide keren staat dezelfde zin, en
# beide vermeldingen komen hier terug. Wélke van de twee de handtekening draagt
# is namelijk niet aan deze functie: het venster van de eerste eindigt waar de
# tweede begint, dus vlák vóór het handtekeningblok, en welk venster dát is valt
# alleen te zien door er een kantoormatcher op los te laten. Dat doet de lader.
#
# Hier stond eerder een ontdubbeling die de vermelding met het langste venster
# hield. Die maatstaf is aantoonbaar fout — zie de toelichting in de adapter —
# en is vervangen door: alles teruggeven, de lader kiest.
HERHALING = (
    "Aanbiedingsbrief aan de raad\n"
    "Wij hebben de jaarrekening 2019 van de gemeente Testdorp gecontroleerd.\n"
    + "vulling " * 60
    + "Bijlage 3: controleverklaring van de onafhankelijke accountant\n"
    "Wij hebben de jaarrekening 2019 van de gemeente Testdorp gecontroleerd.\n"
    + "vulling " * 120
    + "Utrecht, 3 juni 2020 Deloitte Accountants B.V. was getekend\n"
)
uit = ori.verklaringen_uit(HERHALING)
controleer(
    "beide vermeldingen komen terug, zodat de lader kan kiezen",
    len(uit) == 2 and all(v["boekjaar"] == 2019 for v in uit),
    f"gevonden: {[(v['organisatie'], v['boekjaar']) for v in uit]}",
)
met_handtekening = [
    v for v in uit if "Deloitte" in HERHALING[v["venster"][0] : v["venster"][1]]
]
controleer(
    "precies één van de twee vensters bevat het handtekeningblok",
    len(met_handtekening) == 1,
    f"{len(met_handtekening)} van de {len(uit)} vensters bevatten 'Deloitte'",
)
controleer(
    "en dat is de laatste vermelding, niet de aanbiedingsbrief",
    met_handtekening and met_handtekening[0]["positie"] == max(v["positie"] for v in uit),
    "de handtekening hoort bij de vermelding die het dichtst bij de bijlage staat",
)

# --- een onmogelijk jaartal -------------------------------------------------
controleer(
    "een jaarrekening over 2077 bestaat niet",
    ori.verklaringen_uit(
        "Wij hebben de jaarrekening 2077 van Gemeente Nergenshuizen te Nergens "
        "gecontroleerd."
    )
    == [],
)

# --- de aanhef hoort niet bij de naam ----------------------------------------
uit = ori.verklaringen_uit(
    "Aan het algemeen bestuur van gemeenschappelijke regeling SSC DeSom "
    "Wij hebben de jaarrekening 2020 van het algemeen bestuur van "
    "gemeenschappelijke regeling SSC DeSom te Wognum gecontroleerd."
)
controleer(
    "'algemeen bestuur van' hoort niet in de organisatienaam",
    uit and uit[0]["organisatie"] == "Gemeenschappelijke regeling SSC DeSom",
    f"gevonden: {uit[0]['organisatie']!r}" if uit else "niets gevonden",
)

# --- dezelfde organisatie ondanks tekstverschillen ---------------------------
#
# De documenttekst komt uit een pdf en daar sneuvelen koppeltekens. Zonder
# gelijke sleutel splitst de geschiedenis van één veiligheidsregio zich over
# twee organisaties.
PAREN = [
    ("Veiligheidsregio Noord-Holland Noord", "Veiligheidsregio NoordHolland Noord"),
    ("Gemeenschappelijke Regeling Regio West-Brabant", "Gemeenschappelijke Regeling Regio WestBrabant"),
    ("Gemeenschappelijke Regeling SED organisatie", "Gemeenschappelijke Regeling SED-organisatie"),
    ("gemeente Enkhuizen", "Gemeente Enkhuizen"),
]
for links, rechts in PAREN:
    controleer(
        f"zelfde sleutel: {links!r} en {rechts!r}",
        ori.matchsleutel(links) == ori.matchsleutel(rechts),
        f"{ori.matchsleutel(links)!r} != {ori.matchsleutel(rechts)!r}",
    )

# Twee échte verschillende organisaties mogen juist níét samenvallen.
controleer(
    "verschillende organisaties houden verschillende sleutels",
    ori.matchsleutel("Veiligheidsregio Utrecht")
    != ori.matchsleutel("Veiligheidsregio Flevoland"),
)

# --- de plaats hoort niet bij de identiteit ----------------------------------
#
# Gemeten over de volle oogst (8-8-2026, 1.970 namen): de standaardzin schrijft
# de vestigingsplaats soms wél en soms niet achter de naam, en dan staat één
# regeling twee keer in de database. Deze vier schrijfwijzen komen letterlijk uit
# de bron. Samen met de verdubbelingen hieronder voegden ze 21 namen samen tot
# 14 organisaties — zonder één verkeerde samenvoeging.
for links, rechts in [
    ("Gemeenschappelijke Regeling Cocensus",
     "Gemeenschappelijke Regeling Cocensus, te Hoofddorp"),
    ("Recreatieschap Hitland",
     "Recreatieschap Hitland te Nieuwerkerk aan den IJssel"),
    ("Stichting Openbaar Primair Onderwijs Wolderwijs",
     "Stichting openbaar primair onderwijs Wolderwijs te gemeente De Wolden"),
    ("Stichting Openbaar Basisonderwijs West-Brabant",
     "Stichting Openbaar Basisonderwijs West-Brabant, gevestigd te Roosendaal"),
    # En zonder spatie ervóór: de staart plakt in de pdf-tekst soms direct
    # achter de afkorting tussen haakjes. Allebei letterlijk uit de database
    # (organisaties 23962 en 25601), waar ze náást de versie zonder plaatsnaam
    # stonden.
    ("Gemeenschappelijke regeling Openbaar Lichaam Crematoria Twente (OLCT)",
     "Gemeenschappelijke regeling Openbaar Lichaam Crematoria Twente (OLCT)te Enschede"),
    ("Waterschap Amstel, Gooi en Vecht (AGV)",
     "Waterschap Amstel, Gooi en Vecht (AGV)te Amsterdam"),
]:
    controleer(
        f"plaats achteraan telt niet mee: {rechts[:44]!r}",
        ori.matchsleutel(links) == ori.matchsleutel(rechts),
        f"{ori.matchsleutel(links)!r} != {ori.matchsleutel(rechts)!r}",
    )

# Een per ongeluk verdubbeld eerste woord — komt uit de aanhef die aan de naam
# vastplakt ("Aan het bestuur van Stichting …" gevolgd door "Stichting …").
for links, rechts in [
    ("Gemeente De Ronde Venen", "Gemeente Gemeente De Ronde Venen"),
    ("Stichting Openbaar Onderwijs Rijn- en Heuvelland",
     "Stichting Stichting Openbaar Onderwijs Rijn- en Heuvelland"),
]:
    controleer(
        f"verdubbeld eerste woord: {rechts[:44]!r}",
        ori.matchsleutel(links) == ori.matchsleutel(rechts),
        f"{ori.matchsleutel(links)!r} != {ori.matchsleutel(rechts)!r}",
    )

# --- en wat de sleutel absoluut niet mag doen --------------------------------
#
# De verleiding is om ook "gemeente", "provincie" en "gemeenschappelijke
# regeling" weg te strepen — het lijkt dezelfde soort opschoning. Dat is het
# niet: die woorden zíjn de identiteit. Zonder die rem vielen bij de meting
# Gemeente Utrecht en Provincie Utrecht samen, en Gemeente Groningen en
# Provincie Groningen ook. Vier echte, verschillende gecontroleerde partijen.
#
# Hetzelfde geldt voor één letter verschil: dat is precies wat EMCO-groep van
# Felua-groep onderscheidt. Daarom blijft tekstschade uit de pdf
# ("Gemeenschappeiijke", "I]ssel", "Gelderand") een aparte organisatie — liever
# een gesplitste geschiedenis dan twee samengevoegde regelingen.
for omschrijving, links, rechts in [
    ("gemeente is geen provincie", "Gemeente Utrecht", "Provincie Utrecht"),
    ("gemeente is geen provincie", "Gemeente Groningen", "Provincie Groningen"),
    ("één letter scheidt twee regelingen",
     "Gemeenschappelijke Regeling EMCO-groep",
     "Gemeenschappelijke Regeling Felua-groep"),
    ("tekstschade wordt niet stilletjes samengevoegd",
     "Gemeenschappelijke Regeling Senzer",
     "Gemeenschappeiijke Regeling Senzer"),
]:
    controleer(
        f"{omschrijving}: {links!r} != {rechts!r}",
        ori.matchsleutel(links) != ori.matchsleutel(rechts),
        f"beide -> {ori.matchsleutel(links)!r}",
    )

# En de plaatsregel mag geen naam aanvreten die toevallig zo eindigt.
controleer(
    "'Regio Twente' verliest zijn naam niet",
    ori.matchsleutel("Regio Twente") == "regiotwente"
    and ori.matchsleutel("Waterschap Aa en Maas") == "waterschapaaenmaas",
    f"{ori.matchsleutel('Regio Twente')!r} / "
    f"{ori.matchsleutel('Waterschap Aa en Maas')!r}",
)

# --- de tekst kan als lijst binnenkomen --------------------------------------
controleer(
    "tekst per pagina wordt samengevoegd",
    ori._plat(["eerste", "tweede"]) == "eerste\ntweede" and ori._plat(None) == "",
)

# --- de naam mag niet over een kop heen lopen --------------------------------
#
# Den Haag zet "Ons oordeel" als kopje boven de verklaring, en de regel ervóór
# noemt de jaarrekening al. De naam liep dan door tot voorbij dat kopje en er
# ontstond een tweede, verzonnen "organisatie" naast de echte — mét accountant.
# Erger nog: die opgerekte match at de goede zin op, dus Den Haag raakte het jaar
# helemaal kwijt. Op 4.000 documenten (7-8-2026) gebeurde dat 26 keer.
DEN_HAAG = (
    "JAARREKENING 2016 VAN DE GEMEENTE DEN HAAG\n"
    "Controleverklaring van de onafhankelijke accountant\n"
    "Ons oordeel\n"
    "Wij hebben de jaarrekening 2016 van de gemeente Den Haag gecontroleerd.\n"
)
uit = ori.verklaringen_uit(DEN_HAAG)
controleer(
    "de naam stopt bij de kop, en de échte zin wordt alsnog gevonden",
    len(uit) == 1 and uit[0]["organisatie"] == "Gemeente Den Haag"
    and uit[0]["boekjaar"] == 2016,
    f"gevonden: {[(v['organisatie'], v['boekjaar']) for v in uit]}",
)

# --- een tussenzin over de reikwijdte ----------------------------------------
#
# Deze drie schrijfwijzen staan letterlijk in de bron en vielen allemaal weg
# omdat er iets tussen het jaartal en "van" stond.
for omschrijving, zin, verwacht in [
    (
        "(inclusief erratum)",
        "Wij hebben de jaarrekening 2020 (inclusief erratum) van de gemeente "
        "Renkum gecontroleerd.",
        "Gemeente Renkum",
    ),
    (
        "inclusief de SISA bijlage",
        "Wij hebben de jaarrekening 2016 inclusief de SISA bijlage (bijlage 7.1) "
        "van de Gemeenschappelijke Regeling Veiligheidsregio Zeeland gecontroleerd.",
        "Gemeenschappelijke Regeling Veiligheidsregio Zeeland",
    ),
    (
        "en de daarbij behorende bijlagen",
        "Wij hebben de jaarrekening 2014 en de daarbij behorende bijlagen van de "
        "gemeente Eindhoven gecontroleerd.",
        "Gemeente Eindhoven",
    ),
]:
    uit = ori.verklaringen_uit(zin)
    controleer(
        f"tussenzin: {omschrijving}",
        len(uit) == 1 and uit[0]["organisatie"] == verwacht,
        f"gevonden: {[v['organisatie'] for v in uit]}",
    )

# --- en wat de tussenzin níét mag doen ---------------------------------------
#
# De keerzijde, en die is scherper dan hij lijkt: Nederlandse organisatienamen
# zitten vol "van". Met een vrij gat tussen jaartal en "van" sloeg de zoeker het
# échte "van" over en haakte hij aan het "van" binnenín de naam. Dat halveerde
# 113 namen op 4.000 documenten: "Vereniging van Nederlandse Gemeenten" werd
# "Nederlandse Gemeenten" en "Regio Hart van Brabant" werd "Brabant". Een naam
# die stilletjes de helft mist is erger dan een naam die ontbreekt.
for omschrijving, zin, verwacht in [
    (
        "een naam mét 'van' erin blijft heel",
        "Wij hebben de jaarrekening 2021 van de Vereniging van Nederlandse "
        "Gemeenten gecontroleerd.",
        "Vereniging van Nederlandse Gemeenten",
    ),
    (
        "ook als de naam midden in een 'van' zit",
        "Wij hebben de jaarrekening 2022 van de Gemeenschappelijke Regeling Regio "
        "Hart van Brabant gecontroleerd.",
        "Gemeenschappelijke Regeling Regio Hart van Brabant",
    ),
]:
    uit = ori.verklaringen_uit(zin)
    controleer(
        omschrijving,
        len(uit) == 1 and uit[0]["organisatie"] == verwacht,
        f"gevonden: {[v['organisatie'] for v in uit]}",
    )

# Een ándere zin over dezelfde jaarrekening is geen ondertekende verklaring. Met
# een vrij gat leverden deze twee "het bestuur" en "GR-bestuur" op als
# organisatie — allebei bestaan niet.
for omschrijving, zin in [
    ("opgesteld onder verantwoordelijkheid van het bestuur",
     "De jaarrekening 2019 is opgesteld onder verantwoordelijkheid van het "
     "bestuur en wordt door ons gecontroleerd."),
    ("in opdracht van het GR-bestuur",
     "De jaarrekening 2020 wordt net als in voorgaande jaren in opdracht van het "
     "GR-bestuur gecontroleerd."),
]:
    uit = ori.verklaringen_uit(zin)
    controleer(f"geen verklaring: {omschrijving}", uit == [], f"gevonden: {uit}")

# --- staarten achter de naam -------------------------------------------------
#
# De zin hangt een afkorting of de opsteller achter de naam. Zonder schoonmaak
# matcht de naam niet met de organisatie die er al staat en ontstaat er een
# tweede gemeente naast de eerste. De vormen zijn die uit de bron (5-10-2026);
# de namen zijn verzonnen.
for omschrijving, zin, naam, plaats in [
    ("(hierna te noemen …)",
     "Wij hebben de jaarrekening 2018 van de gemeente Testdam (hierna te noemen "
     "‘gemeente’) gecontroleerd.", "Gemeente Testdam", ""),
    ("aanhalingsteken-alias tussen haakjes",
     "Wij hebben de jaarrekening 2018 van Gemeente Testdam (‘de gemeente’) "
     "gecontroleerd.", "Gemeente Testdam", ""),
    ("(verder genoemd: …), met plaats ervóór",
     "Wij hebben de jaarrekening 2018 van de Gemeenschappelijke Regeling GGD "
     "Testland te Testdam (verder genoemd: GGD Testland) gecontroleerd.",
     "Gemeenschappelijke Regeling GGD Testland", "Testdam"),
    ("opgesteld onder verantwoordelijkheid van het college",
     "Wij hebben de in dit document opgenomen jaarrekening 2011 van de gemeente "
     "Testdam, opgesteld onder verantwoordelijkheid van het college van "
     "burgemeester en wethouders, gecontroleerd.", "Gemeente Testdam", ""),
    ("'opgesteld ender' uit de tekstherkenning",
     "Wij hebben de jaarrekening 2019 van GRTD, opgesteld ender verantwoordelijkheid "
     "van het dagelijks bestuur, gecontroleerd.", "GRTD", ""),
    ("aanspreekvorm 'Uw' en een staart",
     "Wij hebben de jaarrekening 2017 van Uw gemeente Testdam (hierna: Testdam) "
     "gecontroleerd.", "Gemeente Testdam", ""),
    ("verdubbelde soortnaam",
     "Wij hebben de jaarrekening 2017 van Gemeente Gemeente Testdam gecontroleerd.",
     "Gemeente Testdam", ""),
    ("plaats achteraan na het afknippen",
     "Wij hebben de jaarrekening 2019 van Testbedrijf B.V. te Testdam ('de "
     "vennootschap') gecontroleerd.", "Testbedrijf B.V.", "Testdam"),
    ("', gevestigd te' hoort niet bij de naam",
     "Wij hebben de jaarrekening 2018 van Stichting Openbaar Basisonderwijs "
     "Testland, gevestigd te Testdam ('de stichting') gecontroleerd.",
     "Stichting Openbaar Basisonderwijs Testland", "Testdam"),
    ("gemeente waarvan 'te' uit de zin viel",
     "Wij hebben de jaarrekening 2019 van de gemeente Testdam Testdam gecontroleerd.",
     "Gemeente Testdam", "Testdam"),
    ("'in liquidatie' tussen aanhalingstekens",
     "Wij hebben de jaarrekening 2018 van Stadsregio Testland \"in liquidatie\" "
     "gecontroleerd.", "Stadsregio Testland", ""),
]:
    uit = ori.verklaringen_uit(zin)
    controleer(
        f"staart weg: {omschrijving}",
        len(uit) == 1 and uit[0]["organisatie"] == naam and uit[0]["plaats"] == plaats,
        f"gevonden: {[(v['organisatie'], v['plaats']) for v in uit]}",
    )

# Een herhaald woord op zich is geen plaats: er bestaat een organisatie die zo
# heet (KvK). Alleen "Gemeente X X" wordt gesplitst.
uit = ori.verklaringen_uit("Wij hebben de jaarrekening 2019 van Stichting Klop Klop gecontroleerd.")
controleer(
    "'Stichting Klop Klop' blijft heel",
    len(uit) == 1 and uit[0]["organisatie"] == "Stichting Klop Klop" and uit[0]["plaats"] == "",
    f"gevonden: {[(v['organisatie'], v['plaats']) for v in uit]}",
)

# Na het afknippen blijft soms alleen de soort over, of een stuk zin. Dat is
# geen organisatie.
for omschrijving, zin in [
    ("alleen 'Gemeente'",
     "Wij hebben de jaarrekening 2018 van de gemeente (hierna te noemen ‘gemeente’) "
     "gecontroleerd."),
    ("alleen 'Gemeenschappelijke regeling'",
     "Wij hebben de jaarrekening 2013 van Uw gemeenschappelijke regeling, opgesteld "
     "onder verantwoordelijkheid van het bestuur, gecontroleerd."),
    ("een doorgelopen zin met 'afgerond'",
     "Wij hebben de controle van de jaarrekening 2023 van de gemeente Testdam "
     "afgerond. Bijgevoegd treft u het verslag aan over wat is gecontroleerd."),
    ("'is door ons'",
     "Wij hebben de jaarrekening 2018 van Kredietbank Testland is door ons gecontroleerd."),
]:
    uit = ori.verklaringen_uit(zin)
    controleer(f"geen organisatie: {omschrijving}", uit == [], f"gevonden: {uit}")

# De database bevat nog namen van vóór de schoonmaak. Op de strenge sleutel
# moeten oud en nieuw samenvallen — en een afkorting zónder aanhalingstekens
# hoort bij de statutaire naam en blijft dus onderscheidend.
for links, rechts in [
    ("Gemeente Testdam", "Gemeente Testdam (‘de gemeente’)"),
    ("Gemeente Testdam", "Gemeente Testdam (hierna te noemen 'gemeente')"),
    ("Gemeenschappelijke Regeling Testland",
     "Gemeenschappelijke Regeling Testland (hierna: Testland)"),
    ("Gemeente Testdam", "Gemeente Testdam, opgesteld onder verantwoordelijkheid van het college"),
]:
    controleer(
        f"zelfde sleutel na schoonmaak: {rechts[:48]!r}",
        ori.matchsleutel(links) == ori.matchsleutel(rechts),
        f"{ori.matchsleutel(links)!r} != {ori.matchsleutel(rechts)!r}",
    )
controleer(
    "een afkorting tussen haakjes blijft onderscheidend",
    ori.matchsleutel("Waterschap Testland (WTL)") != ori.matchsleutel("Waterschap Testland"),
)

# "Uw"/"Onze" is alleen een aanspreekvorm vóór een soortnaam. Daarbuiten is
# het het begin van een echte naam (zulke KvK-organisaties staan in de
# database), en dan mag een lezing zonder dat woord er niet op uitkomen.
controleer(
    "'Uw gemeente …' is de aanspreekvorm van een accountantsverslag",
    ori.matchsleutel("Uw gemeente Testdam") == ori.matchsleutel("Gemeente Testdam")
    and ori.matchsleutel("Uw gemeenschappelijke regeling Testgroep")
    == ori.matchsleutel("Gemeenschappelijke regeling Testgroep"),
)
controleer(
    "'Onze Testartsen B.V.' en 'UW Testmaatschappij B.V.' houden hun eerste woord",
    ori.matchsleutel("Onze Testartsen B.V.") == "onzetestartsenbv"
    and ori.matchsleutel("UW Testmaatschappij B.V.") != ori.matchsleutel("Testmaatschappij B.V."),
)
for zin in (
    "Wij hebben de jaarrekening 2019 van uw onderneming gecontroleerd.",
    "Wij hebben de jaarrekening 2014 van uw milieudienst, opgesteld onder "
    "verantwoordelijkheid van het bestuur, gecontroleerd.",
):
    controleer(
        f"alleen een soortnaam over: {zin[33:60]!r}",
        ori.verklaringen_uit(zin) == [],
        f"gevonden: {ori.verklaringen_uit(zin)}",
    )

# --- het jaar komt uit de kalender ---------------------------------------------
import datetime  # noqa: E402

dit_jaar = datetime.date.today().year
controleer("HUIDIG_JAAR is het lopende jaar", ori.HUIDIG_JAAR == dit_jaar)
controleer(
    "een jaarrekening over het lopende jaar telt, over volgend jaar niet",
    len(ori.verklaringen_uit(f"Wij hebben de jaarrekening {dit_jaar} van Gemeente "
                             "Testdam gecontroleerd.")) == 1
    and ori.verklaringen_uit(f"Wij hebben de jaarrekening {dit_jaar + 1} van Gemeente "
                             "Testdam gecontroleerd.") == [],
)

# --- de oordeelzin vóór de standaardzin --------------------------------------
#
# Het sjabloon van na 2019 zet het oordeel vóór "Wij hebben de jaarrekening …
# gecontroleerd". Het oordeelvenster begint daarom bij de kop van déze
# verklaring, en niet bij die van de buurman.
SJABLOON = (
    "Controleverklaring van de onafhankelijke accountant\nOns oordeel\n"
    "Naar ons oordeel geeft de jaarrekening een getrouw beeld. "
    + "uitleg " * 200
    + "Wij hebben de jaarrekening 2020 van de gemeente Testdam gecontroleerd.\n"
)
uit = ori.verklaringen_uit(SJABLOON)
controleer(
    "het oordeelvenster begint bij de kop, ook ver vóór de standaardzin",
    len(uit) == 1 and uit[0]["oordeelvenster"][0] == 0 and uit[0]["venster"][0] > 0,
    f"gevonden: {[(v['venster'], v['oordeelvenster']) for v in uit]}",
)
TWEE = (
    "Controleverklaring van de onafhankelijke accountant\n"
    "Wij hebben de jaarrekening 2020 van gemeenschappelijke regeling Testpark "
    "gecontroleerd.\n" + "vulling " * 100
    + "Wij hebben de jaarrekening 2020 van gemeenschappelijke regeling Testhaven "
    "gecontroleerd.\n"
)
uit = ori.verklaringen_uit(TWEE)
controleer(
    "zonder eigen kop leent de tweede verklaring de kop van de eerste niet",
    len(uit) == 2 and uit[1]["oordeelvenster"][0] == uit[1]["venster"][0],
    f"gevonden: {[(v['organisatie'], v['oordeelvenster']) for v in uit]}",
)

# --- twee zoekvragen, één definitie ------------------------------------------
gevraagd: list[dict] = []


def nep_haal(lichaam: dict) -> dict:
    gevraagd.append(lichaam)
    if lichaam.get("size") == 0:
        return {"hits": {"total": {"value": 7, "relation": "eq"}}}
    begin = int((lichaam.get("search_after") or [0])[0])
    rest = max(0, 7 - begin)
    return {"hits": {"hits": [
        {"_source": {"name": f"doc {begin + i}"}, "sort": [begin + i + 1]}
        for i in range(min(lichaam["size"], rest))
    ]}}


controleer(
    "het totaal gaat over dezelfde zoekvraag als de documenten",
    ori.totaal_documenten(haal=nep_haal, zoekvraag="accountantsverslag") == 7
    and gevraagd[-1]["query"] == ori.ZOEKVRAGEN["accountantsverslag"],
)
gevraagd.clear()
docs = list(ori.documenten(per_pagina=3, maximum=5, haal=nep_haal, zoekvraag="accountantsverslag"))
controleer(
    "documenten() respecteert het maximum en bladert met search_after",
    len(docs) == 5 and gevraagd[1].get("search_after") == [3]
    and all(v["query"] == ori.ZOEKVRAGEN["accountantsverslag"] for v in gevraagd),
    f"{len(docs)} documenten, verzoeken: {[v.get('search_after') for v in gevraagd]}",
)
controleer(
    "de tweede zoekvraag sluit de eerste uit, zodat totalen optellen",
    {"match_phrase": {"text": ori.ZOEKZIN}}
    in ori.ZOEKVRAGEN["accountantsverslag"]["bool"]["must_not"],
)

# Het documentnummer gaat mee, de titel niet: een titel noemt soms een
# wethouder, en het rapport en de review-queue houden alleen het nummer.
gevraagd.clear()


def nep_haal_met_id(lichaam: dict) -> dict:
    if lichaam.get("search_after"):
        return {"hits": {"hits": []}}
    return {"hits": {"hits": [{
        "_id": "4242",
        "_source": {"name": "Mededeling wethouder Testpersoon", "original_url": "https://voorbeeld.invalid/4242",
                    "text": "Wij hebben de jaarrekening 2019 van Gemeente Testdam gecontroleerd."},
        "sort": [1],
    }]}}


document = next(ori.documenten(haal=nep_haal_met_id))
uit = ori.verklaringen_uit(document["text"], document)
controleer(
    "een vermelding draagt het documentnummer en niet de titel",
    document["_id"] == "4242" and len(uit) == 1 and uit[0]["document_id"] == "4242"
    and "documentnaam" not in uit[0]
    and not any("wethouder" in str(waarde).lower() for waarde in uit[0].values()),
    f"gevonden: {uit}",
)

# --- de lader: wat er met een bestaande rij gebeurt ----------------------------
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent / "extractie"))
import subprocess  # noqa: E402

import laad_raadsinformatie as lader  # noqa: E402

# Het script moet als script ook echt iets doen. Bij het herschrijven van main()
# viel de regel `if __name__ == "__main__"` een keer weg; de lader startte dan,
# importeerde alles en stopte zonder één regel uitvoer — een groene run die
# niets laadt.
hulp = subprocess.run(
    [sys.executable, lader.__file__, "--help"], capture_output=True, text=True
)
controleer(
    "de lader start als script (--help toont de opties)",
    hulp.returncode == 0 and "--droogloop" in hulp.stdout and "--vervang" in hulp.stdout,
    hulp.stdout[-300:] + hulp.stderr[-300:],
)

EIGEN = {11, 12}
NIEUW_BRON = 12
actie, rij = lader.schrijfactie(None, EIGEN, NIEUW_BRON, 5, {"oordeel": "goedkeurend", "tekenend_accountant": None})
controleer(
    "nieuw: invoegen, zonder lege velden",
    actie == "nieuw" and rij == {"kantoor_id": 5, "bron_id": 12, "type_opdracht": "wettelijke_controle", "oordeel": "goedkeurend"},
    f"{actie} {rij}",
)
digimv_rij = {"id": 401, "bron_id": 3, "kantoor_id": 7, "oordeel": "goedkeurend"}
actie, rij = lader.schrijfactie(digimv_rij, EIGEN, NIEUW_BRON, 5, {"oordeel": "beperking"})
controleer(
    "een rij uit een andere bron blijft van die bron: geen vindplaats, geen kantoor, geen oordeel",
    actie == "andere bron" and rij == {},
    f"{actie} {rij}",
)

# Een eigen rij volgt de lezing van nu, ook waar die een veld leeg laat: een
# verbeterde leesregel moet een verkeerd gelezen oordeel kunnen terugnemen.
eigen_rij = {
    "id": 402, "bron_id": 11, "kantoor_id": 5, "oordeel": "oordeelonthouding",
    "continuiteitsonzekerheid": False, "tekenend_accountant": None,
}
actie, rij = lader.schrijfactie(
    eigen_rij, EIGEN, NIEUW_BRON, 5,
    {"oordeel": "goedkeurend", "tekenend_accountant": "A.B. Voorbeeld RA", "continuiteitsonzekerheid": False},
)
controleer(
    "eigen rij: nieuwe vindplaats, en een ander oordeel vervangt het oude",
    actie == "bijwerken"
    and rij == {"bron_id": 12, "kantoor_id": 5, "oordeel": "goedkeurend",
                "tekenend_accountant": "A.B. Voorbeeld RA"},
    f"{actie} {rij}",
)
actie, rij = lader.schrijfactie(eigen_rij, EIGEN, NIEUW_BRON, 5, {})
controleer(
    "eigen rij: wat de lezing van nu niet meer ondersteunt, gaat eraf",
    actie == "bijwerken"
    and rij == {"bron_id": 12, "kantoor_id": 5, "oordeel": None, "continuiteitsonzekerheid": None},
    f"{actie} {rij}",
)
actie, rij = lader.schrijfactie(eigen_rij, EIGEN, NIEUW_BRON, 9, {})
controleer(
    "eigen rij met een ander kantoor: oordeel van de oude lezing gaat mee weg",
    actie == "bijwerken" and rij["kantoor_id"] == 9 and rij.get("oordeel", "x") is None,
    f"{actie} {rij}",
)
actie, rij = lader.schrijfactie({"bron_id": 12, "kantoor_id": 5}, EIGEN, NIEUW_BRON, 9, {})
controleer(
    "twee kantoren voor hetzelfde boekjaar in één run: de eerste lezing blijft",
    actie == "tegenspraak" and rij == {},
)
deze_run = {"bron_id": 12, "kantoor_id": 5, "oordeel": "goedkeurend", "tekenend_accountant": None}
actie, rij = lader.schrijfactie(
    deze_run, EIGEN, NIEUW_BRON, 5, {"oordeel": None, "tekenend_accountant": "C.D. Proef RA"}
)
controleer(
    "een tweede lezing in dezelfde run vult alleen aan: de eerste blijft staan",
    actie == "bijwerken"
    and rij == {"bron_id": 12, "kantoor_id": 5, "tekenend_accountant": "C.D. Proef RA"},
    f"{actie} {rij}",
)

# De zes DigiMV-rijen onder een raadsinformatie-bron_id: het bron_id zegt
# "eigen", maar het oordeel is van DigiMV. Geen enkel veld gaat eraf of erbij,
# en --vervang laat ze staan.
beschermd_id = min(lader.DIGIMV_ONDER_RAADSBRON)
digimv_onder_raadsbron = {
    "id": beschermd_id, "bron_id": 11, "kantoor_id": 5, "oordeel": "goedkeurend",
    "continuiteitsonzekerheid": False,
}
for lezing in ({}, {"oordeel": "beperking", "tekenend_accountant": "A.B. Voorbeeld RA"}):
    actie, rij = lader.schrijfactie(digimv_onder_raadsbron, EIGEN, NIEUW_BRON, 5, lezing)
    controleer(
        f"DigiMV-rij onder een raadsinformatie-bron blijft zoals hij is (lezing {sorted(lezing)})",
        actie == "beschermd" and rij == {},
        f"{actie} {rij}",
    )
controleer(
    "precies de zes gemeten DigiMV-rijen zijn beschermd",
    lader.DIGIMV_ONDER_RAADSBRON == {7223, 9053, 10318, 13418, 20823, 57968},
)
controleer(
    "--vervang wist alles onder het oude bron_id, behalve die zes",
    lader.te_wissen(11) == "bron_id=eq.11&id=not.in.(7223,9053,10318,13418,20823,57968)",
    lader.te_wissen(11),
)

# --- vervang: de ondergrens geldt per zoekvraag ------------------------------
#
# documenten() stopt bij de eerste lege pagina, en een halve doorloop ziet er
# dan uit als een hele. Hier geeft de zoek-API halverwege de tweede zoekvraag
# een lege pagina terug: de eerste is compleet (1.000), van de tweede komen er
# 10 van de 40 binnen. Over de som (1.010 van 1.040, 97%) haalt dat de 95%;
# per zoekvraag niet, en dan mag vervang niets wissen.
TOTAAL = {"controleverklaring": 1000, "accountantsverslag": 40}


def haperende_haal(lichaam: dict) -> dict:
    zoekvraag = next(z for z, v in ori.ZOEKVRAGEN.items() if v == lichaam["query"])
    if lichaam.get("size") == 0:
        return {"hits": {"total": {"value": TOTAAL[zoekvraag], "relation": "eq"}}}
    begin = int((lichaam.get("search_after") or [0])[0])
    if zoekvraag == "accountantsverslag" and begin >= 10:
        return {"hits": {"hits": []}}  # de hapering
    rest = max(0, TOTAAL[zoekvraag] - begin)
    return {"hits": {"hits": [
        {"_id": str(begin + i), "_source": {}, "sort": [begin + i + 1]}
        for i in range(min(lichaam["size"], rest))
    ]}}


gelezen: dict = {}
aantal = sum(1 for _ in lader.lees(40_000, 10, 0.0, gelezen, haal=haperende_haal))
totalen = {z: ori.totaal_documenten(haal=haperende_haal, zoekvraag=z) for z in ori.ZOEKVRAGEN}
reden = lader.reden_om_niet_te_wissen(gelezen, totalen, 40_000)
controleer(
    "een haperende tweede zoekvraag: niet wissen, ook al haalt de som 95%",
    aantal == 1010 and gelezen == {"controleverklaring": 1000, "accountantsverslag": 10}
    and sum(gelezen.values()) >= 0.95 * sum(totalen.values())
    and reden is not None and "accountantsverslag" in reden,
    f"{aantal} gelezen {gelezen}, reden {reden!r}",
)
controleer(
    "elke zoekvraag volledig: wissen mag",
    lader.reden_om_niet_te_wissen(
        {"controleverklaring": 1000, "accountantsverslag": 39}, totalen, 40_000
    ) is None,
)
controleer(
    "een onbekend totaal of een afkapping op --maximum: niet wissen",
    lader.reden_om_niet_te_wissen(
        {"controleverklaring": 1000, "accountantsverslag": 40},
        {"controleverklaring": 1000, "accountantsverslag": None}, 40_000,
    ) is not None
    and lader.reden_om_niet_te_wissen(
        {"controleverklaring": 1000, "accountantsverslag": 40}, totalen, 1040
    ) is not None,
)
gelezen = {}
aantal = sum(1 for _ in lader.lees(1005, 10, 0.0, gelezen, haal=haperende_haal))
controleer(
    "lees() houdt het maximum aan over beide zoekvragen samen",
    aantal == 1005 and gelezen == {"controleverklaring": 1000, "accountantsverslag": 5},
    f"{aantal} {gelezen}",
)

# Welke organisatie bij een naam hoort.
controleer(
    "dubbele rijen zonder KvK-nummer: steeds de oudste",
    lader.kies_kandidaat([{"id": 30}, {"id": 20}])[0]["id"] == 20,
)
controleer(
    "een rij mét KvK-nummer gaat voor op een rij zonder",
    lader.kies_kandidaat([{"id": 20}, {"id": 30, "kvk_nummer": "01234567"}])[0]["id"] == 30,
)
gekozen, reden = lader.kies_kandidaat(
    [{"id": 20, "kvk_nummer": "01234567"}, {"id": 30, "kvk_nummer": "07654321"}]
)
controleer(
    "twee verschillende KvK-nummers: niet kiezen",
    gekozen is None and "KvK" in (reden or ""),
    f"{gekozen} {reden}",
)
# De strenge sleutel laat "te <plaats>" weg. Twee organisaties zonder KvK-nummer
# die alleen in hun plaats verschillen, vallen daar samen — of dat er één is,
# zegt de naam niet. Niet de oudste nemen maar naar de review-queue.
gekozen, reden = lader.kies_kandidaat(
    [{"id": 20, "naam": "Stichting Testwerk te Testdam"},
     {"id": 30, "naam": "Stichting Testwerk", "gemeente": "Proefstad"}]
)
controleer(
    "twee kandidaten in verschillende plaatsen: niet kiezen",
    gekozen is None and "plaats" in (reden or ""),
    f"{gekozen} {reden}",
)
gekozen, reden = lader.kies_kandidaat(
    [{"id": 20, "naam": "Stichting Testwerk te Testdam ('de stichting')"},
     {"id": 30, "naam": "Stichting Testwerk", "gemeente": "TESTDAM"},
     {"id": 40, "naam": "Stichting Testwerk"}]
)
controleer(
    "dezelfde plaats (ook in KAPITALEN) of geen plaats: dubbele rijen, de oudste",
    gekozen is not None and gekozen["id"] == 20 and reden is None,
    f"{gekozen} {reden}",
)
gekozen, reden = lader.kies_kandidaat(
    [{"id": 20, "naam": "Stichting Testzorg", "gemeente": "'s-Testbosch"},
     {"id": 30, "naam": "Stichting Testzorg", "gemeente": "S-TESTBOSCH", "kvk_nummer": "01234567"}]
)
controleer(
    "een plaats met en zonder apostrof is dezelfde plaats",
    gekozen is not None and gekozen["id"] == 30 and reden is None,
    f"{gekozen} {reden}",
)
controleer(
    "de plaats achter een naam, ook achter een staart",
    ori.plaats_achteraan("Stichting Testwerk, gevestigd te Testdam ('de stichting')") == "Testdam"
    and ori.plaats_achteraan("Regio Testland") is None,
)
controleer(
    "Gemeente Bergen zonder (L) of (NH) is een homoniem, de andere niet",
    lader.homoniem("Gemeente Bergen") and lader.homoniem("Gemeente Bergen te Bergen")
    and not lader.homoniem("Gemeente Bergen (L)")
    and not lader.homoniem("Gemeente Bergen op Zoom"),
)
controleer(
    "een gemeente buiten sector overheid wacht; een N.V. in zijn eigen sector niet",
    lader.sector_wacht({"naam": "Gemeente Testdam", "sector": "overig bedrijfsleven"})
    and not lader.sector_wacht({"naam": "Gemeente Testdam", "sector": "overheid"})
    and not lader.sector_wacht({"naam": "Testwater N.V.", "sector": "industrie en bouw"}),
)
# Wie wacht, staat in het log: per sector de ids, zodat een gemeente onder zorg
# of vastgoed niet achter een teller verdwijnt. Geen namen in die regels.
import collections  # noqa: E402

OVERZICHT = lader.wacht_overzicht(collections.Counter({
    (31, "zorg"): 2, (12, "overig bedrijfsleven"): 1, (7, "zorg"): 1, (99, None): 1,
}))
controleer(
    "het wachtoverzicht groepeert per sector, met ids en aantallen",
    OVERZICHT == [
        "  (geen sector): 1 controles bij 1 organisaties, organisatie_id 99",
        "  overig bedrijfsleven: 1 controles bij 1 organisaties, organisatie_id 12",
        "  zorg: 3 controles bij 2 organisaties, organisatie_id 7, 31",
    ],
    f"{OVERZICHT}",
)
controleer(
    "zonder wachtenden geen regels",
    lader.wacht_overzicht(collections.Counter()) == [],
)

# De plaats: alleen als alle lezingen het over één registerplaats eens zijn.
BEKEND = {"testdam": "Testdam", "'s-testbosch": "'s-Testbosch"}
controleer(
    "plaats uit het register, ook bij KAPITALEN",
    lader.enige_plaats({"TESTDAM"}, BEKEND) == "Testdam",
)
controleer(
    "tekstschade naast de echte plaats telt niet mee",
    lader.enige_plaats({"Testdam", "Iestdam"}, BEKEND) == "Testdam",
)
controleer(
    "twee echte plaatsen: niet kiezen",
    lader.enige_plaats({"Testdam", "'s-Testbosch"}, BEKEND) is None
    and lader.enige_plaats({"Iestdam"}, BEKEND) is None,
)
# Het register schrijft een plaats soms in KAPITALEN en soms gewoon. De eerste
# die voorbijkwam won, en dan stond er "PROEFSTAD" op de plaatspagina naast de
# organisaties met "Proefstad".
REGISTER = lader.bekende_plaatsen([
    {"kvk_nummer": "01234567", "gemeente": "PROEFSTAD"},
    {"kvk_nummer": "01234568", "gemeente": "Proefstad"},
    {"kvk_nummer": "01234569", "gemeente": "Proefstad"},
    {"kvk_nummer": None, "gemeente": "Nergensdorp"},
    {"kvk_nummer": "01234570", "gemeente": "TESTHOVEN"},
])
controleer(
    "het register levert de gewone schrijfwijze, ook als KAPITALEN eerst kwamen",
    REGISTER == {"proefstad": "Proefstad", "testhoven": "TESTHOVEN"},
    f"{REGISTER}",
)
controleer(
    "plaats in KAPITALEN in de verklaring: de gewone schrijfwijze uit het register",
    lader.enige_plaats({"PROEFSTAD"}, REGISTER) == "Proefstad",
)
controleer(
    "het register kent alleen KAPITALEN: de schrijfwijze uit de verklaring",
    lader.enige_plaats({"Testhoven"}, REGISTER) == "Testhoven",
)
controleer(
    "allebei KAPITALEN: geen plaats, want die is voor de plaatspagina een andere",
    lader.enige_plaats({"TESTHOVEN"}, REGISTER) is None,
)
controleer(
    "een plaats zonder KvK-organisatie is niet bekend",
    lader.enige_plaats({"Nergensdorp"}, REGISTER) is None,
)

# Oordeel en naam: alleen uit een getekende verklaring van hetzelfde kantoor.
from kantoor_match import bouw_index, laad_aliassen, laad_kantoren, laad_overige_kantoren  # noqa: E402

INDEX = bouw_index(laad_kantoren(), laad_aliassen(), laad_overige_kantoren())
VERKLARING = (
    "Controleverklaring van de onafhankelijke accountant\n"
    "Aan de gemeenteraad van de gemeente Testdam\nOns oordeel\n"
    "Wij hebben de jaarrekening 2021 van de gemeente Testdam gecontroleerd.\n"
    "Naar ons oordeel:\n• geeft de in de jaarstukken opgenomen jaarrekening een "
    "getrouw beeld van de grootte en de samenstelling van zowel de baten en lasten "
    "als van de activa en passiva;\n• zijn de in de jaarrekening verantwoorde baten "
    "en lasten alsmede de balansmutaties in alle van materieel belang zijnde "
    "aspecten rechtmatig tot stand gekomen.\n"
    + "De basis voor ons oordeel. " * 20
    + "\nTestdam, 1 juni 2022\n\nDeloitte Accountants B.V.\n\nwas getekend\n"
    "A.B. Voorbeeld RA\n"
)
deloitte = next(k for k in INDEX.values() if k["naam"] == "Deloitte Accountants B.V.")
positie = VERKLARING.index("Wij hebben")
velden = lader.analysevelden(VERKLARING, positie, INDEX, deloitte["sleutel"])
controleer(
    "een getekende verklaring levert oordeel, continuïteit en naam",
    velden.get("oordeel") == "goedkeurend"
    and velden.get("continuiteitsonzekerheid") is False
    and velden.get("tekenend_accountant") == "A.B. Voorbeeld RA",
    f"gevonden: {velden}",
)
controleer(
    "een ander kantoor dan de lader vond: niets",
    lader.analysevelden(VERKLARING, positie, INDEX, "bestaat-niet") == {},
)
CONCEPT = VERKLARING.replace("Ons oordeel\n", "CONCEPT\nOns oordeel\n")
controleer(
    "een conceptverklaring: geen oordeel en geen naam",
    lader.analysevelden(CONCEPT, CONCEPT.index("Wij hebben"), INDEX, deloitte["sleutel"]) == {},
)

print(f"\n{gedaan - fouten}/{gedaan} goed")
raise SystemExit(1 if fouten else 0)
