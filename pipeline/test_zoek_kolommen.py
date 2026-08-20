"""Test: de koprij van de jaardataset is tweeregelig.

Waarom dit bestaat. `_zoek_kolommen` bepaalt uit de koprij welke kolom welk veld
is, op naam en niet op positie. De patronen in `VELDPATRONEN` zijn de
variabelenamen uit de bron (`ExternalOrganizationId`, `qAccountantWissel`,
`acc_jr_contr`). Maar een koprijcel bevat twéé regels: bovenaan het menselijke
label, eronder de variabelenaam:

    "Bent u van accountant gewisseld?\\nqAccountantWissel_qAccVerklVorm"

De vergelijking deed `startswith` op de hele cel. Die matchte dus geen enkel
patroon, `met_controle` bleef leeg en `doelpopulatie()` gaf nul organisaties
terug — zonder foutmelding. Dat het toch leek te werken kwam doordat
`doelpopulatie_uit_cache()` eerst een csv van 30 juli las die in CI via
actions/cache bleef staan. Verdween die cache, dan laadde `zorgdata.yml`
stilletjes niets.

De reparatie (20-8-2026) vergelijkt op de laatste regel van de cel. Gemeten tegen
`pipeline/.cache/digimv2023.ods`: 1.140 organisaties, rij voor rij en veld voor
veld gelijk aan `doelpopulatie_2023.csv`, inclusief de 301 expliciete `False` bij
`wissel_gerapporteerd`.

Deze test doet dat na op een verzonnen koprij in plaats van op het echte
.ods-bestand: dat bestand staat niet in de repo, en een test die alleen draait
als er toevallig 16 MB in de cache ligt bewaakt niets.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "adapters"))

from digimv_dataset import VELDPATRONEN, _zoek_kolommen  # noqa: E402

goed = 0
fout = 0


def check(omschrijving: str, voorwaarde: bool) -> None:
    global goed, fout
    if voorwaarde:
        goed += 1
    else:
        fout += 1
        print(f"  FOUT: {omschrijving}")


# Een koprij zoals de jaargang 2023 hem echt heeft: label, nieuwe regel,
# variabelenaam. De labels zijn letterlijk overgenomen uit digimv2023.ods.
KOPRIJ = [
    "Code\nConcernCode",
    "Kvk-nummer\nExternalOrganizationId",
    "Naam van de organisatie\nqNawNaam",
    "Vestigingsplaats\nqNawPlaats",
    "Rechtsvorm volgens KvK\nqRechtsvormKvK",
    "Bent u van accountant gewisseld?\nqAccountantWissel_qAccVerklVorm",
    "Honoraria accountant - Controle van de jaarrekening - Bedrag in euro's "
    "per einde boekjaar\nacc_jr_contr_acc_jr_contr_0",
    "Honoraria accountant - Controle van de jaarrekening - Bedrag in euro's "
    "per einde vorig boekjaar\nacc_jr_contr_acc_jr_contr_1",
    "Soort controleverklaring\nbestandAccVerklSoortControleVerkl_0",
    "Datum accountantsverklaring\nbestandDatumAccountantsverklaring_0",
]

kolommen = _zoek_kolommen(KOPRIJ)
velden = kolommen["velden"]

check("de kvk-kolom wordt gevonden ondanks de regel erboven", velden.get("kvk") == 1)
check("de naamkolom wordt gevonden", velden.get("naam") == 2)
check("de plaatskolom wordt gevonden", velden.get("plaats") == 3)
check("de rechtsvorm wordt gevonden", velden.get("rechtsvorm") == 4)
check("de wisselvraag wordt gevonden", velden.get("wisselvlag") == 5)
check(
    "het oordeel komt uit het documentveld, niet uit de vragenlijst",
    velden.get("oordeel_gerapporteerd") == 8,
)
check("de verklaringsdatum wordt gevonden", velden.get("verklaring_datum") == 9)

# Het honorarium heeft twéé kolommen die met hetzelfde patroon beginnen: dit
# boekjaar (_0) en het vorige (_1). De code pakt via next() de eerste treffer, en
# in de bron staat _0 links van _1. Zou die volgorde ooit omdraaien, dan stond
# hier stil het bedrag van het vórige boekjaar -- een fout die nergens opvalt,
# want het is een plausibel bedrag.
check(
    "het controlehonorarium pakt het lopende boekjaar (_0) en niet het vorige",
    velden.get("honorarium_controle") == 6,
)

# En de kern: zonder de reparatie matchte geen enkel patroon.
check(
    "er wordt meer dan één veld herkend; nul betekent dat de koprijvergelijking "
    "weer stuk is en doelpopulatie() stil leeg teruggeeft",
    len(velden) >= 7,
)

# Eenregelige koppen moeten blijven werken: oudere jaargangen hebben ze.
enkel = _zoek_kolommen(["ConcernCode", "c_kvk", "c_naam", "c_plaats"])
check(
    "een eenregelige koprij (oud exportformaat) werkt nog steeds",
    enkel["velden"].get("kvk") == 1 and enkel["velden"].get("naam") == 2,
)

# Witruimte rond de variabelenaam mag niets uitmaken.
met_spaties = _zoek_kolommen(["Code\nConcernCode", "Kvk\n  ExternalOrganizationId  "])
check(
    "spaties rond de variabelenaam worden genegeerd",
    met_spaties["velden"].get("kvk") == 1,
)

check(
    "VELDPATRONEN bevat nog de velden waar deze test op leunt",
    {"kvk", "naam", "wisselvlag", "honorarium_controle"} <= set(VELDPATRONEN),
)

print(f"{goed}/{goed + fout} goed")
sys.exit(1 if fout else 0)
