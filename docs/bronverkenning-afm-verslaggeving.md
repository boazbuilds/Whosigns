# Bronverkenning: AFM-register financiële verslaggeving (beursfondsen)

*Verkend en gemeten op 4-8-2026. Uitkomst: gebouwd — adapter
`pipeline/adapters/afm_verslaggeving.py`, lader
`pipeline/laad_beursfondsen.py`, workflow "Beursfondsdata laden".*

## Waarom deze bron

De toets blijft: *publiceert één partij de verklaringen (of de
accountantsnaam) voor de hele populatie?* Ja: uitgevende instellingen met
Nederland als lidstaat van herkomst moeten hun jaarlijkse financiële
verslaggeving bij de AFM deponeren (Transparantierichtlijn), en de AFM
publiceert de gedeponeerde jaarverslagen in een openbaar register. In elk
jaarverslag zit de controleverklaring — met oordeel én ondertekenend
kantoor. Waar de transparantieverslagen (bron: de kantoren zelf) teruggaan
tot boekjaar 2019, gaat dit register terug tot **boekjaar 2006**: dertien
jaar extra relatiegeschiedenis en kantoorwisselingen in het beurssegment.

## Gemeten

| Wat | Uitkomst |
|---|---|
| Deponeringen totaal | 9.645 (csv-export van het register) |
| Waarvan jaarlijkse verslaggeving | 4.201, van 547 instellingen |
| Boekjaren | 2006 t/m 2025, ~150-270 per jaar |
| Documentlinks | niet in de export; wél via lijstpagina's (`?page=1..193`) naar detailpagina's met per deponering één downloadlink |
| Documentvorm | t/m ~boekjaar 2019 pdf; daarna ESEF-zip met het verslag als xhtml (inline XBRL) |

Drie proefdocumenten door de bestaande verklaring-extractie gehaald
(ongewijzigd, dezelfde leesregels als voor de CBF-verslagen):

| Proef | Uitkomst |
|---|---|
| Envipco Holding N.V., boekjaar 2025 (ESEF-zip) | kantoor **BDO Audit & Assurance B.V.**, oordeel goedkeurend — klopt met de ondertekening in het verslag |
| HAL Trust, boekjaar 2012 (pdf) | géén match: getekend door *PricewaterhouseCoopers Bermuda* — terecht niet aan het Nederlandse PwC gekoppeld; naar de review-wachtrij |
| Pacific Life Funding LLC, boekjaar 2008 (pdf) | geen verklaring herkend (Amerikaans stuk) — afgekeurd |

De ESEF-leesregel die dit mogelijk maakt: inline-XBRL wikkelt spans dwars
door woorden heen, dus bloktags worden regeleindes en alle overige tags
verdwijnen geluidloos (`xhtml_naar_tekst`, met test).

## Drie keuzes

1. **Batch per boekjaren.** Eén boekjaar is 1-3 GB aan documenten; alles
   ineens is tientallen gigabytes. De workflow draait per bereik
   (standaard 2020-2025); documenten worden na het uitlezen weggegooid en
   alleen de tekst blijft in de cache, zodat een herstart niets opnieuw
   downloadt.
2. **Bestaande rijen winnen.** Wat al uit een transparantieverslag bekend
   is, blijft staan; deze bron vult alleen aan. De winst zit vooral vóór
   2019. (Later denkbaar: rijen uit transparantieverslagen "opwaarderen"
   met het oordeel uit de verklaring — nu bewust niet, eenvoud eerst.)
3. **Nooit stil gokken.** Buitenlandse accountants (HAL Trust) en
   onherkenbare ondertekeningen gaan met kandidaat-namen naar de
   review-wachtrij.

Organisaties worden op genormaliseerde naam herkend (ASML uit het
transparantieverslag krijgt er geen tweede rij naast); nieuwe organisaties
krijgen sector "OOB" en geen KvK-nummer, zoals bij de transparantiebron.

## Uitbreiden

Nieuwe deponeringen verschijnen doorlopend in het register; de workflow
opnieuw draaien met een recent bereik pakt ze op. Voor de historie: in een
paar runs terugwerken ("2014-2019", "2006-2013"). Halfjaarcijfers en
tussentijdse verklaringen worden bewust overgeslagen — daar zit geen
controleverklaring bij de jaarrekening in.
