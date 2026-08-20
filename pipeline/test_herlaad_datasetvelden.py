"""Test: --herlaad mag geen datasetvelden vernietigen.

Waarom dit bestaat. `--herlaad` gooit een bestaande opdracht weg en maakt hem
opnieuw aan uit het oogstrapport. Dat weggooien moet, want een gewijzigd
opdrachttype valt onder een andere unieke sleutel en zou anders een tweede rij
naast de eerste opleveren. Maar het rapport kent maar elf kolommen, en de
jaardataset vult er nog acht andere: `oordeel_gerapporteerd`, `verklaring_datum`,
vier honorariumbedragen, de wisselvlag en `standaard`.

Die acht waren na een herlaad dus weg. Gemeten op 20-8-2026: een herlaad van
boekjaar 2023 zou 443 opdrachten verwijderen waarvan er 442 zulke velden droegen
— 441 keer `oordeel_gerapporteerd`, de helft van v_oordeel_afwijking, en 2023 was
het enige boekjaar dat die vergelijking had.

Deze test draait `main()` echt, met een neppe Supabase ervoor, want het gaat hier
om de vólgorde: eerst redden, dan verwijderen, dan invoegen, dan terugzetten. Een
test op alleen `datasetvelden_van` zou die volgorde niet zien.
"""

import csv
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import laad_zorg_rapport  # noqa: E402
from laad_zorg_rapport import DATASETVELDEN, datasetvelden_van  # noqa: E402
from laad_zorg_rapport import opdracht_uit_rapportrij  # noqa: E402

goed = 0
fout = 0


def check(omschrijving: str, voorwaarde: bool) -> None:
    global goed, fout
    if voorwaarde:
        goed += 1
    else:
        fout += 1
        print(f"  FOUT: {omschrijving}")


# --- datasetvelden_van ---------------------------------------------------------
check(
    "leeg in, leeg uit",
    datasetvelden_van([]) == {},
)
check(
    "null-velden worden niet teruggezet; een PATCH met alleen nullen is zinloos",
    datasetvelden_van([{v: None for v in DATASETVELDEN}]) == {},
)
check(
    "een gevuld veld komt eruit",
    datasetvelden_van([{"oordeel_gerapporteerd": "goedkeurend"}])
    == {"oordeel_gerapporteerd": "goedkeurend"},
)
check(
    "bij meer rijen wint per veld de eerste die iets zegt",
    datasetvelden_van(
        [
            {"oordeel_gerapporteerd": None, "verklaring_datum": "2024-05-01"},
            {"oordeel_gerapporteerd": "beperking", "verklaring_datum": "2024-09-09"},
        ]
    )
    == {"oordeel_gerapporteerd": "beperking", "verklaring_datum": "2024-05-01"},
)
check(
    "False is een waarde, geen leegte -- wissel_gerapporteerd=False betekent "
    "'niet gewisseld' en niet 'onbekend'",
    datasetvelden_van([{"wissel_gerapporteerd": False}])
    == {"wissel_gerapporteerd": False},
)
check(
    "een bedrag van 0 blijft ook staan",
    datasetvelden_van([{"honorarium_controle_eur": 0}])
    == {"honorarium_controle_eur": 0},
)

# --- de lijst mag niet overlappen met wat het rapport zelf schrijft -------------
uit_rapport = set(
    opdracht_uit_rapportrij(
        {
            "kvk": "1",
            "naam": "n",
            "plaats": "p",
            "boekjaar": "2023",
            "kantoor": "k",
            "kantoor_sleutel": "s",
            "afm_nummer": "a",
            "type_opdracht": "wettelijke_controle",
            "oordeel": "goedkeurend",
            "grond_beperking": "",
            "continuiteitsonzekerheid": "",
        },
        1,
        2,
        3,
    )
)
check(
    "geen enkel datasetveld wordt ook door het rapport geschreven; anders zou "
    "terugzetten de verse waarde overschrijven met de oude",
    not (set(DATASETVELDEN) & uit_rapport),
)


# --- de echte lus, met een neppe database --------------------------------------
class NepDb:
    """Genoeg Supabase om main() te laten lopen, en hij onthoudt de volgorde."""

    def __init__(self, bestaande_opdracht: dict | None):
        self.bestaande_opdracht = bestaande_opdracht
        self.stappen: list[str] = []
        self.gepatcht: dict = {}
        self.ingevoegd: list[dict] = []
        self.verwijderd: list[str] = []

    def selecteer_alles(self, tabel, query="select=*"):
        if tabel == "kantoren":
            return [{"id": 7, "sleutel": "13000015"}]
        if tabel == "opdrachten" and "organisaties(kvk_nummer)" in query:
            # "wat staat er al" per boekjaar
            return [{"organisaties": {"kvk_nummer": "12345678"}}]
        if tabel == "opdrachten":
            self.stappen.append("bewaren")
            return [dict(self.bestaande_opdracht)] if self.bestaande_opdracht else []
        return []

    def invoegen(self, tabel, rij):
        return {"id": 99}

    def upsert_met_id(self, tabel, rij, conflict_kolom):
        if tabel == "organisaties":
            return {"id": 42}
        self.stappen.append("invoegen")
        self.ingevoegd.append(rij)
        return {"id": 100}

    def verwijderen(self, tabel, filter):
        self.stappen.append("verwijderen")
        self.verwijderd.append(filter)

    def bijwerken(self, tabel, filter, velden):
        self.stappen.append("terugzetten")
        self.gepatcht.update(velden)


def draai(herlaad: bool, bestaande_opdracht: dict | None):
    """Schrijft een rapport van één regel en laat main() erop los."""
    db = NepDb(bestaande_opdracht)
    echte_supabase = laad_zorg_rapport.Supabase
    echte_argv = sys.argv
    laad_zorg_rapport.Supabase = lambda *a, **k: db
    try:
        with tempfile.TemporaryDirectory() as map_naam:
            pad = Path(map_naam) / "zorg_2023.csv"
            with pad.open("w", newline="", encoding="utf-8") as f:
                s = csv.writer(f)
                s.writerow(laad_zorg_rapport.VERPLICHT)
                s.writerow(
                    [
                        "12345678", "Stichting Voorbeeldzorg", "Utrecht", "2023",
                        "Deloitte Accountants B.V.", "13000015", "13000015",
                        "vrijwillige_controle", "beperking", "materieel belang", "",
                    ]
                )
            sys.argv = ["laad_zorg_rapport.py", str(pad)] + (
                ["--herlaad"] if herlaad else []
            )
            laad_zorg_rapport.main()
    finally:
        laad_zorg_rapport.Supabase = echte_supabase
        sys.argv = echte_argv
    return db


BESTAAND = {
    "standaard": None,
    "honorarium_controle_eur": 41000,
    "honorarium_overig_eur": None,
    "honorarium_fiscaal_eur": None,
    "honorarium_nietcontrole_eur": None,
    "wissel_gerapporteerd": False,
    "oordeel_gerapporteerd": "goedkeurend",
    "verklaring_datum": "2024-05-23",
}

met = draai(herlaad=True, bestaande_opdracht=BESTAAND)
check(
    "met --herlaad wordt de bestaande rij verwijderd",
    "verwijderen" in met.stappen,
)
check(
    "de volgorde is bewaren, verwijderen, invoegen, terugzetten",
    met.stappen == ["bewaren", "verwijderen", "invoegen", "terugzetten"],
)
check(
    "oordeel_gerapporteerd overleeft het herladen -- de helft van "
    "v_oordeel_afwijking",
    met.gepatcht.get("oordeel_gerapporteerd") == "goedkeurend",
)
check(
    "verklaring_datum overleeft",
    met.gepatcht.get("verklaring_datum") == "2024-05-23",
)
check(
    "het honorarium overleeft",
    met.gepatcht.get("honorarium_controle_eur") == 41000,
)
check(
    "de wisselvlag False overleeft, want dat is 'niet gewisseld' en geen leegte",
    met.gepatcht.get("wissel_gerapporteerd") is False,
)
check(
    "velden die leeg waren worden niet als null teruggeschreven",
    "standaard" not in met.gepatcht,
)
check(
    "het verse oordeel uit de verklaring blijft staan; terugzetten raakt het niet",
    "oordeel" not in met.gepatcht
    and met.ingevoegd
    and met.ingevoegd[0]["oordeel"] == "beperking",
)
check(
    "het gewijzigde opdrachttype komt door -- daarvoor bestond het verwijderen",
    bool(met.ingevoegd) and met.ingevoegd[0]["type_opdracht"] == "vrijwillige_controle",
)
check(
    "verwijderen gebeurt op organisatie én boekjaar, nooit breder",
    met.verwijderd == ["organisatie_id=eq.42&boekjaar=eq.2023"],
)

# Niets te redden: dan hoort er ook geen PATCH te komen.
leeg = draai(herlaad=True, bestaande_opdracht=None)
check(
    "zonder datasetvelden wordt er niet nodeloos gepatcht",
    "terugzetten" not in leeg.stappen,
)

# Zonder --herlaad wordt de bestaande organisatie-boekjaar overgeslagen.
zonder = draai(herlaad=False, bestaande_opdracht=BESTAAND)
check(
    "zonder --herlaad wordt er niets verwijderd",
    "verwijderen" not in zonder.stappen,
)
check(
    "zonder --herlaad wordt de bestaande rij overgeslagen, niet overschreven",
    zonder.ingevoegd == [],
)

print(f"{goed}/{goed + fout} goed")
sys.exit(1 if fout else 0)
