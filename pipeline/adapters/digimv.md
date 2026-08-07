# DigiMV / Jaarverantwoording Zorg — bronverkenning

*Kolominspectie boekjaar 2023 uitgevoerd op 28-7-2026 (roadmaptaak Fase 1). Andere
jaargangen volgen bij de bouw van de adapter.*

## Vindplaats datasets (.ods, per boekjaar)

Overzicht: `jaarverantwoordingzorg.nl/over-de-jaarverantwoording/gegevens-bekijken/gegevens-per-boekjaar`

| Boekjaar | Document-pagina (relatief aan jaarverantwoordingzorg.nl) |
|---|---|
| 2024 | `/documenten/2026/03/23/dataset-2024---deel-1` t/m `-deel-4` |
| 2023 | `/documenten/2024/10/08/definitieve-dataset-2023` → `DigiMV2023_MultipleTables_20241001_0927.ods` (15,3 MB) |
| 2022 | `/documenten/2024/05/28/definitieve-dataset-2022` |
| 2021 | `/documenten/2023/01/25/dataset-2021-zorg-jeugd-en-veilig-thuis` |
| 2020 | `/documenten/2023/01/25/digimv-2020-definitieve-dataset` |
| 2019 | `/documenten/2021/08/17/digimv-2019-deel-1` + `-deel-2` |
| 2018 | `/documenten/2021/08/17/digimv-2018-deel-1` + `-deel-2` |

Verder: archief met jaarrekeningen en verklaring-pdf's per organisatie
(`digimv13.desan.nl/archive/search`; de site verwijst ook naar digimv8/digimv12 —
het nummer wisselt, bij bouw actuele URL checken). SPSS-varianten op aanvraag via
info@jaarverantwoordingzorg.nl.

## Archief-API (uitgezocht 29-7-2026)

Het archief is een JavaScript-app met een openbare JSON-API eronder — geen scraping
van HTML nodig. Vastgelegd in `digimv_archief.py`:

```
GET /api/ArchiveSearch/GetArchiveSearchResult?organization=&town=&year=
GET /api/ArchiveSearch/GetDocument?documentId=&year=&fileNameOption=&fileName=
```

Zoeken vereist een organisatie- of plaatsfragment (leeg geeft niets terug). Een
resultaat bevat `name`, `town`, **`externalOrganizationId` = KvK-nummer**,
`concernId`, `documents[]`, `locations[]`, `desaveuElements[]`.

Gemeten op boekjaar 2023 (zoekterm "zorg", 1.720 organisaties): **alle 1.720 hebben
een KvK-nummer** — entity resolution is dus geen probleem. Documenttypen in die set:
1.470 Jaarrekening, 495 Accountantsverklaring, 263 Bestuursverslag, 244 Verslag
interne toezichthouder, 144 Verzameldocument, 111 Overig.

## Structuur dataset 2023 (gecontroleerd)

- 21 sheets: `VariableDefinition` (datadictionary: Order, VariableName, VariableLabel,
  DataType, Format, ValueLabelKey/Value — 9.365 rijen) + `RowData_01…` (elk max 256
  kolommen; de vragenlijst is over meerdere sheets uitgesmeerd).
- **6.132 organisaties** (datarijen per RowData-sheet).
- Kolomnamen zijn variabelenamen met prefix `Digimv.2020.prod` (formulierversie ≠
  boekjaar). Veldnamen verschillen per jaargang → mapping per jaar hier bijhouden.
- Join-logica tussen RowData-sheets (rijvolgorde of ConcernCode als sleutel) bij bouw
  bevestigen.

## Belangrijkste velden (2023) — allemaal gestructureerd aanwezig

| Wat | Veld(en) |
|---|---|
| KvK-nummer | `prodKvkNummerExternalOrganizationId`, `…qNawKvk` |
| Soort verklaring | `qAccVerklSoort` (o.a. samenstellingsverklaring; volledige waardenlijst uit de data halen — de dictionary toont alleen waarde 1) |
| **Oordeel** | `qAccVerklVorm` ("Vorm van accountantsverklaring", waarde 1 = goedkeurende verklaring) en `bestandAccVerklSoortControleVerkl_N` |
| **Wisselvlag** | `qAccountantWissel` — *"Bent u van accountant gewisseld?"* (zelfgerapporteerd, per boekjaar!) |
| Honoraria (gesplitst!) | `acc_jr_contr` (controle jaarrekening), `acc_ov_contr` (overige controle w.o. WNT), `acc_fisc_adv` (fiscale advisering), `acc_niet_contr` (niet-controlediensten), `acc_honoraria` (totaal) — telkens huidig + vorig boekjaar |
| Documentmetadata verklaring | `bestandAccountantsVerklaring_N` (bestandsnaam), `bestandDatumAccountantsVerklaring_N`, `bestandInstellingAccountantsVerklaring_N`, `bestandAccountantsVerklaringSoort_N` |

NB: sommige secties zijn Jeugdwet-specifiek; er bestaan parallelle Zorg/WMG/NZa-secties
(o.a. "NZa - Accountantsverklaring"). Veldmapping per doelgroep uitzoeken bij bouw.

## Wat er NIET in zit

- **De naam van de accountantsorganisatie.** Geen enkel veld bevat het kantoor. De
  kantoornaam staat in de verklaring-pdf's in het DigiMV-archief.
- Route voor het MVP (zonder LLM): pdf's ophalen (ruw opslaan), tekst extraheren
  (pdftotext) en de kantoornaam vinden via **stringmatch tegen de AFM-lijst +
  aliastabel** (~233 vergunninghouders, dus een kleine, gesloten matchlijst).
  Geen match → `review_queue`. LLM-vangnet (Claude API) pas in Fase 4.

## Meetresultaat kantoorextractie (29-7-2026) — de route werkt

Getest met `pipeline/valideer_extractie.py` (herhaalbaar) op boekjaar 2023:

| Steekproef | Controleverklaringen herleid tot een AFM-kantoor |
|---|---|
| 12 ziekenhuizen | **12/12 = 100%** |
| 41 gemengde zorginstellingen | **26/27 = 96%** |

Nul valse matches in beide steekproeven. Ook oordeel (goedkeurend / beperking /
oordeelonthouding / afkeurend) en continuïteitsonzekerheid komen deterministisch uit
dezelfde tekst; in de ziekenhuis-steekproef zaten 3 oordelen mét beperking en 2
continuïteitswaarschuwingen — meteen bruikbare signaaldata.

Wat we onderweg leerden:

1. **Samenstellings- en beoordelingsverklaringen matchen niet, en dat hoort zo.**
   Kleine zorg-BV's laten hun jaarrekening samenstellen door administratiekantoren
   *zonder* Wta-vergunning (die staan terecht niet in het AFM-register). Alleen een
   **controleverklaring** is een wettelijke controle. Meet dus nooit op "alle
   verklaringen" — dat onderschat de trefkans fors (60% i.p.v. 96%).
2. **De aliastabel is geen luxe.** Zonder aliassen bleef de trefkans op 85% steken.
   Twee echte gevallen: verklaringen over boekjaar 2023 zijn nog getekend door
   *Ernst & Young Accountants LLP* terwijl het AFM-register sinds juni 2024
   *EY Accountants B.V.* kent, en *De Jong & Laan Accountants en Advies B.V.*
   (handelsnaam) heeft zijn vergunning op *De Jong & Laan Controle B.V.*
   Startlijst staat in `pipeline/seed/kantoor_alias.csv`.
3. **Gescande pdf's zonder tekstlaag** komen voor (enkele procenten). Die leveren
   nul tekst en gaan naar de review-queue; OCR of het LLM-vangnet is Fase 4.
4. **Eén verklaring noemde het kantoor alleen in het logo** (afbeelding). Ook
   review-queue — precies waarvoor die tabel bestaat.

## Consequenties voor de adapter

1. De zes velden komen uit de dataset; **oordeel, honoraria en wisselvlag zitten er
   gestructureerd in en worden meegeladen** (opslaan is gratis; tonen in de UI blijft
   in het MVP beperkt tot de zes velden, conform de visie).
2. Kantoornaam via het aparte pdf-spoor (zie boven).
3. Filter bepalen: samenstellingsverklaring ≠ controle. Alleen rijen met een
   controleverklaring worden `wettelijke_controle`; wat we met de rest doen
   (apart opdrachttype of overslaan) beslissen bij bouw.
4. Zelfgerapporteerde wisselvlag is een tweede bron voor de wisselingenpagina, naast
   het afgeleide `v_wisselingen`.

## Dekkingsstrategie (uitgezocht 29-7-2026) — dataset als bronlijst, archief als naslag

Eerst geprobeerd: losse letters als organisatiefragment in de archiefzoekfunctie
(`organization=a`, `organization=e`, …). Dat werkt technisch — geen harde cap,
`q` geeft 49 treffers, `e` geeft 5.636, dus het is een echte substring-zoekfunctie
— maar is **onbetrouwbaar als dekkingsstrategie**: je weet nooit zeker of de
letters samen de hele populatie dekken, en het genereert enorme overlappende
resultaten om te dedupliceren.

**Betere aanpak, want er ligt al een complete brontabel:** de dataset zelf
(`digimv2023.ods`, RowData-sheets) bevat naast het KvK-nummer óók de officiële
organisatienaam:

| Veld | Betekenis |
|---|---|
| `qNawNaam` | Naam van de organisatie (mogelijk aangepast) |
| `qNawNaamLrza` | Naam van de organisatie (zoals geregistreerd) |
| `qNawPlaatsLrza` | Plaatsnaam |

Dat is de **officiële, complete lijst van 6.132 organisaties** die voor boekjaar
2023 een jaarverantwoording deden — precies de doelpopulatie, zonder giswerk.

**Adapter-strategie (Fase 1-bouw):**
1. Parse de RowData-sheets → per organisatie: KvK-nummer, naam, plaats, en de
   gestructureerde velden uit §"Belangrijkste velden" hierboven (oordeel,
   honoraria, wisselvlag) — dit vult meteen de zes MVP-velden op organisatieniveau.
2. Per organisatie: zoek in het archief op naam + plaats
   (`digimv_archief.zoek(organisatie=naam, plaats=plaats, boekjaar=2023)`),
   match het resultaat op **KvK-nummer** (`externalOrganizationId`) ter controle —
   nooit blind het eerste resultaat pakken.
3. Haal de verklaring-pdf op (`digimv_archief.verklaringen(...)`), analyseer met
   `verklaring.analyseer(...)` → kantoor + oordeel + continuïteit.
4. Bewaar het ruwe pdf in Storage vóór verwerking (principe 1); sla nooit alleen
   het extractieresultaat op.

Dit is trager dan losse letterzoekopdrachten (6.132 gerichte zoekopdrachten in
plaats van ~10 brede), maar wél gegarandeerd volledig en met ingebouwde controle.
Draait straks als achtergrondtaak (GitHub Actions), niet interactief.

## Meerdere boekjaren: drie valkuilen (uitgezocht 29-7-2026)

Bij het uitbreiden van de proefdata naar 2018–2024 bleken er drie dingen mis
te gaan die bij één boekjaar onzichtbaar blijven. Alle drie opgelost.

**1. Het archief houdt een voortschrijdend venster van zeven boekjaren.**
De frontend genereert zijn jarenlijst als "huidig jaar − 1 t/m − 7"; oudere
jaren geven **HTTP 500**. Stand juli 2026: 2019 t/m 2025 beschikbaar,
**2018 bestaat niet meer**. Vastgelegd als `OUDSTE_BOEKJAAR` in `digimv.py`.

> **Strategisch gevolg:** de bron zelf gooit elk jaar het oudste boekjaar weg.
> Wat wij niet oogsten vóór de jaarwisseling, is daarna nergens meer gratis te
> halen. Dat versterkt de moat uit `docs/brainstorm-2026-07.md` ("de historie
> is de moat") aanzienlijk: het historische bestand is niet alleen duur om in
> te halen, het is op termijn **onmogelijk** in te halen. Argument om de
> volledige historie-oogst niet te lang uit te stellen.

**2. Documenten hangen niet altijd op het topniveau.** Bij een deel van de
organisaties — systematisch in boekjaar 2022 — staan de stukken onder
`locations[].documents` (per vestiging) in plaats van `documents[]`. Wie
alleen naar het topniveau kijkt, ziet die organisaties ten onrechte als "geen
stukken gedeponeerd". Opgelost met `alle_documenten()` in `digimv_archief.py`,
dat ook `desaveuElements` meeneemt.

**3. Naam én plaats wisselen per boekjaar; het KvK-nummer niet.** Voorbeelden:

| Boekjaar | Naam | Plaats |
|---|---|---|
| 2023–2024 | Stichting HagaZiekenhuis | 's-Gravenhage |
| 2019–2021 | HagaZiekenhuis (Stichting) | DEN HAAG |

Matchen op naam+plaats breekt dus zodra je meerdere jaren wilt. **KvK-nummer
is de enige stabiele sleutel** (hier 27268552 in alle jaren); de naam dient
alleen nog als zoekterm om de kandidatenlijst klein te houden. Dit geldt net
zo goed voor de latere bulk-run — en het is dubbel belangrijk bij het
groeperen van resultaten: op naam groeperen splitst één organisatie in tweeën
en **verbergt daarmee precies de wisselingen die we willen tonen**.

## Eerste 13 organisaties geladen (29-7-2026) — proefdata voor Fase 2

Met `laad_proefdata.py` (handmatige lijst van 13 bekende ziekenhuizen, geen
bulk) is de hele keten end-to-end getest: archief zoeken → verklaring
downloaden → kantoor + oordeel herkennen → wegschrijven naar Supabase.

Resultaat over boekjaren 2019–2024: **13 organisaties, ~70 opdrachten**,
en daarin **4 echte accountantswisselingen**:

| Organisatie | Wisseling |
|---|---|
| Stichting Catharina Ziekenhuis | EY → PwC (vanaf boekjaar 2023) |
| Stichting Laurentius Ziekenhuis Roermond | Deloitte → EY (vanaf 2021) |
| Stichting Ziekenhuis Gelderse Vallei | Deloitte → PwC (vanaf 2022) |
| Rode Kruis Ziekenhuis B.V. | Deloitte → BDO (vanaf 2023) |

Daarnaast één oordeel *met beperking* (HagaZiekenhuis, boekjaar 2023) tussen
verder goedkeurende oordelen — nuttige variatie voor de UI-test.

Niet elk organisatie-boekjaar levert een rij op: sommige jaren ontbreekt de
deponering of is de verklaring een gescande pdf. Dat is verwacht gedrag en
zichtbaar in de uitvoer, niet stil weggelaten.

## Bulk-run boekjaar 2023 (29-7-2026) — wat de dataset wél en niet oplost

Vastgelegd in `adapters/digimv_dataset.py` (dataset lezen) en `laad_zorg.py`
(bulk-lader). Vier dingen bleken anders dan gedacht.

**1. De dataset snijdt het werk met 84% terug.** Het veld
`bestandAccountantsVerklaringSoort_N` zegt per organisatie wat voor verklaring er
is gedeponeerd. Boekjaar 2023:

| | Aantal |
|---|---|
| Organisaties in de dataset | 6.131 |
| — met een **controleverklaring** | **1.010** |
| — met een samenstellingsverklaring | 422 |
| — met een beoordelingsverklaring | 345 |
| — helemaal niets gedeponeerd | 4.389 |

Alleen die 1.010 hoeven het archief in. Alle 1.010 hebben een KvK-nummer.

**2. `bestandInstellingAccountantsVerklaring_N` is NIET het kantoor.** De naam
suggereert het wel, maar het veld bevat de zórginstelling waar de verklaring over
gaat — 1.625 van de 1.743 gevulde rijen zeggen letterlijk "(de organisatie als
geheel)". De kantoornaam staat nergens in de dataset; het pdf-spoor blijft nodig.

**3. Het documenttype in het archief is een keuze van de indiener en klopt vaak
niet.** Bij "Stichting LuciVer" stond onder *Accountantsverklaring* alleen de
**aanbiedingsbrief** van de accountant, en zat de echte controleverklaring in de
jaarrekening-pdf ernaast. `digimv_archief.verklaringen()` levert de kandidaten
daarom in volgorde van betrouwbaarheid: Accountantsverklaring → Verzameldocument
→ **Jaarrekening** (die laatste als vangnet, en achteraan omdat hij fors groter is).

**4. Een zoekterm moet één wóórd zijn.** Het archief zoekt op deelstring, dus twee
woorden aan elkaar plakken breekt zodra er iets tussen staat: "Admiraal De Ruyter
Ziekenhuis" bevat wel `Admiraal` maar niet `Admiraal Ziekenhuis`. `zoekfragment()`
kiest daarom het langste níét-generieke woord. Lukt dat niet, dan is er een
terugval op zoeken via de plaatsnaam — met altijd het KvK-nummer als eindcontrole.

### Aliassen die deze run opleverde

Dezelfde les als eerder, nu op schaal: de AFM-naam en de tekennaam verschillen.

| Tekent als | AFM-register | Nummer |
|---|---|---|
| Alfa Accountants B.V. | **aaff Audit en Assurance B.V.** (Nijkerk) | 13000259 |
| Moore-DRV | Moore DRV Audit B.V. | 13020116 |
| Qconcepts | **Q-Concepts Accountancy B.V.** | 13000773 |

### Wat nog steeds niet lukt, en waarom dat grotendeels klopt

- **Gescande verklaringen.** Bij grote instellingen (UMCG, Bernhoven, Lentis) staat
  in de jaarrekening-pdf keurig "de controleverklaring is opgenomen op pagina X",
  maar die pagina's zijn ingescand: de tekstlaag bevat alleen het kopje. Vraagt OCR
  of het LLM-vangnet (Fase 4).
- **Kleine zorg-BV's hebben vaak geen jaarrekeningcontrole.** Wat er ligt is een
  controleverklaring bij een *WNT-verantwoording* of een *financiële
  productieverantwoording* — een andere opdracht, vaak van een kantoor zonder
  Wta-vergunning (Cijferhuis Audit, De ZorgAccountants, DVE, G&P, FB Assurance:
  geen van alle in het AFM-register). Dat wij daar niets vastleggen is correct
  gedrag, geen gemiste kans.

> **Let op bij het interpreteren van de trefkans.** De 96% uit de meting hierboven
> gold voor jaarrekening-controleverklaringen. Over de volle doelpopulatie ligt hij
> lager, en dat komt vooral doordat die populatie andere dingen bevat dan wij
> zoeken. Meet dus per categorie, niet op het totaal.

## Jaargangen 2019–2024 verkend (29-7-2026) — de eigen jaarlijst valt af

Onderzocht of elk boekjaar zijn eigen doelpopulatie kan krijgen in plaats van de
lijst van 2023 te hergebruiken. Dat zou het gat dichten van organisaties die in
een ouder jaar bestonden en in 2023 niet meer. **Conclusie: dat gaat niet, en de
kortere weg via `--lijst-uit 2023` blijft de beste optie.**

### Vindplaatsen (alle gecontroleerd, HTTP 200)

| Boekjaar | Bestand | Formaat |
|---|---|---|
| 2024 | `digimv2024-openbaar-20260129-multipletables-part-1..4.ods` | 4 delen, modern |
| 2023 | `DigiMV2023_MultipleTables_20241001_0927.ods` | modern |
| 2022 | `DigiMV2022_20240527_ODS_MultipleTables.zip` | zip (deflate), modern |
| 2021 | `DigiMV2021_tot-en-met_20230121_ODS_MeerdereTabellen.zip` | zip, **oud formaat** |
| 2020 | `DigiMV2020_tot-en-met_20230121_ODS_MeerdereTabellen.zip` | zip, **oud formaat** |
| 2019 | `DigiMV2019_20210816_ODS_1.zip` + `_2.zip` | zip (**Deflate64**), **oud formaat** |

**Boekjaar 2019 gebruikt Deflate64.** Python's `zipfile` weigert dat
("compression method is not supported"); het externe `unzip` kan het wel. Vandaar
dat `download()` uitpakt via een subprocess.

### Waarom de eigen jaarlijst afvalt

**2019 (en waarschijnlijk 2020–2021) hebben een ander exportformaat.** Sheets
heten `x9conc_total_*`, veldnamen zijn `c_kvk`, `c_naam`, `ConcernCode` — geen
`q...`-conventie. Er zit een datadictionary in (`x9conc_total_0`, 3.747 rijen),
maar die bevat **nul** treffers op "verkl", "accountant", "zorgsoort" of
"rechtsvorm". Dat bestand is concernbreed financieel; de accountantsverklaring
zit er niet in. Zonder dat veld is er geen doelpopulatie te bepalen.

**2022 heeft wél het moderne formaat maar een dunnere vulling.** Het veld
`bestandAccountantsVerklaringSoort_N` (per document) ontbreekt; alleen de
vraagvariant `qAccVerklSoort` is er, en die is door 1.901 van de 8.982 rijen
beantwoord. Resultaat: **289 organisaties met een controleverklaring, tegen 1.140
voor 2023.** Die lijst gebruiken zou de dekking van 2022 dus juist verslechteren.

### Wat de verkenning wél opleverde

**Een bug: de vergelijking was hoofdlettergevoelig.** 2023 schrijft
`controleverklaring` in het documentveld en `Controleverklaring` in het
vraagveld. We lazen alleen het eerste, en misten daarmee 130 organisaties die
alleen het tweede hadden ingevuld. De doelpopulatie van boekjaar 2023 gaat van
**1.010 naar 1.140**.

**Kolommen worden nu op naam opgezocht, niet op positie.** Dat moest, want
dezelfde velden staan per jaargang elders: `qRechtsvormKvk` zit in 2023 op
`RowData_09[224]` en in 2022 op `RowData_11[176]`. De tabel met vaste posities is
vervangen door `VELDPATRONEN`, dat de koprij van elke sheet leest. Boekjaar 2023
reproduceert daarmee exact dezelfde uitkomst.

### Wat er nog te halen valt

Voor 2019–2021 zou het tweede bestand (`_2.zip`) of een van de andere sheets de
verklaring-velden alsnog kunnen bevatten; alleen deel 1 van 2019 is bekeken. Dat
is de enige resterende route naar volledige historische dekking, en die is
gebonden aan de klok: boekjaar 2019 verdwijnt bij de eerstvolgende jaarwisseling
uit het archief.

## Steekproef archieflijst boekjaar 2019 (5-8-2026) — bijna de helft raak

100 organisaties uit `digimv_archief.doelpopulatie(2019)`, met `--uit-archief`:
**49 opdrachten, 51 zonder herleidbaar kantoor**, 40,5 minuten met vier werkers
(±24 seconden per organisatie). Ter vergelijking: de route via de jaardataset gaf
2 opdrachten op 12 organisaties. De archiefpopulatie is 2.211 (2019), 2.351
(2020) en 2.471 (2021) — bij dit percentage ligt er ruwweg 7.000 opdrachten over
zeven boekjaren, maar één Action-run van 5,5 uur doet er ongeveer 800. Opknippen
met `vanaf`/`aantal` en meerdere keren draaien; het is idempotent.

### Waarom die 51 misgingen — en wat dat opleverde

De 1.728 pdf's die toen al in de cache stonden (boekjaren 2019–2025) opnieuw
gelezen, alleen op de tekstlaag:

| uitkomst | aantal |
|---|---|
| controle mét kantoor | 828 |
| gescand, geen tekstlaag (OCR nodig) | 349 |
| onleesbaar of nietszeggend (`soort=None`) | 198 |
| controle zónder herkend kantoor | 160 |
| samenstelling | 137 |
| beoordeling | 56 |

Die 160 leverden twee soorten vondsten op, allebei verwerkt:

1. **Kantoren die de lijst niet kende.** Zeven kantoren die productie- en
   WNT-verantwoordingen tekenen staan niet in het AFM-register — daar is geen
   Wta-vergunning voor nodig — en staan nu in `seed/kantoren_overig.csv`:
   FB Assurance, Monteba, AW Accountants, CAS ZorgAccountants, Hilgers, Miedema
   en Hendriksen Accountants Controle. Drie kantoren tékenen onder een andere
   naam dan waaronder ze in het register staan en kregen een alias: Grant
   Thornton (splitsing 2025), Countus Audit (13000483) en Konings Maters
   (fusie februari 2023, 13000504).
2. **Ondertekeningen die de match niet als ondertekening zag.** Een
   handtekeningblok zonder plaats en datum — "CAS ZorgAccountants B.V. S.R. Snel
   AA", "Miedema Accountants ValidSigned door drs. D. van der Bij RA RB" — haalde
   de drempel niet. `kantoor_match._ONDERTEKENAAR_NA` telt nu mee dat de tekenend
   accountant ná de kantoornaam staat; in een cv staat zijn titel er juist vóór,
   dus die gevallen blijven staan.

Gemeten over dezelfde 1.728 pdf's: **828 → 865 met kantoor**, 160 → 123 zonder.
46 pdf's kwamen er nieuw bij, **nul** verklaringen wisselden van kantoor, en in
alle 46 stond precies één bekend kantoor in de tekst — er viel dus niets te
verwarren. Ook de 800+ scans zijn hiermee niet geraakt: die vragen OCR en dat
draait alleen in de Action.

## OCR is de bodem van het tempo (gemeten 6-8-2026)

De oogst van boekjaar 2019 loopt op vier kernen en die staan alle vier voortdurend
op 100% in tesseract. Dat is de bottleneck, niet het netwerk en niet de bron.
Gemeten per gescand document: 3 tot **393 seconden**, mediaan rond de 15. De
aanname in `extractie/verklaring.py` was ~127 seconden; de staart is dus veel
langer dan gedacht, en juist de duurste documenten leveren vaak niets op (de
393-seconden-scan gaf `soort=None`).

Halveren lijkt mogelijk maar is **niet doorgevoerd**. Op twaalf gescande
zorgverklaringen gaf 200 dpi twaalf keer exact dezelfde uitkomst als 300 dpi —
zelfde soort, zelfde opdrachttype, zelfde kantoornaam, inclusief de vier
documenten waar écht een kantoor uit kwam (Flynth, EY, 2× Astrium) — in 52% van
de tijd. Maar de opmerking bij `OCR_DPI` legt een eerdere meting vast waarin bij
200 dpi de kantoornaam juist wegviel, vermoedelijk op de scans van goede doelen.

Bij tegenstrijdig bewijs en een fout die *stil* is (een kantoornaam die net niet
meer leesbaar is, zonder dat iets meldt dat er iets mist) blijft 300 dpi staan.
Wie dit alsnog wil: meet op minstens vijftig scans uit **beide** sectoren, en
vergelijk niet alleen of er een kantoor uitkomt maar of het hetzelfde kantoor is.
Een adaptieve variant — eerst 200 dpi, en alleen bij "controle zonder kantoor"
overdoen op 300 — vangt het risico af tegen een fractie van de kosten, maar raakt
wel de best bewaakte code van dit project.

## Open punten

- [ ] Kolominspectie 2018–2022 en 2024 (4 delen; veldnamen wijken af — `qNawNaam`
      e.d. checken of dat per jaargang hetzelfde heet)
- [ ] Join-logica RowData-sheets bevestigen (hoe organisatie- en documentvelden
      per rij samenhangen over de meerdere sheets)
- [ ] Volledige waardenlijsten `qAccVerklSoort`/`qAccVerklVorm` uit de data
- [x] Archief-API uitgezocht en vastgelegd in `digimv_archief.py`
- [x] Dekkingsstrategie bepaald: dataset als bronlijst (zie boven), niet
      letter-enumeratie
- [ ] Verzameldocumenten (144 in 2023) apart testen: de verklaring zit daar in een
      groter pdf, wat de trefkans kan drukken
- [ ] Snelheid/tempo van 6.132 archiefzoekopdrachten inschatten en een
      redelijke pauze tussen requests vastleggen (vriendelijk voor de bron)

## Wat "bekeken" betekent, en waarom dat een keer opnieuw moet

Gemeten op de oogst van boekjaar 2019 (7-8-2026, na 212 organisaties):

    bekeken                    212
    met opdracht                98   46%
    zonder opdracht            114   54%

Van die 114 zijn er 31 opnieuw onderzocht met de tekst die al in de cache stond.
De uitkomst:

    24   geen enkele bekende kantoornaam in de tekst
     4   kantoornaam staat er wel, maar niet als ondertekenaar
     3   zou nu WEL een kantoor opleveren

Die laatste drie zijn het punt. Ze zijn gelezen voordat de regels van vandaag
erin zaten (de ondertekenaar-na-de-naam, en de nieuwe aliassen), en ze staan in
`verwerkt_<boekjaar>.txt` als bekeken. `--hervat` slaat ze dus voorgoed over.

Dat is geen fout in de oogst maar wel een gat in de werkwijze: elke verbetering
aan de leesregels maakt organisaties herleidbaar die eerder zijn afgevallen, en
niets brengt die terug. Op deze steekproef is dat ongeveer één op de tien van de
niet-gelukte gevallen.

Wat daarvoor nodig is, en bewust nog niet gedaan omdat de oogst loopt: naast het
kvk-nummer ook de reden in `verwerkt_<boekjaar>.txt` zetten (geen tekstlaag /
geen verklaring / kantoor niet herkend). Dan kan een hertoets precies de
categorie "kantoor niet herkend" opnieuw langslopen na een verbetering, zonder
de hele jaargang over te doen. Let op: de pdf's worden na verwerking per
organisatie opgeruimd, dus zo'n hertoets kost opnieuw downloaden.

Niet doen: de niet-gelukte gevallen uit `verwerkt` weglaten zodat ze vanzelf
terugkomen. Dan draait elke ronde ze opnieuw, inclusief de dure OCR, en komt de
oogst nooit vooruit.
