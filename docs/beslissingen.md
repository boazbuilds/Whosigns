# Beslislog

Openstaande keuzes liggen bij de opdrachtgever. Genomen besluiten krijgen een datum en
blijven hier staan (ook als ze later worden teruggedraaid — dan met nieuwe regel).

| # | Keuze | Opties | Aanbeveling | Status |
|---|-------|--------|-------------|--------|
| 1 | Definitieve naam & domein | **WhoSigns** (repo heet al zo) · Auditkaart · anders | WhoSigns: het ís de vraag die het product beantwoordt, en het werkt internationaal. Let op merknuance: antwoord altijd op kantoorniveau (AVG). Domeincheck doen (whosigns.nl / .com). | 🟠 Open |
| 2 | Publiek bij lancering of besloten demo | Publiek met badge "Demo · gedeeltelijke data" · besloten demo met login | Publiek, zodra de zorgsector compleet is. Vrij bladerbare pagina's zijn het acquisitiekanaal (SEO op "[organisatie] accountant") — het Transfermarkt-model. Besloten demo remt precies wat het product sterk maakt. Beslissen aan het eind van Fase 2. | 🟠 Open |
| 3 | Supabase-regio | EU (Frankfurt) · anders | EU/Frankfurt: AVG-comfort, lage latency, geen reden voor iets anders. | 🟠 Open |
| 4 | Moment eerste KvK-inkoop (±€4/jaarrekening) | Nu · na eerste klantvalidatie · "data on demand" per klantvraag | Pas in Fase 5, en dan "data on demand": alleen kopen wat een concrete (proef)klant vraagt. Geen datakosten vóór er bewijs van betalingsbereidheid is. | 🟠 Open |
| 5 | Schema-aanpassingen uit brainstorm (honorarium gesplitst, continuïteitsonzekerheid, signaalstatus, review-queue, 2 extra signaaltypen) | Overnemen · terugdraaien naar concept-schema | Overnemen — kost niets nu, moeilijk achteraf. Zie `docs/brainstorm-2026-07.md` §6. NB: conform de visie blijven deze kolommen in het MVP **leeg**; ze wachten op Fase 4+. | 🟢 Doorgevoerd in migration, terug te draaien op verzoek |
| 6 | Freemium-grens: is de historie gratis bladerbaar? | Historie in Pro (visie-voorstel) · alles bekijken gratis en alleen werk-tools betaald (export, filters, lijsten, alerts, API) | Historie gratis houden. De noordster ("even op WhoSigns kijken") en de SEO-/Wikipedia-werking vereisen dat het antwoord vrij zichtbaar is — Transfermarkt zet niets van de kern achter een muur. Verdien aan wat werk scheelt, niet aan het naslagwerk. Beslissen vóór publieke lancering (Fase 3); bij de klik-test is alles gratis. | 🟠 Open |

| 7 | Gebruik van het CBF-register en de CBF-jaarverslagen als bron voor de goededoelensector | Wel gebruiken en bronvermelding zetten · eerst afstemmen met data@cbf.nl · niet gebruiken en alleen de eigen websites van stichtingen crawlen | Gebruiken, maar stuur eerst een korte mail naar data@cbf.nl. CBF-data is géén open data (voorwaarden aan hergebruik, cijfers/paspoortteksten niet vrij herbruikbaar). Wat wij vastleggen is een feit uit het openbare jaarverslag van de stichting zelf en het CBF is de vindplaats — verdedigbaar, maar liever met een ja op zak dan met een discussie na livegang. De alternatieve route (eigen sites crawlen) is gemeten en levert 1 op 12. Zie `docs/bronverkenning-stichtingen.md`. | 🟠 Open |
| 8 | Vrijwillige controles opnemen (kantoren zonder Wta-vergunning) | Alleen wettelijke controles vastleggen · ook vrijwillige controles, apart opdrachttype en kantoorrij zonder AFM-nummer | Opnemen, met eigen opdrachttype. In de goededoelensector tekent bijna een derde van de verklaringen een kantoor buiten het AFM-register (WITh Accountants, Maas Accountants) — legitiem, want zonder controleplicht is geen Wta-vergunning nodig. Wegfilteren maakt de sector voor een derde leeg, inclusief bekende namen. Voorwaarde: in de UI zichtbaar onderscheid tussen wettelijke en vrijwillige controle, en `kantoren` moet rijen zonder `afm_nummer` toestaan. Beslissen vóór de eerste stichtingen-import. | 🟠 Open |

## Genomen besluiten

| Datum | Besluit | Toelichting |
|-------|---------|-------------|
| juli 2026 | Techstack: Supabase + Next.js/Vercel + Python-pipeline via GitHub Actions + Claude API voor pdf-extractie | Uit conceptdocument; goedkoop (< €50/mnd), door één persoon te onderhouden |
| juli 2026 | Alleen openbare data in v1; nooit natuurlijke personen opslaan | Guardrail, zie `docs/concept.md` §9 |
| juli 2026 | MVP verscherpt tot de zes-velden-relatiegraaf (organisatie, accountant, opdrachttype, jaar, sector, bron); geen AI-extractie, honoraria of switch-scores in het MVP-pad | Zie `docs/visie.md` — leidend document |
| juli 2026 | MVP-volgorde: zorg → klik-machine → lancering + OOB → verdieping (AI/signalen/onderwijs) → omzet | Zie `ROADMAP.md` |
