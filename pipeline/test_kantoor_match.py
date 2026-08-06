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
        "kantoor onder zijn huidige registernaam (Opkikker 2024)",
        "in de interne beheersing Hilversum, 27 juni 2025 M&K Audit B.V. "
        "w.g. J.P.L. van der Moer RA",
        "M & K Audit B.V.",
    ),
    (
        # Het AFM-register kent 13000196 sinds juli 2026 als M & K Audit B.V.; de
        # verklaring over boekjaar 2023 is nog getekend onder de oude naam. Zulke
        # naamswijzigingen zijn precies waarvoor de aliastabel bestaat — en ze komen
        # aan het licht doordat de wekelijkse AFM-snapshot in git wordt vastgelegd.
        "naam van vóór de naamswijziging, via de aliastabel (Opkikker 2023)",
        "in de interne beheersing Hilversum, 31 mei 2024 M & K Hilversum B.V. "
        "was getekend J.P.L. van der Moer RA",
        "M & K Audit B.V.",
    ),
    (
        "kantoor zonder Wta-vergunning (100WEEKS 2024)",
        "Amersfoort, 12 juni 2025 WITh Accountants B.V. was getekend",
        "WITh Accountants B.V.",
    ),
    (
        # Gevonden bij een telling over 1.728 gedownloade verklaringen: Grant
        # Thornton is een groot kantoor en viel er stelselmatig uit, omdat de
        # audittak zich pas ná de splitsing van 2025 Audit en Assurance noemt.
        # Vergunning 13000524 loopt onafgebroken sinds 27-9-2007 en staat in beide
        # namen op dezelfde vestiging in Alphen aan den Rijn.
        "naam van vóór de splitsing van 2025, via de aliastabel (Present 2019)",
        "waaronder eventuele significante tekortkomingen in de interne beheersing. "
        "Alphen aan den Rijn, 18 september 2020 "
        "Grant Thornton Accountants en Adviseurs B.V.",
        "Grant Thornton Audit en Assurance B.V.",
    ),
    (
        # Zonder plaats en datum, zonder ondertekeningsformule — alleen de tekenend
        # accountant ná de naam. Kwam voor bij 46 van de 1.728 verklaringen in de
        # cache (5-8-2026) en viel daar allemaal weg.
        "de tekenend accountant staat ná de kantoornaam (ASSortiMens 2023)",
        "Met vriendelijke groet, CAS ZorgAccountants B.V. S.R. Snel AA",
        "CAS ZorgAccountants B.V.",
    ),
    (
        "een digitale ondertekendienst als handtekeningblok ('t Hummelhûs 2023)",
        "weergeeft. Miedema Accountants ValidSigned door drs. D. van der Bij RA RB "
        "op 29-03-2024",
        "Miedema Accountants",
    ),
    (
        # Ook nuttig als de datum onleesbaar uit de pdf komt: hier stond "25 maarl
        # 2024" en dat is geen datum meer, dus de datumregel hielp niet.
        "verhaspelde datum, maar de ondertekenaar staat er (Dubois 2023)",
        "in de interne beheersing. Amsterdam, 25 maarl 2024 "
        "Dubois & Co. Registeraccountants door M. Belkadi RA",
        "Dubois & Co. Registeraccountants",
    ),
    (
        # Tekennaam van vergunninghouder 13000483; de AFM kent hem als Countus
        # Accountants + Adviseurs B.V., op hetzelfde adres in Zwolle.
        "tekennaam van de auditpraktijk, via de aliastabel (Ibass 2023)",
        "Zwolle, 14 maart 2024 Countus Audit B.V. ValidSigned door "
        "drs. B.E.J. Seemann RA",
        "Countus Accountants + Adviseurs B.V.",
    ),
    (
        # Naam na de fusie van februari 2023; het AFM-register houdt 13000504 nog
        # onder de naam van vóór die fusie.
        "naam na een fusie, via de aliastabel (Onder de Bomen 2023)",
        "waaronder eventuele significante tekortkomingen in de interne beheersing. "
        "Nijmegen, Konings Maters Accountants & Adviseurs W.M. Groothuis RA",
        "Konings & Meeuwissen, accountants en belastingadviseurs",
    ),
    (
        # Gemeenten en regelingen worden ook gecontroleerd door kantoren zonder
        # Wta-vergunning (daar niet nodig) en door gemeentelijke diensten. Deze
        # ondertekening komt letterlijk uit de raadsinformatie-oogst van 5-8-2026.
        "kantoor buiten het AFM-register, briefpapier als context (ODR 2021)",
        "verkregen controle-informatie voldoende en geschikt is als basis voor "
        "ons oordeel. FSV Accountants + Adviseurs B.V. Hogeweg 43 Postbus 128 "
        "5300 AC ZALTBOMMEL",
        "FSV Accountants + Adviseurs B.V.",
    ),
    (
        "gemeentelijke accountantsdienst, via de aliastabel (Dienst Metro 2013)",
        "verenigbaar is met de jaarrekening. Amsterdam, 30 april 2014 "
        "Auditdienst ACAM Origineel getekend door: H. Demirel RA",
        "ACAM Accountancy en Advies",
    ),
    # ---------- mag NIET matchen: de naam staat er wel, maar tekent niet ----------
    (
        # De keerzijde van de regel hierboven: ook in een cv kan er een accountant
        # ná de kantoornaam staan. "werkzaam bij" moet dan zwaarder wegen.
        "kantoornaam in een cv, mét een accountant erachter",
        "de penningmeester is werkzaam bij Flynth Audit B.V. J. Jansen RA en heeft "
        "die functie sinds 2019",
        None,
    ),
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
