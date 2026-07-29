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
