# Pipeline

Python-scripts die openbare bronnen ophalen en naar het kernmodel in Supabase schrijven.
Nog geen code — de eerste adapter komt in Fase 1 (zie `../ROADMAP.md`).

## Geplande structuur

```
pipeline/
  adapters/
    afm_register.py   # Fase 0: seed + wekelijkse snapshot kantorenregister
    digimv.py         # Fase 1: zorgsector (jaarverantwoordingzorg.nl) — alleen
                      #   gestructureerde velden; de zes velden uit docs/visie.md
    transparantie.py  # Fase 3: OOB-cliëntlijsten uit transparantieverslagen
    duo.py            # Fase 4: onderwijs
    tenderned.py      # Fase 4: aanbestedingen accountantsdiensten
  extractie/          # Fase 4: Claude API-extractie van pdf-verklaringen → JSON
  signalen/           # Fase 4: afgeleide signalen (relatieduur, roulatie, …)
```

Het MVP (Fase 0–3) draait **zonder AI-extractie**: alleen wat gestructureerd in de
bron zit. Records waar de kantoornaam enkel in een pdf staat, worden gemarkeerd en
geparkeerd tot Fase 4.

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
