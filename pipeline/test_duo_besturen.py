"""Test: wie een schoolbestuur is, en wanneer een naam daar niets over zegt.

Zonder netwerk: verzonnen besturen in de vorm van de DUO-lijsten, plus een
paar eisen aan de seed zoals die in de repository staat. De regel die hier
bewaakt wordt is "precies één KvK-nummer, anders niets" — een schoolbestuur
op naam aan het verkeerde nummer hangen is erger dan het in overheid laten
staan.
"""

import csv
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "adapters"))

from duo_besturen import (  # noqa: E402
    SEED_PAD,
    bij_aanmaak,
    bouw_index,
    bouw_seed,
    kern,
    kvk_nummers,
    lees_besturen,
    lees_rio,
    review_filter,
    review_kandidaat,
    zoek_kvk,
    zonder_plaatsstaart,
)

goed = 0
fout = 0


def check(omschrijving: str, voorwaarde: bool) -> None:
    global goed, fout
    if voorwaarde:
        goed += 1
    else:
        fout += 1
        print(f"  FOUT: {omschrijving}")


# Zelfde kolommen en dezelfde BOM als de echte besturenlijst; verzonnen inhoud.
LIJST_BO = (
    "\ufeff\"BEVOEGD GEZAG NUMMER\",\"BEVOEGD GEZAG NAAM\",\"PLAATSNAAM\",\"KVK-NUMMER\"\n"
    "\"90001\",\"Stg. Openb. Prim. Onderw. Testdorp\",\"TESTDORP\",\"1234567\"\n"
    "\"90002\",\"Gemeente Testdam\",\"TESTDAM\",\"90000002\"\n"
    "\"90003\",\"Vereniging Scholen met de Bijbel Testveen\",\"TESTVEEN\",\"90000003\"\n"
    "\"90004\",\"Stichting Scholen met de Bijbel Testveen\",\"TESTVEEN\",\"90000004\"\n"
    "\"90005\",\"Stichting Testkring\",\"TESTKRING\",\"90000005\"\n"
    "\"90006\",\"Stichting Testkring\",\"ANDERDORP\",\"90000006\"\n"
    "\"90007\",\"Iris\",\"TESTSTAD\",\"90000007\"\n"
    "\"90008\",\"Onderwijsgroep Testrivier\",\"TESTSTAD\",\"90000008\"\n"
    "\"90009\",\"St. Testmichael Onderwijs\",\"TESTSTAD\",\"90000009\"\n"
    "\"90010\",\"Zonder Nummer Testschool\",\"TESTSTAD\",\"\"\n"
    # Twee verenigingen die alleen in hun plaatsstaart verschillen.
    "\"90012\",\"Vereniging voor Testonderwijs te Testhoeve\",\"TESTHOEVE\",\"90000012\"\n"
    "\"90013\",\"Vereniging voor Testonderwijs\",\"TESTLAND\",\"90000013\"\n"
    "\"90014\",\"Stichting Testkunde te Testveld\",\"TESTVELD\",\"90000014\"\n"
)
LIJST_MBO = (
    "\"BEVOEGD GEZAG NUMMER\",\"BEVOEGD GEZAG NAAM\",\"KVK-NUMMER\"\n"
    "\"90011\",\"Stg. ROC Testregio\",\"90000011\"\n"
)
RIO = (
    "\"ONDERWIJSBESTUURID\",\"KVK_NUMMER\",\"NAAM\",\"INTERNATIONALE_NAAM\"\n"
    # Een oudere naam van een bestuur uit de lijst: telt mee.
    "\"1B1\",\"90000008\",\"Stichting Openbaar Onderwijs Testrivier en Omstreken\",\"\"\n"
    # Een naam van een KvK-nummer búiten de lijsten: telt niet als bestuur,
    # maar maakt dezelfde naam bij een bestuur dubbelzinnig.
    "\"1B2\",\"90000099\",\"Onderwijsgroep Testrivier\",\"\"\n"
    # De gemeente in RIO: blijft buiten de lijst.
    "\"1B3\",\"90000002\",\"Gemeente Testdam\",\"\"\n"
    # Buiten de lijsten, en gelijk aan een bestuursnaam zonder zijn staart.
    "\"1B4\",\"90000098\",\"Stichting Testkunde\",\"\"\n"
)

besturen = lees_besturen(LIJST_BO, "bo") + lees_besturen(LIJST_MBO, "mbo")
check("een rij zonder KvK-nummer valt weg", len(besturen) == 13)
check(
    "een KvK-nummer van zeven cijfers krijgt zijn voorloopnul terug",
    besturen[0]["kvk"] == "01234567" and besturen[0]["bevoegd_gezag"] == "90001",
)
rio = lees_rio(RIO)
check("RIO wordt gelezen", len(rio) == 4)

seed = bouw_seed(besturen, rio)
nummers = {r["kvk"] for r in seed}
check("een gemeente is geen schoolbestuur", "90000002" not in nummers)
check("een RIO-nummer buiten de lijsten komt niet in de seed", "90000099" not in nummers)
check(
    "een oudere RIO-naam van een bestuur uit de lijst komt erbij",
    any(r["herkomst"] == "rio" and r["kvk"] == "90000008" for r in seed),
)
check(
    "een naam die in RIO ook bij een ander nummer hoort, is gemarkeerd",
    any(r["naam"] == "Onderwijsgroep Testrivier" and r["ook_elders"] == "ja" for r in seed),
)
index = bouw_index(seed)

check(
    "afkortingen uit de lijst vallen samen met de voluit geschreven naam",
    zoek_kvk("Stichting Openbaar Primair Onderwijs Testdorp", index) == "01234567",
)
check(
    "een plaatsstaart uit de verklaring maakt niet uit",
    zoek_kvk("Stichting Openbaar Primair Onderwijs Testdorp, gevestigd te Testdorp", index)
    == "01234567",
)
check(
    "zonder_plaatsstaart haalt '… te X' weg",
    zonder_plaatsstaart("Stichting Testkring te Testkring") == "Stichting Testkring",
)
check(
    "de rechtsvorm telt mee als beide namen er een hebben",
    zoek_kvk("Vereniging Scholen met de Bijbel Testveen", index) == "90000003"
    and zoek_kvk("Stichting Scholen met de Bijbel Testveen", index) == "90000004",
)
check(
    "zonder rechtsvorm is dezelfde kern dubbelzinnig: geen treffer",
    zoek_kvk("Scholen met de Bijbel Testveen", index) is None,
)
check(
    "twee besturen met dezelfde naam: geen treffer",
    zoek_kvk("Stichting Testkring", index) is None,
)
check(
    "ook_elders: geen treffer, ook al staat er maar één bestuur in de lijst",
    zoek_kvk("Onderwijsgroep Testrivier", index) is None,
)
check(
    "een oudere naam uit RIO vindt het bestuur",
    zoek_kvk("Stichting Openbaar Onderwijs Testrivier en Omstreken", index) == "90000008",
)
check("een te korte kern zegt niets", zoek_kvk("Stichting Iris", index) is None)
check(
    "een gemeentenaam is nooit een schoolbestuur",
    zoek_kvk("Gemeente Testdam", index) is None,
)
check(
    "'St.' is vooraan stichting en verderop sint",
    kern("St. Testmichael Onderwijs") == ("testmichaelonderwijs", "stichting")
    and kern("Onderwijsstichting St. Testmichael")[0] == "onderwijsstichtingsinttestmichael",
)
check(
    "een mbo-afkorting vindt het ROC",
    zoek_kvk("Stichting ROC Testregio", index) == "90000011",
)
# Zonder plaatsstaart heet de vereniging in Testhoeve net als die in Testland.
check(
    "de volle naam met plaats vindt het juiste bestuur",
    zoek_kvk("Vereniging voor Testonderwijs te Testhoeve", index) == "90000012",
)
check(
    "staart anders geschreven: zonder staart dubbelzinnig, geen treffer",
    zoek_kvk("Vereniging voor Testonderwijs, gevestigd te Testhoeve", index) is None,
)
check(
    "de kale naam is ook dubbelzinnig: er is er één met en één zonder plaats",
    zoek_kvk("Vereniging voor Testonderwijs", index) is None,
)
check(
    "'kort': alleen zonder staart botst de naam met een naam buiten de lijsten",
    any(r["naam"] == "Stichting Testkunde te Testveld" and r["ook_elders"] == "kort" for r in seed),
)
check(
    "met 'kort' werkt de volle naam nog, de naam zonder staart niet",
    zoek_kvk("Stichting Testkunde te Testveld", index) == "90000014"
    and zoek_kvk("Stichting Testkunde, gevestigd te Testveld", index) is None,
)

# bij_aanmaak: wat laad_gunningen en laad_raadsinformatie bij een nieuwe naam
# doen. Nooit een KvK-nummer op naam: een naam is geen harde sleutel.
nieuw = bij_aanmaak("Stichting ROC Testregio", "overheid", set(), index)
check(
    "een schoolbestuur wordt onderwijs; het nummer is een kandidaat, geen toekenning",
    nieuw == {"sector": "onderwijs", "kvk_kandidaat": "90000011", "mogelijk_dubbel": False}
    and "kvk_nummer" not in nieuw,
)
bezet = bij_aanmaak("Stichting ROC Testregio", "overheid", {"90000011": {"id": 7}}, index)
check(
    "staat het nummer al op een andere rij: dezelfde kandidaat, en mogelijk dubbel",
    bezet == {"sector": "onderwijs", "kvk_kandidaat": "90000011", "mogelijk_dubbel": True},
)
check(
    "geen schoolbestuur: de standaardsector, zonder kandidaat",
    bij_aanmaak("Veiligheidsregio Testland", "overheid", set(), index)
    == {"sector": "overheid", "kvk_kandidaat": None, "mogelijk_dubbel": False},
)
regel = review_kandidaat("tenderned", nieuw, [12])
check(
    "de kandidaat gaat naar de review: alleen de id, het nummer en de reden",
    regel["soort"] == "naam_match"
    and regel["payload"]["organisatie_ids"] == [12]
    and regel["payload"]["kvk_nummer"] == "90000011"
    and regel["payload"]["reden"] == "kvk-kandidaat op naam, niet toegekend"
    and not any("naam" in sleutel or "organisatie" == sleutel for sleutel in regel["payload"]),
)
dubbel = review_kandidaat("raadsinformatie", bezet, [12, 7])
check(
    "bij mogelijk dubbel: reden 'mogelijk dubbel' en beide id's, gesorteerd",
    dubbel["payload"]["reden"] == "mogelijk dubbel"
    and dubbel["payload"]["organisatie_ids"] == [7, 12]
    and dubbel["payload"]["kvk_nummer"] == "90000011"
    and not any("naam" in sleutel or "organisatie" == sleutel for sleutel in dubbel["payload"]),
)
check(
    "het dubbelfilter zoekt een open naam_match-regel op het nummer",
    review_filter("90000011")
    == "soort=eq.naam_match&status=eq.open&payload->>kvk_nummer=eq.90000011",
)

# De seed in de repository.
with SEED_PAD.open(encoding="utf-8") as f:
    echte_seed = list(csv.DictReader(f))
echte_nummers = kvk_nummers()
check("de seed heeft meer dan duizend schoolbesturen", len(echte_nummers) > 1000)
check(
    "elk KvK-nummer in de seed heeft acht cijfers",
    all(re.fullmatch(r"\d{8}", r["kvk"]) for r in echte_seed),
)
check(
    "geen gemeente in de seed",
    not any(re.match(r"(?i)\W*gemeente\b", r["naam"]) for r in echte_seed),
)
check(
    "alleen organisatiekolommen: geen adres, telefoon of website",
    set(echte_seed[0].keys())
    == {"kvk", "naam", "herkomst", "soort", "bevoegd_gezag", "ook_elders"},
)
check(
    "elk nummer in de seed staat in een besturenlijst, niet alleen in RIO",
    {r["kvk"] for r in echte_seed if r["herkomst"] == "besturenlijst"} == echte_nummers,
)

print(f"{goed}/{goed + fout} goed")
sys.exit(1 if fout else 0)
