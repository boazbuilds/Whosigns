"""Tests voor de kantoorgerichte bron (cliënten uit losse openbare jaarstukken).

Draaien vanuit de repo-root (geen testframework nodig, geen netwerk):

    python3 pipeline/test_kantoorclienten.py

De gevallen hieronder bewaken de twee dingen die hier echt kunnen misgaan: dat
er een rij in de database komt op grond van een document dat het kantoor
helemaal niet noemt, en dat er per ongeluk toch een Handelsregister-afgeleide
als bron wordt opgevoerd.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "adapters"))

from kantoorclienten import (  # noqa: E402
    BronGeweigerd,
    controleer_vindplaats,
    html_naar_tekst,
    noemt_kantoor,
)

VERKLARING = """
<html><body>
<h2>Controleverklaring van de <span>onafhankelijke</span> accountant</h2>
<p>Aan: de algemene vergadering van Voorbeeld Holding B.V.</p>
<p>Naar ons oordeel geeft de jaarrekening een getrouw beeld.</p>
<p>Amsterdam, 12 mei 2025</p>
<p>Confinant Audit &amp; Assurance B.V.</p>
<p>was getekend</p>
</body></html>
"""

ANDER_KANTOOR = """
<html><body>
<h2>Controleverklaring van de onafhankelijke accountant</h2>
<p>Rotterdam, 3 april 2025</p>
<p>Mazars Accountants N.V.</p>
</body></html>
"""


def main() -> int:
    fouten = 0

    def controleer(omschrijving: str, goed: bool, detail: str = "") -> None:
        nonlocal fouten
        fouten += not goed
        print(f"{'✓' if goed else '✗'} {omschrijving}")
        if not goed and detail:
            print(f"    {detail}")

    tekst = html_naar_tekst(VERKLARING)
    controleer(
        "html: opmaak eruit, entiteiten terug, naam heel",
        "Confinant Audit & Assurance B.V." in tekst
        and "onafhankelijke accountant" in tekst
        and "<p>" not in tekst,
        f"gevonden: {tekst[:120]!r}",
    )

    citaat = noemt_kantoor(tekst, "Confinant Audit & Assurance B.V.")
    controleer(
        "kantoor herkend, met citaat eromheen",
        citaat is not None and "Confinant" in citaat,
        f"gevonden: {citaat!r}",
    )

    controleer(
        "alleen de kern van de naam is genoeg (ondertekening met 'Confinant')",
        noemt_kantoor("Amsterdam, 1 juni 2025. Confinant, was getekend.",
                      "Confinant Audit & Assurance B.V.") is not None,
    )

    controleer(
        "een document van een ánder kantoor levert geen treffer",
        noemt_kantoor(html_naar_tekst(ANDER_KANTOOR),
                      "Confinant Audit & Assurance B.V.") is None,
    )

    controleer(
        "algemene woorden alleen zijn geen treffer",
        noemt_kantoor("Controleverklaring van de onafhankelijke accountant. "
                      "Audit en assurance zijn diensten van accountants.",
                      "Confinant Audit & Assurance B.V.") is None,
        "anders zou elk willekeurig jaarverslag als treffer gelden",
    )

    # Vindplaatsen
    geweigerd = []
    for url in [
        "https://www.kvk.nl/orderstraat/product-kiezen/?kvknummer=123",
        "https://www.company.info/bedrijf/voorbeeld-bv",
        "https://drimble.nl/bedrijf/amsterdam/123/voorbeeld-bv.html",
        "https://opencorporates.com/companies/nl/123",
        "voorbeeld.nl/jaarrekening.pdf",
    ]:
        try:
            controleer_vindplaats(url)
        except BronGeweigerd:
            geweigerd.append(url)
    controleer(
        "Handelsregister-afgeleiden en niet-webadressen worden geweigerd",
        len(geweigerd) == 5,
        f"geweigerd: {len(geweigerd)} van 5 — doorgelaten: "
        f"{[u for u in ['kvk', 'company.info', 'drimble', 'opencorporates', 'zonder schema'] ]}",
    )

    toegelaten = True
    try:
        controleer_vindplaats("https://www.voorbeeld.nl/jaarverslag-2024.pdf")
        controleer_vindplaats("https://stichting-voorbeeld.org/anbi/jaarrekening.pdf")
    except BronGeweigerd:
        toegelaten = False
    controleer("een gewone site of ANBI-publicatie wordt toegelaten", toegelaten)

    totaal = 7
    print(f"\n{totaal - fouten}/{totaal} goed")
    return 1 if fouten else 0


if __name__ == "__main__":
    raise SystemExit(main())
