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

🟢 **Live en zelfvullend** (stand: 24 augustus 2026). De site draait op Vercel
met ruim 60.000 opdrachten bij ruim 18.000 organisaties — van zorg,
woningcorporaties en onderwijs tot pensioenfondsen en het brede bedrijfsleven.
Een dozijn bronroutes vult de database zonder handwerk: elke merge op main die
een seed, lader of aanlevering raakt, start via GitHub Actions zijn eigen
lading. Alleen "Alles verversen" is nog een handmatige totaalknop. Zie
`ROADMAP.md` voor de fases en wat er nog komt.

## Wegwijzer

| Bestand/map | Wat |
|---|---|
| `docs/visie.md` | De productvisie — **leidend** bij twijfel; begin hier |
| `ROADMAP.md` | Het bouwplan: fases, taken, beslismomenten |
| `docs/setup-supabase.md` | Stap voor stap de database opzetten (zonder developer-kennis) |
| `docs/concept.md` | Volledige context: domeinkennis, bronnen, guardrails |
| `docs/bronverkenning-stichtingen.md` | Stichtingen/NGO's: welke routes er zijn en wat ze meten (CBF, ANBI, verticals) |
| `docs/bestaande-databases.md` | "Bestaat de database al?" — dVi-corporaties (accountant staat er als veld in!), BZK-gemeenten, AFM-totalen, Audit Analytics, ESAP vanaf 2028 |
| `docs/brainstorm-2026-07.md` | Analyse "waarom Transfermarkt werkt" + verbetervoorstellen |
| `docs/beslissingen.md` | Beslislog: open keuzes met aanbeveling + genomen besluiten |
| `supabase/migrations/` | Databaseschema (Postgres), draait straks op Supabase |
| `pipeline/` | Python-importscripts per bron (adapters) — Fase 1 e.v. |
| `pipeline/lus.py` | Een sector in rondes laden in plaats van in één bulk-run; werkvoorraad in `pipeline/werkvoorraad/` |
| `web/` | De website (Next.js) — zie `web/README.md` voor draaien en deployen |

## De zes velden, en wat erbij kwam

De kern blijft: organisatie, accountant, opdrachttype, jaar, sector, bron —
gepresenteerd zó dat je blijft doorklikken. Waar de bron het draagt, staan er
inmiddels ook het oordeel, de tekenend accountant, continuïteitsonzekerheid en
de verantwoorde honoraria (art. 2:382a BW) bij. De spelregels zijn ongewijzigd:
alles uit openbare of rechtmatig aangeleverde bronnen met de vindplaats erbij,
en bij twijfel een gat in plaats van een gok — twijfelgevallen wachten in een
review-queue op een mens.

## Techniek in één alinea

Supabase (Postgres + Storage, EU) als database, Next.js op Vercel als website
(UI in het Nederlands), Python-scripts (alleen standaardbibliotheek) via GitHub
Actions als data-pipeline. De extractie uit verklaringen is patroongebaseerd —
geen AI in de pijplijn, dus elke rij is herleidbaar tot een regel tekst in een
document. Kosten: < €50/maand; onderhoudbaar door één persoon met Claude Code.

## Zo werk je hieraan (zonder developer-achtergrond)

1. Open een Claude Code-sessie in deze repo.
2. Zeg bijvoorbeeld: *"Pak de volgende openstaande taak uit Fase 0 in ROADMAP.md."*
3. Claude legt keuzes in gewone taal voor; beslissingen landen in `docs/beslissingen.md`.

## Spelregels (kort)

Alleen openbare data in v1 · herkomst per feit zichtbaar · nooit namen van natuurlijke
personen (AVG) · onzekere matches naar de review-queue, nooit stil mergen · zo simpel
en goedkoop mogelijk. Volledige guardrails: `docs/concept.md` §9.
