# Bronverkenning: aanbestede accountantsdiensten (TED)

*Verkend en gemeten op 4-8-2026. Uitkomst: gebouwd — adapter
`pipeline/adapters/tenderned.py`, lader `pipeline/laad_gunningen.py`, workflow
"Gunningen laden".*

## Waarom deze bron

Alle bestaande bronnen dekken privaatrechtelijke organisaties: zorg,
corporaties, goede doelen, beursfondsen. De hele **publieke laag** ontbrak —
342 gemeenten, 12 provincies, 21 waterschappen, 25 veiligheidsregio's,
gemeenschappelijke regelingen en onderwijsbesturen. Die zijn allemaal
controleplichtig en moeten hun accountant **Europees aanbesteden**. De gunning
staat openbaar in TED (Tenders Electronic Daily).

## Gemeten

| Wat | Uitkomst |
|---|---|
| Toegang | `POST https://api.ted.europa.eu/v3/notices/search` geeft HTTP 200 zonder sleutel en zonder inlog (GET geeft 405) |
| Gunningsberichten sinds 1-1-2024 | 403 in CPV-familie 79200000, aanbesteder in Nederland |
| Waarvan met een winnaar die een accountantskantoor is | **241**, over **233 opdrachtgevers** en 27 kantoren |
| Verdeling opdrachtgevers | 114 gemeenten, 15 onderwijs, 11 gemeenschappelijke regelingen, 7 veiligheidsregio's, 6 provincies, 3 waterschappen, 85 overig |
| Historie | 796 berichten over 2016-2023, waarvan **11** met een winnaarsveld |

Die laatste regel is de belangrijkste beperking: de velden `winner-name` en
`contract-conclusion-date` bestaan pas onder **eForms**, dat vanaf ongeveer
december 2023 in gebruik is. Voor oudere jaren staat de winnaar wél in de
jaarlijkse CSV-export van TED op data.europa.eu (naar verluidt ~91% gevuld);
die route is nog niet gebouwd.

## Twee valkuilen, en wat ertegen is gedaan

**1. De oudercode is nodig, en vervuilt.** De meeste gemeentelijke
accountantsaanbestedingen staan onder CPV 79200000 ("boekhoudkundige, audit- en
fiscale diensten"), niet onder de specifieke 79212\*-codes. Filteren op alleen
79212\* kost meer dan de helft van de populatie. Maar 79200000 vangt óók
WOZ-software, salarisadministratie en organisatieadvies: in de eerste acht
treffers van 2024 zaten `xxllnc Belastingen B.V.`, `ANG B.V.` en `Boer & Croon
Management Solutions`.

**2. De kantorenlijst is het filter.** In plaats van op de titel te raden, gaat
elke winnaar langs het AFM-register en de lijst met kantoren zonder
Wta-vergunning — dezelfde toets die de rest van de pipeline gebruikt. Wat daar
niet in staat is geen accountantskantoor. Van 411 winnaarsregels bleven er 241
over; wat afviel staat in het rapport, zodat een échte accountant die wij nog
niet kenden opvalt in plaats van stilletjes te verdwijnen.

Opvallend in de afvallers, en terecht: `Forvis Mazars N.V.`,
`PricewaterhouseCoopers B.V.` en `KPMG Advisory N.V.`. Dat zijn de advies-
entiteiten van die netwerken, niet de accountantsorganisaties met een
Wta-vergunning (`Forvis Mazars Accountants N.V.`, `PricewaterhouseCoopers
Accountants N.V.`). Een gunning aan de adviestak is geen controleopdracht.

## De ontwerpkeuze die alles bepaalt: een gunning is geen opdracht

Een gunning is een **benoeming vooraf**, voor doorgaans vier jaar. Of die
controle er kwam, en met welk oordeel, staat er niet in; het aanbestede pakket
heet vaak "accountantsdiensten" en is breder dan de wettelijke controle.

Als we dit als `opdrachten` zouden wegschrijven, zou de database vier boekjaren
controle beweren die niemand heeft waargenomen. Vandaar een **eigen tabel**
`gunningen` (migratie `20260804180000`) met een eigen betekenis: *hier is een
kantoor benoemd, op deze datum*. Op de organisatie- en kantoorpagina staat dat
er ook letterlijk bij.

Wat deze bron uniek toevoegt en de andere niet kunnen: het **moment** van
wisselen, met een datum. De andere bronnen leiden een wisseling af uit twee
opeenvolgende boekjaren en weten dus nooit wanneer het besluit viel.

## Nog niet gedaan

- **Oudere jaren (2016-2023)** via de jaarlijkse CSV-export van TED.
- **Nationale aanbestedingen.** Kleine gemeenten besteden soms nationaal aan;
  die berichten bereiken TED nooit en staan alleen op TenderNed. Het gaat om
  enkele tientallen gunningen.
- **Gezamenlijke aanbestedingen.** Eén gunning kan meerdere gemeenten dekken
  ("Gemeenten Deventer, Olst-Wijhe en Raalte"); de meegelifte gemeenten staan
  alleen in ongestructureerde tekst en worden nu niet apart vastgelegd.

## De XML-route: 2016-2023 erbij (5-8-2026)

Het zoekantwoord van de API draagt alleen een `winner-name` voor
eForms-berichten, ruwweg vanaf december 2023. Dat leek een randgeval maar was
het niet: het is precies de periode waarin de meeste gemeenten hun accountant
hebben aanbesteed. Een gemeente besteedt eens in de vier tot acht jaar aan, dus
met alleen 2024-2026 zie je hooguit een derde van de markt.

De winnaar staat er wél in, maar dan in het XML-bericht zelf. Voor elk bericht
zonder `winner-name` halen we dat bericht op — één verzoek, alleen voor wat
anders niets zou opleveren.

Twee schema's, allebei nodig:

| Periode | Gunningsblok | Winnaar staat in | Datum |
|---|---|---|---|
| 2016-2017 | `AWARD_OF_CONTRACT` | `ECONOMIC_OPERATOR_NAME_ADDRESS` | losse `DAY`/`MONTH`/`YEAR` |
| 2018-2023 | `AWARD_CONTRACT` | `AWARDED_CONTRACT` › `CONTRACTORS` › `CONTRACTOR` › `ADDRESS_CONTRACTOR` | `DATE_CONCLUSION_CONTRACT` |

De valkuil is `<OFFICIALNAME>`: die tag staat óók om de aanbesteder zelf en om
de rechtbank waar je bezwaar kunt maken. In het bericht van Gemeente
Vlaardingen staat hij vier keer, en maar één ervan is het kantoor. Daarom
knippen we eerst het gunningsblok uit en zoeken we daarbinnen alleen in het
contractor-omhulsel. De naam van de aanbesteder komt niet uit de XML maar uit
het zoekantwoord, waar hij netjes per taal is uitgesplitst.

Opbrengst over 1-1-2016 t/m nu: **1.142 regels met een winnaar**, waarvan
**725 gunningen** aan een herkend kantoor. Zonder de XML-route waren dat er
412 respectievelijk 244.

## Wat de afvallers leerden over de kantorenlijst

Van de 470 winnaars die eerst geen kantoor bleken, was een flink deel wél een
accountantskantoor — alleen onder een naam die de lijst niet kende. Dat is
opgelost in de seeds, niet in de matcher:

- **Aliassen** voor kantoren die al in het AFM-register staan onder een andere
  naam: Baker Tilly Berk (nu Baker Tilly), Stolwijk Kelderman, Crowe Foederer,
  Afier, Vallei Accountants, en de koepelnamen waaronder de grote vier
  aanbestedingen winnen (Mazars N.V., Ernst & Young Nederland LLP,
  PricewaterhouseCoopers B.V.).
- **Drie kantoren buiten het register**, alle drie gespecialiseerd in
  gemeenten: Astrium Overheidsaccountants (in 2022 opgegaan in Flynth Audit),
  Ipa-Acon Assurance (onderdeel van ETL Nederland) en Hofsteenge Zeeman Groep.

Wat bewust géén alias krijgt, en dus blijft afvallen:

- **Kale merknamen** ("Deloitte", "Ernst & Young", "Baker Tilly"). Die als
  zoeksleutel opnemen zou een eerder opgeloste fout terugbrengen: dezelfde
  index leest ook jaarverslagen, en daar staat een kantoornaam net zo goed in
  het cv van een commissaris. Kost acht gunningen, voorkomt een onbekend
  aantal verzonnen opdrachten.
- **Advies-, fiscale en consultancy-entiteiten** van dezelfde merken: KPMG
  Advisory N.V., Deloitte Risk Advisory B.V., EY Belastingadviseurs B.V.,
  PricewaterhouseCoopers Belastingadviseurs N.V. Die dragen hun functie in de
  naam, winnen onder dezelfde CPV-familie, en doen geen wettelijke controle.
