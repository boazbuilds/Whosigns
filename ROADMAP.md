# WhoSigns — Roadmap

*Bijgewerkt: 27 juli 2026. Volledige context: `docs/concept.md`. Onderbouwing van de
🆕-items: `docs/brainstorm-2026-07.md`. Open keuzes: `docs/beslissingen.md`.*

**Werkwijze:** fase voor fase, elke fase eindigt met iets dat wérkt en te laten zien is.
Niet vooruitwerken aan een latere fase zolang de huidige niet "klaar" is volgens haar
eigen meetlat. Guardrails uit `docs/concept.md` §9 gelden altijd.

## Overzicht

| Fase | Naam | Resultaat | Status |
|------|------|-----------|--------|
| 0 | Fundament | Repo, schema, Supabase, AFM-kantorenseed | 🔨 gestart |
| 1 | Zorgdata (DigiMV) | Duizenden echte opdrachten in de database | ⬜ |
| 2 | Frontend op echte data | Vier doorklikbare pagina's, live | ⬜ |
| 3 | Signalen v1 | Wisselsignalen op profielen + nieuwsbrief-opt-in | ⬜ |
| 4 | Verbreden | Onderwijs (DUO) + OOB's + rotatiekalender | ⬜ |
| 5 | Validatie & eerste omzet | 10 gebruikersgesprekken, besluit KvK-inkoop | ⬜ |

---

## Fase 0 — Fundament

**Doel:** alles staat klaar om in Fase 1 echte data te laten stromen; een niet-developer kan
met de README het project begrijpen en draaien.

- [x] Repo-structuur, roadmap, conceptdocument en beslislog in de repo
- [x] SQL-schema als migration (`supabase/migrations/`), incl. views voor relatieduur,
      wisselingen en marktaandeel, review-queue en Row Level Security (publiek lezen,
      schrijven alleen via de pipeline)
- [ ] Supabase-project aanmaken (EU-regio, zie beslissing #3) en de migration draaien
- [ ] Next.js-app (App Router) opzetten in `/web`, deploy naar Vercel ("hello world" met
      huisstijl-aanzet en de badge "Demo · gedeeltelijke data")
- [ ] AFM-vergunningenregister ophalen → seed van `kantoren` (regulier/OOB) + eerste vulling
      `kantoor_alias`; script in `/pipeline`, herdraaibaar
- [ ] GitHub Action-skelet: pipeline handmatig triggerbaar + wekelijks schema 🆕
      (wekelijks i.p.v. maandelijks: AFM-mutaties zijn het vroegste wisselsignaal)
- [ ] README aangevuld met setup-stappen (Supabase-keys, Vercel, hoe draai ik de pipeline)

**Klaar wanneer:** de site staat live (leeg maar netjes), `kantoren` is gevuld vanuit het
AFM-register, en de pipeline draait groen in GitHub Actions.

## Fase 1 — Zorgdata: DigiMV-adapter (eerste echte data)

**Doel:** de volledige zorgsector in de database, boekjaren 2018–2024.

- [ ] Datasets Zorg/Jeugd per boekjaar downloaden (.ods, jaarverantwoordingzorg.nl) en ruw
      opslaan in Supabase Storage (principe: bron bewaren vóór verwerking)
- [ ] Kolominspectie en veldmapping documenteren in `pipeline/adapters/digimv.md`
      (welke velden over accountant/verklaring/honoraria zitten erin, per jaargang)
- [ ] Adapter `pipeline/adapters/digimv.py`: organisaties (KvK-nummer!), boekjaren,
      financials, honoraria (gesplitst controle/overig waar mogelijk) → kernmodel, idempotent
- [ ] Waar kantoornaam ontbreekt: accountantsverklaring-pdf's uit het DigiMV-archief +
      Claude API-extractie → `{kantoornaam, oordeel, boekjaar, datum_verklaring,
      continuiteitsonzekerheid}`; onzekere gevallen naar `review_queue`
- [ ] Naamnormalisatie tegen `kantoor_alias`; nieuwe aliassen via review, nooit stil mergen
- [ ] Steekproefcontrole: 25 organisaties handmatig naleggen tegen de bron-pdf's

**Klaar wanneer:** duizenden opdrachten in de database, herkomst per feit, en de import is
met één actie opnieuw te draaien zonder duplicaten.

## Fase 2 — Frontend op echte data

**Doel:** de vier MVP-pagina's uit `docs/concept.md` §7, server-side gerenderd, met het
goedgekeurde kantoorprofiel-mockup als referentie.

- [ ] Home/zoek: één zoekbalk (organisatie én kantoor), teasers "recente wisselingen" en
      "grootste kantoren in de zorg"
- [ ] Kantoorprofiel `/kantoor/[slug]`: metric cards (aantal controles, gem. relatieduur,
      netto cliëntgroei, mediaan honorarium), cliëntentabel, sectorverdeling, signalen-paneel
- [ ] Organisatieprofiel `/organisatie/[kvk]`: huidige accountant, historie per boekjaar,
      vorige accountant, actieve signalen, bronvermelding per feit
- [ ] Wisselingen `/wisselingen`: chronologisch, filterbaar op sector/jaar/kantoor
- [ ] Overal: geen doodlopende pagina's (elke naam klikbaar 🆕), nette lege-staten,
      bronlabel per feit, badge "Demo · gedeeltelijke data"

**Klaar wanneer:** je kunt van een willekeurige zorgorganisatie doorklikken naar haar
kantoor, naar een sectoroverzicht, naar een andere organisatie — zonder dood spoor.
**Demo-moment:** laten zien aan 3–5 mensen uit de doelgroep, reacties noteren.

## Fase 3 — Signalen v1

**Doel:** de leads-laag: signalen zichtbaar op profielen en op de wisselingenpagina.

- [ ] Signaal a: relatieduur ≥ 10 jaar (uit `v_relatieduur`)
- [ ] Signaal b: oordeel anders dan goedkeurend, of continuïteitsonzekerheid 🆕
- [ ] Signaal c: kantoor verdwenen uit AFM-register → signaal op álle actieve cliënten
      ("portefeuille moet verkassen"); AFM-snapshot draait wekelijks 🆕
- [ ] Signaal d: TenderNed-adapter — aanbestedingen accountantsdiensten (CPV-codes rond
      79210000, exacte codes uitzoeken en vastleggen), koppelen op KvK/organisatienaam
- [ ] Signaalbeheer: status actief/afgehandeld; wisseling gedetecteerd → signaal sluiten
- [ ] Nieuwsbrief-opt-in op de site (simpel formulier, lijst in Supabase); eerste handmatige
      editie "wisselingen & signalen deze maand" 🆕

**Klaar wanneer:** minimaal drie signaaltypen live met echte gevallen, en de eerste
nieuwsbrief is verstuurd aan de eerste inschrijvers.

## Fase 4 — Verbreden: onderwijs, OOB's en de rotatiekalender

**Doel:** tweede en derde vertical + het voorspellende signaal.

- [ ] DUO-adapter: financiële gegevens + accountantshonoraria per onderwijsbestuur;
      kantoornaam uit openbare jaarverslagen via Claude-extractie (zelfde patroon als Fase 1)
- [ ] Transparantieverslag-adapter: OOB-cliëntlijsten uit de ±6–10 verslagen per jaar
      (EU-Vo. 537/2014 art. 13); eerste benoemingsjaar per cliënt meenemen waar vindbaar
- [ ] Signaal e 🆕: `verplichte_roulatie` — OOB's die de 10-jaarstermijn naderen, met
      verwacht wisseljaar; sectie "Rotatiekalender" op de wisselingenpagina
- [ ] Signaal f 🆕: `kantoor_overgenomen` — fusies/overnames uit AFM-mutaties en nieuws,
      handmatig bijgehouden in de aliastabel-workflow

**Klaar wanneer:** drie sectoren doorzoekbaar (zorg, onderwijs, OOB), rotatiekalender toont
komende verplichte wisselingen met bronvermelding.

## Fase 5 — Validatie & eerste omzet 🆕

**Doel:** bewijs dat iemand hiervoor betaalt, vóórdat er geld naar KvK-data gaat.

- [ ] 10 gesprekken met doelgebruikers (BD accountantskantoren, 1–2 PE-partijen, 1–2
      CFO's/controllers, 1 journalist); gespreksnotities in `docs/validatie/`
- [ ] Eén betaalde pilot proberen (bijv. signaal-alerts voor één kantoor, of één
      PE-due-diligence-rapport over een kantoorportefeuille)
- [ ] Prijshypothese opschrijven (abonnement per kantoor / rapport per stuk / alerts)
- [ ] **Beslismoment KvK-inkoop** (beslissing #4): pas kopen als een klant er aantoonbaar
      op wacht; start "data on demand" (alleen kopen wat een klant vraagt)

**Klaar wanneer:** er is óf een eerste betalende klant/pilot, óf een onderbouwd besluit wat
er aan het product moet veranderen voordat iemand betaalt.

---

## Backlog (niet nu, wel schema-proof)

Volgorde is indicatief; oppakken ná Fase 5 op basis van wat validatie leert.

1. **Records & ranglijsten** 🆕 — marktaandelen per sector, netto cliëntenstroom per kantoor
   ("wisselmarkt boekjaar X"), langste relaties; goedkoop, hoge pers-waarde
2. KvK XBRL-parser (SBR Assurance-verklaringen middelgroot) + pdf-batch voor gekochte
   KvK-jaarrekeningen ("data on demand")
3. Honoraria-benchmark als product (fee per sector/grootteklasse)
4. Verticals: woningcorporaties, gemeenten/provincies/waterschappen, pensioenfondsen,
   CBF-goede doelen
5. Supabase Auth + geclaimde kantoorprofielen (incl. geverifieerde badge "neemt cliënten
   aan"; datagedreven indicator "groeit in sector X" kan eerder 🆕)
6. Uitvraagplaatsingen ("wij zoeken een accountant voor boekjaar X") — sterker dan gedacht
   door de marktkrapte, zie brainstorm §5
7. Wekelijkse wisselingen-nieuwsbrief automatiseren (handmatige versie start al in Fase 3)
8. AQI-import zodra de NBA publiceert (boekjaren vanaf 2027, verwacht beschikbaar 2028)
9. CSRD-assurance als extra kolom (boekjaar 2027+, alleen grote ondernemingen)
10. Stroomdiagram van→naar per boekjaar op de wisselingenpagina

## Definition of done (MVP = na Fase 4)

Website live op een domein, gevuld met de volledige zorgsector (meerdere boekjaren),
doorzoekbaar op organisatie én kantoor, met werkende kantoor- en organisatieprofielen,
minimaal drie typen wisselsignalen, bronvermelding per feit, en een pipeline die met één
commando/actie opnieuw draait.

## Beslismomenten

| Wanneer | Beslissing | Zie |
|---------|-----------|-----|
| Nu | Naam & domein (WhoSigns vs. Auditkaart) | beslissing #1 |
| Vóór Fase 0 afronding | Supabase-regio | beslissing #3 |
| Eind Fase 2 | Publiek lanceren of besloten demo | beslissing #2 |
| Fase 5 | Eerste KvK-inkoop | beslissing #4 |
