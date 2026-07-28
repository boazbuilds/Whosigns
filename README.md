# WhoSigns

**Wie tekent bij …?** De Transfermarkt van de assurance-markt: geen database met
documenten, maar een vrij bladerbare database van **relaties** —

```
Organisatie ↔ Accountant ↔ Opdracht ↔ Jaar
```

Wie controleert wie, in welke sector, sinds wanneer, en waar wordt gewisseld. De
historie van die relaties is de moat; betaalde werk-tools (export, lijsten, alerts,
analyses) zijn het verdienmodel.

**Noordster:** als iemand zich afvraagt *"wie is de accountant van organisatie X?"*,
is het antwoord: *even op WhoSigns kijken.*

## Status

🔨 **Fase 0 — Fundament** (gestart juli 2026). Zie `ROADMAP.md` voor het bouwplan.

## Wegwijzer

| Bestand/map | Wat |
|---|---|
| `docs/visie.md` | De productvisie — **leidend** bij twijfel; begin hier |
| `ROADMAP.md` | Het bouwplan: fases, taken, beslismomenten |
| `docs/concept.md` | Volledige context: domeinkennis, bronnen, guardrails |
| `docs/brainstorm-2026-07.md` | Analyse "waarom Transfermarkt werkt" + verbetervoorstellen |
| `docs/beslissingen.md` | Beslislog: open keuzes met aanbeveling + genomen besluiten |
| `supabase/migrations/` | Databaseschema (Postgres), draait straks op Supabase |
| `pipeline/` | Python-importscripts per bron (adapters) — Fase 1 e.v. |
| `web/` | Next.js-website (komt in Fase 0/2) |

## MVP in één zin

Zes velden — organisatie, accountant, opdrachttype, jaar, sector, bron — voor de hele
zorgsector, gepresenteerd zó dat je blijft doorklikken (elke pagina ≥ 5 vervolgklikken).
Geen AI, geen honoraria, geen voorspellingen: eerst bewijzen dat mensen spontaan zoeken
en doorklikken.

## Techniek in één alinea

Supabase (Postgres + Storage, EU) als database, Next.js op Vercel als website (UI in het
Nederlands), Python-scripts via GitHub Actions als data-pipeline. AI-extractie van
pdf-verklaringen (Claude API) komt pas in Fase 4. Doel: < €50/maand tot de eerste
betalende klant, onderhoudbaar door één persoon met Claude Code.

## Zo werk je hieraan (zonder developer-achtergrond)

1. Open een Claude Code-sessie in deze repo.
2. Zeg bijvoorbeeld: *"Pak de volgende openstaande taak uit Fase 0 in ROADMAP.md."*
3. Claude legt keuzes in gewone taal voor; beslissingen landen in `docs/beslissingen.md`.

## Spelregels (kort)

Alleen openbare data in v1 · herkomst per feit zichtbaar · nooit namen van natuurlijke
personen (AVG) · onzekere matches naar de review-queue, nooit stil mergen · zo simpel
en goedkoop mogelijk. Volledige guardrails: `docs/concept.md` §9.
