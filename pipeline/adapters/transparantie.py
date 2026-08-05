"""Transparantieverslagen van de zes OOB-kantoren: de cliëntenlijst eruit halen.

Elke accountantsorganisatie met OOB-vergunning moet jaarlijks een
transparantieverslag publiceren, en artikel 13 lid 2 onder f van
EU-verordening 537/2014 eist daarin **een lijst van de organisaties van
openbaar belang waarvoor het kantoor wettelijke controles heeft verricht**.
Dat is de enige plek waar de cliëntrelaties van banken, verzekeraars en
beursfondsen openbaar bij elkaar staan — wie controleert ASML staat niet bij
de AFM, wél in het transparantieverslag van KPMG.

Nagemeten op de verslagen van alle zes kantoren (4-8-2026): elk verslag bevat
de lijst, maar elk kantoor zet hem er anders in:

    BDO       "A. Lijst van Organisaties van Openbaar Belang", twee kolommen
              met een losse "X" vóór elke naam
    Deloitte  "Appendix C | Public interest entities", één naam per regel
    EY        "Appendix 1: List of PIE audit clients", twee kolommen; lange
              namen breken af over twee regels
    KPMG      "List of public-interest entity clients" (in het integrated
              report van ~276 pagina's), één naam per regel
    Mazars    "Appendix 1 Public Interest Entities", opsomming met bolletjes
              en tussenkopjes per branche ("Insurance companies")
    PwC       "List of public interest entities" (in een apart bijlagen-pdf),
              met lettermarkeringen: los ("A") én vastgeplakt ("B BMW
              Finance N.V.")

De vindplaatsen staan in seed/transparantieverslagen.csv, met per verslag de
sectiekop en welk cliënt-boekjaar de lijst beslaat. Die vertaling is een
keuze en staat daar toegelicht: een verslag over kantoorboekjaar 2024/2025
gaat over controles die grotendeels jaarrekeningen over 2024 betreffen.

Guardrail: de lijsten bevatten uitsluitend organisatienamen; er wordt niets
anders uit het verslag overgenomen.
"""

import re
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "extractie"))

from kantoor_match import normaliseer  # noqa: E402

CACHE = Path(__file__).resolve().parents[1] / ".cache"
KOPPEN = {"User-Agent": "Mozilla/5.0 (WhoSigns-pipeline)"}

# Een regel telt alleen als organisatienaam wanneer er een rechtsvorm- of
# organisatiewoord in staat. Bewust streng: een afgebroken regel als
# "Verzekeringmaatschappij N.V." zónder de eerste helft eraan vast mag nooit
# als eigen organisatie de database in — liever een naam missen (die komt in
# het droogloop-rapport) dan een halve naam opslaan.
_NAAM_TOKEN = re.compile(
    r"\b(?:B\.?V\.?|N\.?V\.?|SE|U\.?A\.?|plc|Ltd|S\.?A\.?|SICAV|"
    r"Stichting|Co[öo]peratie(?:ve)?|Onderlinge|Vereniging|Organisatie|"
    r"Woningstichting|Woningbouwvereniging|Woonstichting|Wonen|"
    r"Bank|\w*verzekering\w*|Waarborgmaatschappij|Assurantie\w*|"
    r"Pensioenfonds|Fonds|Fund|Beleggingsfonds|"
    r"Holding|Groep|Group|Insurance|Finance|Financing|Treasury|Capital)\b",
    re.I,
)
# "Organisatie" alleen in het enkelvoud: het meervoud ("organisaties van
# openbaar belang") is proza, het enkelvoud een naamsbestanddeel
# ("Nederlandse organisatie voor wetenschappelijk onderzoek (NWO)").

# Namen van het eigen netwerk zijn geen cliënten. De lijsten lopen in het pdf
# soms door in een overzicht van member firms (BDO Duitsland, KPMG Oostenrijk);
# zonder deze rem kwamen die als "cliënt" binnen.
_EIGEN_NETWERK = re.compile(
    r"bdo|kpmg|deloitte|pricewaterhouse|pwc|mazars|ernst\s*&\s*young|\bey\b",
    re.I,
)

# Tussenkopjes per branche (Mazars) — geen namen, maar ook geen reden om te
# stoppen: erná komen gewoon weer cliënten.
_CATEGORIE = re.compile(
    r"^(?:insurance companies|housing corporations|stock exchange funds?|"
    r"banks?|listed companies|investment (?:funds?|institutions)|"
    r"pension funds?|other(?: pies?)?)$",
    re.I,
)

# Regels die nooit een naam zijn: koppen, paginanummers, lettermarkeringen,
# de "X" uit de BDO-kolommen en de uitlegzinnen boven de lijst.
_RUIS = re.compile(
    r"transparantieverslag|transparency report|integrated report|"
    r"in accordance|with this list|requirements of|article|artikel|"
    r"statutory audit|wettelijke controle|alphabetical order|"
    r"list of|lijst van|appendix|bijlage|annexes|public.interest|"
    r"openbaar belang|pie clients|our partners|signed an audit|"
    r"started work|fiscal year|financial year|following|"
    r"accountantsorganisatie|niet zijnde",
    re.I,
)

# Vervolg van een afgebroken naam: begint met een klein woord ("de
# Detailhandel"), met "(" ("(Europe) N.V.") of met het restant van een
# organisatiewoord. De vorige regel krijgt het vervolg eraan vast.
_VERVOLG = re.compile(r"^(?:\(|[a-z])")

# Wat nooit bij een naam hoort, ook al begint het met een kleine letter: het
# slotblok ("www.deloitte.com."), en de voetnoten van kwaliteitsindicatoren.
_GEEN_VERVOLG = re.compile(
    r"www\.|http|kpi|percentage|reporting|survey|practice note|document|^the\b|"
    r"stelsel|kwaliteitsbeheersing|governance|indicatoren|handreiking|ontleend|"
    r"\bmanagement\b", re.I
)

# Een naam die eindigt op een los voorzetsel of lidwoord is nog niet af — de
# rest staat op de regel eronder ("Nederlandse Financierings-Maatschappij
# voor" + "Ontwikkelingslanden N.V."). "Onderlinge" idem: dat woord bungelt
# alleen aan een regeleinde wanneer de naam daar is afgebroken ("Stad Holland
# Zorgverzekeraar Onderlinge" + "Waarborgmaatschappij U.A.").
#
# De tweede helft van het patroon staat er sinds het BDO-verslag over 2013,
# dat de onderlingen afbreekt op het soortwoord ("Onderlinge Verzekering-
# Maatschappij" + "'Noord Nederlandsche P&I Club' U.A."). Zonder de regel
# belandt die tweede helft als eigen organisatie in de database.
#
# Waarom alleen regels die mét "Onderlinge" beginnen én op "maatschappij"
# eindigen, en niet elk woord dat op "maatschappij" eindigt: een kale
# "Schadeverzekeringsmaatschappij" is in de PwC- en EY-lijsten juist géén
# afgebroken eerste helft maar een kolomrestant, en die aan de volgende
# regel plakken vernielde daar telkens een naam die wél goed stond
# ("National Academic Verzekeringsmaatschappij N.V."). Nagemeten over alle
# 51 verslagen: met deze afbakening levert de regel alleen reparaties op.
_EINDIGT_OPEN = re.compile(
    r"\b(?:voor|van|de|het|der|den|ten|ter|en|in|op|te|tot|aan|bij|"
    r"of|for|and|the|onderlinge)$"
    r"|^Onderlinge[\w\s'’-]*maatschappij$",
    re.I,
)

# Proza dat door de naamfilter glipt omdat er toevallig "N.V." of
# "insurance" in staat. Gemeten op de PwC-verslagen 2014/2015 en 2015/2016,
# waar de inleidende zin boven de lijst over drie regels breekt:
#
#     "…audited by PricewaterhouseCoopers Accountants N.V. during the"
#     "…listed on an EU regulated market, credit institutions and (re)insurance"
#
# Twee signalen die een organisatienaam nooit geeft: eindigen op een Engels
# functiewoord, en een komma met een kleinletterwoord erachter. Nagemeten op
# alle 5.476 namen uit de 51 verslagen: samen raken ze precies deze zinnen en
# geen enkele echte naam ("Ons Huis, Woningstichting" houdt een hoofdletter
# na de komma).
#
# Derde signaal: een rechtsvorm met twee kleinletterwoorden erachter. Daar
# houdt de naam op en begint de zin ("... Holding PricewaterhouseCoopers
# Nederland B.V. annual financial statements."). Namen die ná de rechtsvorm
# doorlopen doen dat met een hoofdletter ("N.V. Bank voor de Nederlandse
# Gemeenten"), dus die blijven buiten schot — en "Stichting Wooninc." ook,
# want een punt op zich zegt niets.
_PROZA = re.compile(
    r"\b(?:the|at|as|and|of|during|with|by|from|that|which|our|their)$"
    r"|,\s+[a-z]"
    r"|\b(?:N\.V\.|B\.V\.|U\.A\.|B\.A\.|S\.E\.)\s+"
    r"(?!in\s+(?:liquidatie|oprichting|vereffening)\b)[a-z]+\s+[a-z]+",
)
# De uitzondering in die laatste regel: "Blue Square Re N.V. in liquidatie"
# staat zo in de PwC-lijst. Dat is geen zin maar een rechtstoestand, en die
# hoort bij de naam zoals het kantoor hem opgeeft.

# Een soortnaam plus rechtsvorm en verder niets ("Zorgverzekeraar U.A.",
# "Waarborgmaatschappij U.A.") is geen organisatie maar de staart van een
# afgebroken naam waarvan de eerste helft al als eigen regel is gelezen.
# Zo'n staart is niet betrouwbaar alsnog aan die eerste helft te plakken —
# de alfabetische volgorde van de lijsten bleek daarvoor te grillig (EY zet
# kolommen om en om in de tekststroom, Deloitte sorteert "O.W.M." vóór
# "Opel") — dus: afkeuren, nooit als losse organisatie opslaan.
_LOSSE_STAART = re.compile(
    r"^(?:Waarborgmaatschappij|Zorgverzekeraar|\w*[Vv]erzekering\w*|"
    r"Assurantie\w*|Maatschappij|Pensioenfonds|Beleggingsfonds)"
    r" (?:U\.?A\.?|B\.?V\.?|N\.?V\.?|B\.?A\.?|S\.?E\.?)$"
)


# Elk kantoor kiest een ander opsommingsteken, en het
# teken hoort niet bij de naam. KPMG 2019/2020 gebruikt een kastlijntje
# ("— ING Bank N.V."), BDO 2014 een Wingdings-pijltje dat als U+F03C uit de
# pdf komt — een teken uit het private-use-gebied, dus zonder betekenis
# buiten het lettertype waarin het gezet is.
# Deloitte 2018/2019 gebruikt het gewone streepje, vast tegen de naam aan
# ("-Onderlinge Waarborgmaatschappij Unive Ruinen U.A."), dus de spatie erna
# is optioneel en het ASCII-streepje hoort er expliciet bij.
_BULLET = re.compile("^[\u2022\u2023\u25aa\u25cf\xb7\u2012-\u2015\ue000-\uf8ff-]+\\s*")

# Een zachte afbreekstreep (U+00AD) is onzichtbaar maar telt wel mee bij het
# vergelijken van namen: "Gezondheids­zorg" en "Gezondheidszorg" zouden twee
# organisaties worden. Hij stuurt alleen de regelafbreking in het pdf.
_ZACHT_AFBREEK = re.compile("\xad\\s*")

# Eindigt het stuk vóór het haakje al op een rechtsvorm, dan is die naam af.
_SLUIT_AF = re.compile(r"(?:B\.?V\.?|N\.?V\.?|U\.?A\.?|B\.?A\.?|S\.?E\.?|LLP|Ltd|plc)$", re.I)


def _schoon(regel: str) -> str:
    regel = regel.replace("\t", " ").replace("\x07", " ").strip()
    regel = _ZACHT_AFBREEK.sub("", regel)
    regel = _BULLET.sub("", regel).strip()
    # Een geopend haakje dat niet meer sluit betekent dat de regel middenin
    # een tussenzin is afgekapt ("CZ Zorgverzekeringen N.V. (previously
    # OHRA"). De naam vóór het haakje is wél compleet, dus die houden we —
    # de tussenzin zelf is toelichting en hoort sowieso niet in de naam.
    #
    # Tenzij het haakje zélf de naam opent en de regel middenin die naam
    # breekt: "Mutual Insurance Association 'Munis' (Onderlinge" loopt door
    # op de regel eronder ("Verzekeringsmaatschappij 'Munis') U.A."). Dat
    # herken je eraan dat het stuk achter het haakje open eindigt; knippen
    # zou de aanhechting weghalen en beide helften los opslaan.
    # Twee dingen moeten samenvallen wil er níét geknipt worden: het stuk
    # achter het haakje eindigt open, én het stuk ervóór is zelf nog niet af.
    # Dat tweede is nodig sinds Deloitte 2017/2018, waar "Onderlinge
    # Verzekeringsmaatschappij Unive Samen U.A. (voorheen Onderlinge" wél een
    # afgeronde naam vooraan heeft: daar is het haakje toelichting.
    if regel.count("(") > regel.count(")"):
        knip = regel.rindex("(")
        kop, staart = regel[:knip].strip(), regel[knip + 1 :].strip()
        if not _EINDIGT_OPEN.search(staart) or _SLUIT_AF.search(kop):
            regel = kop
    # PwC plakt de lettermarkering aan de eerste naam van elke groep:
    # "B BMW Finance N.V." -> "BMW Finance N.V.". Eén losse hoofdletter
    # gevolgd door een naam die met een hoofdletter of "(" begint.
    regel = re.sub(r"^[A-Z] (?=[A-Z(])", "", regel)
    # Voetnootverwijzing achter de naam ("Stichting Vestia**") hoort er niet bij.
    # ...en een komma aan het eind is een opsommingsteken, geen naamsdeel.
    regel = re.sub(r"\s*[*,]+$", "", regel)
    return re.sub(r"\s+", " ", regel)


def namen_uit_verslag(tekst: str, kop: str) -> tuple[list[str], list[str]]:
    """(namen, afgekeurd) uit de lijstsectie die op `kop` volgt.

    De kop staat vaak meerdere keren in het verslag: in de inhoudsopgave, als
    paginakopregel, en bij BDO zelfs in een kruisverwijzingstabel ná de echte
    lijst. Daarom proberen we élk voorkomen en wint het startpunt dat de
    meeste namen oplevert — de echte lijst is altijd veruit de langste.
    """
    regels = tekst.split("\n")
    kop_norm = normaliseer(kop)
    starts = []
    for i, regel in enumerate(regels):
        if not kop_norm:
            continue
        if kop_norm in normaliseer(regel):
            starts.append(i)
        elif i + 1 < len(regels) and kop_norm in normaliseer(f"{regel} {regels[i + 1]}"):
            # De kop kan over twee regels gebroken zijn: PwC 2021/2022 zet
            # "Lijst van organisaties van" en "openbaar belang" onder elkaar.
            starts.append(i + 1)
    if not starts:
        return [], [f"sectiekop niet gevonden: {kop}"]

    beste: tuple[list[str], list[str]] = ([], [])
    for start in starts:
        uitkomst = _lees_vanaf(regels, start)
        if len(uitkomst[0]) > len(beste[0]):
            beste = uitkomst
    return beste


def _lees_vanaf(regels: list[str], start: int) -> tuple[list[str], list[str]]:
    namen: list[str] = []
    nrs: list[int] = []  # regelnummer van de (laatste) regel van elke naam
    afgekeurd: list[str] = []
    leeg_op_rij = 0
    wacht: str | None = None  # mogelijk de eerste helft van een afgebroken naam
    wacht_nr = -9
    # Een écht vervolg van een afgebroken naam staat op de regel pál onder de
    # eerste helft. Elk gemeten lijmgeval (voetnoten, zijbalkfragmenten als
    # "regulatory framework") stond juist ná een witregel of tussenliggende
    # rommel — daarom plakken alle samenvoegregels hieronder uitsluitend
    # aaneengesloten regels aan elkaar.
    for nr, regel in enumerate(regels[start + 1 :]):
        ruw = _schoon(regel)
        if not ruw or ruw == "X" or re.fullmatch(r"\d{1,3}", ruw) or re.fullmatch(r"[A-Z]", ruw):
            continue
        if ruw.startswith("*"):
            # Voetnootregels dragen hun markering voorop ("** Stichting Vestia
            # has been split ...") — nooit een naam, ook al staat er een
            # organisatiewoord in.
            afgekeurd.append(ruw)
            continue
        genormaliseerd = normaliseer(ruw)
        if _RUIS.search(ruw):
            # Een vólgende bijlage betekent: einde van de lijst.
            # Spatie verplicht tussen "bijlage" en de letter: het losse woord
            # "Bijlagen" in een zijbalk is geen volgende bijlage.
            if re.search(
                r"appendix\s*[2-9]|bijlage\s+[b-z]\b|network organisations|"
                r"audit quality indicators",
                ruw,
                re.I,
            ):
                break
            continue
        if ruw.count(")") > ruw.count("("):
            # Een sluithaakje zonder opening is de tweede helft van iets. Staat
            # de eerste helft pal erboven en hangt daar een haakje open, dan
            # horen ze bij elkaar: "Mutual Insurance Association 'Munis'
            # (Onderlinge" + "Verzekeringsmaatschappij 'Munis') U.A.".
            if (
                namen
                and nr == nrs[-1] + 1
                and namen[-1].count("(") > namen[-1].count(")")
                and len(f"{namen[-1]} {ruw}") <= 110
            ):
                namen[-1] = f"{namen[-1]} {ruw}"
                nrs[-1] = nr
                leeg_op_rij = 0
                wacht = None
                continue
            # Anders is de eerste helft al afgeknipt ("Zorgverzekeringen N.V.)")
            # en is dit geen naam op zichzelf.
            afgekeurd.append(ruw)
            wacht = None
            continue
        if ruw.endswith(":"):
            # Een label boven een groepje ("Merger between:"), nooit de eerste
            # helft van een naam. Zonder deze rem plakt Deloitte 2018/2019 het
            # kopje aan de fusiepartner eronder vast.
            afgekeurd.append(ruw)
            wacht = None
            continue
        if _PROZA.search(ruw):
            # Een zin, geen naam. Afkeuren en verder lezen: de lijst zelf
            # begint vaak pál onder deze inleidende zinnen. Deze toets staat
            # bewust ná _RUIS en _EIGEN_NETWERK: die twee bepalen waar de
            # lijst ophoudt, en een zin die hier al werd weggevangen kon dat
            # einde niet meer melden. Proza telt mee voor het geduld: staat
            # er alleen nog lopende tekst, dan is de lijst voorbij.
            afgekeurd.append(ruw)
            wacht = None
            leeg_op_rij += 1
            if leeg_op_rij >= (25 if namen else 40):
                break
            continue
        if _CATEGORIE.fullmatch(ruw):
            wacht = None
            continue
        sluit_op_naam = bool(namen) and nr == nrs[-1] + 1
        sluit_op_wacht = wacht is not None and nr == wacht_nr + 1
        if _VERVOLG.match(ruw) and (namen or wacht):
            # Vervolg van een afgebroken naam ("de Detailhandel", "(Europe) N.V.").
            # Een lánge kleine-letterregel is proza — bij PwC staan de
            # voetnoten van de kwaliteitsindicatoren dwars door de lijst heen,
            # dus proza betekent hier "overslaan", niet "stoppen": erna komen
            # gewoon weer cliënten. De 40 is gemeten: het langste echte
            # vervolg is 30 tekens, de kortste voetnootregel 54.
            if len(ruw) > 40 or _GEEN_VERVOLG.search(ruw) or _EIGEN_NETWERK.search(ruw):
                wacht = None
                continue
            if sluit_op_wacht:
                # Tweede regel van een naam die nog geen organisatiewoord
                # had; samen alsnog compleet ("Nederlandse organisatie voor
                # wetenschappelijk" + "onderzoek (NWO)") of verder wachten.
                if afgekeurd and afgekeurd[-1] == wacht:
                    afgekeurd.pop()
                wacht = f"{wacht} {ruw}"
                wacht_nr = nr
                if _NAAM_TOKEN.search(wacht) and not wacht.islower() and len(wacht) <= 90:
                    namen.append(wacht)
                    nrs.append(nr)
                    wacht = None
                    leeg_op_rij = 0
                else:
                    afgekeurd.append(wacht)
                continue
            if sluit_op_naam and len(f"{namen[-1]} {ruw}") <= 90:
                namen[-1] = f"{namen[-1]} {ruw}"
                nrs[-1] = nr
                leeg_op_rij = 0
                continue
            # Kleine-letterregel los van elke naam: zijbalk- of voetnootfragment.
            wacht = None
            continue
        if _EIGEN_NETWERK.search(ruw):
            # Overzicht van member firms bereikt: einde van de cliëntenlijst.
            afgekeurd.append(ruw)
            leeg_op_rij += 3
            if leeg_op_rij >= 10:
                break
            continue
        if not _NAAM_TOKEN.search(ruw):
            # Eindigt de naam erbóven open, dan is dit de rest ervan:
            # "Stichting Bedrijfstakpensioenfonds voor de" + "Bouwnijverheid".
            if (
                sluit_op_naam
                and _EINDIGT_OPEN.search(namen[-1])
                and ruw[:1].isupper()
                and len(f"{namen[-1]} {ruw}") <= 90
            ):
                namen[-1] = f"{namen[-1]} {ruw}"
                nrs[-1] = nr
                leeg_op_rij = 0
                continue
            # Kan de eerste helft van een afgebroken naam zijn (EY breekt
            # "DAS Nederlandse Rechtsbijstand / Verzekeringmaatschappij N.V."
            # over twee regels). Kort en met een hoofdletter: even vasthouden;
            # sluit de vólgende regel erop aan met een organisatiewoord, dan
            # horen ze bij elkaar.
            if len(ruw) <= 45 and ruw[:1].isupper() and len(ruw.split()) <= 5:
                wacht = ruw
                wacht_nr = nr
            else:
                wacht = None
            afgekeurd.append(ruw)
            leeg_op_rij += 1
            # Lang niets naamachtigs meer: de lijst is voorbij en we lezen
            # inmiddels gewone verslagtekst. De 25 is gemeten: een
            # paginawissel middenin PwC's Nederlandstalige lijst kost 13
            # tellende regels (zijbalk-inhoudsopgave plus intro en voetnoot,
            # elke pagina opnieuw); het échte lijsteinde wordt vooral door de
            # markeringen hierboven en de member-firm-rem gevangen. Vóór de
            # eerste naam is het geduld groter: tussen de kop en de lijst
            # staat bij PwC een volle zijbalk-inhoudsopgave.
            if leeg_op_rij >= (25 if namen else 40):
                break
            continue
        if len(genormaliseerd) < 4 or len(ruw) > 90:
            # Eén losse rechtsvorm ("U.A.") pal onder een naam is de
            # afgebroken staart van die naam, geen eigen regel waard
            # (PwC 2023/2024: "Onderlinge Verzekeringsmaatschappij Univé
            # Samen" met "U.A." op de regel eronder).
            if sluit_op_naam and len(genormaliseerd) < 4 and len(f"{namen[-1]} {ruw}") <= 90:
                namen[-1] = f"{namen[-1]} {ruw}"
                nrs[-1] = nr
                leeg_op_rij = 0
            else:
                afgekeurd.append(ruw)
            continue
        # Een regel geheel in kleine letters is nooit een cliëntnaam, wel een
        # stukje voetnoot uit een smalle kolom ("verzekeringsmaatschappijen
        # (niet" — afgebroken midden in "niet zijnde", dus per regel onherkenbaar).
        if ruw.islower():
            afgekeurd.append(ruw)
            continue
        leeg_op_rij = 0
        eerste_woord = ruw.split()[0] if ruw.split() else ""
        if sluit_op_wacht and (_NAAM_TOKEN.match(eerste_woord) or _EINDIGT_OPEN.search(wacht)):
            samengevoegd = f"{wacht} {ruw}"
            if len(samengevoegd) <= 90:
                afgekeurd = [a for a in afgekeurd if a != wacht]
                namen.append(samengevoegd)
                nrs.append(nr)
                wacht = None
                continue
        if sluit_op_naam and _EINDIGT_OPEN.search(namen[-1]) and len(f"{namen[-1]} {ruw}") <= 90:
            # "Stad Holland Zorgverzekeraar Onderlinge" + "Waarborgmaatschappij
            # U.A.": de vorige naam eindigt open, dus dit is de rest ervan.
            namen[-1] = f"{namen[-1]} {ruw}"
            nrs[-1] = nr
            wacht = None
            continue
        wacht = None
        if _LOSSE_STAART.match(ruw):
            afgekeurd.append(ruw)
            continue
        namen.append(ruw)
        nrs.append(nr)

    # Dezelfde naam kan twee keer in een verslag staan (kolomovergangen).
    uniek: list[str] = []
    gezien: set[str] = set()
    for naam in namen:
        sleutel = normaliseer(naam)
        if sleutel not in gezien:
            gezien.add(sleutel)
            uniek.append(naam)
    return uniek, afgekeurd


def haal_verslag(url: str, doel: Path) -> Path:
    """Downloadt het pdf één keer; wat er al staat, blijft staan."""
    if not (doel.exists() and doel.stat().st_size > 100_000):
        verzoek = urllib.request.Request(url, headers=KOPPEN)
        with urllib.request.urlopen(verzoek, timeout=300) as antwoord:
            doel.write_bytes(antwoord.read())
    return doel
