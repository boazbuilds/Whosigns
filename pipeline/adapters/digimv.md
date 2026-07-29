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

## Open punten

- [ ] Kolominspectie 2018–2022 en 2024 (4 delen; veldnamen wijken af)
- [ ] Join-logica RowData-sheets bevestigen
- [ ] Volledige waardenlijsten `qAccVerklSoort`/`qAccVerklVorm` uit de data
- [x] Archief-API uitgezocht en vastgelegd in `digimv_archief.py`
- [ ] Volledige organisatielijst per boekjaar ophalen: de zoek-API vereist een
      fragment, dus we hebben een dekkende strategie nodig (alfabet- of
      plaatsgewijs zoeken, daarna dedupliceren op KvK-nummer)
- [ ] Verzameldocumenten (144 in 2023) apart testen: de verklaring zit daar in een
      groter pdf, wat de trefkans kan drukken
