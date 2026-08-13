"""In welke volgorde de oogst zijn tussenstand vastlegt.

Draaien vanuit de repo-root (geen testframework nodig, geen netwerk):

    python3 pipeline/test_oogst_volgorde.py

Waarom dit bestand bestaat: de oogst draait in een omgeving die elk half uur
opnieuw begint, en `.cache` overleeft dat niet. Alles hangt daarom aan de
volgorde waarin twee bestanden groeien — het rapport met de opdrachten, en
verwerkt_<jaar>.txt met "deze heb ik gehad". Staat een KvK-nummer eenmaal in dat
tweede bestand, dan slaat elke volgende run hem over. Voor altijd.

Gaat die volgorde de verkeerde kant op, dan levert een afbreking precies tussen
de twee schrijfacties een organisatie op die als afgehandeld geldt terwijl zijn
opdracht nergens staat. Dat is stil en onherstelbaar: geen foutmelding, geen
ontbrekende rij die opvalt, alleen een verklaring die nooit meer wordt gelezen.

Dit zijn structuurcontroles op de broncode, geen gedragstests. Ze kunnen niet
aantonen dát het goed gaat; ze kunnen wel voorkomen dat de volgorde ongemerkt
terugdraait bij een latere bewerking. Voor zoiets is dat het verschil tussen een
regel die je moet onthouden en een regel die zichzelf verdedigt.
"""

from pathlib import Path

fouten = 0
gedaan = 0


def controleer(omschrijving: str, goed: bool, detail: str = "") -> None:
    global fouten, gedaan
    gedaan += 1
    fouten += not goed
    print(f"{'✓' if goed else '✗'} {omschrijving}")
    if not goed and detail:
        print(f"    {detail}")


WORTEL = Path(__file__).resolve().parent
lader = (WORTEL / "laad_zorg.py").read_text(encoding="utf-8").splitlines()
script = (WORTEL / "oogst_zorg.sh").read_text(encoding="utf-8").splitlines()


def regel_met(regels: list[str], fragment: str, vanaf: int = 0) -> int:
    """Regelnummer (0-gebaseerd) van de eerste regel die het fragment bevat."""
    for i in range(vanaf, len(regels)):
        if fragment in regels[i]:
            return i
    return -1


def alle_regels_met(regels: list[str], fragment: str) -> list[int]:
    return [i for i, r in enumerate(regels) if fragment in r]


# --- de lader -----------------------------------------------------------------

schrijfacties = alle_regels_met(lader, "verwerkt_log.write(")
controleer(
    "er is precies één plek die 'bekeken' opschrijft",
    len(schrijfacties) == 1,
    f"gevonden op regel(s): {[n + 1 for n in schrijfacties]}",
)

definitie = regel_met(lader, "def noteer_bekeken(")
controleer(
    "en die zit in noteer_bekeken()",
    definitie != -1 and schrijfacties and definitie < schrijfacties[0],
    "de schrijfactie hoort achter één deur, niet los in de lus",
)

aanroepen = [n for n in alle_regels_met(lader, "noteer_bekeken(") if n != definitie]
controleer(
    "elke uitgang van de lus komt er langs",
    len(aanroepen) == 3,
    f"{len(aanroepen)} aanroepen op regel(s) {[n + 1 for n in aanroepen]} — "
    "verwacht: geen resultaat, kantoor onbekend, en het normale einde",
)

# De kern. In de lus staat eerst de afhandeling van 'geen resultaat' (die mag
# meteen noteren, er valt niets te bewaren), dan de rapportregel, en pas daarna
# de aantekening voor een organisatie die wél iets opleverde.
geen_resultaat = regel_met(lader, "if not resultaat:")
rapport_flush = regel_met(lader, "rapport.flush()")
laatste_aanroep = max(aanroepen) if aanroepen else -1

controleer(
    "de aantekening voor een treffer komt ná het flushen van de rapportregel",
    rapport_flush != -1 and laatste_aanroep > rapport_flush,
    f"rapport.flush() op regel {rapport_flush + 1}, "
    f"laatste noteer_bekeken op regel {laatste_aanroep + 1}",
)

vroege = [n for n in aanroepen if n < geen_resultaat]
controleer(
    "niets noteert 'bekeken' vóórdat de uitkomst bekend is",
    not vroege,
    f"aanroep(en) vóór 'if not resultaat' op regel(s) {[n + 1 for n in vroege]}",
)

controleer(
    "de pdf's worden pas opgeruimd in diezelfde functie",
    definitie != -1 and regel_met(lader, "pdf.unlink(") > definitie,
    "opruimen is onomkeerbaar en hoort dus bij het moment van afschrijven",
)

# --- het script ---------------------------------------------------------------

controleer(
    "het script bewaart ook tijdens een blok",
    regel_met(script, "BEWAARKLOK") != -1 and regel_met(script, 'sleep "$BEWAARKLOK"') != -1,
    "zonder tussentijds bewaren kost elke herstart het hele lopende blok",
)

klok_stil = regel_met(script, 'kill "$KLOK"')
python_aanroep = regel_met(script, "laad_zorg.py")
eigen_bewaar = -1
for i in range(klok_stil + 1, len(script)):
    if script[i].strip() == "bewaar":
        eigen_bewaar = i
        break
controleer(
    "de bewaarklok gaat uit vóór het script zelf bewaart",
    klok_stil > python_aanroep and eigen_bewaar > klok_stil,
    "twee git-commits tegelijk vechten om index.lock",
)

controleer(
    "een rapport dat midden in een regel eindigt wordt niet bewaard",
    regel_met(script, 'tail -c 1 "$RAPPORT"') != -1,
    "tijdens een blok wordt er doorgeschreven; een halve regel gaat de database in",
)

print(f"\n{gedaan - fouten}/{gedaan} goed")
raise SystemExit(1 if fouten else 0)
