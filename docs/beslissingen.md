# Beslislog

Openstaande keuzes liggen bij de opdrachtgever. Genomen besluiten krijgen een datum en
blijven hier staan (ook als ze later worden teruggedraaid — dan met nieuwe regel).

| # | Keuze | Opties | Aanbeveling | Status |
|---|-------|--------|-------------|--------|
| 1 | Definitieve naam & domein | **WhoSigns** (repo heet al zo) · Auditkaart · anders | WhoSigns: het ís de vraag die het product beantwoordt, en het werkt internationaal. Let op merknuance: antwoord altijd op kantoorniveau (AVG). Domeincheck doen (whosigns.nl / .com). | 🟠 Open |
| 2 | Publiek bij lancering of besloten demo | Publiek met badge "Demo · gedeeltelijke data" · besloten demo met login | Publiek, zodra de zorgsector compleet is. Vrij bladerbare pagina's zijn het acquisitiekanaal (SEO op "[organisatie] accountant") — het Transfermarkt-model. Besloten demo remt precies wat het product sterk maakt. Beslissen aan het eind van Fase 2. | 🟠 Open |
| 3 | Supabase-regio | EU (Frankfurt) · anders | EU/Frankfurt: AVG-comfort, lage latency, geen reden voor iets anders. | 🟠 Open |
| 4 | Moment eerste KvK-inkoop (±€4/jaarrekening) | Nu · na eerste klantvalidatie · "data on demand" per klantvraag | Pas in Fase 5, en dan "data on demand": alleen kopen wat een concrete (proef)klant vraagt. Geen datakosten vóór er bewijs van betalingsbereidheid is. | 🟠 Open |
| 5 | Schema-aanpassingen uit brainstorm (honorarium gesplitst, continuïteitsonzekerheid, signaalstatus, review-queue, 2 extra signaaltypen) | Overnemen · terugdraaien naar concept-schema | Overnemen — kost niets nu, moeilijk achteraf. Zie `docs/brainstorm-2026-07.md` §6. | 🟢 Doorgevoerd in migration, terug te draaien op verzoek |

## Genomen besluiten

| Datum | Besluit | Toelichting |
|-------|---------|-------------|
| juli 2026 | Techstack: Supabase + Next.js/Vercel + Python-pipeline via GitHub Actions + Claude API voor pdf-extractie | Uit conceptdocument; goedkoop (< €50/mnd), door één persoon te onderhouden |
| juli 2026 | Alleen openbare data in v1; nooit natuurlijke personen opslaan | Guardrail, zie `docs/concept.md` §9 |
| juli 2026 | MVP-volgorde: zorg → frontend → signalen → onderwijs/OOB → validatie | Zie `ROADMAP.md` |
