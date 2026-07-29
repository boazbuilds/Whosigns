# Supabase instellen — stap voor stap

*Geschreven voor iemand zonder developer-achtergrond. Duurt ongeveer 15 minuten.
Je hebt hiervoor niets te installeren; alles gaat via de browser.*

## Wat is Supabase ook alweer?

De plek waar onze gegevens wonen: een database (Postgres) plus opslag voor de
originele bronbestanden. Gratis in de startfase.

---

## Stap 1 — Project aanmaken

Op supabase.com → New project:

| Veld | Kiezen | Waarom |
|---|---|---|
| Organization | je eigen (Free) | — |
| **GitHub (optional)** | **overslaan** | Automatische deploys maken het onvoorspelbaarder; we voeren het schema één keer handmatig in. Later eventueel aanzetten. |
| Project name | `Whosigns` | — |
| Database password | **Generate a password** → opslaan in je wachtwoordmanager | Alleen nodig voor directe koppelingen zoals Power BI. Nooit in een chat of in de code plakken. |
| Region | Europe (Frankfurt als het gevraagd wordt) | AVG-comfort en snelheid |
| Enable Data API | **aan** | Hiermee leest de website straks de gegevens |
| Automatically expose new tables | aan (mag) | Veilig zolang RLS aan staat — ons schema regelt dat |
| **Enable automatic RLS** | **aan** | Vangnet: nieuwe tabellen zijn nooit per ongeluk publiek leesbaar |

> **Wachtwoord per ongeluk gedeeld?** Zolang het project nog niet is aangemaakt:
> gewoon opnieuw genereren. Bestaat het project al: Settings → Database →
> Reset database password.

## Stap 2 — Het schema aanmaken (één keer)

1. Open in Supabase links **SQL Editor** → **New query**.
2. Open in GitHub het bestand `supabase/migrations/20260727000000_init.sql`,
   klik op de kopieerknop (rechtsboven in het bestand).
3. Plak alles in de SQL Editor en klik **Run**.
4. Je hoort "Success. No rows returned" te zien. Links onder **Table Editor**
   staan nu de tabellen: `organisaties`, `kantoren`, `opdrachten`, `bronnen`,
   `signalen`, `review_queue` en de rest.
5. Herhaal stap 1–3 voor élk volgend bestand in `supabase/migrations/`, op
   naam gesorteerd (het nummer vooraan is de datum, dus oudste eerst):
   `20260729210000_extra_velden.sql` en `20260730000000_kantoren_zonder_wta.sql`.
   Ze zijn zo geschreven dat opnieuw draaien geen kwaad kan.

### Of: migraties door GitHub laten draaien (aanrader, één keer instellen)

Zodra dit eenmaal staat, hoef je nooit meer SQL te kopiëren — ook niet bij volgende
wijzigingen. De workflow **Migraties draaien** past zelf toe wat er nog niet op de
database staat, en houdt in een tabel `schema_migraties` bij wat al gedaan is.

1. In Supabase: **Project Settings → Database → Connection string → Session pooler**.
   Neem die URI (níet "Direct connection": die werkt alleen over IPv6 en een
   GitHub-runner heeft dat niet) en vul je databasewachtwoord in op de plek van
   `[YOUR-PASSWORD]`.
2. In GitHub: **Settings → Secrets and variables → Actions → New repository secret**,
   naam `SUPABASE_DB_URL`, waarde die URI.
3. **Actions → Migraties draaien → Run workflow.** Laat `overslaan` staan op het
   init-script als je dat al met de hand hebt gedraaid; dat wordt dan alleen
   geregistreerd. Met `droogloop` aan zie je eerst wat er zou gebeuren.

De drie migraties zijn getest tegen een schone PostgreSQL 16: ze draaien in deze
volgorde door, en de laatste kan zonder bezwaar twee keer.

Bij een foutmelding: kopieer die en plak hem in een Claude Code-sessie; dan zoek ik
het uit.

## Stap 3 — Sleutels veilig doorgeven

De pipeline moet gegevens kunnen wegschrijven. Dat doet hij vanuit GitHub, met
sleutels die als *secret* zijn opgeslagen — zo staan ze nergens in de code en hoeft
niemand ze door te sturen.

In Supabase: zoekbalk → **API Keys**. Sinds medio 2026 heten de sleutels daar anders
dan vroeger, maar het principe is hetzelfde:

| Nieuwe naam (huidig scherm) | Oude naam ("Legacy" tabblad) | Wat het is |
|---|---|---|
| Publishable key | anon key | mag openbaar, komt later in Vercel voor de website |
| **Secret key** | **service_role key** | **geheim — deze heb je nu nodig** |

Je hebt twee waarden nodig:

- **Project URL** — staat bovenaan de project-Overview (huisje-icoon), ziet eruit
  als `https://xxxx.supabase.co`
- **Secret key** — bij API Keys → sectie "Secret keys" → oog-icoontje om te tonen →
  kopieer-icoontje

In GitHub: ga naar de repo → **Settings → Secrets and variables → Actions →
New repository secret**, en maak er twee aan (de namen hieronder zijn wat onze
code verwacht — die blijven zo, ook al noemt Supabase het zelf anders):

| Name | Secret |
|---|---|
| `SUPABASE_URL` | de Project URL |
| `SUPABASE_SERVICE_ROLE_KEY` | de Secret key |

> De **Secret / service_role key** omzeilt alle beveiliging en hoort alleen in
> GitHub Secrets — nooit in de repo, een chat of de website.
> De **Publishable / anon key** is juist bedoeld om openbaar te zijn; die komt
> later in Vercel te staan voor de website.

## Stap 4 — Controleren of het werkt

In GitHub: tabblad **Actions** → workflow **Pipeline** → **Run workflow**.
Hij vult de kantorenlijst (233 accountantsorganisaties) in de database. Groen
vinkje = klaar. In Supabase zie je ze onder Table Editor → `kantoren`.

## Daarna

Zeg in een Claude Code-sessie: *"Supabase staat klaar, ga verder met de roadmap."*
Dan laad ik de zorgdata in en bouw ik de eerste pagina's.

---

## Kort: wie mag wat?

| Sleutel | Wie gebruikt hem | Mag |
|---|---|---|
| anon key | de website (in de browser) | alleen lezen wat publiek is |
| service_role key | de pipeline (in GitHub Actions) | alles lezen en schrijven |
| database password | jij, vanuit bijv. Power BI | directe databaseverbinding |

De review-queue (twijfelgevallen die menselijke controle nodig hebben) staat
bewust niet open voor de website.
