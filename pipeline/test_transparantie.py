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
    (
        "zijbalkfragmenten na de lijst plakken nergens aan vast (PwC 2023/2024)",
        "List of public interest entities",
        "List of public interest entities\n"
        "Woonstichting ‘thuis\n"
        "Yapi Kredi Bank Nederland N.V.\n"
        "\n"
        "Reporting criteria of the key performance indicators\n"
        "Our system of quality\n"
        "management\n"
        "Our governance\n"
        "Legislative and\n"
        "regulatory framework\n"
        "firms that belong to\n"
        "member firms\n",
        ["Woonstichting ‘thuis", "Yapi Kredi Bank Nederland N.V."],
    ),
    (
        "voetnootregels en voetnootsterretjes (PwC 2022/2023)",
        "List of public interest entities",
        "List of public interest entities\n"
        "Stichting Thuisvester\n"
        "Stichting Vestia**\n"
        "Stichting Wonen Zuid\n"
        "*\tCompanies established in the Netherlands listed on an EU regulated market, banks\n"
        "** Stichting Vestia has been split into three legal entities after 1 January 2023.\n",
        ["Stichting Thuisvester", "Stichting Vestia", "Stichting Wonen Zuid"],
    ),
    (
        "EY: naam zonder rechtsvorm over twee regels, buurnamen blijven los",
        "List of PIE audit clients",
        "Appendix 1: List of PIE audit clients\n"
        "Stichting Parteon\n"
        "Stichting Pensioenfonds ING\n"
        "\n"
        "Nederlandse organisatie voor wetenschappelijk\n"
        "onderzoek (NWO)\n"
        "\n"
        "Stichting Pensioenfonds Medisch Specialisten\n",
        [
            "Stichting Parteon",
            "Stichting Pensioenfonds ING",
            "Nederlandse organisatie voor wetenschappelijk onderzoek (NWO)",
            "Stichting Pensioenfonds Medisch Specialisten",
        ],
    ),
    (
        "EY: eerste helft eindigt op een voorzetsel, tweede helft met hoofdletter",
        "List of PIE audit clients",
        "Appendix 1: List of PIE audit clients\n"
        "ING Groep N.V.\n"
        "Nederlandse Financierings-Maatschappij voor\n"
        "Ontwikkelingslanden N.V.\n"
        "NIBC Bank N.V.\n",
        [
            "ING Groep N.V.",
            "Nederlandse Financierings-Maatschappij voor Ontwikkelingslanden N.V.",
            "NIBC Bank N.V.",
        ],
    ),
    (
        "EY: kolommen om en om in de tekststroom — losse namen blijven los",
        "List of PIE audit clients",
        "Appendix 1: List of PIE audit clients\n"
        "Ease2pay N.V.\n"
        "Airbus SE\n"
        "Enexis Holding N.V.\n"
        "Akelius Residential Property Financing B.V.\n",
        [
            "Ease2pay N.V.",
            "Airbus SE",
            "Enexis Holding N.V.",
            "Akelius Residential Property Financing B.V.",
        ],
    ),
    (
        "PwC: afgebroken staarten — aanplakken waar het kan, afkeuren waar het moet",
        "List of public interest entities",
        "List of public interest entities\n"
        "Onderlinge Verzekeringsmaatschappij Univé Samen\n"
        "U.A.\n"
        "Onderlinge Waarborgmaatschappij DSW\n"
        "Zorgverzekeraar U.A.\n"
        "Optimix Investment Funds N.V.\n"
        "Sinopel 2019 B.V.\n"
        "Stad Holland Zorgverzekeraar Onderlinge\n"
        "Waarborgmaatschappij U.A.\n"
        "STG Global Finance B.V.\n",
        # "Zorgverzekeraar U.A." is niet betrouwbaar aan DSW te plakken (de
        # volgorde van de lijsten is te grillig om op te leunen): de staart
        # wordt afgekeurd en DSW blijft — herkenbaar maar afgekort — staan.
        [
            "Onderlinge Verzekeringsmaatschappij Univé Samen U.A.",
            "Onderlinge Waarborgmaatschappij DSW",
            "Optimix Investment Funds N.V.",
            "Sinopel 2019 B.V.",
            "Stad Holland Zorgverzekeraar Onderlinge Waarborgmaatschappij U.A.",
            "STG Global Finance B.V.",
        ],
    ),
    (
        "KPMG/BDO: opsommingstekens horen niet bij de naam",
        "Lijst van organisaties van openbaar belang",
        "Lijst van organisaties van openbaar belang\n"
        "— ING Bank N.V.\n"
        "\uf03c Adagio CLO I B.V.\n"
        "• Xeikon N.V.\n",
        ["ING Bank N.V.", "Adagio CLO I B.V.", "Xeikon N.V."],
    ),
    (
        "KPMG: een tussenzin die niet meer sluit hoort niet bij de naam",
        "Lijst van organisaties van openbaar belang",
        "Lijst van organisaties van openbaar belang\n"
        "CZ Zorgverzekeringen N.V. (previously OHRA\n"
        "Zorgverzekeringen N.V.)\n"
        "Qiagen N.V.\n",
        ["CZ Zorgverzekeringen N.V.", "Qiagen N.V."],
    ),
    (
        "BDO: onderlingen afgebroken op het soortwoord worden weer heel",
        "Lijst van organisaties van openbaar belang",
        "Lijst van organisaties van openbaar belang\n"
        "Onderlinge Waarborg Maatschappij\n"
        "Achterhoek U.A.\n"
        "Ctac N.V.\n",
        ["Onderlinge Waarborg Maatschappij Achterhoek U.A.", "Ctac N.V."],
    ),
    (
        "PwC: de inleidende zin boven de lijst is geen cliënt",
        "List of public interest entities",
        "List of public interest entities\n"
        "Accountants N.V. \u200bduring the\n"
        "Netherlands listed on an EU regulated market, credit institutions and (re)insurance\n"
        "Akzo Nobel N.V.\n"
        "Blue Square Re N.V. in liquidatie\n"
        "Stichting Wooninc.\n",
        # "in liquidatie" en "Wooninc." blijven staan: een rechtstoestand en
        # een punt in de naam zijn geen proza.
        [
            "Akzo Nobel N.V.",
            "Blue Square Re N.V. in liquidatie",
            "Stichting Wooninc.",
        ],
    ),
    (
        "Deloitte: streepje vast aan de naam, label erboven, zachte afbreekstreep",
        "PIEs audited",
        "PIEs audited\n"
        "Merger between:\n"
        "-Onderlinge Verzekeringsmaatschappij Midden Drenthe U.A.,\n"
        "-Onderlinge Waarborgmaatschappij Univ\u00e9 Ruinen U.A.\n"
        "Onderlinge Waarborgmaatschappij voor Instellingen in de "
        "Gezondheids\u00ad zorg MediRisk B.A.\n",
        # "Merger between:" is een kopje en mag niet aan de naam eronder
        # geplakt worden; de zachte afbreekstreep is onzichtbaar maar zou
        # "Gezondheids zorg" een andere organisatie maken dan "Gezondheidszorg".
        [
            "Onderlinge Verzekeringsmaatschappij Midden Drenthe U.A.",
            "Onderlinge Waarborgmaatschappij Univ\u00e9 Ruinen U.A.",
            "Onderlinge Waarborgmaatschappij voor Instellingen in de "
            "Gezondheidszorg MediRisk B.A.",
        ],
    ),
    (
        "BDO: een naam die zelf tussen haakjes doorloopt blijft heel",
        "Lijst van organisaties van openbaar belang",
        "Lijst van organisaties van openbaar belang\n"
        "Mutual Insurance Association Munis (Onderlinge\n"
        "Verzekeringsmaatschappij Munis) U.A.\n"
        "Ctac N.V.\n",
        ["Mutual Insurance Association Munis (Onderlinge Verzekeringsmaatschappij Munis) U.A.",
         "Ctac N.V."],
    ),
    (
        "Deloitte: is de naam vóór het haakje al af, dan is de rest toelichting",
        "PIEs audited",
        "PIEs audited\n"
        "Onderlinge Verzekeringsmaatschappij Univ\u00e9 Samen U.A. (voorheen Onderlinge\n"
        "Verzekeringsmaatschappij Univ\u00e9 Noord-Holland U.A.)\n"
        "Ctac N.V.\n",
        # "U.A." sluit de naam af, dus hier wordt wél geknipt -- anders dan bij
        # Munis hierboven, waar de naam vóór het haakje nog niet af was.
        ["Onderlinge Verzekeringsmaatschappij Univ\u00e9 Samen U.A.", "Ctac N.V."],
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
