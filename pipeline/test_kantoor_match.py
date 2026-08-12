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
    # ---------- tekstschade uit de pdf: de ampersand verhaspelt ----------
    #
    # Gevonden bij een telling over alle 21.339 raadsstukken (8-8-2026). De grootste
    # oorzaak van weggevallen kantoren is niet een onbekende naam maar één verhaspeld
    # teken: de "&" in het handtekeningblok komt er als "£t", "Et", "S" of "yK" uit.
    # Daardoor viel juist bij de twee grootste kantoren de verklaring weg.
    (
        "BDO met een verhaspelde ampersand (gemeente Delft 2015)",
        "in overeenstemming met het Besluit begroting en verantwoording provincies "
        "en gemeenten. Utrecht, 29 juni 2016 BDO Audit £t Assurance B.V. "
        "namens deze, w.g. drs. R.H.",
        "BDO Audit & Assurance B.V.",
    ),
    (
        "EY met een verhaspelde ampersand (Omgevingsdienst 2018)",
        "waaronder eventuele significante tekortkomingen in de interne beheersing. "
        "Eindhoven, 2 juli 2019 Ernst S Young Accountants LLP "
        "EY Building a better working world",
        "EY Accountants B.V.",
    ),
    (
        # Hier is het de Y die als V wordt gelezen.
        "EY met een V in plaats van een Y",
        "in de interne beheersing. Arnhem, 4 juni 2015 Ernst & Voung Accountants LLP",
        "EY Accountants B.V.",
    ),
    (
        "hoofdletter I gelezen als kleine l (GR ReinUnie 2014)",
        "verenigbaar is met de jaarrekening. Verklaring Haarlem, 9 april 2015 "
        "Reg.nr. : 1000006/215/343/2316 lpa-Acon Assurance B.V. "
        "Was getekend : mr. drs. J.C. Olij RA",
        "Ipa-Acon Assurance B.V.",
    ),
    (
        "naam aan elkaar geplakt, met een stempelrest ervoor (Westfries Archief 2014)",
        "voor zover wij dat kunnen beoordelen, verenigbaar is met de jaarrekening. "
        "Zwaag, 3 april 2015 DTG KAAPHOORN Audit & Assurance B.V. W.g. S.A. Dekker RA",
        "Kaap Hoorn Audit & Assurance B.V.",
    ),
    # ---------- kantoren die vandaag geen Wta-vergunning (meer) hebben ----------
    #
    # Het AFM-register is een momentopname van vandaag, maar WhoSigns legt de markt
    # vanaf 2010 vast. Een kantoor dat in 2019 tekende en daarna fuseerde staat er
    # niet meer in, en dan valt elke verklaring die het ooit tekende weg. Bij
    # gemeenten, regelingen en schoolbesturen mag een kantoor zonder Wta-vergunning
    # ook gewoon tekenen. Elk van deze namen is nagelopen op het handtekeningblok in
    # de verklaring zelf: plaats, datum en de naam van de tekenend accountant.
    (
        "onderwijskantoor, opgegaan in Crowe Foederer (Lek en Linge 2019)",
        "significante tekortkomingen in de interne beheersing. Eindhoven, 11 juni 2020 "
        "Wijs Accountants Was getekend: M.M.P.G. van Os MSc RA",
        "Wijs Accountants",
    ),
    (
        "Amsterdams kantoor buiten het register (Spaarnesant 2019)",
        "significante tekortkomingen in de interne beheersing. Amsterdam, 16 juni 2020 "
        "Horlings Accountants & Belastingadviseurs B.V. De heer C. Rabe Registeraccountant",
        "Horlings Accountants & Belastingadviseurs B.V.",
    ),
    (
        # Bewust géén alias naar Moore DRV Audit B.V.: die vergunning (13020116)
        # loopt pas vanaf 10-9-2019 en deze verklaring is van mei 2019, dus het is
        # niet dezelfde vergunninghouder onder een nieuwe naam.
        "DRV vóór de vergunning van Moore DRV (Papendrecht & Sliedrecht 2018)",
        "waaronder eventuele significante tekortkomingen in de interne beheersing. "
        "Middelburg, 29 mei 2019 DRV Accountants & Adviseurs w.g. drs. J.J. Driessen RA",
        "DRV Accountants & Adviseurs",
    ),
    (
        "kantoor genoemd naar de tekenend partner (Historisch Goud 2024)",
        "significante tekortkomingen in de interne beheersing. Landgraaf, 30 april 2025 "
        "Kalnenek Accountants Origineel getekend door drs. E.E.T.M. Kalnenek RA Partner",
        "Kalnenek Accountants",
    ),
    (
        "tekennaam van een vergunninghouder in dezelfde plaats (Erfgoedcentrum 2025)",
        "in de interne beheersing. Doetinchem, 13 maart 2026 "
        "Confirm Audit & Assurance R. Hulshof RA",
        "Coöperatie ConFirm U.A.",
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
    (
        # Bij het toevoegen van Parallel Accountants & Adviseurs (Arnhem, 11-8-2026)
        # kwam de vraag op of "parallel" zou gaan matchen op de straatnaam
        # Parallelweg, die op talloze briefpapieren staat — en hier zelfs mét
        # plaats en datum ervoor, dus in een volwaardige ondertekeningscontext.
        # Dat kan niet: de zoeksleutels van dat kantoor zijn "parallel accountants
        # adviseurs" en "parallel accountants adviseurs b v", nooit het losse
        # woord. Een latere afkorting van de sleutel zou dat stukmaken, en dan
        # kreeg elk kantoor aan een Parallelweg de opdrachten van een ander
        # kantoor toegeschreven. Jacobs staat in geen enkele seed, dus het juiste
        # antwoord is "niets gevonden" — en vooral: niet Parallel.
        # Een korte eennaam plus een rechtsvorm zónder punten. Het register
        # schrijft "Joore N.V." (sleutel 'joore n v'), het handtekeningblok
        # schrijft "Joore NV" (sleutel 'joore nv') — en de terugval op de
        # kernnaam is hier 'joore', vijf letters, onder MIN_SLEUTELLENGTE. Bij
        # elk ánder kantoor vangt de kernnaam dit verschil op; bij een naam van
        # één kort woord valt het kantoor volledig weg. Gevonden in de zorgoogst
        # van boekjaar 2020 (Actief Zorg B.V.).
        "rechtsvorm zonder punten bij een korte eennaam, via de aliastabel (Actief Zorg 2020)",
        "waaronder eventuele significante tekortkomingen in de interne beheersing, "
        "Tilburg, 24 september 2021 Joore NV wg. D.E. van Boekel Msc. RA AA",
        "Joore N.V.",
    ),
    (
        # Dezelfde woorden in de andere volgorde. Het register kent 13000490 als
        # Kreston Van Herwijnen Accountants B.V. te Tiel; het briefpapier van dat
        # kantoor zet zijn eigen naam andersom.
        "woordvolgorde omgedraaid, via de aliastabel (DIT Coaching 2019)",
        "bij de financiële productieverantwoording op totaalniveau. Tiel, "
        "3 juni 2020 VAN HERWIJNEN KRESTON ACCOUNTANTS B.V. "
        "Stephensonstraat 19 4004 JA Tiel",
        "Kreston Van Herwijnen Accountants B.V.",
    ),
    (
        # HLB is een netwerkmerk, geen kantoor. hlb.nl schrijft zelf dat de vijf
        # Nederlandse HLB-kantoren "volledig autonoom" werken en zelfstandige
        # rechtspersonen zijn. Twee daarvan hebben een Wta-vergunning (Den Hartog
        # 13000106, Nannen 13000479) en Van Daal niet. Als het merk zwaarder zou
        # gaan wegen dan de rest van de naam, kreeg Van Daal de opdrachten van
        # Den Hartog toegeschreven — en dat is precies het soort verwisseling
        # waar dit bestand voor bestaat.
        "netwerkmerk verwisselt de kantoren niet (ThuisZorg 2019)",
        "waaronder eventuele significante tekortkomingen in de interne beheersing. "
        "Dongen, 18 juni 2020 HLB van Daal Audit B.V. "
        "w.g. P.W.M.H. Kosters Registeraccountant",
        "HLB van Daal Audit B.V.",
    ),
    (
        "hetzelfde merk, het ándere kantoor (HLB Den Hartog)",
        "Rotterdam, 5 juni 2021 HLB Den Hartog Accountants & Consultants "
        "w.g. A. Jansen RA",
        "HLB Den Hartog Accountants & Consultants",
    ),
    (
        # Hier is niet de ampersand maar de merknaam zelf verhaspeld: "Witlox"
        # komt er als "Wilox", "vtlox" en "Witiex" uit, terwijl "VCS Accountants"
        # heel blijft. Nagemeten over de hele OCR-cache (12-8-2026): "VCS" komt
        # nooit zonder Witlox ervoor, en het register kent maar één VCS, dus de
        # kortere sleutel kan niet naar een ander kantoor wijzen.
        "de merknaam is verhaspeld, de rest niet (zorgoogst 2019)",
        "Breda, 31 augustus 2020 Wilox VCS Accountants "
        "Was getekend M. Kilingarslan RA",
        "Witlox VCS audit B.V.",
    ),
    (
        # De naam van het kantoor is hier half weggevallen ("Namens V r Net
        # Accountants B.V."), maar het briefpapier erboven draagt hem voluit.
        # Let op: "P. van der Net RA" eronder is de tekenend accountant en geen
        # kantoor — precies het soort persoonsnaam waar de matcher niet in mag
        # trappen.
        "kantoor uit het briefpapier, persoonsnaam eronder (productieverantwoording 2020)",
        "transacties en gebeurtenissen zonder materiële afwijkingen weergeeft. "
        "Arnhem, 29 maart 2021 Namens Van der Net Accountants B.V. "
        "P. van der Net RA",
        "Van der Net Accountants B.V.",
    ),
    (
        "een straatnaam die op een kantoornaam lijkt (Parallelweg)",
        "Weert, 3 juni 2021 Jacobs Accountants B.V. Parallelweg 12 6001 HM Weert",
        None,
    ),
]


def vervallen_vergunning(index: dict) -> list[tuple[str, bool]]:
    """Kantoren waarvan de vergunning is vervallen, en wat dat betekent.

    Waarom dit apart getest wordt: `wta_vergunning` staat in de tegenwoordige
    tijd en is voor deze kantoren onwaar — ze stáán niet meer in het register.
    Maar een woningcorporatie is controleplichtig, en de lader leidt uit "geen
    vergunning" af dat het geen wettelijke controle kán zijn. Zonder `wta_ooit`
    kregen vijftien corporaties die accon avm liet controleren daardoor de
    stempel "vrijwillige controle" — onjuist, en het leest als een misstand die
    er nooit is geweest. Accon avm tekende bevoegd; de vergunning verviel pas
    jaren later door de fusie met Flynth Audit.
    """
    uitkomsten = []
    for naam, verwacht_ooit in [
        # Vergunning vervallen door een juridische fusie: tekende destijds bevoegd.
        ("Accon AVM", True),
        ("Accon-AVM Controlepraktijk B.V.", True),
        ("Astrium Overheidsaccountants B.V.", True),
        # Nooit een vergunning gehad: hier is "geen wettelijke controle" juist wél
        # het goede antwoord, en dat mag deze uitzondering niet stilletjes opheffen.
        ("WITh Accountants B.V.", False),
        ("FSV Accountants + Adviseurs B.V.", False),
        ("ACAM Accountancy en Advies", False),
    ]:
        treffer = zoek_kantoor(f"Rotterdam, 1 juni 2026 {naam}", index)
        kantoor = treffer["kantoor"] if treffer and not treffer["zwak"] else None
        goed = kantoor is not None and bool(kantoor.get("wta_ooit")) == verwacht_ooit
        # Een vervallen vergunning is nooit een huidige vergunning.
        if kantoor is not None and kantoor["wta_vergunning"]:
            goed = False
        uitkomsten.append((f"vervallen vergunning: {naam!r} -> ooit={verwacht_ooit}", goed))
    return uitkomsten


def main() -> int:
    index = bouw_index(laad_kantoren())
    fouten = 0
    for omschrijving, goed in vervallen_vergunning(index):
        fouten += not goed
        print(f"{'✓' if goed else '✗'} {omschrijving}")
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
    gedaan = len(GEVALLEN) + len(vervallen_vergunning(index))
    print(f"\n{gedaan - fouten}/{gedaan} goed")
    return 1 if fouten else 0


if __name__ == "__main__":
    raise SystemExit(main())
