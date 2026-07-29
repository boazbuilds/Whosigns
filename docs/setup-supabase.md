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

Bij een foutmelding: kopieer die en plak hem in een Claude Code-sessie; dan zoek ik
het uit.

## Stap 3 — Sleutels veilig doorgeven

De pipeline moet gegevens kunnen wegschrijven. Dat doet hij vanuit GitHub, met
sleutels die als *secret* zijn opgeslagen — zo staan ze nergens in de code en hoeft
niemand ze door te sturen.

In Supabase: **Project Settings → API**. Je hebt twee waarden nodig:

- **Project URL** — ziet eruit als `https://xxxx.supabase.co`
- **service_role key** — de lange geheime sleutel (níét de anon key)

In GitHub: ga naar de repo → **Settings → Secrets and variables → Actions →
New repository secret**, en maak er twee aan:

| Name | Secret |
|---|---|
| `SUPABASE_URL` | de Project URL |
| `SUPABASE_SERVICE_ROLE_KEY` | de service_role key |

> De **service_role key** omzeilt alle beveiliging en hoort alleen in GitHub
> Secrets — nooit in de repo, een chat of de website.
> De **anon key** is juist bedoeld om openbaar te zijn; die komt later in Vercel te
> staan voor de website.

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
