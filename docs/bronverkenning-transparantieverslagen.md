# Bronverkenning: transparantieverslagen van de OOB-kantoren

*Verkend en gemeten op 4-8-2026. Uitkomst: gebouwd — adapter
`pipeline/adapters/transparantie.py`, lader `pipeline/laad_transparantie.py`,
workflow "Transparantiedata laden".*

## Waarom deze bron

De toets uit de eerdere verkenningen: *publiceert één partij de verklaringen
(of de accountantsnaam) voor de hele populatie?* Hier is het antwoord ja,
door een wettelijke plicht: artikel 13 lid 2 onder f van EU-verordening
537/2014 verplicht elke accountantsorganisatie met OOB-vergunning om in haar
jaarlijkse transparantieverslag **de lijst op te nemen van organisaties van
openbaar belang waarvoor zij wettelijke controles verrichtte**. Banken,
verzekeraars, beursfondsen en (aangewezen) grote woningcorporaties staan
nergens anders openbaar met hun accountant — ASML, ABN AMRO en Adyen wel in
deze lijsten.

Zes kantoren hebben een OOB-vergunning (AFM-register, stand 29-7-2026):
BDO, Deloitte, EY, KPMG, Forvis Mazars en PwC.

## Gemeten

Alle zes kantoren publiceren de lijst, elk in een eigen vorm (details en de
bijbehorende leesregels: `adapters/transparantie.py`). Oogst per verslag na
vier iteraties van de leesregels, handmatig gecontroleerd op begin en eind
van elke lijst:

| Verslag | Namen | Bijzonderheid |
|---|---|---|
| BDO 2024 | 88 | losse "X" vóór elke naam (twee kolommen) |
| BDO 2023 | 86 | zelfde opbouw als 2024 |
| Deloitte 2024/2025 | 125 | lijst loopt over in disclaimerblok |
| EY 2024/2025 | 137 | lange namen breken af over twee regels |
| KPMG 2024/2025 | 116 | in het integrated report van 276 pagina's |
| Forvis Mazars 2023/2024 | 76 | branchekopjes tussen de namen |
| PwC 2024/2025 | 120 | apart bijlagen-pdf; voetnoten dwars door de lijst |

**Tweede ronde (4-8-2026):** acht oudere jaargangen
toegevoegd en gemeten — Deloitte 2019/2020 t/m 2023/2024 (125, 125, 129, 129
en 124 namen; de oudere jaren dragen de kop "PIEs audited"), EY 2022/2023
(140), KPMG 2023/2024 (117) en PwC 2021/2022 (138, bijlagen-pdf met de
Nederlandse kop "Lijst van organisaties van openbaar belang", die over twee
regels gebroken kan zijn). PwC's bijlage was niet vindbaar via de site
(scriptpagina); de link staat als URI-annotatie ín het hoofdverslag-pdf en is
daar uitgelezen. **Derde ronde (4-8-2026):** BDO 2022 (83), Forvis Mazars
2024/2025 (78) en — via het geraden pad `jaarbericht{jaar}` — PwC 2022/2023
(161) en 2023/2024 (161). Samen 2.258 cliëntregels over negentien verslagen.
Nog toe te voegen langs hetzelfde recept: BDO t/m 2021, EY 2023/2024 (url
nog niet gevonden), KPMG t/m 2022/2023, Mazars oudere jaren, PwC t/m
2020/2021.

Bij de derde ronde zijn de leesregels aangescherpt na een handmatige
staartcontrole: samenvoegen van afgebroken namen mag alleen nog tussen
regels die pál op elkaar aansluiten (elk lijmgeval bleek juist ná een
witregel of zijbalkfragment te komen), voetnootregels met sterretjes worden
afgekeurd, een naam die op een los voorzetsel eindigt krijgt de regel
eronder erbij ("Stichting Bedrijfstakpensioenfonds voor de" +
"Bouwnijverheid") en een losse soortnaam-met-rechtsvorm ("Zorgverzekeraar
U.A.") wordt nooit meer als eigen organisatie bewaard. De twaalf gevallen
staan in `pipeline/test_transparantie.py`; de migratie
`20260804090000_transparantie_reset.sql` wist de rijen die de oude
leesregels hadden vervuild, waarna één run van de workflow alles schoon
terugzet.

## Twee ontwerpkeuzes

1. **Boekjaarvertaling.** De lijst gaat over controles *verricht in het
   kantoorboekjaar*. Een verslag over 2024/2025 betreft dus grotendeels
   jaarrekeningen over 2024; BDO's kalenderjaarverslag 2024 grotendeels
   jaarrekeningen over 2023. Die vertaling staat per verslag in
   `seed/transparantieverslagen.csv` en is een benadering (gebroken
   boekjaren kunnen er één naast zitten).
2. **Bestaande rijen winnen.** Vanwege 1 en omdat DigiMV/CBF/dVi het oordeel
   én het precieze boekjaar kennen, schrijft deze lader nooit over een
   bestaande opdracht heen: hij vult alleen aan wat nergens anders staat.
   Corporaties uit de dVi-lading worden op genormaliseerde naam herkend en
   niet gedupliceerd.

Organisaties die alleen hier voorkomen krijgen sector "OOB" en geen
KvK-nummer (de verslagen noemen alleen namen); hun paginas dragen `o<id>` in
het adres, zoals kantoren zonder AFM-nummer `k<id>` dragen.

## Uitbreiden

Nieuwe jaargang? Eén regel bij `seed/transparantieverslagen.csv` (kop van de
lijstsectie meenemen) en de workflow draaien. Deloitte heeft een online
archief terug tot 2015/2016; PwC's oudere bijlagen hangen als URI-annotatie
in de verslagen zelf. Oudere jaargangen toevoegen = meer relatiegeschiedenis
en wisselingen in het OOB-segment.
