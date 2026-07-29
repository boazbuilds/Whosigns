# Pipeline

Python-scripts die openbare bronnen ophalen en naar het kernmodel in Supabase schrijven.

## Structuur

```
pipeline/
  adapters/
    afm_register.py    ✅ AFM-kantorenregister → seed/kantoren.csv
    digimv_archief.py  ✅ client voor de archief-API (zoeken + document ophalen)
    digimv.py          ✅ organisatie → opdracht (archief + kantoor_match + verklaring)
                       ⬜ dataset-gedreven bulk-run (Fase 1, zie digimv.md)
    transparantie.py   ⬜ Fase 3: OOB-cliëntlijsten
    duo.py             ⬜ Fase 4: onderwijs
    tenderned.py       ⬜ Fase 4: aanbestedingen accountantsdiensten
  extractie/
    kantoor_match.py   ✅ kantoornaam herkennen via AFM-lijst + aliassen
    verklaring.py      ✅ pdf → soort verklaring, oordeel, continuïteit, kantoor
  seed/
    kantoren.csv       ✅ 233 vergunninghouders (6 met OOB-vergunning)
    kantoor_alias.csv  ✅ handelsnamen en oude namen na fusie/rebranding
  supabase_client.py   ✅ PostgREST-client (upsert, upsert_met_id, invoegen, selecteer)
  laad_kantoren.py     ✅ kantoren + aliassen → Supabase
  laad_proefdata.py    ✅ 13 bekende ziekenhuizen → Supabase (proefdata voor Fase 2)
  valideer_extractie.py ✅ meet de trefkans van de kantoorextractie
  signalen/            ⬜ Fase 4: afgeleide signalen (relatieduur, roulatie, …)
```

Het MVP (Fase 0–3) draait **zonder AI-extractie**. De kantoornaam staat in de
zorgsector alleen in de verklaring-pdf's; die halen we eruit met `pdftotext` +
stringmatch tegen de AFM-lijst/aliastabel. Gemeten trefkans op controleverklaringen:
**96–100%, zonder valse matches** (zie `adapters/digimv.md`). Onmatchbare gevallen
— gescande pdf's, kantoornaam alleen in een logo — wachten in de `review_queue` op
het LLM-vangnet van Fase 4.

Vereist buiten Python: `pdftotext` (pakket `poppler-utils`).

## Spelregels (gelden voor elke adapter)

1. **Ruwe bron eerst.** Download → sha256 → opslaan in Supabase Storage → rij in
   `bronbestanden` → pas daarna verwerken. Herverwerken kan dan altijd zonder opnieuw
   te downloaden.
2. **Idempotent.** Upserts op de unieke sleutels uit het schema
   (`organisatie_id + boekjaar + type_opdracht`, KvK-nummer, AFM-nummer). Twee keer
   draaien = zelfde resultaat, geen duplicaten.
3. **Herkomst per feit.** Elke schrijfactie hangt aan een rij in `bronnen`
   (type, URL, ophaaldatum, `publiek`/`zelf_aangeleverd`).
4. **Nooit stil mergen.** Kantoornamen eerst exact matchen op `kantoor_alias`; fuzzy
   matches en onzekere AI-extracties gaan naar `review_queue` en wachten op menselijke
   bevestiging.
5. **AVG.** Geen namen van natuurlijke personen opslaan — ook niet in ruwe
   extractie-output of logs.

## Draaien (vanaf Fase 0-afronding)

Via GitHub Actions: wekelijks schema + handmatige trigger. Secrets die de workflow nodig
heeft: `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`; `ANTHROPIC_API_KEY` pas vanaf Fase 4
(AI-extractie zit niet in het MVP).
