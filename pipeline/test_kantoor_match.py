"""Tests voor de kantoormatch — elk geval komt uit een echt jaarverslag.

Draaien vanuit de repo-root (geen testframework nodig, geen netwerk):

    python3 pipeline/test_kantoor_match.py

Waarom dit bestand bestaat: de match werkt op tekst uit pdf's, en elke keer dat er een
nieuwe sector bij kwam bleek er een manier waarop een kantoornaam in een jaarverslag
staat zónder dat het kantoor de verklaring ondertekende. Drie keer op rij leverde dat
een opdracht op die niet bestond — en één keer zelfs een "wisseling" die nooit heeft
plaatsgevonden. Die gevallen staan hier, zodat ze niet stil kunnen terugkomen.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "extractie"))

from kantoor_match import bouw_index, laad_kantoren, zoek_kantoor  # noqa: E402

# (omschrijving, tekst, verwacht kantoor of None)
GEVALLEN = [
    # ---------- moet matchen: dit zijn ondertekeningen ----------
    (
        "plaats en datum vóór de naam (Hartstichting 2023)",
        "waaronder eventuele significante tekortkomingen in de interne beheersing "
        "Amstelveen, 3 juni 2024 KPMG Accountants N.V. E. Breijer RA",
        "KPMG Accountants N.V.",
    ),
    (
        "oordeelparagraaf kort ervoor (Hartstichting 2024)",
        "verkregen controle-informatie voldoende en geschikt is als basis voor ons "
        "oordeel. Forvis Mazars Accountants N.V., statutair gevestigd te Rotterdam",
        "Forvis Mazars Accountants N.V.",
    ),
    (
        "plaats en datum ná de naam (Peace Parks 2024)",
        "Controleverklaring van Kaap Hoorn Audit & Assurance B.V. Rotterdam, 3 mei 2025",
        "Kaap Hoorn Audit & Assurance B.V.",
    ),
    (
        "tekennaam via de aliastabel (Opkikker 2024)",
        "in de interne beheersing Hilversum, 27 juni 2025 M&K Audit B.V. "
        "w.g. J.P.L. van der Moer RA",
        "M & K Hilversum B.V.",
    ),
    (
        "kantoor zonder Wta-vergunning (100WEEKS 2024)",
        "Amersfoort, 12 juni 2025 WITh Accountants B.V. was getekend",
        "WITh Accountants B.V.",
    ),
    # ---------- mag NIET matchen: de naam staat er wel, maar tekent niet ----------
    (
        "werkgever van een bestuurslid (Kerk in Actie 2023)",
        "J.W. Stam MSc RA, senior manager bureau vaktechniek bij Baker Tilly "
        "Netherlands N.V., lid van het moderamen sinds 1 mei 2020",
        None,
    ),
    (
        "werkgever van een bestuurslid (Kerk in Actie 2022)",
        "drs J.M. van Lieshout RA, secretaris, accountant bij Koeleman accountants & "
        "belastingadviseurs, rooster van aftreden bestuur",
        None,
    ),
    (
        "kernwaarde die toevallig een kantoornaam is (Oxfam Novib 2023)",
        "we hold ourselves accountable to the people we work with and for courage",
        None,
    ),
    (
        "kantoornaam in een cv (Oxfam Novib 2024)",
        "he was a member and chair of the board of directors of Mazars Holding N.V. "
        "and Mazars Accountants N.V. Paul was also a part-time lecturer",
        None,
    ),
    (
        "Engelse standaardzin, geen kantoor (100WEEKS 2024)",
        "we performed our audit procedures in accordance with Dutch Standards on Auditing",
        None,
    ),
    (
        "'accuraat' is geen kantoor",
        "de administratie is accuraat en volledig bijgehouden gedurende het boekjaar",
        None,
    ),
]


def main() -> int:
    index = bouw_index(laad_kantoren())
    fouten = 0
    for omschrijving, tekst, verwacht in GEVALLEN:
        treffer = zoek_kantoor(tekst, index)
        # Een zwakke treffer is geen vastgesteld kantoor (die gaat naar de
        # review-queue), dus die telt hier als "niet gematcht" — precies zoals
        # verklaring.analyseer() ermee omgaat.
        gevonden = (
            None if treffer is None or treffer["zwak"] else treffer["kantoor"]["naam"]
        )
        goed = gevonden == verwacht
        fouten += not goed
        print(
            f"{'✓' if goed else '✗'} {omschrijving}\n"
            f"    verwacht: {verwacht}\n    gevonden: {gevonden}"
            + ("" if goed else f"\n    context:  {treffer['context'] if treffer else '-'}")
        )
    print(f"\n{len(GEVALLEN) - fouten}/{len(GEVALLEN)} goed")
    return 1 if fouten else 0


if __name__ == "__main__":
    raise SystemExit(main())
