"""Test: wat de goededoelenroute sinds 5-10-2026 anders doet — zonder CBF of database.

Draaien vanuit de repo-root:

    python3 pipeline/test_goede_doelen.py

Waarom dit bestaat. Drie dingen in deze route gingen stil mis, en geen van drie
viel op in de database:

- `stichtingen._uit_tekst()` kreeg de tekenend accountant van `analyseer()` en
  liet hem vallen. Geen van de 1.426 CBF-opdrachten had een naam.
- `laad_stichtingen` telde een rij uit het marktonderzoek (`controle_onbepaald`)
  als "al geladen". Veertien D/E-organisaties met een CBF-verslag over 2025
  werden daardoor nooit gelezen.
- Bij de naam is de kantooreis van `ondertekenaar.py` het eerste woord van de
  kantoornaam, als deel van een woord. Bij "Van …" en "De …" toetst dat niets.

Kantoren, organisaties en personen hieronder zijn verzonnen.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent / "adapters"))
sys.path.insert(0, str(Path(__file__).resolve().parent / "extractie"))

import laad_stichtingen  # noqa: E402
import stichtingen  # noqa: E402
import vul_ondertekenaar_cbf  # noqa: E402
from kantoor_match import bouw_index  # noqa: E402
from supabase_client import SupabaseFout  # noqa: E402

goed = 0
fout = 0


def check(omschrijving: str, voorwaarde: bool) -> None:
    global goed, fout
    if voorwaarde:
        goed += 1
    else:
        fout += 1
        print(f"  FOUT: {omschrijving}")


KANTOREN = [
    {"naam": "Van Verzinsel Accountants B.V.", "afm_nummer": "99000001",
     "sleutel": "99000001", "wta_vergunning": True},
    {"naam": "Ander Bedenksel Audit B.V.", "afm_nummer": "99000002",
     "sleutel": "99000002", "wta_vergunning": True},
]
INDEX = bouw_index(KANTOREN, aliassen=[], overige=[], vervallen=[])
VERZINSEL = KANTOREN[0]
BEDENKSEL = KANTOREN[1]


def verklaring(kantoorregel: str, ondertekening: str) -> str:
    return (
        "Controleverklaring van de onafhankelijke accountant\n\n"
        "Aan: het bestuur van Stichting Fictief Goed Doel\n\n"
        "Ons oordeel\n"
        "Naar ons oordeel geeft de jaarrekening een getrouw beeld van de grootte en "
        "samenstelling van het vermogen van de stichting op 31 december 2025.\n\n"
        "Utrecht, 12 mei 2026\n\n"
        f"{kantoorregel}\n\n"
        f"{ondertekening}\n"
    )


# --- de naam komt nu mee -------------------------------------------------------
tekst = verklaring("Van Verzinsel Accountants B.V.", "was getekend\n\ndrs. Q.R. Fantasie RA")
gevonden = stichtingen._uit_tekst(tekst, INDEX, "https://voorbeeld.invalid/jaarverslag.pdf")
check("de controle wordt herkend, met kantoor",
      gevonden is not None and (gevonden["kantoor"] or {}).get("sleutel") == "99000001")
check("en de ondertekenaar gaat niet meer verloren",
      gevonden is not None and gevonden.get("tekenend_accountant") == "drs. Q.R. Fantasie RA")

# --- strengere kantooreis ------------------------------------------------------
check("volledige kantoornaam vlak boven de naam: ja",
      stichtingen.naam_bij_kantoor(tekst, "drs. Q.R. Fantasie RA", VERZINSEL, INDEX))
check("een naam die over twee regels loopt wordt ook gevonden",
      stichtingen.naam_bij_kantoor(
          verklaring("Van Verzinsel Accountants B.V.", "drs. Q.R.\nFantasie RA"),
          "drs. Q.R. Fantasie RA", VERZINSEL, INDEX))

# Twee verklaringen in één stuk: de naam staat onder het ándere kantoor, en "van"
# staat er gewoon in de buurt. De oude toets (eerste woord, als deel van een woord)
# liet dat door; deze niet.
twee = verklaring(
    "Ander Bedenksel Audit B.V.\nnamens deze van harte",
    "was getekend\n\ndrs. Q.R. Fantasie RA",
)
check("onder een ander kantoor: nee, ook al staat 'van' erboven",
      not stichtingen.naam_bij_kantoor(twee, "drs. Q.R. Fantasie RA", VERZINSEL, INDEX))
check("onder dat andere kantoor zelf: ja",
      stichtingen.naam_bij_kantoor(twee, "drs. Q.R. Fantasie RA", BEDENKSEL, INDEX))
ver_weg = verklaring("Van Verzinsel Accountants B.V." + "\n" + "x " * 200,
                     "was getekend\n\ndrs. Q.R. Fantasie RA")
check(f"meer dan {stichtingen.KANTOOR_VOOR_NAAM} tekens ertussen: nee",
      not stichtingen.naam_bij_kantoor(ver_weg, "drs. Q.R. Fantasie RA", VERZINSEL, INDEX))
check("een naam die niet in de tekst staat: nee",
      not stichtingen.naam_bij_kantoor(tekst, "A.B. Elders RA", VERZINSEL, INDEX))
check("een kantoor zonder zoeksleutel in de index: nee",
      not stichtingen.naam_bij_kantoor(tekst, "drs. Q.R. Fantasie RA",
                                       {"sleutel": "onbekend"}, INDEX))

# --- review: geen kantoor, dus ook geen naam ---------------------------------------
onbekend = verklaring("Nergens Bekend Kantoor B.V.", "was getekend\n\ndrs. Q.R. Fantasie RA")
gevonden = stichtingen._uit_tekst(onbekend, INDEX, "")
check("een review-geval krijgt geen naam mee",
      gevonden is not None and gevonden["kantoor"] is None
      and not gevonden.get("tekenend_accountant"))

# --- bijvullen: alleen als het dezelfde verklaring is -------------------------------
rij = {"id": 1, "type_opdracht": "vrijwillige_controle", "oordeel": "goedkeurend",
       "kantoor_sleutel": "99000001"}
gelezen = {"tekenend_accountant": "drs. Q.R. Fantasie RA", "kantoor": {"sleutel": "99000001"},
           "opdrachttype": "vrijwillige_controle", "oordeel": "goedkeurend"}
check("zelfde kantoor, type en oordeel: naam",
      vul_ondertekenaar_cbf.naam_voor_rij(rij, gelezen) == "drs. Q.R. Fantasie RA")
for veld, waarde, reden in (
    ("kantoor", {"sleutel": "99000002"}, "ander kantoor"),
    ("opdrachttype", "wettelijke_controle", "ander opdrachttype"),
    ("oordeel", "beperking", "ander oordeel"),
    ("tekenend_accountant", None, "geen naam op een ondertekeningsplek"),
):
    anders = {**gelezen, veld: waarde}
    check(f"{reden}: geen naam", vul_ondertekenaar_cbf.naam_voor_rij(rij, anders) is None)
    check(f"{reden}: zo geteld", vul_ondertekenaar_cbf.uitkomst(rij, anders) == reden)
check("niets gelezen: geen naam", vul_ondertekenaar_cbf.naam_voor_rij(rij, None) is None)
check("een lege naam is geen naam",
      vul_ondertekenaar_cbf.naam_voor_rij(rij, {**gelezen, "tekenend_accountant": "  "})
      is None)

check("een KvK-nummer onder twee namen in het register valt af",
      vul_ondertekenaar_cbf.namen_per_kvk([
          {"kvknummer": "90000001", "naam": "Stichting Fictief A"},
          {"kvknummer": "90000002", "naam": "Stichting Fictief B"},
          {"kvknummer": "90000002", "naam": "Stichting Fictief B (oud)"},
          {"kvknummer": "", "naam": "Stichting Zonder Nummer"},
      ]) == {"90000001": "Stichting Fictief A"})
check("de bijvulvraag pakt alleen lege velden van CBF-controles",
      "tekenend_accountant=is.null" in vul_ondertekenaar_cbf.VRAAG
      and "bronnen.bron_type=eq.cbf" in vul_ondertekenaar_cbf.VRAAG
      and "type_opdracht=in.(wettelijke_controle,vrijwillige_controle)"
      in vul_ondertekenaar_cbf.VRAAG)


# --- al geladen: een marktonderzoekrij telt niet ------------------------------------
class NepDb:
    def __init__(self, faal_gericht: bool = False):
        self.vragen: list[str] = []
        self.faal_gericht = faal_gericht

    def selecteer_alles(self, tabel: str, query: str) -> list:
        self.vragen.append(query)
        if self.faal_gericht and "!inner" in query:
            raise SupabaseFout("PostgREST kent !inner niet")
        # Zoals PostgREST het teruggeeft nádat het filter is toegepast.
        return [{"organisaties": {"kvk_nummer": "90000001"}},
                {"organisaties": None}]


db = NepDb()
uit = laad_stichtingen.al_geladen_kvk(db, 2025, ["90000001", "90000002"])
check("al geladen: alleen wat PostgREST teruggeeft, zonder lege", uit == {"90000001"})
check("de gerichte vraag sluit controle_onbepaald uit",
      "type_opdracht=neq.controle_onbepaald" in db.vragen[0]
      and "kvk_nummer=in.(90000001,90000002)" in db.vragen[0]
      and "boekjaar=eq.2025" in db.vragen[0])
db = NepDb(faal_gericht=True)
laad_stichtingen.al_geladen_kvk(db, 2025, ["90000001"])
check("de brede terugvalvraag ook", len(db.vragen) == 2
      and "type_opdracht=neq.controle_onbepaald" in db.vragen[1])

print(f"{goed}/{goed + fout} goed")
sys.exit(1 if fout else 0)
