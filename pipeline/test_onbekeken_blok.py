"""Welke organisaties het volgende blok van de oogst pakt.

Draaien vanuit de repo-root (geen testframework nodig, geen netwerk):

    python3 pipeline/test_onbekeken_blok.py

Waarom dit bestand bestaat: de oogst leest een boekjaar in blokken en bewaart na
elk blok, want de omgeving waarin hij draait begint elk half uur opnieuw. Welk
blok aan de beurt is werd afgeleid uit een index in de doelpopulatie — "vanaf
2078" betekende stilzwijgend "de eerste 2078 zijn al gedaan".

Die aanname hield het niet. Toen heeft_verklaring() ook de verklaringen onder
locations[] ging meetellen, groeide boekjaar 2021 van 2.471 naar 2.678
organisaties, en de 207 nieuwe schoven ertussen in plaats van erachter. Gemeten
op 13-8-2026: van de 597 nog te lezen organisaties stonden er 125 op een index
ónder de hervatpositie, de laagste op index 14. Die zou de lopende oogst nooit
meer bekijken — niet als fout, gewoon als stilte.

Deze tests leggen vast dat er eerst wordt weggestreept en dan pas gesneden, en
dat de lus die daarop draait alles precies één keer aandoet.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from laad_zorg import onbekeken_blok  # noqa: E402

fouten = 0
gedaan = 0


def controleer(omschrijving: str, goed: bool, detail: str = "") -> None:
    global fouten, gedaan
    gedaan += 1
    fouten += not goed
    print(f"{'✓' if goed else '✗'} {omschrijving}")
    if not goed and detail:
        print(f"    {detail}")


def populatie(*kvks: str) -> list[dict]:
    return [{"kvk_nummer": k, "naam": f"Stichting {k}"} for k in kvks]


def nummers(blok: list[dict]) -> list[str]:
    return [o["kvk_nummer"] for o in blok]


# --- de basis -----------------------------------------------------------------

alles = populatie("a", "b", "c", "d", "e")

controleer(
    "zonder iets gezien komt de hele lijst terug, in volgorde",
    nummers(onbekeken_blok(alles, set())) == ["a", "b", "c", "d", "e"],
)

controleer(
    "wat gezien is valt eruit",
    nummers(onbekeken_blok(alles, {"b", "d"})) == ["a", "c", "e"],
)

controleer(
    "aantal=0 betekent alles, niet niets",
    len(onbekeken_blok(alles, set(), aantal=0)) == 5,
    "argparse geeft 0 als default; dat mag geen leeg blok opleveren",
)

controleer(
    "aantal snijdt de kop eraf",
    nummers(onbekeken_blok(alles, set(), aantal=2)) == ["a", "b"],
)

controleer(
    "de bronlijst blijft heel",
    len(alles) == 5,
    "onbekeken_blok mag zijn invoer niet aanpassen",
)

# --- waar het misging ---------------------------------------------------------
#
# De populatie groeide: "n1" en "n2" kwamen erbij op index 1 en 3. Al bekeken
# zijn "a", "b" en "c" — de eerste drie van de oude lijst.

gegroeid = populatie("a", "n1", "b", "n2", "c", "d")
gezien = {"a", "b", "c"}

controleer(
    "de nieuwe tussenvoegingen komen terug, ook al staan ze vooraan",
    nummers(onbekeken_blok(gegroeid, gezien)) == ["n1", "n2", "d"],
)

controleer(
    "vanaf telt in de nog-te-doen lijst, niet in de volle populatie",
    nummers(onbekeken_blok(gegroeid, gezien, vanaf=1)) == ["n2", "d"],
    "vanaf=1 slaat n1 over, niet 'a'",
)

# Dit is precies de regressie. Sneed je eerst op index en streepte je daarna pas
# weg, dan gaf "vanaf 3" (drie bekeken) alleen nog n2, c en d — n1 viel eruit en
# kwam nooit meer terug.
oud = [o for o in gegroeid[3:] if o["kvk_nummer"] not in gezien]
controleer(
    "de oude volgorde liet er eentje vallen; de nieuwe niet",
    nummers(oud) == ["n2", "d"] and "n1" in nummers(onbekeken_blok(gegroeid, gezien)),
    f"oud: {nummers(oud)}",
)

# --- de lus van oogst_zorg.sh -------------------------------------------------
#
# Het script vraagt steeds opnieuw `--vanaf 0 --aantal BLOK` en schrijft elke
# behandelde organisatie in verwerkt_<jaar>.txt. Deze simulatie doet dat na en
# controleert wat de lus waard is: alles één keer, en hij stopt uit zichzelf.

groot = populatie(*[f"k{i:04d}" for i in range(97)])
verwerkt: set[str] = set()
volgorde: list[str] = []
rondes = 0
while True:
    blok = onbekeken_blok(groot, verwerkt, vanaf=0, aantal=4)
    if not blok:
        break
    rondes += 1
    for organisatie in blok:
        verwerkt.add(organisatie["kvk_nummer"])
        volgorde.append(organisatie["kvk_nummer"])
    if rondes > 200:  # noqa: S101 — vangnet, mag nooit aanslaan
        break

controleer(
    "de lus stopt uit zichzelf",
    rondes == 25,
    f"rondes: {rondes} (97 organisaties in blokken van 4 = 24 volle en 1 restje)",
)

controleer(
    "elke organisatie is precies één keer aan de beurt geweest",
    len(volgorde) == 97 and len(set(volgorde)) == 97,
    f"{len(volgorde)} behandeld, {len(set(volgorde))} uniek",
)

controleer(
    "en in de volgorde van de bron",
    volgorde == nummers(groot),
)

# Een organisatie die halverwege bij de populatie komt, komt alsnog aan de beurt
# — ook als hij vooraan in de lijst wordt ingevoegd nadat de oogst al liep.
laat = populatie("nieuw") + groot
controleer(
    "een organisatie die er later bij komt wordt alsnog opgepakt",
    nummers(onbekeken_blok(laat, verwerkt)) == ["nieuw"],
)

# --- de randen ----------------------------------------------------------------

controleer(
    "vanaf voorbij het einde geeft een leeg blok",
    onbekeken_blok(alles, set(), vanaf=999999) == [],
    "zo peilt oogst_zorg.sh de omvang zonder werk te doen",
)

controleer(
    "alles gezien geeft een leeg blok",
    onbekeken_blok(alles, {"a", "b", "c", "d", "e"}, aantal=4) == [],
    "dit is het signaal waarop de lus in oogst_zorg.sh afsluit",
)

controleer(
    "een lege populatie geeft een leeg blok",
    onbekeken_blok([], set(), aantal=4) == [],
)

controleer(
    "gezien mag namen bevatten die niet in de populatie staan",
    nummers(onbekeken_blok(alles, {"x", "y", "b"})) == ["a", "c", "d", "e"],
    "verwerkt_<jaar>.txt kan organisaties bevatten die de bron niet meer levert",
)

controleer(
    "een blok groter dan de rest levert gewoon de rest",
    nummers(onbekeken_blok(alles, {"a", "b", "c"}, aantal=99)) == ["d", "e"],
)

print(f"\n{gedaan - fouten}/{gedaan} goed")
raise SystemExit(1 if fouten else 0)
