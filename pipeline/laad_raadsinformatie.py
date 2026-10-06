"""Controleverklaringen uit raadsstukken -> opdrachten in de database.

    Open Raadsinformatie  ->  documenten met "controleverklaring van de
                              onafhankelijke accountant", plus (tweede
                              zoekvraag) accountantsverslagen en oudere
                              verklaringen met dezelfde standaardzin
                          ->  de zin "Wij hebben de jaarrekening JJJJ van X
                              te Y gecontroleerd"
                          ->  kantoor uit het handtekeningblok eróver
                          ->  oordeel, continuïteit en tekenend accountant
                              uit hetzelfde venster (alleen bij een echte
                              controleverklaring, zie keuze 5)
                          ->  opdracht-rij

Vindplaats en leesregels: adapters/raadsinformatie.py.

Draaien:
    python3 pipeline/laad_raadsinformatie.py --droogloop
    python3 pipeline/laad_raadsinformatie.py --maximum 5000
    python3 pipeline/laad_raadsinformatie.py --vervang

`--droogloop` schrijft nooit iets. Staan SUPABASE_URL en een sleutel in de
omgeving, dan leest hij wél de database — de publieke leessleutel is genoeg —
en telt hij wat een echte run zou doen: nieuwe controles, geschreven en
teruggenomen oordelen, rijen van een andere bron die blijven staan, en of en
wat --vervang zou wissen.
Zonder omgeving alleen het CSV-rapport, zoals vroeger.

Zes keuzes die het gedrag bepalen:

1.  **De gecontroleerde organisatie komt uit de verklaring, niet uit de
    vindplaats.** Een gemeenteraad bespreekt ook de jaarstukken van elke
    gemeenschappelijke regeling waarin de gemeente deelneemt. Wie de
    publicerende raad als gecontroleerde partij neemt, schrijft die controles
    toe aan de verkeerde organisatie. Zie de toelichting in de adapter.

2.  **Het handtekeningblok houdt op bij de volgende verklaring.** Een
    raadsbundel zet meerdere jaarstukken achter elkaar in één pdf; zonder die
    grens vindt de matcher de accountant van de buurorganisatie. Het venster
    per verklaring komt daarom uit de adapter.

3.  **Alleen een ondertekening telt.** `zoek_kantoor` markeert een treffer als
    zwak wanneer die niet in de buurt van een datum, plaats of
    ondertekeningsformule staat — dan is de kantoornaam eerder een vermelding
    dan een handtekening. Zwakke treffers en niet-herkende namen komen in het
    rapport terecht, niet in de database.

4.  **Een rij uit een andere bron blijft van die bron; een eigen rij volgt de
    lezing van nu.** Tot 5-10-2026 schreef deze lader met merge-duplicates, en
    dan kreeg een controle die DigiMV al had gelezen stilletjes een
    raadsdocument als vindplaats en het kantoor uit dat document — terwijl het
    oordeel van DigiMV bleef staan. De site toonde zo een oordeel met een
    vindplaats waar dat oordeel niet in staat. Op 5-10-2026 waren dat zes
    zorgrijen. Nu: staat het organisatie-boekjaar er al uit een andere bron,
    dan blijft die rij zoals hij is. Een eigen rij (een raadsinformatie-
    bron_id) krijgt de nieuwe vindplaats en de oordeelvelden van deze lezing,
    ook als die een veld leeg laat: een verbeterde leesregel moet een eerder
    verkeerd gelezen oordeel kunnen terugnemen zonder migratie. Die zes
    zorgrijen zijn de uitzondering, zie `DIGIMV_ONDER_RAADSBRON`.

5.  **Het oordeel is het getrouwheidsoordeel.** Een verklaring bij een
    decentrale overheid draagt tot en met boekjaar 2022 twee oordelen: over de
    getrouwheid van de jaarrekening en over de rechtmatigheid. Het tweede
    staat in een ander soort zin, en de gewone oordeelregel pakt het als
    jaarrekeningoordeel — dan heeft een gemeente met een goedgekeurde
    jaarrekening ineens een "afkeurend oordeel". Zie
    `verklaring.oordeel_getrouwheid`, ook voor de vorm vanaf 2023, waarin de
    rechtmatigheid wél bij het jaarrekeningoordeel hoort. Kan het
    getrouwheidsoordeel niet worden vastgesteld, of spreken kop en oordeelzin
    elkaar tegen, dan blijft het veld leeg. Uit de tweede zoekvraag komt nooit
    een oordeel: een accountantsverslag is geen verklaring.

6.  **De tweede zoekvraag maakt geen organisaties aan.** Hij levert een
    controle alleen bij een organisatie die er al staat. Een nieuwe naam uit
    een accountantsverslag is te vaak tekstschade ("Qemeente Nieuwegein",
    "Hoogheemraadschap van Delfiand") of een stuk zin; die gaat naar de
    review-queue en niet de database in.

Twijfel gaat naar de review-queue, met alleen de organisatienaam, het
boekjaar, het kantoor en het documentnummer in Open Raadsinformatie — nooit een
persoonsnaam. Dat geldt voor een naam die bij organisaties met verschillende
KvK-nummers of in verschillende plaatsen hoort (zie `kies_kandidaat`) en voor
"Gemeente Bergen" zonder (L) of (NH): Nederland heeft er twee.

Deze organisaties zijn overheden: gemeenten, provincies, waterschappen,
gemeenschappelijke regelingen, omgevingsdiensten, veiligheidsregio's. Ze
krijgen sector "overheid" en geen KvK-nummer (de verklaring noemt dat niet), en
worden op genormaliseerde naam herkend zodat dezelfde organisatie niet twee
keer ontstaat — ook niet naast een organisatie die al uit de TED-gunningen
kwam.

Waarom `--vervang` bestaat
--------------------------
De naam-extractie is na de eerste volledige lading (6-8-2026, 3.940 opdrachten)
vier keer verbeterd: de naam mag niet meer over een kop heen lopen, een
herhaalde verklaring houdt de vermelding mét handtekeningblok, en de
matchsleutel herkent de plaatsstaart nu ook zonder spatie. Elke verbetering
levert schónere namen op — maar een blinde herdraai zet die schone namen als
nieuwe organisaties naast de oude verhaspelde, want de upsert-sleutel is de
organisatie en die matcht dan niet. Gemeten op 11-8-2026: er stonden ~195
naamfragmenten te veel in sector overheid ("…Utrechtte Soest", "…('de
vennootschap')" als organisatienaam).

`--vervang` herleest daarom eerst de volledige bron met de huidige leesregels.
Elke verklaring die opnieuw wordt gezien krijgt het nieuwe bron_id (een eigen
rij wordt daarvoor bijgewerkt, een nieuwe ingevoegd); wat er ná de doorloop nog aan
een oud raadsinformatie-bron_id hangt is dus precies wat alleen de oude
leesregels zagen, en dát wordt gewist. Tot slot gaan de organisaties weg die
daardoor nergens meer aan hangen — alleen die zonder KvK-nummer en zonder
resterende opdrachten, gunningen of signalen, zodat een organisatie uit een
register of met geschiedenis uit een andere bron nooit mee wordt gegrepen.

Die volgorde — eerst laden, dan pas wissen — is bewust: crasht de run
halverwege, dan is er niets verwijderd en draai je hem gewoon opnieuw. De bron
is klein genoeg (25.622 documenten over beide zoekvragen, zie de workflow voor
de gemeten duur) om dit per run volledig te doen.

Er wordt alleen gewist als de doorloop aantoonbaar de héle bron heeft gezien.
Dat is niet vanzelfsprekend: `documenten()` stopt zodra de zoek-API een lege
pagina teruggeeft, en van buitenaf ziet een halve doorloop er dan precies zo uit
als een hele. Een haperende API zou zo de oude uitkomst laten wissen terwijl de
vervanger nooit is gelezen — het verschil tussen vervangen en kwijtraken.
Daarom wordt per zoekvraag het aantal gelezen documenten vergeleken met het
totaal dat de bron zelf opgeeft (`totaal_documenten()`), en gaat er niets weg
als één van de twee onder de 95% blijft, bij een afkapping op --maximum, of als
een van die totalen niet op te vragen is. Per zoekvraag en niet over de som:
de tweede is een vijfde van de eerste, en op de som haalde een doorloop die
daar bijna een derde van miste de ondergrens nog gewoon (zie
`reden_om_niet_te_wissen`).

Een decentrale overheid is op grond van de Gemeentewet (of de Waterschapswet,
of de eigen gemeenschappelijke regeling) controleplichtig, dus dit zijn
wettelijke controles.
"""

import argparse
import collections
import csv
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent / "adapters"))
sys.path.insert(0, str(Path(__file__).resolve().parent / "extractie"))

import duo_besturen  # noqa: E402
import raadsinformatie  # noqa: E402
import verklaring  # noqa: E402
from kantoor_match import (  # noqa: E402
    bouw_index,
    laad_aliassen,
    laad_kantoren,
    laad_overige_kantoren,
    normaliseer,
    zoek_kantoor,
)
from supabase_client import Supabase, SupabaseFout  # noqa: E402

CACHE = Path(__file__).resolve().parent / ".cache"
SECTOR = "overheid"
TYPE_OPDRACHT = "wettelijke_controle"

# Namen die geen organisatie zijn maar een restant van de zin eromheen. Gemeten
# op de eerste tweehonderd documenten; zonder deze rem komen er rijen binnen
# als "onze controle" of "het onderdeel".
_GEEN_ORGANISATIE = re.compile(
    r"^(?:onze|onze\s|het\s|deze\s|die\s|welke\s|bovengenoemde\s)|"
    r"^(?:controle|jaarstukken|jaarrekening|begroting|bijlage)\b",
    re.I,
)


def bruikbaar(naam: str) -> bool:
    if len(naam) < 5 or len(naam) > 110:
        return False
    if _GEEN_ORGANISATIE.search(naam):
        return False
    # Een organisatienaam draagt minstens twee woorden of een hoofdletter.
    return bool(re.search(r"[A-ZÀ-Ý]", naam) or " " in naam)


# De velden die uit de verklaring zelf komen, naast kantoor en vindplaats.
ANALYSEVELDEN = (
    "oordeel",
    "grond_beperking",
    "continuiteitsonzekerheid",
    "tekenend_accountant",
)

# Een conceptverklaring in een raadsstuk: de accountant stuurt hem mee met het
# accountantsverslag, vóórdat de raad de jaarrekening vaststelt. Het kantoor
# klopt, maar oordeel en naam komen dan uit een stuk dat nog niet getekend is
# (gezien bij Purmerend 2016). Alleen gezocht van de kop van de verklaring tot
# kort na de standaardzin: daar staat het woord in de kop of het watermerk, en
# "concept" verderop in een raadsbundel kan over iets heel anders gaan. Gemeten
# op 5-10-2026: 40 van de 4.075 ondertekende verklaringen dragen het rond de
# zin, 168 ergens in het hele venster.
_CONCEPT = re.compile(r"\bconcept\b", re.I)
CONCEPT_VENSTER = 400

# Nederland heeft twee gemeenten Bergen: in Noord-Holland en in Limburg. De
# verklaring schrijft er soms "(L)" of "(NH)" achter, en dan is er niets aan de
# hand. Zonder die toevoeging is het een gok welke van de twee het is — en de
# database had op 5-10-2026 precies zo'n gok staan: een "Gemeente Bergen" met
# het KvK-nummer van Bergen (NH) en daaronder controles uit raadsstukken waarvan
# niet te zeggen is welke Bergen ze bedoelen. Andere gemeentenamen komen sinds
# de herindelingen van de jaren zeventig niet meer dubbel voor.
_HOMONIEMEN = {"gemeentebergen"}


def homoniem(naam: str) -> bool:
    return raadsinformatie.matchsleutel(naam) in _HOMONIEMEN


# Namen van openbare lichamen. Staat zo'n organisatie in de database onder een
# andere sector dan overheid, dan is dat een fout in de sector en niet in de
# naam: op 5-10-2026 stonden 96 organisaties waarvan de naam met "Gemeente "
# begint als "overig bedrijfsleven", allemaal met een KvK-nummer uit het
# marktonderzoek (de samenvoegregel van 20260922160000 laat het label overheid
# verliezen van de sector die de registerrij al had). Een nieuwe controle daar
# telt mee in het marktaandeel van een bedrijfslevensector, en in "overig
# bedrijfsleven" kwamen de wettelijke controles met een kantoor toen al vooral
# uit raadsstukken (313 rijen bij die 96 gemeenten). De tweede zoekvraag zou er
# 115 bij zetten. Zulke nieuwe rijen wachten daarom tot de sector klopt;
# bestaande eigen rijen blijven gewoon staan.
_OPENBAAR_LICHAAM = re.compile(
    r"^(?:gemeente|provincie|waterschap|hoogheemraadschap|wetterskip|"
    r"gemeenschappelijke\s+regeling|veiligheidsregio|omgevingsdienst|"
    r"regionale\s+uitvoeringsdienst|ggd|gemeentelijke\s+gezondheidsdienst|"
    r"gemeenschappelijke\s+gezondheidsdienst|werkvoorzieningss?chap|"
    r"recreatieschap|metropoolregio|openbaar\s+lichaam|"
    r"bedrijfsvoeringsorganisatie|belastingsamenwerking)\b",
    re.I,
)


def sector_wacht(organisatie: dict) -> bool:
    """Een openbaar lichaam dat (nog) niet in sector overheid staat."""
    return organisatie.get("sector") != SECTOR and bool(
        _OPENBAAR_LICHAAM.match(organisatie.get("naam") or "")
    )


def wacht_overzicht(wachtend: collections.Counter) -> list[str]:
    """De wachtende controles per sector, met alleen organisatie-ids.

    Een teller alleen ("wacht op sector overheid: 129") zegt niet wélke
    organisaties verkeerd staan, en niet alles wacht op dezelfde reparatie. Van
    de 53 wachtende organisaties in de droogloop van 6-10-2026 stonden er 46
    als "overig bedrijfsleven" met SBI 84.11/84.12 (openbaar bestuur) — die
    zet een sectorregel op die codes in één keer recht. De andere zeven niet
    vanzelf: een veiligheidsregio met SBI 84.25 onder overig bedrijfsleven,
    drie onder zorg (een gemeente, een GGD, een veiligheidsregio), twee
    regelingen onder zakelijke dienstverlening en een gemeente onder vastgoed.
    Zonder deze regels in het Actions-log blijven die een stil gat. Geen namen:
    de id vindt de rij, en meer hoeft een log niet te dragen.
    """
    per_sector: dict[str, collections.Counter] = collections.defaultdict(collections.Counter)
    for (organisatie_id, sector), aantal in wachtend.items():
        per_sector[sector or "(geen sector)"][organisatie_id] += aantal
    return [
        f"  {sector}: {sum(ids.values())} controles bij {len(ids)} organisaties, "
        "organisatie_id " + ", ".join(str(i) for i in sorted(ids))
        for sector, ids in sorted(per_sector.items())
    ]


def plaats_van(organisatie: dict) -> str | None:
    """Waar een organisatie volgens de database zit, als vergelijkingssleutel.

    De gemeente als die er staat, anders een plaats achter de naam ("… te
    Hoorn", ", gevestigd te Roosendaal"): de strenge sleutel haalt die juist
    weg, dus daar moet hij hier vandaan komen. Alleen letters en cijfers, want
    "'s-Hertogenbosch", "s-Hertogenbosch" en "’S-HERTOGENBOSCH" zijn dezelfde
    plaats (Stichting Farent stond op 6-10-2026 met twee van die drie in de
    database).
    """
    plaats = organisatie.get("gemeente") or raadsinformatie.plaats_achteraan(
        organisatie.get("naam") or ""
    )
    sleutel = re.sub(r"[^a-z0-9]", "", normaliseer(plaats or ""))
    return sleutel or None


def kies_kandidaat(kandidaten: list[dict]) -> tuple[dict | None, str | None]:
    """De organisatie bij een naam, of (None, reden) als dat een gok zou zijn.

    Hier stond `kandidaten[0]`: de eerste van de organisaties met deze naam,
    in de volgorde van de database. Drie gevallen zijn echter verschillend:

    * de kandidaten dragen verschillende KvK-nummers. Dan zijn het volgens het
      handelsregister twee rechtspersonen, en welke van de twee de verklaring
      bedoelt staat niet in de naam: naar de review-queue;
    * de kandidaten zitten volgens de database in verschillende plaatsen. De
      strenge sleutel (zie matchsleutel) laat "te Hoorn" weg, dus twee
      organisaties zonder KvK-nummer die alleen in hun plaats verschillen
      vallen daar samen — en of dat één organisatie is, zegt de naam niet. Ook
      naar de review-queue. Een kandidaat zonder bekende plaats spreekt niets
      tegen;
    * verder hooguit één KvK-nummer en één plaats. Dan zijn het dubbele rijen
      van één organisatie — de rij zonder nummer is ooit uit een raadsstuk
      ontstaan naast de registerrij. De rij mét nummer gaat voor; zonder
      nummer de oudste rij, zodat elke run dezelfde kiest en de geschiedenis
      bij elkaar blijft.

    Gemeten op 6-10-2026 over alle 17.653 organisaties: 121 strenge sleutels
    wijzen naar meer dan één organisatie; 50 daarvan met verschillende
    KvK-nummers, 5 met verschillende plaatsen (GGD Hart voor Brabant in
    Tilburg en 's-Hertogenbosch, Cyclus N.V. te Moordrecht en te Zuidplas …).
    In de droogloop van die dag kwamen 20 lezingen bij meer dan één kandidaat
    uit (Omgevingsdienst Zuid-Holland Zuid, Waddenfonds, Burgernet
    Zuid-Limburg …), geen enkele met twee nummers of twee plaatsen.
    """
    if len(kandidaten) == 1:
        return kandidaten[0], None
    nummers = {k.get("kvk_nummer") for k in kandidaten if k.get("kvk_nummer")}
    if len(nummers) > 1:
        return None, "naam hoort bij organisaties met verschillende KvK-nummers"
    plaatsen = {plaats for plaats in map(plaats_van, kandidaten) if plaats}
    if len(plaatsen) > 1:
        return None, "naam hoort bij organisaties in verschillende plaatsen"
    return min(kandidaten, key=lambda k: (not k.get("kvk_nummer"), k["id"])), None


def analysevelden(venster: str, positie: int, index: dict, kantoorsleutel: str) -> dict:
    """Oordeel, grond, continuïteit en tekenend accountant uit één verklaring.

    `venster` loopt van de kop van de verklaring tot de volgende verklaring
    (`oordeelvenster` uit de adapter); `positie` is waar de standaardzin daarin
    begint. Leeg als het geen bruikbare verklaring is: een concept, een stuk
    zonder oordeelzin, of een venster waarin `analyseer` een ánder kantoor
    vindt dan de lader. Dat laatste is de rem op raadsbundels: oordeel en naam
    moeten uit hetzelfde handtekeningblok komen als het kantoor.

    De naam komt uitsluitend uit `analyseer` (en dus uit ondertekenaar.py), met
    dezelfde eisen als bij elke andere bron.
    """
    # Van de kop tot net na de standaardzin: daar staat "CONCEPT" als het een
    # concept is, in de kop zelf of als watermerk op die pagina.
    if _CONCEPT.search(venster[: positie + CONCEPT_VENSTER]):
        return {}
    analyse = verklaring.analyseer(venster, index)
    kantoor = analyse.get("kantoor")
    if analyse.get("soort") != "controle" or not kantoor:
        return {}
    if kantoor.get("sleutel") != kantoorsleutel:
        return {}
    velden: dict = {"tekenend_accountant": analyse.get("tekenend_accountant")}
    oordeel = verklaring.oordeel_getrouwheid(venster)
    if oordeel:
        velden["oordeel"] = oordeel
        velden["continuiteitsonzekerheid"] = bool(analyse.get("continuiteitsonzekerheid"))
        # De grondregel leest bij een overheid ook een rechtmatigheidsbeperking
        # als "inhoudelijk" (gezien bij Hilversum 2016, Zevenaar 2019 en
        # Leiden 2018), en dat betekent op de site iets anders. Alleen WNT is
        # hier een vaststelling; de rest blijft leeg: niet vastgesteld.
        if oordeel == "beperking":
            grond = verklaring._grond_beperking(normaliseer(venster))
            velden["grond_beperking"] = grond if grond == "wnt" else None
    return velden


# Zes zorgrijen met een DigiMV-oordeel onder een raadsinformatie-bron_id. Tot
# 5-10-2026 schreef deze lader met merge-duplicates (zie keuze 4), en toen
# kregen deze controles — door DigiMV aangemaakt en gelezen, met oordeel en
# continuïteit, deels met verklaringsdatum, en bij één ook honoraria en een
# tekenend accountant — het bron_id van een raadsstuk. Die DigiMV-bron is
# overschreven en niet terug te halen: het oogstbestand bewaart geen
# vindplaats. Het bron_id zegt dus "eigen rij", maar de oordeelvelden zijn niet
# van deze lader: hij schrijft er niets overheen en --vervang wist ze niet,
# ook niet als een lezing ze ooit niet meer ziet. Opdracht-ids, gemeten op
# 6-10-2026: precies de eigen rijen met een oordeel (GGD Zuid-Limburg 2022 en
# 2025, GGD Brabant-Zuidoost 2024, Veiligheidsregio Kennemerland 2020, Gemeente
# Amsterdam 2020 onder zorg, Coöperatie JENS 2024).
DIGIMV_ONDER_RAADSBRON = frozenset({7223, 9053, 10318, 13418, 20823, 57968})


def te_wissen(oude_bron: int) -> str:
    """Het PostgREST-filter waarmee --vervang de oude uitkomst van één bron wist.

    Alles onder dat bron_id, behalve de DigiMV-rijen hierboven: die blijven ook
    staan als een lezing ze ooit niet meer ziet.
    """
    beschermd = ",".join(str(i) for i in sorted(DIGIMV_ONDER_RAADSBRON))
    return f"bron_id=eq.{oude_bron}&id=not.in.({beschermd})"


def schrijfactie(
    bestaand: dict | None,
    eigen_bronnen: set[int],
    bron_id: int | None,
    kantoor_id: int,
    velden: dict,
) -> tuple[str, dict]:
    """Wat er met de controle van dit organisatie-boekjaar gebeurt.

    ("nieuw", rij)          er staat nog niets: invoegen
    ("bijwerken", velden)   een eigen rij: nieuwe vindplaats en de lezing van nu
    ("andere bron", {})     een rij uit een andere bron: met rust laten
    ("beschermd", {})       een DigiMV-rij onder een raadsinformatie-bron_id
    ("tegenspraak", {})     deze run las al een ánder kantoor voor dit boekjaar

    Een eigen rij volgt de lezing van nu, ook waar die een veld leeg laat. Hier
    werden eerder alleen lege velden aangevuld, en dan bleef een oordeel dat
    een oudere leesregel verkeerd las voorgoed staan: de oordeelonthouding van
    Hilversum 2024 en de beperking van Twenterand 2022 (zie
    `verklaring.oordeel_getrouwheid`) waren met een verbeterde regel alleen nog
    met een migratie weg te krijgen. Deze lader is de enige die zo'n rij
    schrijft, dus er gaat niets van een andere bron verloren — behalve bij
    `DIGIMV_ONDER_RAADSBRON`, en die blijven daarom buiten schot.

    Eén uitzondering binnen een run: schreef deze run de rij zelf al (een
    tweede schrijfwijze van dezelfde organisatie), dan blijft die eerste lezing
    staan en vult de tweede alleen aan wat leeg is. Gemeten op 6-10-2026
    kwam dat niet voor; de volgorde van de bron ligt vast, dus de uitkomst is
    elke run dezelfde.
    """
    if bestaand is None:
        rij = {"kantoor_id": kantoor_id, "bron_id": bron_id, "type_opdracht": TYPE_OPDRACHT}
        rij.update({veld: waarde for veld, waarde in velden.items() if waarde is not None})
        return "nieuw", rij
    if bestaand.get("id") in DIGIMV_ONDER_RAADSBRON:
        return "beschermd", {}
    if bestaand.get("bron_id") not in eigen_bronnen:
        return "andere bron", {}
    deze_run = bestaand.get("bron_id") == bron_id
    if deze_run and bestaand.get("kantoor_id") != kantoor_id:
        # Twee schrijfwijzen van dezelfde organisatie in één run, met twee
        # kantoren voor hetzelfde boekjaar. De eerste lezing blijft staan;
        # kiezen tussen de twee zou gokken zijn.
        return "tegenspraak", {}
    wijziging: dict = {"bron_id": bron_id, "kantoor_id": kantoor_id}
    for veld in ANALYSEVELDEN:
        nieuw = velden.get(veld)
        if deze_run:
            if nieuw is not None and bestaand.get(veld) is None:
                wijziging[veld] = nieuw
        elif nieuw != bestaand.get(veld):
            wijziging[veld] = nieuw
    return "bijwerken", wijziging


def bekende_plaatsen(organisaties: list[dict]) -> dict[str, str]:
    """Plaats in kleine letters -> de gewone schrijfwijze uit het register.

    Alleen gemeenten van organisaties met een KvK-nummer (zie enige_plaats).
    Het register schrijft dezelfde plaats soms in KAPITALEN en soms gewoon;
    op 6-10-2026 bij 76 van de 655 plaatsen allebei. Hier stond de eerste die
    voorbijkwam, en dan kreeg Gemeente Schouwen-Duiveland "ZIERIKZEE" als
    plaats — en de plaatspagina vergelijkt letterlijk, dus "ook in Zierikzee"
    miste haar. Daarom de gewone schrijfwijze; bij meer dan één de meest
    gebruikte. Twintig plaatsen staan er alleen in KAPITALEN (HATTEM,
    VENRAY …); daarvoor zie enige_plaats.
    """
    spellingen: dict[str, collections.Counter] = collections.defaultdict(collections.Counter)
    for organisatie in organisaties:
        gemeente = (organisatie.get("gemeente") or "").strip()
        if organisatie.get("kvk_nummer") and gemeente:
            spellingen[gemeente.lower()][gemeente] += 1
    return {
        sleutel: min(teller, key=lambda s: (s.isupper(), -teller[s], s))
        for sleutel, teller in spellingen.items()
    }


def enige_plaats(plaatsen: set[str], bekend: dict[str, str]) -> str | None:
    """De vestigingsplaats, als alle lezingen het over één bekende plaats eens zijn.

    "Bekend" betekent: de plaats staat al als gemeente bij een organisatie met
    een KvK-nummer, dus uit een register. Dat is de rem op tekstschade: in de
    tweede zoekvraag stonden "Iilburg", "Is-Hertogenbosch" en
    "HardinxveldGiessendam" als plaats (5-10-2026), en die horen niet op een
    plaatspagina. KAPITALEN uit oudere stukken lossen zo ook op: de
    schrijfwijze komt uit het register (zie bekende_plaatsen). Kent het
    register de plaats alleen in KAPITALEN, dan de schrijfwijze uit de
    verklaring zelf — en staat die er ook zo, dan niets: een plaats in
    KAPITALEN is een andere plaats voor de plaatspagina.
    """
    erkend: dict[str, set[str]] = {}
    for plaats in plaatsen:
        if plaats.lower() in bekend:
            erkend.setdefault(plaats.lower(), set()).add(plaats)
    if len(erkend) != 1:
        return None
    sleutel, gelezen = erkend.popitem()
    if not bekend[sleutel].isupper():
        return bekend[sleutel]
    gewoon = sorted(plaats for plaats in gelezen if not plaats.isupper())
    return gewoon[0] if gewoon else None


# Wissen met --vervang mag alleen als elke zoekvraag voor minstens dit deel is
# gelezen (zie de toelichting bovenin).
ONDERGRENS = 0.95


def lees(maximum: int, per_pagina: int, pauze: float, gelezen: dict[str, int], haal=None):
    """Alle documenten van beide zoekvragen, op volgorde: (zoekvraag, document).

    `gelezen` houdt per zoekvraag bij hoeveel documenten er binnenkwamen; de
    ondergrens van --vervang geldt per zoekvraag (zie reden_om_niet_te_wissen).
    Samen nooit meer dan `maximum`.
    """
    for zoekvraag in raadsinformatie.ZOEKVRAGEN:
        gelezen[zoekvraag] = 0
        resterend = maximum - sum(gelezen.values())
        if resterend <= 0:
            return
        for document in raadsinformatie.documenten(
            per_pagina=per_pagina,
            maximum=resterend,
            haal=haal,
            zoekvraag=zoekvraag,
            pauze=pauze,
        ):
            gelezen[zoekvraag] += 1
            yield zoekvraag, document


def reden_om_niet_te_wissen(
    gelezen: dict[str, int], totalen: dict[str, int | None], maximum: int
) -> str | None:
    """Waarom --vervang de oude uitkomst moet laten staan, of None als wissen mag.

    Wissen mag alleen na een aantoonbaar volledige doorloop. Drie manieren
    waarop die níét volledig is:

    1. afgekapt op --maximum;
    2. het opgegeven totaal van een zoekvraag is onbekend;
    3. de zoek-API gaf halverwege een lege pagina terug. `documenten()` stopt
       dan gewoon — de lus eindigt op `if not treffers: return` — en van
       buitenaf ziet een halve doorloop er precies zo uit als een hele.

    Het derde geval wordt per zoekvraag gemeten. Over de som van beide (21.339
    + 4.283 op 5-10-2026) haalde een doorloop die van de tweede maar 3.002
    documenten las de 95% nog gewoon, en vanaf de tweede run wiste vervang
    dan de controles die alleen die tweede vraag oplevert (313 in de
    droogloop van 6-10-2026) terwijl de vervanger nooit gelezen was.
    """
    if sum(gelezen.values()) >= maximum:
        return (
            f"doorloop afgekapt op {maximum} documenten; draai zonder krappe --maximum"
        )
    for zoekvraag in raadsinformatie.ZOEKVRAGEN:
        totaal = totalen.get(zoekvraag)
        if totaal is None:
            return (
                f"het brontotaal van '{zoekvraag}' is onbekend, dus niet te "
                "controleren of de hele bron gelezen is"
            )
        aantal = gelezen.get(zoekvraag, 0)
        if aantal < totaal * ONDERGRENS:
            return (
                f"maar {aantal} van de {totaal} documenten van '{zoekvraag}' gelezen "
                f"(minder dan {ONDERGRENS:.0%}); de doorloop is onvolledig"
            )
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--droogloop", action="store_true")
    # Beide zoekvragen samen telden 25.622 documenten op 5-10-2026. Het oude
    # plafond van 25.000 zou de tweede vraag dus afkappen, en dan weigert
    # --vervang terecht te wissen.
    parser.add_argument(
        "--maximum", type=int, default=40_000,
        help="hoogstens zoveel documenten lezen, over beide zoekvragen samen",
    )
    parser.add_argument(
        "--per-pagina", type=int, default=100, dest="per_pagina",
        help="documenten per verzoek aan de zoek-API",
    )
    parser.add_argument(
        "--pauze", type=float, default=0.2,
        help="seconden tussen twee verzoeken aan de zoek-API",
    )
    parser.add_argument(
        "--vervang", action="store_true",
        help="wis eerst de eerdere raadsinformatie-uitkomst en laad opnieuw "
        "(zie de toelichting bovenin dit bestand)",
    )
    argumenten = parser.parse_args()
    if argumenten.vervang and argumenten.droogloop:
        print("--vervang en --droogloop gaan niet samen: vervangen raakt de database.")
        return 1
    return laad(argumenten)


def laad(argumenten) -> int:
    index = bouw_index(laad_kantoren(), laad_aliassen(), laad_overige_kantoren())
    schrijven = not argumenten.droogloop

    db = None
    try:
        db = Supabase()
    except SupabaseFout as fout:
        if schrijven:
            print(fout)
            return 1
        print("droogloop zonder database: alleen het CSV-rapport")

    kantoor_id_per_sleutel: dict[str, int] = {}
    org_per_naam: dict[str, list[dict]] = {}
    org_per_streng: dict[str, list[dict]] = {}
    kvk_per_id: dict[int, str | None] = {}
    # KvK-nummer -> organisatierij: of het DUO-nummer van een schoolbestuur
    # dat deze lader aanmaakt al op een rij staat (duo_besturen.bij_aanmaak).
    org_per_kvk: dict[str, dict] = {}
    gemeente_per_id: dict[int, str | None] = {}
    plaatsen_register: dict[str, str] = {}
    # (organisatie_id, boekjaar) -> de wettelijke controle die er al staat
    bestaand: dict[tuple[int, int], dict] = {}
    # organisatie-boekjaren met een controle van een ander type (vrijwillig, of
    # "voorwerp onbekend" uit het marktonderzoek); alleen om te tellen
    ander_type: dict[tuple[int, int], set[str]] = {}
    eigen_bronnen: set[int] = set()
    in_review: set[tuple[str, int]] = set()
    geraakt: set[int] = set()
    oude_bronnen: list[int] = []
    bron_id = None
    if db is not None:
        if not schrijven:
            print("droogloop: de database wordt alleen gelezen", flush=True)
        kantoor_id_per_sleutel = {
            rij["sleutel"]: rij["id"]
            for rij in db.selecteer_alles("kantoren", "select=id,sleutel")
            if rij.get("sleutel")
        }
        if not kantoor_id_per_sleutel:
            print("Geen kantoren in de database — draai eerst de Pipeline-workflow.")
            return 1
        organisaties = db.selecteer_alles(
            "organisaties", "select=id,naam,kvk_nummer,gemeente,sector"
        )
        plaatsen_register = bekende_plaatsen(organisaties)
        for rij in organisaties:
            kvk_per_id[rij["id"]] = rij.get("kvk_nummer")
            if rij.get("kvk_nummer"):
                org_per_kvk[rij["kvk_nummer"]] = rij
            gemeente_per_id[rij["id"]] = rij.get("gemeente")
            org_per_naam.setdefault(normaliseer(rij["naam"]), []).append(rij)
            # Tweede index op de strengere sleutel: zie matchsleutel() in de
            # adapter. Wijst hij naar meer dan één organisatie, dan alleen als
            # die niet aantoonbaar verschillen — anders is samenvoegen een gok
            # (zie kies_kandidaat).
            org_per_streng.setdefault(
                raadsinformatie.matchsleutel(rij["naam"]), []
            ).append(rij)
        eigen_bronnen = {
            rij["id"]
            for rij in db.selecteer_alles("bronnen", "select=id,bron_type")
            if rij["bron_type"] == "raadsinformatie"
        }
        # Alles in één keer voorgeladen: per verklaring een verzoek kost bij
        # deze aantallen meer tijd dan de hele doorloop.
        for rij in db.selecteer_alles(
            "opdrachten",
            "select=id,organisatie_id,boekjaar,type_opdracht,kantoor_id,bron_id,"
            + ",".join(ANALYSEVELDEN)
            + "&type_opdracht=in.(wettelijke_controle,vrijwillige_controle,"
            "controle_onbepaald)",
        ):
            sleutel = (rij["organisatie_id"], rij["boekjaar"])
            if rij["type_opdracht"] == TYPE_OPDRACHT:
                bestaand[sleutel] = rij
            else:
                ander_type.setdefault(sleutel, set()).add(rij["type_opdracht"])
        # Wat al in de review-queue wacht, zodat een herhaalde run het niet
        # opnieuw aanbiedt. De publieke sleutel mag deze tabel niet lezen; in
        # een droogloop daarmee komt hier niets terug, en dat is goed genoeg om
        # te tellen.
        for rij in db.selecteer_alles(
            "review_queue",
            "select=id,payload&soort=eq.naam_match&status=eq.open"
            "&payload->>bron=eq.raadsinformatie",
        ):
            payload = rij.get("payload") or {}
            in_review.add((payload.get("organisatie"), payload.get("boekjaar")))

        geraakt = {
            organisatie_id
            for (organisatie_id, _), rij in bestaand.items()
            if rij["bron_id"] in eigen_bronnen
        }
        if argumenten.vervang:
            # Nog niets wissen — alleen onthouden wat er nu staat. Elke
            # verklaring die de huidige leesregels opnieuw opleveren krijgt
            # hieronder het nieuwe bron_id. Wat er ná de volledige doorloop nog
            # aan een oud bron_id hangt, is dus precies de uitkomst die de oude
            # leesregels te veel zagen — en pas dán wordt er gewist. Crasht de
            # run halverwege, dan is er niets verwijderd en draai je hem gewoon
            # opnieuw.
            oude_bronnen = sorted(eigen_bronnen)
            print(
                f"vervang: {len(oude_bronnen)} eerdere ladingen gevonden, "
                f"{len(geraakt)} organisaties; opruiming volgt na de doorloop",
                flush=True,
            )

        if schrijven:
            bron = db.invoegen(
                "bronnen",
                {
                    "bron_type": "raadsinformatie",
                    "url": raadsinformatie.API,
                    "betrouwbaarheid": "publiek",
                },
            )
            bron_id = bron["id"]
        else:
            # Een denkbeeldig bron_id, zodat de droogloop een rij die hij in
            # deze run al "schreef" net zo herkent als een echte run.
            bron_id = -1
        eigen_bronnen.add(bron_id)

    CACHE.mkdir(exist_ok=True)
    rapport_pad = CACHE / "resultaat_raadsinformatie.csv"
    rapport = rapport_pad.open("w", newline="", encoding="utf-8")
    schrijver = csv.writer(rapport)
    # Dit rapport wordt als artifact bewaard bij een publieke repo, dus alleen
    # nummers, de organisatie, het boekjaar, het kantoor en uitkomsten. Geen
    # naam van de tekenend accountant ("gevonden ja/nee" is genoeg om te
    # meten), en geen documenttitel of url: een titel noemt soms een wethouder,
    # en een deel van de urls draagt de bestandsnaam (zie verklaringen_uit in
    # de adapter). Het documentnummer vindt het stuk terug in Open
    # Raadsinformatie. Tot 6-10-2026 stonden titel, url en plaats er wél in.
    schrijver.writerow(
        ["organisatie_id", "organisatie", "boekjaar", "kantoor", "zoekvraag",
         "status", "actie", "oordeel", "ondertekenaar", "document_id"]
    )

    telling: collections.Counter = collections.Counter()
    afgekeurd: collections.Counter = collections.Counter()
    gezien: set[tuple[str, int]] = set()
    plaatsen_per_org: dict[int, set[str]] = collections.defaultdict(set)
    nieuwe_rijen_per_jaar: collections.Counter = collections.Counter()
    oordeel_per_jaar: collections.Counter = collections.Counter()
    # (organisatie_id, sector) -> controles die wachten tot de sector klopt.
    wachtend: collections.Counter = collections.Counter()
    vrij_id = -2  # denkbeeldige organisatie-ids in een droogloop
    gelezen: dict[str, int] = {}
    begin = time.monotonic()

    def naar_review(reden: str, naam: str, boekjaar: int, kantoornaam: str,
                    document_id: str, organisatie_ids: list[int] | None = None) -> None:
        """Eén reviewgeval per organisatienaam en boekjaar.

        Alleen de organisatienaam, het boekjaar, het kantoor en het
        documentnummer in Open Raadsinformatie: geen documenttitel en geen url
        (een titel noemt soms een wethouder, en een url soms de titel) en geen
        persoonsnaam. Het nummer vindt het stuk terug met een zoekvraag
        {"ids": {"values": [nummer]}} op dezelfde API.
        """
        telling[f"review: {reden}"] += 1
        if (naam, boekjaar) in in_review:
            return
        in_review.add((naam, boekjaar))
        payload = {
            "bron": "raadsinformatie",
            "reden": reden,
            "organisatie": naam,
            "boekjaar": boekjaar,
            "kantoor": kantoornaam,
            "document_id": document_id,
        }
        if organisatie_ids:
            payload["organisatie_ids"] = organisatie_ids
        if schrijven:
            db.invoegen("review_queue", {"soort": "naam_match", "payload": payload})

    def verwerk(naam: str, boekjaar: int, vermelding: dict, treffer: dict,
                velden: dict, zoekvraag: str) -> tuple[str, int | None]:
        """Organisatie herkennen en de controle schrijven.

        Geeft de actie terug en de organisatie waar de controle bij hoort.
        """
        nonlocal vrij_id
        if db is None:
            return "droogloop", None
        kantoornaam = treffer["kantoor"]["naam"]
        kantoor_id = kantoor_id_per_sleutel.get(treffer["kantoor"]["sleutel"])
        if kantoor_id is None:
            print(f"  LET OP: {kantoornaam} staat niet in de database — draai laad_kantoren.py")
            telling["kantoor niet in de database"] += 1
            return "kantoor onbekend", None
        document_id = vermelding["document_id"]
        if homoniem(naam):
            naar_review("gemeentenaam bestaat twee keer (Bergen NH of L)",
                        naam, boekjaar, kantoornaam, document_id)
            return "review", None

        streng = raadsinformatie.matchsleutel(naam)
        kandidaten = org_per_naam.get(normaliseer(naam), [])
        if not kandidaten:
            # Koppeltekens en spaties sneuvelen in de pdf-tekst; op de
            # strengere sleutel is "Regio West-Brabant" hetzelfde als
            # "Regio WestBrabant".
            kandidaten = org_per_streng.get(streng, [])
            if len(kandidaten) == 1:
                telling["op strenge sleutel herkend"] += 1
        if len(kandidaten) > 1:
            telling["naam meer dan één keer in de database"] += 1
        gekozen, twijfel = kies_kandidaat(kandidaten) if kandidaten else (None, None)
        if twijfel:
            naar_review(twijfel, naam, boekjaar, kantoornaam, document_id,
                        [k["id"] for k in kandidaten])
            return "review", None
        if gekozen:
            organisatie_id = gekozen["id"]
        elif zoekvraag != "controleverklaring":
            # Zie keuze 6 bovenin: een accountantsverslag maakt geen
            # organisaties aan.
            naar_review("nieuwe organisatie uit een accountantsverslag",
                        naam, boekjaar, kantoornaam, document_id)
            return "review", None
        else:
            # Een openbaar schoolbestuur legt zijn jaarrekening ook aan de raad
            # voor; dat is onderwijs, geen overheid (migratie 20261006110000).
            # Het KvK-nummer uit DUO komt níet op de rij — een naam is geen
            # harde sleutel — maar gaat hieronder als kandidaat naar de review.
            keuze = duo_besturen.bij_aanmaak(naam, SECTOR, org_per_kvk)
            nieuw = {"naam": naam, "kvk_nummer": None, "sector": keuze["sector"],
                     "gemeente": None}
            if schrijven:
                organisatie = db.invoegen("organisaties", nieuw)
            else:
                organisatie = {**nieuw, "id": vrij_id}
                vrij_id -= 1
            org_per_naam.setdefault(normaliseer(naam), []).append(organisatie)
            org_per_streng.setdefault(streng, []).append(organisatie)
            # Uit de rij die is aangemaakt en niet vast None: komt er een
            # KvK-nummer mee, dan wist --vervang deze organisatie nooit.
            gemeente_per_id[organisatie["id"]] = nieuw["gemeente"]
            kvk_per_id[organisatie["id"]] = nieuw["kvk_nummer"]
            kandidaat = keuze["kvk_kandidaat"]
            if kandidaat:
                telling["kvk-kandidaat naar review"] += 1
            if kandidaat and schrijven and not db.bestaat(
                "review_queue", duo_besturen.review_filter(kandidaat)
            ):
                ids = [organisatie["id"]]
                if keuze["mogelijk_dubbel"]:
                    ids.append(org_per_kvk[kandidaat]["id"])
                db.invoegen("review_queue", duo_besturen.review_kandidaat(
                    "raadsinformatie", keuze, ids))
            organisatie_id = organisatie["id"]
            telling["nieuwe organisatie"] += 1

        if vermelding["plaats"]:
            plaatsen_per_org[organisatie_id].add(vermelding["plaats"])

        sleutel = (organisatie_id, boekjaar)
        if sleutel not in bestaand and gekozen and sector_wacht(gekozen):
            telling["wacht op sector overheid"] += 1
            wachtend[(organisatie_id, gekozen.get("sector"))] += 1
            return "wacht op sector", organisatie_id
        actie, wijziging = schrijfactie(
            bestaand.get(sleutel), eigen_bronnen, bron_id, kantoor_id, velden
        )
        telling[actie] += 1
        if actie == "nieuw":
            if sleutel in ander_type:
                soorten = "/".join(sorted(ander_type[sleutel]))
                telling[f"nieuw naast {soorten}"] += 1
            if schrijven:
                db.invoegen_zonder_overschrijven(
                    "opdrachten",
                    [{"organisatie_id": organisatie_id, "boekjaar": boekjaar, **wijziging}],
                    "organisatie_id,boekjaar,type_opdracht",
                )
            bestaand[sleutel] = {
                "organisatie_id": organisatie_id, "boekjaar": boekjaar, **wijziging
            }
            nieuwe_rijen_per_jaar[boekjaar] += 1
        elif actie == "bijwerken":
            if schrijven:
                db.bijwerken(
                    "opdrachten",
                    f"organisatie_id=eq.{organisatie_id}&boekjaar=eq.{boekjaar}"
                    f"&type_opdracht=eq.{TYPE_OPDRACHT}"
                    f"&bron_id=in.({','.join(str(b) for b in sorted(eigen_bronnen))})",
                    wijziging,
                )
            if bestaand[sleutel].get("kantoor_id") != kantoor_id:
                telling["eigen rij, ander kantoor"] += 1
            bestaand[sleutel].update(wijziging)
        elif actie in ("andere bron", "beschermd") and bestaand[sleutel].get("kantoor_id") != kantoor_id:
            # Twee bronnen, twee kantoren voor hetzelfde boekjaar. De rij van
            # de andere bron blijft staan; dit komt in het rapport.
            telling[f"{actie}, ander kantoor"] += 1
            actie = f"{actie}, ander kantoor"
        if wijziging.get("oordeel"):
            oordeel_per_jaar[(boekjaar, wijziging["oordeel"])] += 1
            telling["oordeel geschreven"] += 1
        if wijziging.get("tekenend_accountant"):
            telling["tekenend accountant geschreven"] += 1
        # Wat een eigen rij kwijtraakt omdat deze lezing het niet meer
        # ondersteunt (zie schrijfactie).
        for veld in ANALYSEVELDEN:
            if veld in wijziging and wijziging[veld] is None:
                telling[f"{veld} gewist"] += 1
        return actie, organisatie_id

    for zoekvraag, document in lees(
        argumenten.maximum, argumenten.per_pagina, argumenten.pauze, gelezen
    ):
        documenten = sum(gelezen.values())
        if documenten % 500 == 0:
            print(
                f"  {documenten} documenten, {telling['opdracht']} controles, "
                f"{time.monotonic() - begin:.0f} s",
                flush=True,
            )
        tekst = raadsinformatie._plat(document.get("text"))
        for vermelding in raadsinformatie.verklaringen_uit(tekst, document):
            naam = vermelding["organisatie"]
            if not bruikbaar(naam):
                afgekeurd[naam[:60]] += 1
                telling["naam onbruikbaar"] += 1
                continue

            streng = raadsinformatie.matchsleutel(naam)
            boekjaar = vermelding["boekjaar"]
            if (streng, boekjaar) in gezien:
                telling["al gezien"] += 1
                continue

            van, tot = vermelding["venster"]
            treffer = zoek_kantoor(tekst[van:tot], index)
            if treffer is None:
                status, kantoornaam = "geen kantoor", ""
            elif treffer.get("zwak"):
                status, kantoornaam = "geen ondertekening", treffer["kantoor"]["naam"]
            else:
                status, kantoornaam = "opdracht", treffer["kantoor"]["naam"]
            telling[status] += 1
            actie, velden, organisatie_id = "", {}, None

            if status == "opdracht":
                # Pas hier als gezien merken: een venster zonder
                # ondertekening mag een latere vermelding mét
                # handtekening niet blokkeren (zie de adapter).
                gezien.add((streng, boekjaar))
                if zoekvraag == "controleverklaring":
                    oordeel_van, oordeel_tot = vermelding["oordeelvenster"]
                    velden = analysevelden(
                        tekst[oordeel_van:oordeel_tot],
                        vermelding["positie"] - oordeel_van,
                        index,
                        treffer["kantoor"]["sleutel"],
                    )
                actie, organisatie_id = verwerk(
                    naam, boekjaar, vermelding, treffer, velden, zoekvraag
                )

            schrijver.writerow(
                [
                    organisatie_id or "", naam, boekjaar, kantoornaam, zoekvraag,
                    status, actie, velden.get("oordeel") or "",
                    "ja" if velden.get("tekenend_accountant") else "",
                    vermelding["document_id"],
                ]
            )

    rapport.close()
    duur = time.monotonic() - begin
    documenten = sum(gelezen.values())
    for zoekvraag, aantal in gelezen.items():
        telling[f"documenten {zoekvraag}"] = aantal
    afgekapt = documenten >= argumenten.maximum

    # De vestigingsplaats aanvullen waar die nog leeg is. Pas na de doorloop,
    # omdat dan pas te zien is of alle lezingen het over één plaats eens zijn.
    if db is not None:
        for organisatie_id, plaatsen in plaatsen_per_org.items():
            if gemeente_per_id.get(organisatie_id):
                continue
            plaats = enige_plaats(plaatsen, plaatsen_register)
            if plaats is None:
                telling["plaats niet vastgesteld"] += 1
                continue
            telling["plaats aangevuld"] += 1
            if schrijven:
                db.bijwerken(
                    "organisaties", f"id=eq.{organisatie_id}&gemeente=is.null",
                    {"gemeente": plaats},
                )

    if db is not None and not schrijven:
        # Wat --vervang na deze doorloop zou wissen: eigen rijen die deze
        # lezing niet opnieuw zag. Zo is vóór de echte run te zien hoeveel er
        # verdwijnt, en waarom (het rapport heeft de rest).
        oud = eigen_bronnen - {bron_id}

        def wist(rij: dict) -> bool:
            return rij.get("bron_id") in oud and rij.get("id") not in DIGIMV_ONDER_RAADSBRON

        verouderd = [s for s, rij in bestaand.items() if wist(rij)]
        blijft = {o for (o, _), rij in bestaand.items() if not wist(rij)}
        blijft.update(o for o, _ in ander_type)
        wezen = {
            o for o, _ in verouderd if o not in blijft and not kvk_per_id.get(o)
        }
        print(
            f"droogloop: --vervang zou {len(verouderd)} eigen rijen wissen die deze "
            f"lezing niet meer ziet, en hooguit {len(wezen)} organisaties opruimen "
            "(gunningen en signalen niet meegeteld)"
        )

    if db is not None and (argumenten.vervang or not schrijven):
        # Wissen mag alleen na een aantoonbaar volledige doorloop, per
        # zoekvraag gemeten tegen het totaal dat de bron zelf opgeeft (zie
        # reden_om_niet_te_wissen). De droogloop vraagt het ook, zodat vóór de
        # echte run te zien is of vervang zou wissen.
        totalen: dict[str, int | None] = {}
        for zoekvraag in raadsinformatie.ZOEKVRAGEN:
            try:
                totalen[zoekvraag] = raadsinformatie.totaal_documenten(zoekvraag=zoekvraag)
            except Exception as fout:  # noqa: BLE001 — geen totaal is ook een antwoord
                print(f"vervang: kon het brontotaal van '{zoekvraag}' niet opvragen ({fout})")
                totalen[zoekvraag] = None
        reden = reden_om_niet_te_wissen(gelezen, totalen, argumenten.maximum)
        if not schrijven:
            print(
                "droogloop: --vervang zou "
                + (f"niets wissen: {reden}" if reden else "wissen (elke zoekvraag volledig gelezen)")
                + f"; gelezen {gelezen}, opgegeven {totalen}"
            )
        elif reden:
            print(f"vervang: {reden}. De oude uitkomst blijft staan.")
        else:
            # Alles wat de huidige leesregels opnieuw zagen draagt nu het
            # nieuwe bron_id. De rest is de oude uitkomst — behalve de
            # DigiMV-rijen onder een raadsinformatie-bron_id (zie te_wissen).
            gewist = 0
            for oude_bron in oude_bronnen:
                voorwaarde = te_wissen(oude_bron)
                rijen = db.selecteer_alles("opdrachten", f"select=id&{voorwaarde}")
                if not rijen:
                    continue
                db.verwijderen("opdrachten", voorwaarde)
                gewist += len(rijen)
            # Wezen: organisaties die alleen voor zo'n gewiste rij bestonden.
            # Alleen zonder KvK-nummer (mét nummer komt ze uit een register) en
            # zonder resterende opdrachten, gunningen of signalen.
            met_rij: set[int] = set()
            for tabel in ("opdrachten", "gunningen", "signalen"):
                met_rij.update(
                    rij["organisatie_id"]
                    for rij in db.selecteer_alles(tabel, "select=organisatie_id")
                )
            wezen = [
                organisatie_id
                for organisatie_id in sorted(geraakt)
                if organisatie_id not in met_rij
                and not kvk_per_id.get(organisatie_id)
            ]
            for organisatie_id in wezen:
                db.verwijderen("organisaties", f"id=eq.{organisatie_id}")
            print(
                f"vervang: {gewist} verouderde opdrachten gewist, "
                f"{len(wezen)} organisaties zonder resterende rijen opgeruimd"
            )

    print(f"\n{documenten} documenten gelezen in {duur:.0f} s")
    if afgekapt:
        # Beide zoekvragen samen telden 25.622 documenten (5-10-2026) bij een
        # plafond van 40.000. Groeit de bron daar ooit overheen, dan is deze
        # regel het enige dat het verklapt — de lus stopt gewoon.
        print(
            f"LET OP: afgekapt op --maximum {argumenten.maximum}; "
            "de bron bevat meer. Draai met een hoger maximum."
        )
    print(f"Uitkomst: {dict(sorted(telling.items()))}")
    if wachtend:
        print("Wacht op sector overheid (zet de sector recht, dan landen deze bij de volgende run):")
        for regel in wacht_overzicht(wachtend):
            print(regel)
    if nieuwe_rijen_per_jaar:
        print(f"Nieuwe controles per boekjaar: {dict(sorted(nieuwe_rijen_per_jaar.items()))}")
    if oordeel_per_jaar:
        print("Geschreven oordelen per boekjaar:")
        for jaar in sorted({jaar for jaar, _ in oordeel_per_jaar}):
            per_soort = {
                soort: aantal for (j, soort), aantal in sorted(oordeel_per_jaar.items())
                if j == jaar
            }
            print(f"  {jaar}: {per_soort}")
    if afgekeurd:
        print("\nNamen die geen organisatie bleken (top 10):")
        for naam, aantal in afgekeurd.most_common(10):
            print(f"  {aantal:4d}x  {naam}")
    print(f"\nRapport: {rapport_pad}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


