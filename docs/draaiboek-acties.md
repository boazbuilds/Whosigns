# Draaiboek: welke knop wanneer

Voor wie op **Actions** staat en niet meer weet wat ook alweer waarvoor was.
Kort antwoord: druk **Alles verversen** en je bent klaar. De rest van dit
document is de uitleg en de uitzonderingen.

## De ene knop

**Alles verversen** draait alles in de goede volgorde met de juiste invoer:
eerst de migraties (database-schema bijwerken), daarna elke bron. Je hoeft
niets in te vullen. Alles is idempotent: wat er al staat wordt overgeslagen,
dus te vaak drukken kan geen kwaad — het kost alleen minuten.

Valt één bron om, dan draaien de volgende gewoon door. Alleen als de
migratiestap faalt stopt de rest, want laden op een achterlopend schema is
gevaarlijker dan even niets doen.

Wanneer drukken:

1. **Na elke merge** van een pull request met pipeline- of migratiewijzigingen.
2. Verder hooguit **maandelijks** — de bronnen veranderen langzaam.

## Wat kost het

Gemeten over de runs van 4/5-8-2026:

| onderdeel (zit in Alles verversen) | duur |
|---|---|
| Migraties draaien | < 1 min |
| Zorgoogst inladen | ± 2 min |
| Gunningen laden (TED) | ± 6 min |
| Raadsinformatie laden | ± 8 min |
| Stichtingendata laden (CBF) | ± 30 min* |
| Corporatiedata laden (dVi) | ± 26 min |
| Transparantiedata laden | ± 30 min |
| **samen** | **± 1,5 uur** |

\* na de eerste volledige lading; een nieuwe categorie of een leeg boekjaar
duurt langer.

| aparte knoppen (niet in Alles verversen) | duur | wanneer |
|---|---|---|
| Beursfondsdata laden | ± 3,5 uur | hooguit maandelijks |
| Zorgdata laden | uren per boekjaar | liever niet — zie hieronder |
| Zorgoogst inladen (los) | ± 2 min | als er een nieuw oogstbestand in `pipeline/oogst/` staat |
| Pipeline / Kantoorclienten / Stichtingenlus | minuten | draaien zichzelf of op verzoek |

Het maandbudget van GitHub Actions op een privérepo is **2.000 minuten (Free)**
of **3.000 (Pro)**; kijken kan op github.com → Settings → Billing → Actions.
Eén "Alles verversen" per maand plus de automatische checks past daar ruim in.
Wat er níét in past is "Zorgdata laden" voor de inhaalslag — vandaar:

## Geen OCR op een runner

Tekstherkenning is verreweg het duurste dat deze pipeline doet. Gemeten op
gescande zorgverklaringen (6-8-2026): tientallen seconden tot **ruim zes minuten
per document**, tegen milliseconden voor een pdf mét tekstlaag. Ongeveer een
vijfde van de verklaringen is een scan.

Daarom staat OCR op GitHub uit. Elke workflow die pdf's leest zet
`WHOSIGNS_OCR: "0"` en installeert geen tesseract meer; de schakelaar zit op één
plek in `extractie/verklaring.py`. Zonder OCR gedraagt elke lader zich als vóór
de OCR-terugval: een gescande pdf levert geen tekst en dus geen opdracht, netjes
gemeld als `onleesbaar` — nooit een gok.

Wat daarmee verschuift naar hier (buiten Actions):

| bron | wat er zonder OCR blijft liggen |
|---|---|
| zorg (DigiMV) | ±20% van de verklaringen is een scan |
| goede doelen (CBF) | 33 van de 262 in categorie A/B per jaargang, 11 in C, 9 in D/E |
| kantoorcliënten, beursfondsen | scans bij de kleinere organisaties |

Die worden geoogst via de route hieronder en komen als csv binnen. Wie lokaal
juist wél alles wil lezen doet niets: buiten Actions staat OCR gewoon aan.

## De zorg-inhaalslag: oogsten buiten Actions om

Het DigiMV-archief is met ±2.300 organisaties per boekjaar (2019–2025) de
grootste bron die er nog ligt, maar het lezen kost ±24 seconden per organisatie
— tientallen uren rekentijd, veel meer dan het maandbudget.

Daarom is dat werk in tweeën geknipt:

1. **Oogsten** (duur, gratis): `laad_zorg.py --droogloop --uit-archief` draait
   buiten Actions — bijvoorbeeld in een Claude-sessie — en schrijft alles wat
   de database nodig heeft naar een csv. Die komt als `pipeline/oogst/zorg_<boekjaar>.csv`
   in de repo.
2. **Inladen** (goedkoop): **Zorgoogst inladen** zet zo'n bestand er in ±2
   minuten in. Deze stap zit ook in Alles verversen, dus meestal hoef je er
   niet apart aan te denken.

De knop **Zorgdata laden** blijft bestaan voor kleine, gerichte runs (één nieuw
boekjaar als het tegoed het toelaat), maar voor de inhaalslag is de oogstroute
de bedoeling.

## Als een run rood is

- **Open de run en lees de eerste melding.** Elke lader meldt in gewone taal
  wat er mis is (ontbrekend secret, bron onbereikbaar, tijdslimiet).
- **Opnieuw draaien is altijd veilig** — alles is idempotent en pakt op waar
  het gebleven was.
- **Rood binnen een paar seconden, zonder logs**: dat is geen fout in de code
  maar het Actions-tegoed dat op is (of een billing-blokkade). Er is dan niets
  te herstellen; kijk bij Settings → Billing en wacht op de maandreset, verhoog
  tijdelijk de spending limit, of upgrade het account.

## Volgorde-regels (voor wie toch losse knoppen drukt)

1. **Migraties draaien** altijd eerst na een merge; twee keer drukken doet niets.
2. De laders daarna, volgorde maakt niet uit.
3. Nieuwe kantoren in de seed-CSV's komen automatisch mee: elke lader werkt
   eerst de kantorenlijst bij.

## De site deployt niet meer ("Resource is limited")

Meldt Vercel *"Resource is limited - try again in 24 hours (api-deployments-free-per-day)"*,
dan is het dagtegoed van honderd deployments op — en dan deployt de échte site
ook niet meer.

De oorzaak is de zorgoogst, niet de site. Die draait buiten Actions om en commit
per blok van twee organisaties, dus op een normale dag staan er meer dan honderd
pushes op de oogstbranch. `ignoreCommand` in `web/vercel.json` zorgde er al voor
dat er niets *gebouwd* wordt zolang `web/` niet verandert, maar Vercel maakt de
deployment dan nog wel aan en die telt gewoon mee.

Daarom staat er in `web/vercel.json` ook:

    "git": { "deploymentEnabled": { "claude/audit-market-platform-vv9vbq": false } }

Dat scheelt het aanmaken zelf. Prijs: op die branch komt geen preview-deployment
meer, ook niet bij een pull request. Voor een branch die per dag honderden
datacommits produceert is dat de juiste ruil — productie deployt vanaf `main` en
dat blijft werken.

**Komt er een nieuwe oogstbranch, zet hem hier dan ook in.** Anders is het
tegoed binnen een dag weer op en lijkt het alsof de site stuk is.
