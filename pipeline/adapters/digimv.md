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
  aliastabel** (~honderden vergunninghouders, dus een kleine, gesloten matchlijst).
  Geen match → `review_queue`. LLM-vangnet (Claude API) pas in Fase 4.

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
- [ ] Archief: actuele URL, download-etiquette (tempo/robots) en dekking checken vóór
      bulk-download van pdf's
