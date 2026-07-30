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
    cbf.py             ✅ register-API erkende goede doelen + jaarverslag-pdf's
    anbi.py            ✅ ANBI-bestand Belastingdienst als populatielijst
    anbi_publicatie.py ✅ terugval: jaarstuk op de eigen site van een stichting
    stichtingen.py     ✅ goed doel → opdracht (cbf + terugval + kantoor_match)
    transparantie.py   ⬜ Fase 3: OOB-cliëntlijsten
    duo.py             ⬜ Fase 4: onderwijs
    tenderned.py       ⬜ Fase 4: aanbestedingen accountantsdiensten
  extractie/
    kantoor_match.py   ✅ kantoornaam herkennen via AFM-lijst + aliassen
    verklaring.py      ✅ pdf → soort verklaring, oordeel, continuïteit, kantoor
  seed/
    kantoren.csv       ✅ 233 Wta-vergunninghouders (6 met OOB-vergunning)
    kantoren_overig.csv ✅ kantoren zónder Wta-vergunning die controleverklaringen
                          tekenen bij organisaties zonder controleplicht
    kantoor_alias.csv  ✅ handelsnamen en oude namen na fusie/rebranding
  werkvoorraad/
    stichtingen.json   ✅ de 133 blokken van de goededoelensector en wat ze opleverden;
                          de git-diff van dit bestand is het voortgangslog
  supabase_client.py   ✅ PostgREST-client (upsert, upsert_met_id, invoegen, selecteer)
  lus.py               ✅ laadt een sector in rondes van een paar blokken in plaats van
                          in één bulk-run (plan | stand | draai) — workflow "Stichtingenlus"
  laad_kantoren.py     ✅ beide kantorenlijsten + aliassen → Supabase
  laad_proefdata.py    ✅ 13 bekende ziekenhuizen → Supabase (proefdata voor Fase 2)
  laad_stichtingen.py  ✅ CBF-erkende goede doelen → Supabase (workflow "Stichtingendata")
  valideer_extractie.py ✅ meet de trefkans van de kantoorextractie (zorg)
  verken_stichtingen.py ✅ zelfde meting voor de goededoelensector (dekking, extractie,
                          oogst van onbekende kantoren, wisselingen tussen twee jaren)
  test_kantoor_match.py ✅ 11 gevallen uit echte verslagen; zonder netwerk te draaien
  signalen/            ⬜ Fase 4: afgeleide signalen (relatieduur, roulatie, …)
```

Het MVP (Fase 0–3) draait **zonder AI-extractie**. De kantoornaam staat in de
zorgsector alleen in de verklaring-pdf's; die halen we eruit met `pdftotext` +
stringmatch tegen de AFM-lijst/aliastabel. Gemeten trefkans op controleverklaringen:
**96–100%, zonder valse matches** (zie `adapters/digimv.md`). Onmatchbare gevallen
— gescande pdf's, kantoornaam alleen in een logo — wachten in de `review_queue` op
het LLM-vangnet van Fase 4.

Buiten de zorg ligt die trefkans structureel lager, en dat is geen tekortkoming van de
extractie: bij goede doelen tekent bijna een derde van de verklaringen een kantoor
zónder Wta-vergunning (vrijwillige controle, dus terecht niet in het AFM-register).
Zie `docs/bronverkenning-stichtingen.md`.

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

6. **In rondes, niet in één hoop.** Een sector laden is uren werk waar één slechte pdf
   een hele run kan laten struikelen, en aan het eind heb je één grote uitkomst die
   niemand nog nakijkt. `lus.py` knipt het in blokken van 50 organisaties met de
   voortgang in de repo: elke ronde levert iets op dat te lezen is vóór de volgende
   begint, en hervatten is de normale gang van zaken in plaats van een noodgreep.

## Draaien (vanaf Fase 0-afronding)

Via GitHub Actions: wekelijks schema + handmatige trigger. Secrets die de workflow nodig
heeft: `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`; `ANTHROPIC_API_KEY` pas vanaf Fase 4
(AI-extractie zit niet in het MVP). Optioneel `VERCEL_DEPLOY_HOOK`: dan ververst de
website meteen na een ronde in plaats van binnen het uur (ISR).

De goededoelensector loopt via de lus:

```
python3 pipeline/lus.py plan       # werkvoorraad opbouwen uit het CBF-register
python3 pipeline/lus.py stand      # wat is klaar, wat staat open
python3 pipeline/lus.py draai      # de volgende zes blokken
```

In GitHub Actions doet de workflow *Stichtingenlus* dat vier keer per dag, met de
werkvoorraad als commit op `data/stichtingenlus` en één PR die meegroeit. Een droogloop
(`--droogloop`) meet zonder te schrijven en laat de werkvoorraad met opzet ongemoeid.
