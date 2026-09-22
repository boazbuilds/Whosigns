"""Test: de ondertekenaar mag alleen worden vastgelegd als hij het echt is.

Waarom dit bestaat. Sinds 20-8-2026 mag de naam van de tekenend accountant in de
database (`docs/concept.md` §9). Daarmee wordt een fout hier duurder dan elders:
een verkeerde kantoornaam is een correctie, een verkeerde persoonsnaam onder een
niet-goedkeurend oordeel is een beschuldiging. Leeg is gratis.

De gevallen hieronder komen niet uit de duim. Twee onafhankelijke ontwerpen zijn
op 20-8-2026 over 1.084 gecachte documenten met tekstlaag gedraaid en daarna
tegen elkaar gelegd; wat hier staat is wat die vergelijking opleverde aan manieren
om de vérkeerde naam te pakken:

- de begeleidende brief bij een accountantsverslag ("Hoogachtend, <kantoor>
  <naam> RA") — wel een naam achter een kantoornaam, geen controleverklaring;
- een zin uit het verslag van de raad van toezicht ("<kantoor>, vertegenwoordigd
  door <naam> RA") die de ondertekeningsdrempel haalt met de bonus die de
  ondertekenaar-regel zélf uitkeert;
- een afkortingenlijst waarin "RA x Registeraccountant" het naampatroon haalt —
  geen verkeerde persoon maar een verzónnen persoon;
- colofon, bijlage en dankwoord ná de verklaring;
- Nederlandse samenstellingen die door een filter op woordgrenzen glippen:
  auditcommissie, kascommissie, verantwoordingsorgaan, bestuurssecretaris;
- twee handtekeningen in één blok, die stil tot één werden platgeslagen.

En het geval dat de eerste versie van deze module zélf fout deed: élke
controleverklaring begint met "Aan: het bestuur van ..." of "Aan de raad van
toezicht van ...". Een rolfilter met een venster van tweehonderd tekens wijst
daardoor in een kort blok precies de goede naam af.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "extractie"))

from ondertekenaar import zoek_ondertekenaar  # noqa: E402
from verklaring import analyseer  # noqa: E402

goed = 0
fout = 0


def check(omschrijving: str, voorwaarde: bool) -> None:
    global goed, fout
    if voorwaarde:
        goed += 1
    else:
        fout += 1
        print(f"  FOUT: {omschrijving}")


KOP = "Controleverklaring van de onafhankelijke accountant"


def verklaring(ondertekening: str, oordeelzin: str = "Naar ons oordeel geeft de "
               "jaarrekening een getrouw beeld van de grootte en samenstelling "
               "van het vermogen.") -> str:
    return (
        f"{KOP}\n\n"
        "Aan: het bestuur van Stichting Voorbeeld\n\n"
        "Ons oordeel\n"
        f"{oordeelzin}\n\n"
        "Utrecht, 12 mei 2024\n\n"
        "Voorbeeld Accountants B.V.\n\n"
        f"{ondertekening}\n"
    )


# --- het gewone geval ----------------------------------------------------------
r = zoek_ondertekenaar(verklaring("was getekend\n\ndrs. J. Jansen RA"),
                       "Voorbeeld Accountants B.V.")
check("een gewone ondertekening levert de naam op", r["naam"] == "drs. J. Jansen RA")
check("en er blijft geen reden over", r["reden"] == "")
check("het blok wordt teruggegeven, zodat het oordeel erbij te zoeken is",
      r["blok"] is not None)

check(
    "de aanhef 'Aan: het bestuur van' mag de ondertekenaar niet wegfilteren; "
    "die staat in élke verklaring",
    zoek_ondertekenaar(
        f"{KOP}\n\nAan de raad van toezicht van Stichting Voorbeeld\n\n"
        "Naar ons oordeel geeft de jaarrekening een getrouw beeld.\n\n"
        "Utrecht, 12 mei 2024\n\nwas getekend\n\nA. de Vries RA\n"
    )["naam"] == "A. de Vries RA",
)

check(
    "een naam zonder aanhef werkt ook",
    zoek_ondertekenaar(verklaring("A.B. van der Meer RA"))["naam"]
    == "A.B. van der Meer RA",
)

# --- wat er géén ondertekenaar is ----------------------------------------------
check(
    "een zin uit het verslag van de raad van toezicht is geen ondertekening",
    zoek_ondertekenaar(
        "Verslag van de raad van toezicht\n\n"
        "De raad werd bijgestaan door Voorbeeld Accountants B.V., "
        "vertegenwoordigd door drs. P. Pietersen RA.\n"
    )["naam"] is None,
)

check(
    "een begeleidende brief zonder verklaring-kop levert niets op",
    zoek_ondertekenaar(
        "Betreft: jaarrekening 2023\n\nGeachte directie,\n\n"
        "Hierbij ontvangt u de jaarstukken.\n\nHoogachtend,\n\n"
        "Voorbeeld Accountants B.V.\n\ndrs. K. Klaassen RA\n"
    )["naam"] is None,
)

check(
    "een kop in de inhoudsopgave telt niet: er staat geen oordeelzin in dat blok",
    zoek_ondertekenaar(
        "Inhoudsopgave\n\n4.3 " + KOP + " .......... 98\n\n"
        "Utrecht, 12 mei 2024\n\ndrs. J. Jansen RA\n"
    )["naam"] is None,
)

check(
    "'was getekend' zonder naam geeft geen naam",
    zoek_ondertekenaar(verklaring("was getekend"))["naam"] is None,
)

check(
    "een afkortingenlijst levert geen verzonnen persoon op",
    zoek_ondertekenaar(
        verklaring("was getekend\n\nX. Registeraccountant RA")
    )["naam"] is None,
)

# --- rollen, ook als samenstelling ---------------------------------------------
for rol in ("auditcommissie", "kascommissie", "verantwoordingsorgaan",
            "bestuurssecretaris", "adviesraad", "ledenraad"):
    check(
        f"'{rol}' op dezelfde regel maakt het geen ondertekening",
        zoek_ondertekenaar(
            verklaring(f"was getekend\n\nLid {rol}: drs. J. Jansen RA")
        )["naam"] is None,
    )

check(
    "een kop 'Colofon' bóven de naam telt ook",
    zoek_ondertekenaar(
        verklaring("was getekend\n\nColofon\ndrs. J. Jansen RA")
    )["naam"] is None,
)

# --- meer dan één naam ---------------------------------------------------------
twee_in_blok = zoek_ondertekenaar(
    verklaring("was getekend\n\nA. Jansen RA\nA.Z. Pietersen RA")
)
check(
    "twee namen in hetzelfde handtekeningblok worden niet tot één gegokt",
    twee_in_blok["naam"] is None,
)

twee_blokken = zoek_ondertekenaar(
    verklaring("was getekend\n\ndrs. J. Jansen RA")
    + verklaring("was getekend\n\nA. de Vries RA")
)
check(
    "twee verschillende ondertekenaars in één document geven geen naam",
    twee_blokken["naam"] is None,
)
check(
    "en de afgewezen kandidaten gaan mee, zodat de review-queue iets heeft",
    len(twee_blokken["kandidaten"]) == 2,
)

# --- het kantoor moet kloppen ---------------------------------------------------
check(
    "een handtekening bij een ánder kantoor telt niet mee voor dit kantoor",
    zoek_ondertekenaar(
        f"{KOP}\n\nNaar ons oordeel geeft de jaarrekening een getrouw beeld.\n\n"
        "Rotterdam, 1 juni 2024\n\nHeel Ander Accountants B.V.\n\n"
        "was getekend\n\ndrs. J. Jansen RA\n",
        "Voorbeeld Accountants B.V.",
    )["naam"] is None,
)

# --- de koppeling met het oordeel ----------------------------------------------
# Dit is de reden dat `blok` wordt teruggegeven. `analyseer` bepaalt het oordeel
# over de hele tekst (eerste treffer wint) terwijl de naam uit één blok komt. In
# een jaarverslag met een goedkeurende jaarrekeningverklaring én een
# WNT-verklaring met beperking zou het anders willekeurig zijn welke naam bij
# welk oordeel belandt -- precies de twee stukken die de bron zelf ook door
# elkaar haalt.
gemengd = (
    verklaring("was getekend\n\ndrs. J. Jansen RA")
    + verklaring(
        "was getekend\n\ndrs. J. Jansen RA",
        oordeelzin="Naar ons oordeel, uitgezonderd de gevolgen van de "
        "aangelegenheid beschreven in de paragraaf 'De basis voor ons oordeel "
        "met beperking', geeft de WNT-verantwoording een getrouw beeld.",
    )
)
uit = analyseer(gemengd, {})
check(
    "bij twee blokken met een verschillend oordeel wordt er geen naam vastgelegd",
    uit["tekenend_accountant"] is None,
)

enkel = analyseer(verklaring("was getekend\n\ndrs. J. Jansen RA"), {})
check(
    "bij één blok komt de naam wél door analyseer heen",
    enkel["tekenend_accountant"] == "drs. J. Jansen RA",
)
check(
    "en het oordeel klopt nog steeds",
    enkel["oordeel"] == "goedkeurend",
)

leeg = analyseer("te kort", {})
check(
    "het vroege returndict voor een gescande pdf kent de sleutel ook; anders "
    "valt de lader om op een KeyError bij de eerste treffer",
    "tekenend_accountant" in leeg,
)

# --- hoofdletters en OCR-schade in de handtekeningregel ------------------------
#
# Gemeten op 22-9-2026 tegen de 4.260 bewaarde OCR-teksten in pipeline/oogst/ocr:
# van de 543 verklaringen waar wél tekst van was maar geen naam uit kwam, lag het
# bij 95 alleen aan de schrijfwijze. "Was getekend:" met een hoofdletter, "Drs.",
# "W.G." en "Origineel getekend door" haalden het patroon niet, want dat was
# hoofdlettergevoelig. De hele regex `re.I` maken mag juist níét — dan matcht
# `[A-Z]` ook kleine letters en wordt elk woord een initiaal.
for regel, verwacht in [
    ("Was getekend: P.G.M. Retra AA", "P.G.M. Retra AA"),
    ("Was getekend, H.M. Oprinsen RA", "H.M. Oprinsen RA"),
    ("Origineel getekend door drs. H.A.B. de Coninck RA", "drs. H.A.B. de Coninck RA"),
    ("Origineel getekend door: S. Stegeman MSc RA", "S. Stegeman MSc RA"),
    ("Drs. L. van der Stelt RA", "Drs. L. van der Stelt RA"),
    ("W.G. dhr. R. van Dijk RA", "dhr. R. van Dijk RA"),
]:
    check(
        f"de handtekeningregel {regel!r} levert de naam op",
        zoek_ondertekenaar(verklaring(regel), "Voorbeeld Accountants B.V.")["naam"]
        == verwacht,
    )

# De regel begint bij "Was getekend:", en dat is zélf het anker. Wie de afstand
# tot het anker meet vanaf de naam in plaats van vanaf het regelbegin, gooit
# precies die regels weg — vijf van de bestaande namen verdwenen daarop.
lang = (
    f"{KOP}\n\nNaar ons oordeel geeft de jaarrekening een getrouw beeld.\n\n"
    "Utrecht, 12 mei 2024\n\nVoorbeeld Accountants B.V.\n"
    + "." * 140
    + "\nWas getekend: drs. J. Jansen RA\n"
)
check(
    "een naam net binnen het venster blijft staan, ook met 'Was getekend:' ervoor",
    zoek_ondertekenaar(lang, "Voorbeeld Accountants B.V.")["naam"]
    == "drs. J. Jansen RA",
)

# --- het anker: wat OCR met de plaats-en-datumregel doet -----------------------
def met_datumregel(regel: str) -> str:
    return (
        f"{KOP}\n\nNaar ons oordeel geeft de jaarrekening een getrouw beeld.\n\n"
        f"{regel}\n\nVoorbeeld Accountants B.V.\n\ndrs. J. Jansen RA\n"
    )


for regel, omschrijving in [
    ("Middelburg, 12 Juni 2020", "een maandnaam met een hoofdletter"),
    ("osterwolde, 15 juni 2021", "een plaats waarvan OCR de eerste letter at"),
    ("\u2019s-Hertogenbosch, 16 juli 2021", "een plaats die met een apostrof begint"),
    ("Drachten, 24 juli-2020 _ Ss", "een streepje en een kras van de handtekening"),
    ("Leusden, 28 september 2021 / Al", "twee tekens rommel achter het jaartal"),
]:
    check(
        f"{omschrijving} telt nog steeds als ondertekeningsanker",
        zoek_ondertekenaar(met_datumregel(regel), "Voorbeeld Accountants B.V.")["naam"]
        == "drs. J. Jansen RA",
    )

# En de grens van die soepelheid: staat er een zin achter de datum, dan is het
# geen ondertekeningsregel maar lopende tekst, en dan is er geen anker.
check(
    "een datum midden in een zin is geen ondertekeningsanker",
    zoek_ondertekenaar(
        met_datumregel("De stichting, 12 mei 2024 opgericht, groeide hard"),
        "Voorbeeld Accountants B.V.",
    )["naam"]
    is None,
)

print(f"{goed}/{goed + fout} goed")
sys.exit(1 if fout else 0)
