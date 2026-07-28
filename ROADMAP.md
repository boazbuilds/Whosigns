# WhoSigns — Roadmap

*Bijgewerkt: 28 juli 2026. Leidraad: `docs/visie.md` (zes velden, relatiegraaf, klik-test).
Volledige achtergrond: `docs/concept.md`. Onderbouwing 🆕-items: `docs/brainstorm-2026-07.md`.
Open keuzes: `docs/beslissingen.md`.*

**Werkwijze:** fase voor fase, elke fase eindigt met iets dat wérkt en te laten zien is.
Niet vooruitwerken aan een latere fase zolang de huidige niet "klaar" is volgens haar
eigen meetlat. Guardrails uit `docs/concept.md` §9 gelden altijd.

**MVP-scope (uit de visie):** de zes velden — organisatie, accountant, opdrachttype,
jaar, sector, bron. Geen AI-extractie, geen honoraria, geen switch-scores in het MVP-pad;
het schema houdt er wel plek voor (kolommen blijven leeg tot een latere fase).

## Overzicht

| Fase | Naam | Resultaat | Status |
|------|------|-----------|--------|
| 0 | Fundament | Repo, schema, Supabase, AFM-kantorenseed, lege site live | 🔨 gestart |
| 1 | Zorgdata | Relatiegraaf gevuld: eerste 1.000 → volledige zorgsector | ⬜ |
| 2 | Klik-machine | Vier doorklikbare pagina's + klik-test met echte gebruikers | ⬜ |
| 3 | Lancering & OOB | Publiek live: volledige zorg + beursfondsen/banken/verzekeraars | ⬜ |
| 4 | Verdieping | AI-extractie, signalen, onderwijs, nieuwsbrief | ⬜ |
| 5 | Omzet | Freemium live, pricing-validatie, besluit KvK-inkoop | ⬜ |

---

## Fase 0 — Fundament

**Doel:** alles staat klaar om in Fase 1 echte data te laten stromen; een niet-developer
kan met de README het project begrijpen en draaien.

- [x] Repo-structuur, roadmap, conceptdocument, visie en beslislog in de repo
- [x] SQL-schema als migration (`supabase/migrations/`): de relatiegraaf
      (organisaties ↔ kantoren ↔ opdrachten ↔ boekjaren) + bronnen, signalen,
      review-queue, views (relatieduur, wisselingen, marktaandeel) en Row Level Security
- [ ] Supabase-project aanmaken (EU-regio, beslissing #3) en de migration draaien
- [ ] Next.js-app (App Router) in `/web`, deploy naar Vercel ("hello world" met
      huisstijl-aanzet en badge "Demo · gedeeltelijke data")
- [ ] AFM-vergunningenregister ophalen → seed van `kantoren` (regulier/OOB) + eerste
      vulling `kantoor_alias`; script in `/pipeline`, herdraaibaar
- [ ] GitHub Action-skelet: pipeline handmatig triggerbaar + wekelijks schema 🆕
- [ ] README aangevuld met setup-stappen (Supabase-keys, Vercel, pipeline draaien)

**Klaar wanneer:** de site staat live (leeg maar netjes), `kantoren` is gevuld vanuit
het AFM-register, en de pipeline draait groen in GitHub Actions.

## Fase 1 — Zorgdata: de relatiegraaf vullen

**Doel:** Organisatie ↔ Accountant ↔ Opdracht ↔ Jaar voor de zorgsector, boekjaren
2018–2024. **Alleen gestructureerde velden — geen pdf/AI-extractie (dat is Fase 4).**

- [ ] Datasets Zorg/Jeugd per boekjaar downloaden (.ods, jaarverantwoordingzorg.nl) en
      ruw opslaan in Supabase Storage (bron bewaren vóór verwerking — de financials en
      honoraria die we nú niet laden, blijven zo beschikbaar voor later)
- [ ] Kolominspectie per jaargang, vastleggen in `pipeline/adapters/digimv.md`: in welke
      jaren zit de kantoornaam gestructureerd in de dataset, hoe heten de velden
- [ ] Adapter `pipeline/adapters/digimv.py`: de zes velden → kernmodel, idempotent
      (organisatie mét KvK-nummer, kantoor via aliastabel, opdrachttype, boekjaar,
      sector, bron)
- [ ] Naamnormalisatie: exact op `kantoor_alias`, fuzzy naar `review_queue`, nooit stil
      mergen (gewone tekstmatching — hier is geen AI voor nodig)
- [ ] **Mijlpaal A: eerste 1.000 organisaties** in de database — de klik-test-dataset
- [ ] **Mijlpaal B: volledige zorgsector** voor de jaren waar de bron het toelaat
- [ ] Steekproefcontrole: 25 organisaties handmatig naleggen tegen de bron
- [ ] Organisaties waar de kantoornaam alléén in de pdf-verklaring staat: markeren en
      parkeren voor Fase 4 (niet nu oplossen)

**Klaar wanneer:** duizenden opdrachten in de database met herkomst per feit, en de
import is met één actie opnieuw te draaien zonder duplicaten.

## Fase 2 — De klik-machine

**Doel:** de vier pagina's, gebouwd rond de zes velden, die klikken als Wikipedia —
en de test of dat écht gebeurt.

- [ ] Home/zoek: één zoekbalk (organisatie én kantoor), teasers "recente wisselingen"
      en "grootste kantoren in de zorg"
- [ ] Kantoorprofiel `/kantoor/[slug]`: metric cards (aantal controles, gemiddelde
      relatieduur, netto cliëntgroei, actieve sectoren — géén honorarium-card in het
      MVP), cliëntentabel, sectorverdeling, "cliënt sinds"
- [ ] Organisatieprofiel `/organisatie/[kvk]`: huidige accountant, historie per boekjaar,
      vorige accountant, bronvermelding per feit
- [ ] Wisselingen `/wisselingen`: uit de historie afgeleide wisselingen (`v_wisselingen`),
      chronologisch, filterbaar op sector/jaar/kantoor — feiten, geen voorspellingen
- [ ] **Harde eis (visie): elke pagina minimaal 5 interessante vervolgklikken; elke naam
      klikbaar; geen doodlopende pagina's**
- [ ] Nette lege-staten, bronlabel per feit, badge "Demo · gedeeltelijke data"
- [ ] **Klik-test:** 5–10 mensen uit de doelgroep zonder uitleg laten rondkijken.
      Meten: zoeken ze spontaan een naam op, doorklikdiepte (doel ≥ 5 pagina's/sessie),
      komen ze later uit zichzelf terug? Notities in `docs/validatie/`

**Klaar wanneer:** de klik-test is gedaan en testgebruikers klikken spontaan door
(Wikipedia-gevoel). Zo niet: eerst begrijpen waarom, dan pas verder.

## Fase 3 — Publieke lancering & OOB's

**Doel:** live voor iedereen, met een geloofwaardige dataset: de volledige zorgsector
plus de meest gezochte namen van Nederland (beursfondsen, banken, verzekeraars).

- [ ] Volledige zorgdekking is de lat voor lancering (een site met gaten oogt
      onbetrouwbaar; beslissing #2)
- [ ] OOB-cliëntlijsten uit de ±6–10 transparantieverslagen per jaar (EU-Vo. 537/2014
      art. 13) — klein genoeg om desnoods handmatig over te nemen, geen AI-pipeline
      nodig; eerste benoemingsjaar meenemen waar vindbaar
- [ ] Freemium-grens vaststellen (beslissing #6); bij lancering mag alles nog gratis
- [ ] Domein live (beslissing #1), SEO-basis (sitemap, nette titels/meta's per
      profielpagina), privacyvriendelijke analytics zodat de noordster meetbaar is
- [ ] Aankondiging: één goed lijstje als lanceringshaakje (bijv. "marktaandelen in de
      zorg" of "alle wisselingen 2024") richting vakpers 🆕

**Klaar wanneer:** de site is publiek, vindbaar en wordt zonder uitleg gebruikt;
bezoek en doorklikgedrag zijn zichtbaar in analytics.

## Fase 4 — Verdieping: AI-extractie, signalen, onderwijs

**Doel:** de lagen die het MVP bewust oversloeg — nu de graaf bewezen werkt.

- [ ] AI-extractiemodule (Claude API) voor pdf-verklaringen →
      `{kantoornaam, oordeel, boekjaar, datum_verklaring, continuiteitsonzekerheid}`;
      onzekere extracties naar `review_queue`. Ontgrendelt: de geparkeerde zorg-gaten
      uit Fase 1, oordelen, en de onderwijssector
- [ ] DUO-adapter (onderwijs): besturen + financiën gestructureerd; kantoornaam uit
      jaarverslagen via de extractiemodule
- [ ] Signalen v1: lange relatie (≥ 10 jaar), niet-goedkeurend oordeel of
      continuïteitsonzekerheid 🆕, kantoor verdwenen uit AFM-register (wekelijkse
      snapshot; hele portefeuille moet verkassen), TenderNed-aanbestedingen
      (CPV-codes rond 79210000 uitzoeken)
- [ ] Rotatiekalender 🆕: `verplichte_roulatie` voor OOB's die de 10-jaarstermijn
      naderen (afgeleide van de Fase 3-data) — van signaleren naar voorspellen
- [ ] Signaalbeheer: status actief/afgehandeld; wisseling gedetecteerd → signaal sluiten
- [ ] Nieuwsbrief-opt-in + eerste handmatige editie "wisselingen & signalen" 🆕

**Klaar wanneer:** drie sectoren doorzoekbaar (zorg, OOB, onderwijs), minimaal drie
signaaltypen live met echte gevallen, eerste nieuwsbrief verstuurd.

## Fase 5 — Omzet & validatie

**Doel:** bewijs dat iemand betaalt, vóórdat er geld naar KvK-data gaat.

- [ ] Freemium aanzetten conform beslissing #6 (Pro/Team uit `docs/visie.md`)
- [ ] 10 gesprekken met doelgebruikers (BD kantoren, 1–2 PE-partijen, 1–2 CFO's,
      1 journalist); notities in `docs/validatie/`
- [ ] Eén betaalde pilot proberen (alerts voor één kantoor, of een
      PE-due-diligence-rapport over een kantoorportefeuille 🆕)
- [ ] Prijshypothese vastleggen (abonnement / rapport / alerts)
- [ ] **Beslismoment KvK-inkoop** (beslissing #4): pas kopen als een klant er aantoonbaar
      op wacht; "data on demand" — het bedrijfsleven (denk aan het
      Studio-Anneloes-voorbeeld uit de visie) komt pas met deze stap op naam beschikbaar

**Klaar wanneer:** er is óf een eerste betalende klant/pilot, óf een onderbouwd besluit
wat er moet veranderen voordat iemand betaalt.

---

## Backlog (niet nu, wel schema-proof)

Volgorde indicatief; oppakken op basis van wat de klik-test en Fase 5 leren.

1. **Records & ranglijsten** 🆕 — langste relatie van NL, netto cliëntenstroom per
   kantoor ("wisselmarkt boekjaar X"), marktaandelen; goedkoop, hoge pers-waarde
2. KvK XBRL-parser (SBR Assurance, middelgroot) + pdf-batch voor gekochte
   KvK-jaarrekeningen — ontsluit het bedrijfsleven op naam ("data on demand")
3. Verticals: ANBI's/CBF-goede doelen, woningcorporaties, gemeenten/provincies/
   waterschappen, pensioenfondsen, fondsen
4. Switch-scores / voorspelmodellen — uitdrukkelijk pas ná validatie (visie: "nog niet")
5. Honoraria tonen + fee-benchmark (kolommen liggen klaar; art. 2:382a BW, DigiMV, DUO)
6. Supabase Auth + geclaimde kantoorprofielen (badge "neemt cliënten aan"; datagedreven
   indicator "groeit in sector X" kan eerder 🆕)
7. Uitvraagplaatsingen ("wij zoeken een accountant") — sterk door de marktkrapte
8. Nieuwsbrief automatiseren; alerts als betaalfunctie
9. AQI-import zodra de NBA publiceert (boekjaren vanaf 2027); CSRD-assurance als kolom
10. Stroomdiagram van→naar per boekjaar; sectoroverzichtpagina's per regio
11. België / Duitsland / Europa — zelfde EU-openbaarmakingsregels, zelfde model

## Definition of done (MVP = na Fase 3)

Website publiek op een eigen domein, gevuld met de volledige zorgsector (meerdere
boekjaren) én de OOB-cliëntlijsten, doorzoekbaar op organisatie én kantoor, werkende
kantoor- en organisatieprofielen plus wisselingenoverzicht uit de historie, de zes
velden overal met bronvermelding per feit, elke pagina ≥ 5 vervolgklikken, een
geslaagde klik-test, en een pipeline die met één commando/actie opnieuw draait.

*(Afwijking van `docs/concept.md` §10: wisselsignalen zitten niet meer in de MVP-lat
maar in Fase 4 — conform `docs/visie.md`: eerst bewijzen dat mensen zoeken en klikken.)*

## Beslismomenten

| Wanneer | Beslissing | Zie |
|---------|-----------|-----|
| Nu | Naam & domein (WhoSigns vs. Auditkaart) | beslissing #1 |
| Vóór Fase 0-afronding | Supabase-regio | beslissing #3 |
| Eind Fase 2 / vóór lancering | Publiek + waar ligt de freemium-grens | beslissingen #2 en #6 |
| Fase 5 | Eerste KvK-inkoop | beslissing #4 |
