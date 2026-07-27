# WhoSigns — Conceptdocument (volledige context)

> Aangeleverd door de opdrachtgever, juli 2026. Dit document vat een uitgebreide verkenning
> samen en is de volledige context voor de bouw. Werk fase voor fase (zie `ROADMAP.md`),
> vraag bij onduidelijkheid door, en houd je aan de guardrails onderaan. De opdrachtgever is
> assistant manager in de audit, geen developer: leg keuzes kort uit in gewone taal en houd
> alles zo simpel en goedkoop mogelijk.
>
> Aanvullingen en verbetervoorstellen uit de brainstorm staan in `docs/brainstorm-2026-07.md`.
> Openstaande keuzes staan in `docs/beslissingen.md`.

## 1. Wat we bouwen

Een **audit-market-intelligence-platform voor Nederland**: een database plus website die
zichtbaar maakt welke accountantsorganisatie welke organisatie controleert, hoe dat zich over
de jaren ontwikkelt, en waar wisselingen (gaan) plaatsvinden. Denk: "de PitchBook / Chambers
van de Nederlandse auditmarkt" — met de bladerbaarheid van transfermarkt.nl.

- **Kernobject is de opdracht (assurance-engagement), niet de organisatie.**
  Organisatiegegevens zijn overal te koop; de auditrelatie is de zeldzame data.
- **Doelgroepen (betalend):** business development bij accountantskantoren, private equity,
  CFO's/controllers die een accountant zoeken, recruiters, journalisten/onderzoekers.
- **Killer feature: wisselsignalen** — voorspellen/signaleren welke organisaties (binnenkort)
  van accountant wisselen. De database is het middel; leads en alerts zijn het product.
- **Langetermijnvisie (niet in MVP):** tweezijdig platform — kantoren claimen hun profiel en
  vullen aan (in ruil voor benchmarks), organisaties plaatsen uitvragen ("wij zoeken een
  accountant voor boekjaar X"), geverifieerde opdrachtgeverstevredenheid
  (Chambers/Legal500-model, géén open Trustpilot-reviews).

## 2. Domeinkennis (belangrijk, gevalideerd via onderzoek in juli 2026)

- **Controleplicht (NL):** 2 van 3 criteria, 2 jaar op rij: netto-omzet > €15 mln,
  balanstotaal > €7,5 mln, ≥ 50 werknemers. Grofweg is dit de doelpopulatie
  (orde van grootte: ~20.000 wettelijke controles/jaar).
- **KVK Open Dataset Jaarrekeningen is GEANONIMISEERD** (geen bedrijfsnaam, geen KvK-nummer).
  Alleen bruikbaar voor marktstatistiek, NIET voor data op naam. Niet proberen te
  de-anonimiseren (juridisch/AVG).
- **Data op naam** komt uit: (a) individuele KVK-deponeringen (±€3,65 per jaarrekening;
  bulklevering in pdf/XBRL mogelijk op offerte), en (b) gratis openbare bronnen in de
  (semi)publieke sector — daar begint het MVP.
- **XBRL-verplichting deponeren:** micro/klein sinds boekjaar 2016; middelgroot sinds
  boekjaar 2017 (inclusief digitale controleverklaring met elektronische handtekening van de
  accountant — SBR Assurance: kantoornaam is gestructureerd extraheerbaar); groot verplicht
  digitaal vanaf boekjaar 2025 (SBR Instance of SBR Report Package/iXBRL). De pipeline wordt
  dus elk jaar makkelijker.
- **Honoraria:** grote rechtspersonen moeten accountantshonoraria toelichten in de
  jaarrekening (art. 2:382a BW). Onderwijs (DUO) en zorg publiceren honoraria in open data.
  Basis voor een fee-benchmark.
- **Deponeringstermijn:** max. 12 maanden na boekjaareinde — data druppelt het hele jaar
  binnen; imports moeten herhaalbaar/idempotent zijn.
- **AQI's (toekomstige bron):** vanaf boekjaren startend 1-1-2027 rapporteren OOB-kantoren
  wettelijke kwaliteitsindicatoren aan de NBA, die ze openbaar maakt (o.a. tekortkomingen,
  teamverloop, budgetoverschrijdingen, opdrachtgeverstevredenheid).
- **CSRD:** door Omnibus I (definitief, in werking maart 2026) alleen nog >1.000 werknemers
  én >€450 mln omzet vanaf boekjaar 2027, alleen limited assurance. Kleine extra kolom,
  geen pijler.
- **Niet publiek beschikbaar (buiten scope):** ISAE 3402/SOC-rapporten, vrijwillige controles
  bij kleine rechtspersonen, de meeste subsidiecontroles, COS 4400-rapporten.

## 3. Databronnen (prioriteitsvolgorde)

| # | Bron | Inhoud | Kosten | MVP? |
|---|------|--------|--------|------|
| 1 | **Jaarverantwoording Zorg / DigiMV** — jaarverantwoordingzorg.nl (datasets per boekjaar, .ods, vanaf 2018) + archief per organisatie (digimv8.desan.nl/archive) met jaarrekeningen en accountantsverklaringen (pdf). Incl. KvK-nummers. | Wie controleert de zorg + financials + WNT | Gratis | ✅ Fase 1 |
| 2 | **OOB-transparantieverslagen** — websites van de ±6–10 OOB-vergunninghouders; jaarlijks, met lijst OOB-controlecliënten (EU-Vo. 537/2014 art. 13) | Alle beursfondsen, banken, verzekeraars | Gratis | ✅ Fase 4 |
| 3 | **AFM-vergunningenregister accountantsorganisaties** — afm.nl → registers → accountantsorganisaties | Referentietabel kantoren (regulier/OOB), mutaties = wisselsignaal | Gratis | ✅ Fase 0 (seed) |
| 4 | **DUO Open Onderwijsdata** — duo.nl/open_onderwijsdata (financiële gegevens per bestuur, incl. accountantshonoraria); kantoornaam uit openbare jaarverslagen van besturen | Onderwijssector | Gratis | ✅ Fase 4 |
| 5 | **TenderNed** — aanbestedingen accountantsdiensten (CPV-codes rond 79210000; exacte codes opzoeken) | Aangekondigde wisselingen (semi)publiek | Gratis | ✅ Fase 3 |
| 6 | **Woningcorporaties** (Aw/jaarverslagen), **gemeenten/provincies/waterschappen** (jaarstukken), **pensioenfondsen** (DNB-register + jaarverslagen), **CBF-erkende goede doelen** | Semipublieke verticals | Gratis | Backlog |
| 7 | **KVK-deponeringen** — kvk.nl (per stuk of bulk-offerte; XBRL parsen voor middelgroot, pdf + AI-extractie voor ouder/groot) | Commerciële mid-market op naam | ±€4/stuk | Backlog (pas na eerste omzet, "data on demand") |
| 8 | **KVK Open Dataset Jaarrekeningen** (geanonimiseerd) | Alleen benchmarks/marktstatistiek | Gratis | Backlog |

## 4. Architectuur: drie principes (niet onderhandelbaar)

1. **Bewaar altijd de ruwe bron.** Elke import slaat het originele bestand
   (ods/xml/xbrl/pdf/html) op in Supabase Storage vóór verwerking.
   Modelwijziging = alles herverwerken, nooit opnieuw downloaden.
2. **Eén kernmodel, bronnen via adapters.** Elke bron heeft een eigen importscript
   (`adapters/digimv.py`, `adapters/duo.py`, …) dat naar hetzelfde kernmodel schrijft.
   Nieuwe bron = nieuw script, nooit een schemaverbouwing.
3. **Herkomst per feit.** Elk gegeven verwijst naar een bron met type, URL en ophaaldatum,
   en het label `publiek` of `zelf_aangeleverd`. Dit label wordt later ook in de UI getoond —
   objectiviteit is het merk.

**Entity resolution:** KvK-nummer als sleutel voor organisaties; AFM-vergunningnummer voor
kantoren; aliastabel voor kantoornamen (fusies, handelsnamen, spelvarianten).
Naamnormalisatie: eerst exact op alias, dan fuzzy match met menselijke bevestiging
(review-queue), nooit stil automatisch mergen.

## 5. Datamodel (Supabase / Postgres, migrations in repo)

Zie `supabase/migrations/` voor de actuele, uitvoerbare versie. Conceptueel:

```sql
organisaties   (id, kvk_nummer text unique, naam, rechtsvorm, sector, sbi_code,
                grootteklasse, gemeente, created_at)
kantoren       (id, afm_nummer text unique, naam, oob_vergunning bool,
                actief bool, website)
kantoor_alias  (alias text, kantoor_id fk)
opdrachten     (id, organisatie_id fk, kantoor_id fk, boekjaar int,
                type_opdracht text default 'wettelijke_controle',
                standaard text null,           -- bijv. 'NV COS 700'
                oordeel text null,             -- goedkeurend | beperking |
                                               -- oordeelonthouding | afkeurend
                honorarium_eur numeric null,
                bron_id fk,
                unique (organisatie_id, boekjaar, type_opdracht))
bronnen        (id, bron_type text,            -- digimv | duo | kvk_xbrl | kvk_pdf |
                                               -- transparantieverslag | tenderned |
                                               -- zelf_aangeleverd
                url, opgehaald_op timestamptz,
                betrouwbaarheid text)          -- publiek | zelf_aangeleverd
bronbestanden  (id, bron_id fk, storage_pad, bestandstype, sha256)
signalen       (id, organisatie_id fk, type_signaal text,
                -- aanbesteding | lange_relatie | niet_goedkeurend_oordeel |
                -- kantoor_vergunning_beeindigd
                omschrijving, datum, bron_id fk)
```

**Afgeleiden (views, niet opslaan):** relatieduur (opeenvolgende boekjaren zelfde kantoor),
wisseling (ander kantoor_id in boekjaar n+1), marktaandelen per sector/regio.

## 6. Techstack

- **Database/backend:** Supabase (managed Postgres, EU-regio), incl. Auth (later voor
  geclaimde profielen), Storage (bronbestanden), Row Level Security.
- **Website:** Next.js (App Router) op Vercel. UI-taal: Nederlands.
- **Pipeline:** Python-scripts in dezelfde repo (`/pipeline`), gedraaid via GitHub Actions
  op schema (maandelijks + handmatig triggerbaar). Idempotent (upserts op unieke sleutels).
- **AI-extractie:** Claude API voor pdf-controleverklaringen → gestructureerde JSON:
  `{kantoornaam, oordeel, boekjaar, datum_verklaring, continuiteitsonzekerheid: bool}`.
  Batch, met retry en logging van onzekere extracties naar een review-tabel.
- **Interne analyse:** directe Postgres-koppeling voor Power BI (opdrachtgever kent Power BI).
- **Kosten:** free tiers waar mogelijk; doel < €50/maand tot eerste betalende klant.

## 7. UI-specificatie (MVP-pagina's)

Stijl: clean, flat, licht, veel witruimte; badge **"Demo · gedeeltelijke data"** zolang
dekking beperkt is. Er bestaat al een goedgekeurd mockup van het kantoorprofiel; bouw dat na.

- **Home/zoek:** één zoekbalk (organisatie of kantoor), daaronder teasers:
  "recente wisselingen", "grootste kantoren in de zorg".
- **Kantoorprofiel** (`/kantoor/[slug]`): header (naam, vergunningstype, badge "neemt
  cliënten aan" — later self-reported); vier metric cards: aantal wettelijke controles,
  gemiddelde relatieduur, netto cliëntgroei laatste jaar, mediaan honorarium; cliëntentabel
  (organisatie, sector, oordeel laatste boekjaar, cliënt sinds); sectorverdeling als
  horizontale balkjes; paneel "wisselsignalen".
- **Organisatieprofiel** (`/organisatie/[kvk]`): huidige accountant, historie per boekjaar
  (kantoor + oordeel + honorarium), sinds wanneer, vorige accountant, actieve signalen,
  bronvermelding per feit.
- **Wisselingen** (`/wisselingen`): chronologische lijst van gedetecteerde wisselingen en
  signalen, filterbaar op sector/jaar/kantoor.

## 8. Bouwplan

Zie `ROADMAP.md` — dat is de actuele versie van het bouwplan, inclusief aanvullingen uit de
brainstorm. Oorspronkelijke volgorde: Fase 0 fundament → Fase 1 DigiMV-adapter → Fase 2
frontend op echte data → Fase 3 signalen v1 → Fase 4 verbreden (DUO + transparantieverslagen)
→ backlog.

## 9. Guardrails

- **Alleen openbare data in v1**; label `publiek` vs. `zelf_aangeleverd` overal verplicht.
- **AVG:** sla uitsluitend het kantóór op, nooit namen van tekenend accountants of andere
  natuurlijke personen. Ook niet in ruwe extractie-output bewaren.
- **KVK:** geëxtraheerde feiten gebruiken, maar geen volledige gedeponeerde documenten
  publiek herpubliceren; geen de-anonimisering van open datasets; leveringsvoorwaarden
  checken vóór livegang van KvK-gebaseerde data.
- **Datakwaliteit:** imports idempotent; onzekere AI-extracties (< hoge confidence) naar een
  review-queue, niet stil in productie; nooit fictieve/demo-data mengen met echte data
  (aparte seed-set met duidelijke vlag).
- **Eenvoud:** geen microservices, geen Kubernetes, geen extra SaaS-abonnementen zonder
  noodzaak. Alles moet door één persoon met Claude Code te onderhouden zijn.

## 10. Definition of done (MVP)

Website live op een domein, gevuld met de volledige zorgsector (meerdere boekjaren),
doorzoekbaar op organisatie én kantoor, met werkende kantoor- en organisatieprofielen,
minimaal drie typen wisselsignalen, bronvermelding per feit, en een pipeline die met één
commando/actie opnieuw draait.

## 11. Open keuzes (aan de opdrachtgever voorleggen)

Bijgehouden in `docs/beslissingen.md`: definitieve naam en domein (werktitel "Auditkaart",
repo heet "WhoSigns"); wel/geen publieke toegang bij lancering of eerst besloten demo;
Supabase-regio (EU/Frankfurt aanbevolen); moment van eerste KvK-inkoop (advies: pas na
eerste klantvalidatie).
