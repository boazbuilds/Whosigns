"""Tests voor het lezen van OOB-cliëntenlijsten uit transparantieverslagen.

Draaien vanuit de repo-root (geen testframework nodig, geen netwerk):

    python3 pipeline/test_transparantie.py

Elk geval hieronder is een verkleinde weergave van iets dat in een écht
verslag staat (gemeten 4-8-2026): de losse "X"-kolommen van BDO, de
afgebroken namen van EY, de vastgeplakte lettermarkeringen en de
voetnoten-dwars-door-de-lijst van PwC, de branchekopjes van Mazars en het
disclaimersblok waar de lijst van Deloitte in overloopt. Wie aan de
leesregels sleutelt, hoort deze gevallen groen te houden.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "adapters"))
sys.path.insert(0, str(Path(__file__).resolve().parent / "extractie"))

from transparantie import namen_uit_verslag  # noqa: E402

# (omschrijving, kop, tekst, verwachte namen)
GEVALLEN = [
    (
        "BDO: X-kolommen en aanhalingstekens",
        "A. Lijst van Organisaties van Openbaar Belang",
        "A. Lijst van Organisaties van Openbaar Belang\n"
        "X\n\nAlmelose Woningstichting ‘Beter Wonen’\n"
        "X\n\nAnker Insurance Company N.V.\n"
        "X\n\nStichting Acantus\n",
        ["Almelose Woningstichting ‘Beter Wonen’", "Anker Insurance Company N.V.", "Stichting Acantus"],
    ),
    (
        "EY: afgebroken naam over twee regels",
        "List of PIE audit clients",
        "Appendix 1: List of PIE audit clients\n"
        "ABN AMRO Bank N.V.\n"
        "DAS Nederlandse Rechtsbijstand\n"
        "Verzekeringmaatschappij N.V.\n"
        "Achmea B.V.\n",
        ["ABN AMRO Bank N.V.", "DAS Nederlandse Rechtsbijstand Verzekeringmaatschappij N.V.", "Achmea B.V."],
    ),
    (
        "PwC: lettermarkeringen, klein-lettervervolg en voetnoot er dwars doorheen",
        "List of public interest entities",
        "List of public interest entities\n"
        "A\n\nAdyen N.V.\n"
        "B BMW Finance N.V.\n"
        "\tStichting Bedrijfstakpensioenfonds voor\n"
        "de Detailhandel\n"
        "indicators (KPI’s) are taken from the NBA Practice Note stated in the Practice Note. the main document of this\n"
        "Triodos Bank N.V.\n",
        ["Adyen N.V.", "BMW Finance N.V.", "Stichting Bedrijfstakpensioenfonds voor de Detailhandel", "Triodos Bank N.V."],
    ),
    (
        "Mazars: branchekopjes tussen de namen",
        "Appendix 1 Public Interest Entities",
        "Appendix 1 Public Interest Entities\n"
        "Insurance companies\n"
        "• Actua Schadeverzekering N.V.\n"
        "Housing corporations\n"
        "• Stichting Area\n",
        ["Actua Schadeverzekering N.V.", "Stichting Area"],
    ),
    (
        "Deloitte: lijst loopt over in het disclaimersblok",
        "Public interest entities audited for statutory purposes",
        "Public interest entities audited for statutory purposes by X in 2024/2025:\n"
        "Aalberts N.V.\n"
        "Woonstichting De Kernen\n"
        "www.deloitte.com.\n"
        "network of member firms, and their related entities (collectively, the “Deloitte organisation”) is a long disclaimer.\n",
        ["Aalberts N.V.", "Woonstichting De Kernen"],
    ),
    (
        "kruisverwijzing vóór de echte lijst: het langste startpunt wint",
        "Lijst van Organisaties van Openbaar Belang",
        "Inhoud: Lijst van Organisaties van Openbaar Belang ... 54\n"
        "een verwijzing naar de Lijst van Organisaties van Openbaar Belang staat ook hier\n"
        "Lijst van Organisaties van Openbaar Belang\n"
        "Cogas Holding N.V.\n"
        "Brand New Day Bank N.V.\n",
        ["Cogas Holding N.V.", "Brand New Day Bank N.V."],
    ),
]


def main() -> int:
    fouten = 0
    for omschrijving, kop, tekst, verwacht in GEVALLEN:
        namen, _ = namen_uit_verslag(tekst, kop)
        goed = namen == verwacht
        fouten += not goed
        print(f"{'✓' if goed else '✗'} {omschrijving}")
        if not goed:
            print(f"    verwacht: {verwacht}")
            print(f"    gevonden: {namen}")
    print(f"\n{len(GEVALLEN) - fouten}/{len(GEVALLEN)} goed")
    return 1 if fouten else 0


if __name__ == "__main__":
    raise SystemExit(main())
