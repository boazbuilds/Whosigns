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

print(f"\n{gedaan - fouten}/{gedaan} goed")
raise SystemExit(1 if fouten else 0)
