"""Tests voor het lezen van gunningen uit TED.

Draaien vanuit de repo-root (geen testframework nodig, geen netwerk):

    python3 pipeline/test_tenderned.py

De gevallen zijn verkleinde weergaven van echte antwoorden van de TED-API
(opgehaald 4-8-2026): meertalige velden, een datum met tijdzone, een bericht
met meerdere winnaars, en een bericht van vóór eForms dat helemaal geen
winnaarsveld heeft.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "adapters"))

from tenderned import gunningen_uit, schoon_opdrachtgever, zoek  # noqa: E402

# Zoals de API het echt teruggeeft.
BERICHTEN = [
    {
        "publication-number": "1739-2024",
        "buyer-name": {"nld": ["waterschap Hoogheemraadschap De Stichtse Rijnlanden"]},
        "winner-name": {"nld": ["Crowe Foederer Audit & Assurance B.V."]},
        "contract-conclusion-date": ["2023-12-28+01:00"],
        "notice-title": {"nld": ["Nederland – Accountantsdiensten"]},
    },
    {
        # Bericht van vóór eForms: wél een koper, geen winnaarsveld.
        "publication-number": "274576-2016",
        "buyer-name": {"nld": ["Veiligheidsregio Zuid-Holland Zuid"]},
        "contract-conclusion-date": None,
        "notice-title": {"nld": ["Nederland-Dordrecht: Accountantsdiensten"]},
    },
    {
        # Meerdere percelen, meerdere winnaars, met een dubbele erin.
        "publication-number": "33114-2024",
        "buyer-name": {"nld": ["Stichting Regionale Publieke Omroep"]},
        "winner-name": {
            "nld": [
                "KPMG Accountants N.V.",
                "Deloitte Accountants B.V.",
                "KPMG Accountants N.V.",
            ]
        },
        "contract-conclusion-date": ["2023-12-04+01:00", "2023-12-20+01:00"],
        "notice-title": {"nld": ["Nederland – Raamovereenkomst"]},
    },
    {
        # Geen koper: onbruikbaar, moet eruit vallen.
        "publication-number": "99999-2024",
        "winner-name": {"nld": ["Iemand B.V."]},
    },
]


def main() -> int:
    fouten = 0

    def controleer(omschrijving: str, goed: bool, detail: str = "") -> None:
        nonlocal fouten
        fouten += not goed
        print(f"{'✓' if goed else '✗'} {omschrijving}")
        if not goed and detail:
            print(f"    {detail}")

    regels = gunningen_uit(BERICHTEN)

    controleer(
        "meertalige velden plat, tijdzone van de datum af",
        len(regels) >= 1
        and regels[0]["opdrachtgever"] == "waterschap Hoogheemraadschap De Stichtse Rijnlanden"
        and regels[0]["winnaar"] == "Crowe Foederer Audit & Assurance B.V."
        and regels[0]["gunningsdatum"] == "2023-12-28",
        f"gevonden: {regels[0] if regels else None}",
    )

    controleer(
        "bericht zonder winnaarsveld levert niets op",
        not any(r["publicatienummer"] == "274576-2016" for r in regels),
    )

    controleer(
        "bericht zonder opdrachtgever levert niets op",
        not any(r["publicatienummer"] == "99999-2024" for r in regels),
    )

    omroep = [r for r in regels if r["publicatienummer"] == "33114-2024"]
    controleer(
        "meerdere winnaars worden losse regels, dubbelen eruit",
        len(omroep) == 2
        and {r["winnaar"] for r in omroep}
        == {"KPMG Accountants N.V.", "Deloitte Accountants B.V."},
        f"gevonden: {[r['winnaar'] for r in omroep]}",
    )

    controleer(
        "een rubriekaanduiding in het winnaarsveld is geen partij",
        gunningen_uit([{
            "publication-number": "1-2024",
            "buyer-name": {"nld": ["Gemeente Ergens"]},
            "winner-name": {"nld": ["Gegunde opdrachten"]},
        }]) == [],
    )

    controleer(
        "elke regel draagt een vindplaats",
        all(r["url"].startswith("https://ted.europa.eu/") and r["publicatienummer"] in r["url"]
            for r in regels),
    )

    # Rommelige aanbestedersnamen
    gevallen = [
        ("Afdeling Inkoop, Gemeente Nijmegen", "Gemeente Nijmegen"),
        ("Gemeente Kerkrade, Raadhuis", "Gemeente Kerkrade"),
        ("gemeentehuis Borsele", "Borsele"),
        ("waterschap Rijn en IJssel", "Waterschap Rijn en IJssel"),
        ("provincie Drenthe", "Provincie Drenthe"),
        ("gemeente Tilburg", "Gemeente Tilburg"),
        ("Provincie Utrecht", "Provincie Utrecht"),
    ]
    mis = [(ruw, schoon_opdrachtgever(ruw), verwacht)
           for ruw, verwacht in gevallen if schoon_opdrachtgever(ruw) != verwacht]
    controleer(
        "aanhangsels van aanbestedersnamen eraf",
        not mis,
        f"mis: {mis}",
    )

    # Bladeren stopt zodra een pagina niet vol is.
    opgevraagd = []

    def nep(lichaam):
        opgevraagd.append(lichaam["page"])
        return {"notices": [{"publication-number": f"p{lichaam['page']}"}] * (2 if lichaam["page"] < 3 else 1)}

    berichten = zoek(per_pagina=2, haal=nep)
    controleer(
        "bladeren stopt bij de eerste niet-volle pagina",
        opgevraagd == [1, 2, 3] and len(berichten) == 5,
        f"opgevraagd: {opgevraagd}, berichten: {len(berichten)}",
    )

    totaal = 8
    print(f"\n{totaal - fouten}/{totaal} goed")
    return 1 if fouten else 0


if __name__ == "__main__":
    raise SystemExit(main())
