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


def controleer(omschrijving: str, goed: bool, detail: str = "") -> None:
    global fouten
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
):
    gevonden = aw_dvi.normaliseer_kantoornaam(onbekend, afm={})
    controleer(
        f"onbekend blijft onbekend: {onbekend!r}",
        gevonden == onbekend,
        f"gevonden: {gevonden!r}",
    )

totaal = len(GEVALLEN) + 3 + 8
print(f"\n{totaal - fouten}/{totaal} goed")
raise SystemExit(1 if fouten else 0)
