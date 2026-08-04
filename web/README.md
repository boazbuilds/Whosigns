# WhoSigns — website

De publieke kant van WhoSigns: vier doorklikbare pagina­soorten bovenop de
relatiegraaf in Supabase. Fase 0 (site live) en de basis voor Fase 2
(klik-machine) uit [`../ROADMAP.md`](../ROADMAP.md).

## Wat staat waar?

| Pad | Pagina | Wat je ziet |
|---|---|---|
| `/` | Start | Zoeken, recente wisselingen, kantoren, alle organisaties |
| `/organisatie/<kvk>-<naam>` | Organisatie | Accountant per boekjaar, wisselingen, relatiegeschiedenis |
| `/kantoor/<afm>-<naam>` | Kantoor | Cliënten, gewonnen en verloren opdrachten, concurrenten |
| `/sector/<sector>` | Sector | Kruistabel controles per kantoor per boekjaar, wisselingen |
| `/wisselingen` | Wisselingen | Alle wisselingen, gegroepeerd per boekjaar |
| `/organisaties` | Alle organisaties | Alfabetisch register met plaats en subsector |
| `/bevindingen` | Oordelen | Niet-goedkeurende oordelen en continuïteit, met de grond |
| `/subsector/[naam]` | Subsector | Kantoren en organisaties binnen één subsector |
| `/zoeken?q=` | Zoeken | Organisaties én kantoren |

**URL-vorm:** het nummer vooraan is de sleutel (KvK, resp. AFM-nummer), de naam
erachter is voor de lezer en voor Google. Zo blijft een link werken als de bron de
naam volgend boekjaar anders spelt — hetzelfde probleem dat de pipeline op
KvK-nummer oplost.

## Twee regels die niet mogen sneuvelen

1. **Minimaal 5 vervolgklikken per pagina** (`docs/visie.md`). Het onderdeel
   `<Doorklik>` waarschuwt in de console tijdens ontwikkelen als een pagina eronder
   zakt. Ook de 404 heeft doorklikken — juist daar loopt iemand anders vast.
2. **Nooit natuurlijke personen.** De site toont uitsluitend
   accountants*organisaties*; de database bevat niets anders (AVG-guardrail,
   `docs/concept.md` §9).

## Lokaal draaien

```bash
cd web
npm install
cp .env.example .env.local     # en vul de twee waarden in
npm run dev                    # http://localhost:3000
```

`.env.local` heeft twee waarden nodig:

| Variabele | Waar vandaan |
|---|---|
| `NEXT_PUBLIC_SUPABASE_URL` | Supabase → Project Settings → Data API |
| `NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY` | Supabase → Project Settings → API Keys → **Publishable** |

> **Alleen de publishable key.** Die mag openbaar zijn: Row Level Security geeft
> iedereen leesrecht en er bestaat bewust géén schrijfpolicy. De **secret key**
> (voorheen service_role) hoort uitsluitend in GitHub Secrets, waar de pipeline hem
> gebruikt — nooit in deze map, nooit in een browser.

## Deploy (Vercel)

Eenmalig: vercel.com → New Project → repo `Whosigns` importeren.

| Instelling | Waarde |
|---|---|
| Root Directory | `web` |
| Environment Variables | de twee hierboven |
| Framework Preset | staat vast in `vercel.json`, hoef je niet te kiezen |

Daarna is elke push naar `main` automatisch live.

**Waarom `vercel.json`?** Staat het Framework Preset in het dashboard per ongeluk
op "Other", dan zoekt Vercel na de build naar een map `public` en faalt de deploy
met *"No Output Directory named public found"* — terwijl de build zelf gewoon
slaagde. Next.js schrijft naar `.next`, niet naar `public`. Door `framework` in
`vercel.json` te zetten wint de repo van de dropdown en kan die verwarring niet
meer ontstaan.

## Nog niet vindbaar in Google

`app/layout.tsx` zet `robots: { index: false }`. Dat blijft staan tot beslissing #2
(publiek gaan) is genomen — zie `docs/beslissingen.md`. Aanzetten is dat ene blok
weghalen.

## Keuzes die om uitleg vragen

- **Geen CSS-framework.** Eén bestand `app/globals.css` met Nederlandse
  klassenamen. De pagina's zijn dichte tabellen; daar is geen framework voor nodig,
  en zo blijft het leesbaar (guardrail: geen afhankelijkheden zonder noodzaak).
- **Geen Supabase-bibliotheek.** `lib/db.ts` praat met gewone `fetch` tegen
  PostgREST, net als `pipeline/supabase_client.py` aan de schrijfkant.
- **Feiten staan in SQL, niet hier.** Wat een wisseling ís, hoe lang een relatie
  loopt en wat marktaandeel is, staat als view in `supabase/migrations/`. `lib/`
  groepeert en telt alleen voor de weergave, zodat database en website nooit iets
  anders kunnen beweren.
- **Antwoorden worden een uur hergebruikt** (`revalidate: 3600`). De pipeline draait
  wekelijks, dus verser hoeft niet en het houdt het aantal database-verzoeken laag.
