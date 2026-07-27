# WhoSigns

**Wie tekent bij …?** Audit-market-intelligence voor Nederland: een vrij bladerbare
database + website die laat zien welke accountantsorganisatie welke organisatie
controleert, hoe die relaties zich over de jaren ontwikkelen, en waar wisselingen
(gaan) plaatsvinden — de Transfermarkt van de auditmarkt.

De database is het middel; **wisselsignalen** (leads en alerts over aanstaande
accountantswisselingen) zijn het product.

## Status

🔨 **Fase 0 — Fundament** (gestart juli 2026). Zie `ROADMAP.md` voor het volledige
bouwplan en wat er nu speelt.

## Wegwijzer

| Bestand/map | Wat |
|---|---|
| `ROADMAP.md` | Het bouwplan: fases, taken, beslismomenten — begin hier |
| `docs/concept.md` | Volledige context: wat we bouwen, domeinkennis, bronnen, guardrails |
| `docs/brainstorm-2026-07.md` | Analyse "waarom Transfermarkt werkt" + verbetervoorstellen |
| `docs/beslissingen.md` | Beslislog: open keuzes met aanbeveling + genomen besluiten |
| `supabase/migrations/` | Databaseschema (Postgres), draait straks op Supabase |
| `pipeline/` | Python-importscripts per bron (adapters) — Fase 1 e.v. |
| `web/` | Next.js-website (komt in Fase 0/2) |

## Techniek in één alinea

Supabase (Postgres + Storage, EU) als database, Next.js op Vercel als website (UI in het
Nederlands), Python-scripts via GitHub Actions als data-pipeline, en de Claude API om
kantoornaam en oordeel uit pdf-controleverklaringen te halen. Doel: < €50/maand tot de
eerste betalende klant, onderhoudbaar door één persoon met Claude Code.

## Zo werk je hieraan (zonder developer-achtergrond)

1. Open een Claude Code-sessie in deze repo.
2. Zeg bijvoorbeeld: *"Pak de volgende openstaande taak uit Fase 0 in ROADMAP.md."*
3. Claude legt keuzes in gewone taal voor; beslissingen landen in `docs/beslissingen.md`.

## Spelregels (kort)

Alleen openbare data in v1 · herkomst per feit zichtbaar · nooit namen van natuurlijke
personen (AVG) · onzekere extracties naar de review-queue, nooit stil mergen · zo simpel
en goedkoop mogelijk. Volledige guardrails: `docs/concept.md` §9.
