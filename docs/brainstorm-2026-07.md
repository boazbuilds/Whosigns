# Brainstorm: van "database met auditrelaties" naar "de Transfermarkt van de auditmarkt"

*Juli 2026 — analyse en verbetervoorstellen op `docs/concept.md`. Voorstellen die de
opdrachtgever overneemt, landen in `ROADMAP.md` en `docs/beslissingen.md`.*

Het concept is sterk: het kernobject (de opdracht, niet de organisatie) klopt, de bronvolgorde
(gratis semipubliek eerst) klopt, en de drie architectuurprincipes zijn precies de dingen die
dit soort dataprojecten anders na een jaar de das omdoen. Dit document gaat over de vraag:
wat maakt Transfermarkt zo goed, en wat betekent dat concreet voor WhoSigns?

---

## 1. Waarom Transfermarkt werkt — en de vertaling per mechanisme

Transfermarkt is geen "database met voetballers". Het is een web van vijf mechanismen die
elkaar versterken. Elk mechanisme heeft een directe audit-equivalent:

| Transfermarkt | Mechanisme | WhoSigns-equivalent |
|---|---|---|
| Alles is gratis bladerbaar | Traffic & SEO zijn het acquisitiekanaal; betalen doe je voor diepte/alerts | Duizenden organisatie- en kantoorpagina's die ranken op "*[organisatienaam]* accountant". Elke pagina is een landingspagina. |
| Speler ↔ club ↔ competitie ↔ makelaar: nooit een doodlopende pagina | Elke entiteit linkt naar elke andere entiteit | Organisatie ↔ kantoor ↔ sector ↔ boekjaar ↔ wisseling. Elke tabelcel klikbaar. |
| **Contract tot 2027** | Einddatums maken de toekomst bladerbaar | **Verplichte kantoorroulatie (OOB, max 10 jaar) en aanbestedingskalenders maken wisselingen voorspelbaar op jaartal** — zie §2, dit is de grootste vondst. |
| Transfervensters, recordtransfers, ranglijstjes | Records genereren pers en terugkerend bezoek | "Wisselmarkt boekjaar 2025": van→naar-stromen per kantoor, langste relatie van NL, grootste wissel van het jaar, snelste groeier per sector. |
| Marktwaarde per speler | Eén getal dat iedereen wil weten | Honorarium als "marktwaarde" van een opdracht; benchmark per sector/grootteklasse (zorg, onderwijs en groot hebben publieke fees). |
| Geruchtenmolen | Signalen vóór het feit | Wisselsignalen (zit al in het concept: aanbestedingen, lange relatie, niet-goedkeurend oordeel, vergunning beëindigd). |

**Conclusie:** het concept dekt de onderste twee rijen al goed. De winst zit in de middelste
drie: voorspelbaarheid (§2), records/ranglijsten (§4) en het doorklik-web als harde UI-eis.

## 2. Grootste verbetervoorstel: de rotatiekalender (wisselingen vóórspellen in plaats van signaleren)

Het concept behandelt wisselsignalen als indicaties achteraf of terzijde. Maar een deel van de
markt heeft wisselingen die **wettelijk vaststaan**:

- **OOB's moeten rouleren.** EU-verordening 537/2014 begrenst de benoemingsduur; Nederland
  hanteert de strikte termijn van maximaal 10 jaar zonder verlengingsoptie. Wie de
  transparantieverslagen parst (Fase 4) en per OOB-cliënt het eerste benoemingsjaar kent, kan
  per beursfonds/bank/verzekeraar uitrekenen: *"moet uiterlijk boekjaar X wisselen"*. Dat is
  het audit-equivalent van "contract loopt af in 2027" — deterministisch, uit openbare data,
  en precies de lead waarvoor BD-teams betalen.
- **(Semi)publieke sector tendert periodiek.** Gemeenten, corporaties en zorginstellingen
  boven de drempel moeten Europees aanbesteden; contracten lopen typisch 4–8 jaar
  (basis + verlengingen). TenderNed (Fase 3) geeft de aankondiging; de historie geeft het ritme.

**Voorstel:** nieuw signaaltype `verplichte_roulatie` met een verwacht boekjaar, gevoed vanuit
de transparantieverslag-adapter. Plus een pagina/sectie **"Rotatiekalender"**: welke controles
komen de komende 1–3 jaar verplicht vrij. Kosten: klein (afgeleide van data die Fase 4 toch al
binnenhaalt). Waarde: dit kan op zichzelf al een betaald product zijn.

## 3. Tweede vondst: kantoorconsolidatie als signaalbron én als klantsegment

Er loopt een consolidatiegolf door de Nederlandse accountancy: private-equity-partijen kopen
kantoren op en voegen ze samen. Dat raakt WhoSigns twee keer:

1. **Als signaal.** Na een overname of fusie heroverwegen cliënten hun relatie
   (cultuur, tarieven, vaste contactpersonen, onafhankelijkheidsconflicten bij
   portefeuille-overlap). Nieuw signaaltype `kantoor_overgenomen`. De aliastabel moet fusies
   toch al bijhouden — dit is dezelfde data, nu ook als lead ontsloten. Zelfde geldt voor
   kantoren die hun Wta-vergunning inleveren (signaal bestaat al in het concept): dan moet de
   **hele portefeuille** tegelijk verkassen. Dat is de beste leadlijst die er bestaat, en een
   gegarandeerd persbericht.
2. **Als klant.** PE-partijen die kantoren kopen hebben due-diligence-vragen die exact onze
   data zijn: hoeveel wettelijke controles heeft dit kantoor, in welke sectoren, hoe loyaal is
   de portefeuille (relatieduur!), groeit of krimpt hij, wat is het honorariumniveau. Eén
   PE-rapport kan meer opleveren dan maanden abonnementsomzet. Doelgroep "private equity" uit
   het concept wordt hiermee concreet: niet alleen PE die een accountant zoekt voor
   portfoliobedrijven, maar vooral **PE die accountantskantoren koopt**.

**Voorstel:** AFM-register niet maandelijks maar **wekelijks** snapshotten (GitHub Action is
gratis; mutaties zijn het vroegste harde signaal dat er bestaat), en `kantoor_overgenomen`
als signaaltype opnemen in het schema (gedaan).

## 4. Records, ranglijsten en de jaarlijkse "wisselmarkt" (goedkoop, veel pers)

Transfermarkt wordt geciteerd omdat journalisten er lijstjes uit kunnen halen. Onze
equivalenten zijn triviale queries zodra de data er is:

- Marktaandeel-ranglijst per sector per boekjaar ("de eredivisie van de zorgaudit").
- Netto cliëntenstroom per kantoor per boekjaar: wie won, wie verloor, van/aan wie
  (op termijn als stroomdiagram van→naar).
- Records: langste auditrelatie van Nederland, meeste wisselingen in één jaar, grootste
  honorariumstijging.
- Jaarlijks vast moment: "Wisselmarkt boekjaar X" — overzichtsartikel/pagina zodra een
  boekjaar redelijk compleet gedeponeerd is.

**Voorstel:** backlog-item "records & ranglijsten" toevoegen met hoge prioriteit ná MVP.
Geen extra data nodig, puur presentatie — en het is gratis marketing richting de doelgroep
journalisten (die vervolgens onze naam bij BD-teams op het netvlies zetten).

## 5. De marktkrapte omdraaien: "neemt cliënten aan" is premium-informatie

Het concept noemt de badge "neemt cliënten aan" als latere self-reported feature. Belangrijke
context: de Nederlandse auditmarkt is **aanbodgedreven** — er is een tekort aan
accountants(capaciteit), organisaties in het (semi)publieke domein kunnen soms nauwelijks een
controlerend accountant vinden. Dat verandert de waarde van het platform:

- Voor CFO's/controllers is "welk kantoor heeft überhaupt ruimte in mijn sector" misschien
  wel de #1 vraag. Niemand publiceert dit.
- Wij kunnen het benaderen uit data: een kantoor dat in sector X netto groeit, neemt daar
  kennelijk cliënten aan. Een afgeleide indicator ("groeit in de zorg"), later te vervangen
  door geverifieerde self-reporting bij geclaimde profielen.
- De langetermijnvisie "organisaties plaatsen uitvragen" wordt hierdoor sterker dan het
  concept suggereert: in een krappe markt is de uitvraagzijde de vraagzijde, en kantoren
  *willen* die leads zien. Blijft ná MVP, maar verdient een hogere plek op de backlog.

## 6. Kleinere aanscherpingen (doorgevoerd in schema/roadmap, terug te draaien)

1. **Honorarium gesplitst** in `honorarium_controle_eur` en `honorarium_overig_eur` in plaats
   van één bedrag. Art. 2:382a BW splitst honoraria in categorieën (controle / andere
   controleopdrachten / fiscaal / overig), en DigiMV en DUO leveren de splitsing vaak mee.
   Nu twee kolommen kost niets; achteraf splitsen is niet te doen. De fee-benchmark wordt er
   ook eerlijker van (alleen controle-fees vergelijken).
2. **`continuiteitsonzekerheid` als kolom op `opdrachten`.** De AI-extractie levert dit veld
   al (staat in het concept, §6); het hoort bij de verklaring en is zowel een wisselsignaal
   als een journalistiek haakje. Zonder kolom gooien we het weg.
3. **Signalen kregen `status` (actief/afgehandeld) en een unieke sleutel** zodat de pipeline
   idempotent kan draaien en signalen kunnen worden afgesloten zodra de wisseling een feit is.
4. **`review_queue`-tabel** vanaf dag één (het concept noemt de review-queue op twee plekken
   maar had er nog geen tabel voor): onzekere AI-extracties en fuzzy naam-matches wachten daar
   op menselijke bevestiging. Nooit stil mergen — dat principe heeft een plek nodig.
5. **Nieuwsbrief naar voren.** "Wekelijkse wisselingen-nieuwsbrief" stond in de backlog, maar
   een mailinglijst is het goedkoopste validatie- en distributiekanaal dat er is. Voorstel:
   simpele opt-in vanaf Fase 3 (zodra er signalen zijn), handmatig verstuurd is prima. De
   lijst is later de springplank naar het betaalde alert-product.
6. **Expliciete validatiefase (Fase 5).** Het concept zegt "KvK-inkoop pas na eerste
   klantvalidatie" maar had validatie nergens als stap. Nu wel: na Fase 2 demo's aan 5–10
   doelgebruikers, na Fase 4 een betaalde pilot proberen. Meetlat vóór we geld uitgeven.

## 7. Naam: WhoSigns

De repo heet al WhoSigns en dat is een betere naam dan de werktitel "Auditkaart":

- Het is letterlijk de vraag die het product beantwoordt ("wie tekent bij …?").
- Werkt internationaal als het concept ooit de grens over gaat (elke EU-lidstaat heeft
  dezelfde openbaarmakingsplichten uit dezelfde EU-verordening).
- Eén nuance bewaken: door de AVG-guardrail beantwoorden we de vraag op **kantoorniveau**
  (welke accountantsorganisatie tekent), nooit op persoonsniveau. Dat moet ook in de
  merkcommunicatie helder zijn — "who signs" gaat bij ons over het kantoor.

Definitieve keuze (incl. domeincheck) ligt bij de opdrachtgever → `docs/beslissingen.md`.

## 8. Risico's eerlijk benoemd (en wat we eraan doen)

| Risico | Ernst | Mitigatie |
|---|---|---|
| **Kip-ei / dekking:** site met gaten oogt onbetrouwbaar | Hoog | Verticale volledigheid vóór breedte: lanceer pas als de zorgsector compleet is ("álle zorg, meerdere jaren" is een claim; "wat losse bedrijven" niet). Badge "Demo · gedeeltelijke data" staat al in het concept. |
| **Nieuwsritme:** jaarrekeningen zijn een jaarcyclus, site kan doods aanvoelen | Middel | Signalen geven weekritme: TenderNed, AFM-mutaties (wekelijkse snapshot), overnames. Nieuwsbrief bundelt het. |
| **Kopieerbaarheid:** Company.info/Bureau van Dijk-achtigen kunnen dit toevoegen | Middel | Moat = historie-diepte (jaren opbouwen kost jaren), signalenlaag, en later geclaimde profielen/uitvragen (netwerkeffect). Snelheid telt. |
| **Juridisch:** herpubliceren van gegevens | Laag-middel | Feiten (wie controleert wie) zijn niet auteursrechtelijk beschermd; we herpubliceren geen volledige documenten; KvK-leveringsvoorwaarden checken vóór de KvK-fase; AVG-guardrail (geen natuurlijke personen) staat hard in schema en prompts. |
| **DigiMV-veldkwaliteit:** kantoornaam mogelijk vrije tekst of afwezig in sommige jaren | Middel | Fase 1 begint met kolominspectie (staat in concept); vrije tekst vangen we met de aliastabel + review-queue; ontbrekend → pdf-extractie uit het archief. |
| **AI-extractiefouten** komen ongemerkt in productie | Middel | Confidence-drempel + review_queue (nu ook echt in het schema); steekproef per batch handmatig checken in Fase 1. |

## 9. Wat ik bewust níét voorstel

- Geen tweede vertical vóór de zorg compleet is (breedte verleidt, diepte overtuigt).
- Geen scraping van betaalde/afgeschermde bronnen of de-anonimisering (guardrails).
- Geen reviews/ratings in het MVP — het Chambers-model (geverifieerde tevredenheid) blijft
  langetermijn; open reviews zouden het merk "objectiviteit" direct beschadigen.
- Geen extra tooling: het concept zegt terecht "één persoon + Claude Code moet dit kunnen
  onderhouden". Alles hierboven past binnen Supabase + Next.js + Python + GitHub Actions.

## 10. Samengevat: wat er door deze brainstorm verandert

1. Nieuw signaaltype **verplichte roulatie** + rotatiekalender (Fase 4, afgeleide van data
   die we toch al ophalen) — van signaleren naar voorspellen.
2. Nieuw signaaltype **kantoor overgenomen**; AFM-register wekelijks in plaats van
   maandelijks snapshotten (Fase 3).
3. **PE-due-diligence op kantoren** expliciet als klantsegment en later als productvorm
   (rapport per kantoor).
4. Schema: honorarium gesplitst, continuïteitsonzekerheid, signaalstatus, review-queue.
5. **Nieuwsbrief** vanaf Fase 3 (was backlog); **records/ranglijsten** hoog op de backlog.
6. **Fase 5 "Validatie & eerste omzet"** toegevoegd met meetbare beslismomenten.
7. Naamadvies: **WhoSigns** (beslissing bij opdrachtgever).

## 11. Veelgestelde vraag: "Graydon/Creditsafe heeft toch al alles over bedrijven?"

Terechte vraag (juli 2026, gesteld door de opdrachtgever). Kredietinformatiebureaus —
Creditsafe (dat Graydon overnam), Altares Dun & Bradstreet, Company.info — hebben
inderdaad enorm veel bedrijfsdata: jaarrekeningen uit KvK-deponeringen, kredietscores,
betaalgedrag, bestuurders, concernstructuren. Maar hun **kernobject is het bedrijf**;
het onze is de **auditrelatie**. Dat verschil zit diep:

1. **De accountant is bij hen geen veld, maar een voetnoot.** De kantoornaam staat in
   de gedeponeerde pdf die zij doorverkopen, maar is niet als doorzoekbaar,
   historisch gegeven ontsloten. Vragen die bij ons de kern zijn, kun je daar niet
   stellen: *geef alle cliënten van BDO in de zorg · wie wisselde er in 2024 van
   accountant · hoe lang zit EY al bij organisatie X · welk marktaandeel heeft
   kantoor Y bij corporaties · wie nadert de verplichte OOB-roulatie.*
2. **Een kantoor is bij hen geen entiteit.** Er bestaat geen "profiel van
   accountantskantoor X met portefeuille, sectorspreiding en verloop". Bij ons is dat
   de helft van het product.
3. **Ander verdienmodel, andere ervaring.** Zij verkopen rapporten per bedrijf achter
   een betaalmuur; wij zijn vrij bladerbaar over de héle markt (Transfermarkt-model)
   en verdienen aan werk-tools bovenop de graaf.
4. **Onze MVP-bronnen zitten niet in hun pijplijn.** DigiMV (zorg), DUO (onderwijs) en
   OOB-transparantieverslagen zijn geen KvK-deponeringen; juist in het (semi)publieke
   domein — waar wij beginnen — hebben zij weinig.
5. **Eerlijk is eerlijk:** met hun documentenarchief zóúden ze dit kunnen bouwen. De
   verdediging is snelheid, historie-diepte (die koop je niet in, die bouw je op),
   nichefocus en later de tweezijdige laag (geclaimde profielen, uitvragen). En:
   zo'n partij is eerder een potentiële afnemer of overnemer van onze dataset dan een
   directe concurrent — wat de exit-waarde van de historie alleen maar onderstreept.
