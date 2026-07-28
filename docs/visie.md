# Visie — WhoSigns

*Vastgelegd juli 2026, aangeleverd door de opdrachtgever. Dit document is **leidend**:
waar `docs/concept.md` of oudere plannen ervan afwijken, geldt de visie. De roadmap
(`ROADMAP.md`) volgt deze scope.*

## In één zin

**Transfermarkt voor de assurance-markt.** Geen database met documenten, maar een
database van **relaties**:

```
Organisatie ↔ Accountant ↔ Opdracht ↔ Jaar
```

## Wat is het product?

Een platform waar je kunt ontdekken:

- Wie controleert wie?
- Welke accountants zijn actief in welke sector?
- Welke organisaties wisselen van accountant?
- Welke kantoren winnen/verliezen marktaandeel?
- Welke assurance-opdrachten worden uitgevoerd?

## MVP: zes velden, meer niet

| Veld | Waarom |
|---|---|
| Organisatie | Kernobject |
| Accountant | Kernobject |
| Opdrachttype | Controle, subsidie, ISAE, etc. |
| Jaar | Historie |
| Sector | Navigatie |
| Bron | Verifieerbaarheid |

**Expliciet níét in het MVP** (nog niet — het schema houdt er wel rekening mee):

- ❌ AI(-extractie in de pipeline)
- ❌ Switch scores / switch probability
- ❌ Honoraria
- ❌ ANBI-checks
- ❌ Europa
- ❌ AI-agenten

**Wél, nu:**

- ✅ Zorgdataset ophalen
- ✅ Organisatie ↔ Accountant ↔ Opdracht ↔ Jaar vullen
- ✅ Eerste 1.000 organisaties laden
- ✅ Kijken of mensen **spontaan gaan zoeken en doorklikken**

## Waarom dit schaalbaar is

Het model is universeel en werkt onveranderd voor zorg, ANBI's, woningcorporaties,
onderwijs, fondsen en het bedrijfsleven — en later voor België, Duitsland, Europa
(dezelfde EU-openbaarmakingsregels). Nieuwe vertical of nieuw land = nieuwe adapter,
zelfde vier-entiteiten-model.

## De echte moat

Niet AI. Niet software. Maar: **de grootste historische database van
accountant-opdrachtrelaties.** Bijvoorbeeld (illustratief):

```
Studio Anneloes          Organisatie Y
  2022  Qconcepts          2022  BDO
  2023  Qconcepts          2023  BDO
  2024  Qconcepts          2024  EY   ← wisseling, uit historie
  2025  Qconcepts          2025  EY
```

Die historie wordt elk jaar waardevoller en is niet in te halen door wie later begint.
(Let op: wisselingen als *feit* — af te leiden uit de historie — horen bij het MVP;
alleen *voorspellende* scores zijn "nog niet".)

## Hoe gebruikers klikken

Niet als Excel. Wel als **Wikipedia, LinkedIn, Transfermarkt**:

```
Studio Anneloes → Qconcepts → retailsector → andere retailbedrijven
→ BDO → nieuwe cliënten → andere sector → …
```

**Harde UI-regel: op elke pagina minimaal 5 interessante vervolgklikken.**
Nooit een doodlopende pagina.

## Freemium (richting, prijzen later)

| Gratis | Pro | Team |
|---|---|---|
| Organisatie zoeken | Historische accountants | Prospectielijsten |
| Accountant zoeken | Accountantswissels | Marktaandelen |
| Sectoroverzichten | Export | Concurrentieanalyse |
| | Geavanceerde filters | API |

*Waar de grens tussen gratis en betaald precies ligt (m.n. of historie gratis bladerbaar
is) is een open keuze — zie `docs/beslissingen.md` #6. Beslissen vóór publieke lancering;
bij de klik-test is alles gratis.*

## Noordster

Als iemand over twee jaar denkt: *"wie is eigenlijk de accountant van organisatie X?"* —
dan moet het antwoord zijn: **"even op WhoSigns kijken."**

Meetbaar gemaakt voor de klik-test (Fase 2): zoeken testgebruikers spontaan een naam op,
hoe diep klikken ze door (doel: ≥ 5 pagina's per sessie), en komen ze uit zichzelf terug?
