# Bestaat de database al? — verkenning van bestaande bronnen

*Onderzocht 30-7-2026, naar aanleiding van de vraag "misschien is er al een database".
Alle cijfers hieronder zijn gemeten of uit de bron geciteerd, niet geschat.*

## Kort antwoord

**Nee, er is geen database die de Nederlandse opdrachtrelatie dekt** — maar er zijn drie
soorten bronnen die stukken ervan kant-en-klaar leveren, en één daarvan hebben we
tot nu toe gemist:

| | Wat het is | Dekking | Kosten |
|---|---|---|---|
| 🥇 **dVi woningcorporaties** | open dataset mét kolom `Accountant` per corporatie | ±272–349 corporaties × boekjaren 2015–2024 | gratis (CC-0) |
| **BZK-gemeenten** | marktaandeel per kantoor + oordelen, jaarlijks rapport | 330 gemeenten, 17 kantoren | gratis |
| **AFM Sector in Beeld** | sectortotalen en marktaandelen wettelijke controles | hele markt, geaggregeerd | gratis |
| **Audit Analytics Europe** | opdrachten, wisselingen, honoraria, KAM's, transparantieverslagen | 8.000 EU-**beursfondsen**, vanaf 2010 | commercieel |
| **ESAP (ESMA)** | jaarrekeningen + controleverklaringen centraal, met API | hele EU, vanaf 2028 | gratis |

De belangrijkste conclusie: **voor woningcorporaties hoeven we helemaal geen pdf's te
lezen.** De accountant staat er als veld in, met KvK-nummer ernaast, tien boekjaren diep.
Dat is de goedkoopste vertical die we tot nu toe zijn tegengekomen — goedkoper nog dan
de zorg en de goede doelen, waar het pdf-spoor nodig was.

## 1. dVi woningcorporaties — de accountant staat er gewoon in

Bron: Autoriteit woningcorporaties (Aw/ILT), gepubliceerd op data.overheid.nl,
licentie **CC-0** (vrij te gebruiken, geen bronvermeldingsplicht).

Hoofdstuk 1 van de verantwoordingsinformatie (dVi) bevat per corporatie:

```
KVK_nummer | Instellingsnummer | Instellingsnaam | GEMEENTE | Scheidingsregime |
Accountant | BalAfwijk | … | WerknEV | WerknGC
```

Gemeten op de jaargangen die we hebben opgehaald:

| Jaargang | Corporaties | Met accountantsnaam | Met KvK-nummer | Veldnaam |
|---|---|---|---|---|
| dVi2015 | 349 | 349 (100%) | ja | `CorpGeg_AccountantOrg_j1515` |
| dVi2022 | 277 | 277 (100%) | 277 (100%) | `Accountant` |
| dVi2024 | 272 | 272 (100%) | ja | `Accountant` |

Beschikbare jaargangen: **2007 t/m 2024** (2007–2013 als één bestand hoofdstuk 1 t/m 5,
daarna los, 2023–2024 weer gebundeld). Vanaf 2015 zijn ze los per hoofdstuk en direct
bruikbaar; dat zijn tien boekjaren, oftewel in de orde van **3.000 opdrachtrijen** met
negen jaarovergangen om wisselingen uit te lezen.

**Marktaandeel corporaties, boekjaar 2022** (na normalisatie tegen onze kantorenlijst):
BDO 65, Deloitte 35, Q-Concepts 24, PwC 20, Verstegen 19, EY 17, Forvis Mazars 17,
KPMG 11, Share Impact 9. In 2024 is BDO nog groter (51 van de 272) en Deloitte gehalveerd
(20) — er is dus beweging in te zien.

### Gebouwd en gemeten (30-7-2026)

`adapters/aw_dvi.py` + `laad_corporaties.py` + workflow *Corporatiedata laden*. Droogloop
op drie jaargangen:

| Boekjaar | Corporaties | Opdracht | Review |
|---|---|---|---|
| 2024 | 272 | **271** | 1 |
| 2022 | 277 | **275** | 2 |
| 2015 | 349 | **335** | 14 |

Wat overblijft zijn typefouten in de bron ("Deloitte Acocuntants B.V.", "BakerTillyBerk",
"Verstegen accountants en advisuers") en historische namen ("Mazars Paardekoper Hoffman
N.V.", "Accountantskantoor Foederer B.V."). Die gaan naar de review-queue met de opgegeven
naam erbij — één regel werk per geval.

En dit is wat de sector meteen laat zien, 2015 tegen 2024:

| Kantoor | 2015 | 2024 | |
|---|---|---|---|
| Deloitte | 94 | 29 | −65 |
| EY | 62 | 19 | −43 |
| BDO | 98 | 66 | −32 |
| PwC | 42 | 22 | −20 |
| Q-Concepts | 1 | **31** | +30 |
| Verstegen | 12 | **36** | +24 |
| Forvis Mazars | 0 | 23 | +23 |
| Share Impact | 0 | 12 | +12 |

De Big 4 zijn in tien jaar uit deze sector weggelopen (of weggestuurd) en gespecialiseerde
kantoren hebben het overgenomen. Dat is precies het soort feit waarvoor dit product
bestaat — en het staat gratis online.

Twee dingen om rekening mee te houden, allebei bekend terrein:

1. **De schrijfwijze is een zooitje.** In één jaargang komt BDO voor als "BDO Audit &
   Assurance B.V.", "BDO Audit en Assurance BV", "BDO Audit&Assurace BV" en zelfs
   "BDO Audit @ Assurance B.V."; Verstegen in acht varianten. Onze bestaande matcher komt
   daarmee op **225 van de 277 (81%)**; de missers zijn vrijwel allemaal de korte vorm
   ("BDO", "Deloitte", "Baker Tilly"), die met een handvol aliassen op te lossen is.
   Let op: dit veld is zelfgerapporteerd door de corporatie en dus géén ondertekening —
   de positiecontrole uit `kantoor_match` slaat hier niet aan en is hier ook niet nodig.
2. **De veldnaam wisselt per jaargang**, net als bij DigiMV. Dus een mapping per jaar
   bijhouden, precies zoals `adapters/digimv_dataset.py` dat doet.

Eén rij bevatte twee kantoren ("PricewaterhouseCoopers Accountants N.V. en BDO Audit &
Assurance B.V."). Zulke gevallen horen in de review-queue, niet in een gok.

## 2. BZK — marktaandeel en oordelen bij gemeenten

Bron: *Integraal Overzicht Financiën Gemeenten* (BZK, jaarlijks, open.overheid.nl).
Editie 2025 bevat over boekjaar 2024:

- **Marktaandeel per kantoor** (aantal gemeenten, met mutatie t.o.v. vorig jaar):
  Baker Tilly 50 (−5), Deloitte 40 (−2), BDO 40 (−3), Eshuis 33 (−2),
  Crowe Foederer 24 (+6), PwC 23 (+3), ETL 23 (+1), PSA 21 (+1), Verstegen 18 (+2),
  **Flynth 12 (−16)**, Stolwijk Kelderman 11 (−3), RSM 10, KSG 8 (+2), RA12 6 (+4),
  WHS 5 (+3), Mijn Overheidsaccountants 3 (+3), plus de gemeentelijke
  accountantsdiensten GAD (Den Haag) en ACAM (Amsterdam), en Q-Concepts 1 (−2).
- **Oordelen:** 328 van de 330 goedkeurend, 2 met beperking (Goeree-Overflakkee en
  Voorne aan Zee), geen enkele afkeurend of oordeelonthouding.
- 17 kantoren in deze markt; van 12 gemeenten was het oordeel nog niet bekend.

Wat er **niet** in staat: welk kantoor bij wélke gemeente. BZK baseert het op
aanleveringen van gemeenten, dus die per-gemeente-tabel bestáát — hij wordt alleen niet
gepubliceerd. Twee routes: een Woo-verzoek bij BZK, of de gemeentelijke jaarstukken en
raadsbesluiten zelf (die zijn openbaar, maar per gemeente verspreid).

Voor nu is dit vooral **gratis validatiemateriaal en een verhaal**: Flynth die in één jaar
zestien gemeenten verliest, is precies het soort feit waar dit product om draait.

## 3. AFM Sector in Beeld — de totalen om tegen te ijken

De AFM vraagt jaarlijks bij alle accountantsorganisaties de wettelijke controles op
(*uitvraag wettelijke controles*). De onderliggende data is niet openbaar, de
geaggregeerde uitkomsten wel:

- over 2021 t/m 2024: **22.633 wettelijke controles** door regulier vergunninghouders en
  **15.595** door OOB-organisaties;
- het marktaandeel van reguliere vergunninghouders bij niet-OOB-cliënten groeide van 18%
  (2014) naar **40%** (2024); de omzet daar van €678 mln naar €1.485 mln;
- naar schatting **36%** van de wettelijke controles door reguliere vergunninghouders
  wordt in 2025 gedaan door een kantoor dat (deels) in handen is van private equity —
  tegen 11% in 2023.

Nuttig op drie manieren: het bevestigt de orde van grootte in `docs/concept.md`
(±20.000 wettelijke controles per jaar), het geeft ons een noemer om dekking tegen af te
zetten ("wij hebben X van de ±20.000"), en de PE-trend is een verhaallijn die niemand
anders per kantoor zichtbaar maakt.

## 4. Commercieel: Audit Analytics Europe (en Orbis, Company.info)

**Audit Analytics Europe** (Ideagen) is het dichtst bij "onze database": opdrachten en
mandaten, wisselingen, honoraria (73.000 records vanaf 2010), oordelen, key audit matters
en transparantieverslagen. Maar: **alleen beursgenoteerde ondernemingen** — 8.000 stuks in
31 EEA-landen plus Zwitserland, waarvan een paar honderd Nederlands. Dat is precies het
segment dat wij in Fase 4 uit de OOB-transparantieverslagen halen, en het zegt niets over
de zorg, de goede doelen, de corporaties of de gemeenten. Licenties lopen via WRDS
(universiteiten) of direct; commercieel geprijsd.

**Orbis** (Moody's/Bureau van Dijk) en **Company.info** leveren bedrijfsdata en
jaarrekeningen (pdf en XML/XBRL) van alle Nederlandse rechtspersonen, met API's. Dat is
interessant als leverancier van *jaarrekeningen op naam* — de dure route uit
`docs/concept.md` (backlog: KvK-deponeringen) — maar geen van beide adverteert een
onderhouden accountant-veld voor de hele markt. Vóór er geld naartoe gaat: eerst een
proefbestand opvragen en tellen hoe vaak het accountantsveld gevuld is.

## 5. ESAP — vanaf 2028 wordt de grondstof gratis

ESMA moet het **European Single Access Point** uiterlijk **10 juli 2027** in de lucht
hebben. Bedrijven leveren aan een nationale verzamelinstantie, die via één API doorlevert
aan het centrale portaal; toegang is gratis en machineleesbaar. Fasering:

| Vanaf | Wat |
|---|---|
| jan 2028 | jaarrekeningen, bestuursverslagen, duurzaamheidsrapportage **en controleverklaringen** |
| jan 2030 | transparantieverslagen van accountantsorganisaties en sancties |
| jan 2031 | CSDDD-verklaringen |

Dat verandert de strategie niet, maar wel de klok. Wat wij nu met pdftotext uit
jaarverslagen peuteren, komt vanaf 2028 in gestructureerde vorm uit één API — voor het
deel van de markt dat onder de EU-openbaarmakingsregels valt. De moat verschuift daarmee
van *toegang* naar wat ESAP níét zal hebben: **de historie van vóór 2028**, de
semipublieke sector buiten de EU-richtlijnen (zorg, goede doelen, corporaties, gemeenten)
en de relatiegraaf zelf. Dat is precies waar WhoSigns nu op inzet — en het is een extra
argument om de historie te oogsten vóór bronnen hun oude jaargangen weggooien.

## Wat dit betekent voor de bouwvolgorde

1. **Woningcorporaties zijn nu de goedkoopste vertical.** Geen archief, geen pdf's, geen
   OCR: één xlsx per boekjaar, KvK-nummer inbegrepen, tien jaargangen historie. Een
   adapter `adapters/aw_dvi.py` in de geest van `digimv_dataset.py` (veldnaam per jaar,
   normaliseren tegen de kantorenlijst, rest naar de review-queue) levert naar schatting
   3.000 opdrachtrijen op. Dat is meer dan de goededoelensector, voor een fractie van het
   werk.
2. **Gemeenten: begin met het marktaandeel, niet met de relatie.** De BZK-cijfers zijn
   direct te tonen (en jaarlijks te verversen); de koppeling per gemeente kan later via
   een Woo-verzoek of de jaarstukken.
3. **AFM-totalen als noemer en als kwaliteitscontrole** bij elke sector die we laden.
4. **Niets kopen** zolang de gratis verticals nog niet uitgeput zijn. Audit Analytics
   dekt alleen het segment dat we via transparantieverslagen gratis kunnen krijgen.

## Bronnen

- dVi/dPi open data woningcorporaties: <https://www.ilent.nl/onderwerpen/autoriteit-woningcorporaties/publicaties-cijfers-en-wetgeving-autoriteit-woningcorporaties/publicaties-en-data/open-data>
  en de datasets op <https://data.overheid.nl/dataset/verantwoordingsinformatie-woningcorporaties-dvi2022-hfd1>
- Integraal Overzicht Financiën Gemeenten 2025 (BZK): <https://open.overheid.nl/documenten/0ceeb3e8-e2b6-4237-9772-f75087e320ed/file>
- AFM Sector in Beeld 2025 — Accountancy en Verslaggeving: <https://www.afm.nl/~/profmedia/files/rapporten/2025/sector-in-beeld-2025-accountancy-en-verslaggeving.pdf>
- AFM uitvraag wettelijke controles (aanleverspecificatie): <https://www.afm.nl/~/profmedia/files/doelgroepen/accountantsorganisaties/2024/aanleverspecificaties-uitvraag-wettelijke-controles-2024-v14.pdf>
- Audit Analytics Europe: <https://www.auditanalytics.com/product-catalog?filter=europe>
- ESAP-factsheet (Accountancy Europe): <https://accountancyeurope.eu/wp-content/uploads/2024/06/ESAP-factsheet.pdf>
  en de EU-samenvatting: <https://eur-lex.europa.eu/EN/legal-content/summary/european-single-access-point.html>
- Orbis (Moody's): <https://www.moodys.com/web/en/us/capabilities/company-reference-data/orbis.html> ·
  Company.info: <https://companyinfo.nl/bedrijfsinformatie/financiele-informatie-bedrijven/>
