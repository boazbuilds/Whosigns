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
| 0 | Fundament | Repo, schema, Supabase, AFM-kantorenseed, site live | 🔨 bijna klaar (alleen de Vercel-deploy nog) |
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
- [x] Supabase-project aanmaken en het schema draaien; GitHub Secrets
      `SUPABASE_URL`/`SUPABASE_SERVICE_ROLE_KEY` toegevoegd — zie `docs/setup-supabase.md`
      (beslissing #3, regio: opdrachtgever koos opnieuw bij het aanmaken, niet
      hier vastgelegd — bevestigen welke regio het uiteindelijk is geworden)
- [x] Wegschrijfroute naar Supabase klaar: `pipeline/supabase_client.py`
      (PostgREST, stdlib-only) + `pipeline/laad_kantoren.py` (idempotente upsert
      van kantoren en aliassen)
- [x] GitHub Action `.github/workflows/pipeline.yml`: wekelijks + handmatig;
      ververst de seed, commit mutaties als log, schrijft naar de database zodra
      de secrets er zijn (en slaat die stap netjes over zolang dat niet zo is)
      — **eerste succesvolle run bevestigd 29-7-2026**
- [x] Next.js-app (App Router) in `/web` — geen "hello world" geworden maar meteen
      de vier doorklikbare pagina­soorten op de echte proefdata, mét badge
      "Demo · gedeeltelijke data" en `robots: noindex` tot beslissing #2.
      Zie `web/README.md`. **Deploy naar Vercel: handmatige stap van de
      opdrachtgever** (Root Directory `web`, twee omgevingsvariabelen)
- [x] AFM-vergunningenregister ophalen via de officiële XML-export →
      `pipeline/adapters/afm_register.py` + `pipeline/seed/kantoren.csv`
      (233 kantoren, 6 met OOB-vergunning; hersnapshot = script draaien en committen,
      de git-diff is het mutatielog)
- [x] Seed naar Supabase upserten: `pipeline/laad_kantoren.py`, draait nu groen
      in productie — 233 kantoren + aliassen staan in de database
      `kantoor_alias` verder vullen zodra de eerste DigiMV-namen binnenkomen (Fase 1)
- [x] README aangevuld met de Vercel-stappen (`web/README.md`; Supabase staat in
      `docs/setup-supabase.md`)

**Klaar wanneer:** de site staat live (leeg maar netjes), `kantoren` is gevuld vanuit
het AFM-register, en de pipeline draait groen in GitHub Actions.
*Stand: alles klaar behalve de Vercel-deploy zelf — die is een handmatige stap.*

## Fase 1 — Zorgdata: de relatiegraaf vullen

**Doel:** Organisatie ↔ Accountant ↔ Opdracht ↔ Jaar voor de zorgsector, boekjaren
2018–2024. Zonder LLM: gestructureerde velden + deterministische tekstmatch.

*Kolominspectie 2023 is gedaan (zie `pipeline/adapters/digimv.md`): KvK-nummer, soort
en vorm van de verklaring (oordeel), honoraria (gesplitst) en zelfs de vraag "bent u
van accountant gewisseld?" zitten gestructureerd in de dataset — de kantoornaam níét;
die staat in de verklaring-pdf's in het DigiMV-archief.*

- [x] Dataset boekjaar 2023 downloaden en streamend lezen →
      `pipeline/adapters/digimv_dataset.py` (content.xml is 300 MB, dus iterparse)
- [x] Kolominspectie boekjaar 2023 → `pipeline/adapters/digimv.md`
- [ ] Kolominspectie overige jaargangen (2019–2022, 2024) — veldnamen verschillen per
      jaar; download-adressen staan in `digimv.md`, `KOLOM` in `digimv_dataset.py`
      aanvullen. Boekjaar 2025 heeft nog geen gepubliceerde dataset.
      **Niet blokkerend:** met `--lijst-uit 2023` laadt de bulk-lader álle boekjaren
      2019–2025 op de lijst van 2023. Deze taak gaat alleen nog over de organisaties
      die in 2023 géén controle hadden maar in een ander jaar wél
- [ ] Datasets ruw opslaan in Supabase Storage (bron bewaren vóór verwerking) —
      zie ook beslissing #8 hieronder over pdf's
- [x] **Doelpopulatie-filter gevonden — dit halveert Fase 1 meer dan eens.**
      `bestandAccountantsVerklaringSoort_N` zegt vooraf wie een controleverklaring
      heeft: van de 6.131 organisaties (bj. 2023) zijn dat er **1.010**; 422 hebben
      een samenstellings-, 345 een beoordelingsverklaring en 4.389 deponeerden niets.
      Alleen die 1.010 hoeven het archief in — ±35.000 verzoeken minder
- [x] Kantoornaam-route bewezen: archief-API uitgezocht (`digimv_archief.py`),
      pdftotext + stringmatch tegen AFM-lijst/aliastabel (`kantoor_match.py`,
      `verklaring.py`), meetbaar via `valideer_extractie.py` —
      **12/12 ziekenhuizen (100%), 26/27 gemengd (96%), nul valse matches**;
      oordeel en continuïteitsonzekerheid komen uit dezelfde tekst
- [x] Aliastabel gestart (`pipeline/seed/kantoor_alias.csv`) — zonder aliassen bleef
      de trefkans op 85% steken (Ernst & Young LLP → EY B.V., handelsnamen)
- [x] Dekkingsstrategie bepaald: de dataset zelf (`qNawNaam`/`qNawPlaatsLrza` in
      de RowData-sheets) is de officiële, complete lijst van 6.132 organisaties —
      geen letter-enumeratie in het archief nodig, wél per organisatie gericht
      zoeken op naam+plaats met KvK-nummer als controle (zie `digimv.md`)
- [x] Adapter `pipeline/adapters/digimv.py` gebouwd (archiefzoekopdracht →
      verklaring ophalen en analyseren → structuur klaar voor Supabase) en
      **end-to-end bewezen over meerdere boekjaren**:
      `pipeline/laad_proefdata.py` laadt 13 bekende ziekenhuizen × boekjaren
      2019–2024 (~70 opdrachten), met **4 echte accountantswisselingen** en
      één oordeel met beperking — eigen workflow `proefdata.yml`
- [x] Matchen op KvK-nummer i.p.v. naam+plaats (naam en plaats wisselen per
      boekjaar in de bron); documenten ook uit `locations[]` halen; venster
      van het archief vastgelegd (2019+, ouder geeft HTTP 500) — zie `digimv.md`
- [x] Bulk-lader gebouwd: `pipeline/laad_zorg.py` + workflow `zorgdata.yml`.
      Hervatbaar (al geladen organisatie-boekjaren worden overgeslagen), op te
      knippen met `--vanaf`/`--aantal`, en met `--droogloop` te draaien zonder
      database. Vier organisaties tegelijk: ~1 seconde per organisatie in plaats
      van 7,5 — dat maakt het verschil tussen een kwartier en twee uur per jaargang
- [ ] **Bulk-run boekjaar 2023 naar de database** (proefrit gedaan, zie hieronder)
- [ ] Bulk-run overige boekjaren, ná de kolominspectie per jaargang
- [ ] Ruwe pdf's opslaan — **beslissing #8: alleen de tekst + vingerafdruk**, en
      het hele pdf enkel bij gevallen die misgingen. Eén jaargang van één sector
      verkeert al ±3 GB aan pdf's; Supabase gratis geeft 1 GB
- [ ] Restgevallen (gescande pdf's, kantoornaam alleen in logo) naar `review_queue`
- [ ] **Mijlpaal A: eerste 1.000 organisaties** in de database — de klik-test-dataset.
      Ligt binnen handbereik: de doelpopulatie van boekjaar 2023 is er precies 1.010
- [ ] **Mijlpaal B: volledige zorgsector** voor de jaren waar de bron het toelaat
- [ ] Steekproefcontrole: 25 organisaties handmatig naleggen tegen de bron

**Wat de proefrit over boekjaar 2023 leerde** (droogloop, zie `digimv.md`):

- Trefkans ligt rond **43%** over de volle doelpopulatie — véél lager dan de 96% op
  ziekenhuizen, en dat klopt: kleine zorg-BV's hebben vaak geen jaarrekeningcontrole
  maar een WNT- of productieverantwoording, meestal van een kantoor zónder
  Wta-vergunning. Dat wij daar niets vastleggen is de guardrail die werkt.
- Wat we wél missen en willen hebben: **gescande verklaringen** in de jaarrekeningen
  van grote instellingen (UMCG, Bernhoven, Lentis). Vraagt OCR → Fase 4.
- **Aliassen blijven de grootste winst per uur werk.** Drie erbij deze ronde, gevonden
  door handtekeningblokken te lezen: Alfa Accountants → *aaff Audit en Assurance B.V.*,
  Moore-DRV, en Qconcepts → *Q-Concepts Accountancy B.V.*

**Klaar wanneer:** duizenden opdrachten in de database met herkomst per feit, en de
import is met één actie opnieuw te draaien zonder duplicaten.

## Fase 2 — De klik-machine

**Doel:** de vier pagina's, gebouwd rond de zes velden, die klikken als Wikipedia —
en de test of dat écht gebeurt.

*Eerste versie van de vier pagina's staat er al (gebouwd op de proefdata, zodat er
iets te beoordelen viel vóór de bulk-run). Wat hieronder nog openstaat is verfijning
en de test zelf.*

- [x] Home/zoek: één zoekbalk (organisatie én kantoor), teasers "recente wisselingen"
      en "grootste kantoren in de zorg"
- [x] Kantoorprofiel `/kantoor/[slug]`: cliëntentabel met relatieduur, gewonnen en
      verloren opdrachten (mét "naar wie"), concurrenten
      — [ ] nog: metric cards, sectorverdeling zodra er meer dan één sector is
- [x] Organisatieprofiel `/organisatie/[kvk]`: huidige accountant, historie per boekjaar,
      relatiegeschiedenis per periode, bronvermelding per feit
- [x] Wisselingen `/wisselingen`: uit de historie afgeleide wisselingen (`v_wisselingen`),
      gegroepeerd per boekjaar
      — [ ] nog: de zelfgerapporteerde wisselvlag uit DigiMV ernaast, en filters op
      sector/jaar/kantoor (nu nog niet nodig bij 4 wisselingen)
- [x] **Harde eis (visie): elke pagina minimaal 5 interessante vervolgklikken; elke naam
      klikbaar; geen doodlopende pagina's** — het onderdeel `<Doorklik>` waarschuwt
      tijdens ontwikkelen als een pagina eronder zakt; ook de 404 heeft doorklikken
- [x] Nette lege-staten, bronlabel per feit, badge "Demo · gedeeltelijke data"
- [ ] Sectorpagina uitbreiden zodra er meer dan één sector in de database zit
- [ ] Opmaak/huisstijl (nu bewust sober: eerst inhoud beoordelen, dan pas mooi)
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
