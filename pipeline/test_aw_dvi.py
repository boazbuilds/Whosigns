"""Leesregels van de dVi-adapter, op de vormen die de bron echt heeft.

Alle gevallen hieronder zijn overgenomen uit een echte jaargang; erboven staat
welke. De jaargangen 2007 t/m 2013 zijn het lastigst: die gebruiken de interne
veldnamen van het dVi-model in plaats van leesbare koppen.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "adapters"))
sys.path.insert(0, str(Path(__file__).resolve().parent / "extractie"))

import aw_dvi  # noqa: E402

fouten = 0
gedaan = 0


def controleer(omschrijving: str, goed: bool, detail: str = "") -> None:
    global fouten, gedaan
    gedaan += 1
    fouten += not goed
    print(f"{'✓' if goed else '✗'} {omschrijving}")
    if not goed and detail:
        print(f"    {detail}")


# --- welke kolom is de accountant? -----------------------------------------
#
# dVi2008 heeft er drie, en op kolomvolgorde wint de persoonsnaam. Zou die
# gekozen worden, dan kwam "Drs. H.D.M. Plomp RA" als accountantskantoor in de
# database.
kop_2008 = {
    "A": "IdCorp_J08",
    "B": "CorpGeg_AccountantNaam_j0808",
    "C": "CorpGeg_AccountantOrg_j0808",
    "D": "CorpGeg_AccountantPlaats_j0808",
    "E": "CorpGeg_StatNm_DB_j0808",
    "F": "CorpGeg_NmGemVest_DB_j0808",
}
kolommen = aw_dvi._kolommen(kop_2008)
controleer(
    "dVi2008: de organisatiekolom wint van de persoonsnaam",
    kolommen and kolommen["accountant"] == "C",
    f"gevonden: {kolommen}",
)
controleer(
    "dVi2008: naam, gemeente en corporatienummer worden herkend",
    kolommen
    and kolommen.get("naam") == "E"
    and kolommen.get("gemeente") == "F"
    and kolommen.get("instellingsnummer") == "A",
    f"gevonden: {kolommen}",
)

# dVi2007 heeft maar één accountantkolom, en die heet ook Org.
kolommen = aw_dvi._kolommen(
    {
        "A": "IdCorp_j07",
        "B": "CorpGeg_StatNm_DB_j0707",
        "C": "CorpGeg_NmGemVest_DB_j0707",
        "D": "CorpGeg_WSWDeeln_j0707",
        "E": "CorpGeg_AccountantOrg_j0707",
    }
)
controleer(
    "dVi2007: één accountantkolom, naam en gemeente uit de modelveldnamen",
    kolommen
    and kolommen["accountant"] == "E"
    and kolommen.get("naam") == "B"
    and kolommen.get("gemeente") == "C",
    f"gevonden: {kolommen}",
)

# De nieuwere jaargangen hebben leesbare koppen; die mogen niet stukgaan.
kolommen = aw_dvi._kolommen(
    {"A": "L-nummer", "B": "Instellingsnaam", "C": "Gemeente",
     "D": "KvK-nummer", "E": "Accountant"}
)
controleer(
    "dVi2022: de leesbare koppen blijven werken",
    kolommen and kolommen["accountant"] == "E" and kolommen.get("naam") == "B",
    f"gevonden: {kolommen}",
)

# Een blad zonder accountantkolom levert niets op; anders zou de lezer het
# verkeerde blad pakken.
controleer(
    "een blad zonder accountant telt niet",
    aw_dvi._kolommen({"A": "Instellingsnaam", "B": "Gemeente"}) is None,
)

# --- het KvK-nummer ---------------------------------------------------------
#
# dVi2010 schrijft 1032035, dVi2013 schrijft 01032035 voor dezelfde corporatie.
# Zonder gelijktrekken staat die corporatie twee keer in de database.
controleer(
    "KvK-nummers krijgen allemaal acht cijfers",
    aw_dvi._schoon_kvk("1032035") == "01032035"
    and aw_dvi._schoon_kvk("01032035") == "01032035"
    and aw_dvi._schoon_kvk("24112244") == "24112244",
    f"gevonden: {aw_dvi._schoon_kvk('1032035')}",
)
controleer(
    "een leeg of onleesbaar KvK-nummer blijft leeg",
    aw_dvi._schoon_kvk("") == "" and aw_dvi._schoon_kvk("n.v.t.") == "",
)

# --- een KvK-kolom die stelselmatig is afgerond -----------------------------
#
# dVi2010 t/m 2012 slaan het KvK-nummer op als getal met te weinig precisie,
# waardoor het laatste cijfer wegvalt: 14614733 wordt 14614730. Zo'n nummer
# wijst naar niemand, dus elke corporatie kwam er een tweede keer bij — 164
# dubbele corporaties in één lading, voordat dit werd gevangen.
afgerond = [f"1461{n:03d}0" for n in range(100, 190)] + ["14614733", "16024737"]
controleer(
    "een kolom waarin bijna alles op nul eindigt wordt geweigerd",
    aw_dvi.kvk_kolom_is_afgerond(afgerond),
    f"aandeel: {sum(1 for w in afgerond if w.endswith('0')) / len(afgerond):.2f}",
)

# Twaalf procent op nul is toeval, geen afronding: dat is precies wat dVi2013
# en dVi2014 laten zien en die kolommen moeten gewoon bruikbaar blijven.
echt = [f"146147{n:02d}" for n in range(0, 100)]
controleer(
    "een normale kolom blijft bruikbaar",
    not aw_dvi.kvk_kolom_is_afgerond(echt),
    f"aandeel: {sum(1 for w in echt if w.endswith('0')) / len(echt):.2f}",
)
controleer(
    "een handvol waarden is te weinig om over te oordelen",
    not aw_dvi.kvk_kolom_is_afgerond(["10000000", "20000000", "30000000"]),
)

# --- wanneer is de corporatienummer-brug nodig? -----------------------------
#
# De weigering hierboven had een staart die pas later opviel: de lader bouwde de
# brug alleen voor boekjaren vóór 2010, dus 2010 t/m 2012 hielden een geweigerde
# kolom én geen brug over. Alle 1.169 rijen vielen om als `geen_kvk` en die drie
# jaargangen leverden nul opdrachten. Met de brug erbij: 369, 371 en 375.
controleer(
    "geen enkel KvK-nummer (2007-2009, of een geweigerde kolom): brug nodig",
    aw_dvi.brug_nodig([
        {"kvk_nummer": "", "instellingsnummer": "L0013"},
        {"kvk_nummer": "", "instellingsnummer": "L0021"},
    ]),
)
controleer(
    "een jaargang met eigen KvK-nummers heeft de brug niet nodig",
    not aw_dvi.brug_nodig([
        {"kvk_nummer": "14614733", "instellingsnummer": "L0013"},
        {"kvk_nummer": "", "instellingsnummer": "L0021"},
    ]),
)
controleer(
    "een lege jaargang vraagt niet om een brug",
    not aw_dvi.brug_nodig([]),
)

# --- de kantoornaam ---------------------------------------------------------
#
# De opgave is met de hand ingevuld. Deze schrijfwijzen komen letterlijk voor.
GEVALLEN = [
    ("BDO CampsObers Audit & Assurance B.V.", "BDO Audit & Assurance B.V."),
    ("BDO Camps Obers Accountants", "BDO Audit & Assurance B.V."),
    ("BDO ChampsObers Audit & Assurance B.V.", "BDO Audit & Assurance B.V."),
    ("B.D.O. CampsObers Accountants", "BDO Audit & Assurance B.V."),
    ("BDO A&A", "BDO Audit & Assurance B.V."),
    ("Price Waterhouse Coopers Accountants NV", "PricewaterhouseCoopers Accountants N.V."),
    ("PricewatrerhouseCoopers", "PricewaterhouseCoopers Accountants N.V."),
    ("PricewaterhouseCoopersAccountants N.V.", "PricewaterhouseCoopers Accountants N.V."),
    ("Deloiite Accountants BV", "Deloitte Accountants B.V."),
    ("Deloittte Accountants BV", "Deloitte Accountants B.V."),
    ("Berk N.V.", "Baker Tilly (Netherlands) B.V."),
    ("GIBO Registeraccountants B.V.", "Flynth Audit B.V."),
    ("Ernst & Young Accountants LLP", "EY Accountants B.V."),
    # Hieronder de schrijfwijzen die in de review-queue bleven hangen: 84 rijen
    # over alle jaargangen, waarvan deze 56 aantoonbaar tikfouten waren van een
    # kantoor dat gewoon in het register staat. Ze staan er allemaal letterlijk zo.
    #
    # De les eruit: een patroon dat de hele naam uitspelt overleeft de tikfout
    # niet. Op "Coopers" viel elk van deze vijf om.
    ("PricewaterhouseCooper Accountants N.V.", "PricewaterhouseCoopers Accountants N.V."),
    ("PricewaterhouseCoupers Accountants N.V.", "PricewaterhouseCoopers Accountants N.V."),
    ("PricewaterhoudseCoopers Accountants N.V.", "PricewaterhouseCoopers Accountants N.V."),
    ("PriceWaterhouseCoorpers Accountants N.V.", "PricewaterhouseCoopers Accountants N.V."),
    ("PricewaterhouseC oopers Accountants N.V.", "PricewaterhouseCoopers Accountants N.V."),
    # De voornaam van Ernst & Young is op vijf manieren verhaspeld; "Young" niet
    # één keer. Een losse "EY" en "E & Y" komen ook voor.
    ("Enst&Young Accountants", "EY Accountants B.V."),
    ("Enrst & Young Accountants LLP", "EY Accountants B.V."),
    ("Erns & Young Accountants LLP", "EY Accountants B.V."),
    ("Ersnt & Young", "EY Accountants B.V."),
    ("Ernst & Young Accountant's LLP", "EY Accountants B.V."),
    ("E & Y Accountants LLP", "EY Accountants B.V."),
    ("EY AccountantsLLP", "EY Accountants B.V."),
    ("KMPG Accountants N.V.", "KPMG Accountants N.V."),
    # Aan elkaar geplakt; op een afsluitende woordgrens viel dit af.
    ("BDOAudit & Assurance B.V.", "BDO Audit & Assurance B.V."),
    ("BakerTillyBerk", "Baker Tilly (Netherlands) B.V."),
    ("Baker Tily Berk", "Baker Tilly (Netherlands) B.V."),
    ("Verstegen accountatns en adviseurs", "Verstegen accountants en adviseurs B.V."),
    ("Verstegen Accountants & Adviseuers", "Verstegen accountants en adviseurs B.V."),
    ("Verstegen accountants en advisuers", "Verstegen accountants en adviseurs B.V."),
    # Naam van de vergunninghouder tot de rebranding. Het transparantieverslag
    # over 2016 van het kantoor zelf zegt het met zoveel woorden: "De wettelijke
    # controleactiviteiten zijn ondergebracht in Mazars Paardekooper Hoffman
    # Accountants N.V.", statutair gevestigd te Rotterdam en vergunninghouder
    # voor wettelijke controles inclusief OOB's. Het AFM-register kent precies
    # één Rotterdamse OOB-vergunning op mazars.nl: 13000408.
    ("Mazars Paardekooper Hoffman Accountants N.V.", "Forvis Mazars Accountants N.V."),
    ("Mazars Paardekoper Hoffman N.V.", "Forvis Mazars Accountants N.V."),
    ("Mazars Paardekooper en Hoffman NV", "Forvis Mazars Accountants N.V."),
]
for ruw, verwacht in GEVALLEN:
    gevonden = aw_dvi.normaliseer_kantoornaam(ruw, afm={})
    controleer(f"naam: {ruw!r}", gevonden == verwacht, f"gevonden: {gevonden!r}")

# Wat níét herkend wordt moet ongewijzigd terugkomen, zodat de lader het in de
# review-queue zet in plaats van te gokken.
for onbekend in (
    "Accountantskantoor E. Nikkels AA",
    "Du Roi Accountants & Belastingadviseurs B.V.",
    "Van den Berk & Partners",
    # Deze staan nog in de review-queue en dat hoort zo: geen van drieën staat in
    # het AFM-register, en raden is hier erger dan wachten.
    "Tjakkes Riethorst Nijssen",
    "Westpark registeraccountants belastingadviseurs",
    "Accon AVM",
    # De naam van vóór de aansluiting bij Mazars (dVi2007). Zonder "Mazars"
    # ernaast mag die niet op eigen houtje aan vergunning 13000408 worden
    # gehangen — dat zou een toeschrijving zijn die nergens uit blijkt.
    "Paardekooper en Hoffman NV",
):
    gevonden = aw_dvi.normaliseer_kantoornaam(onbekend, afm={})
    controleer(
        f"onbekend blijft onbekend: {onbekend!r}",
        gevonden == onbekend,
        f"gevonden: {gevonden!r}",
    )

# Zelf tellen. Het totaal stond hier als een som met de hand bijgehouden, en die
# liep achter: drie nieuwe controles erbij en er stond nog steeds 27/27.
print(f"\n{gedaan - fouten}/{gedaan} goed")
raise SystemExit(1 if fouten else 0)
