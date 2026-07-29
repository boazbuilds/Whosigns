# Stichtingen en NGO's — hoe halen we die sector op?

*Bronverkenning van 29-7-2026. Alle cijfers in dit document zijn gemeten, niet geschat;
`pipeline/verken_stichtingen.py` herhaalt de metingen. Backlog-item 3 in `ROADMAP.md`.*

## Kort antwoord

**Het CBF is voor de goededoelensector wat DigiMV voor de zorg is.** Eén openbare API
geeft de complete lijst erkende goede doelen mét KvK-nummer, RSIN, sector en
omvangcategorie; het CBF host de bijbehorende jaarverslagen zelf op een voorspelbare
URL, zeven boekjaren diep. De bestaande extractieketen (pdftotext + stringmatch) werkt
daar op: over de hele categorie D/E van boekjaar 2024 levert dat **213 opdrachten op 241
controleverklaringen (88%)**, en de pipeline om het te laden staat klaar als workflow
*Stichtingendata laden*.

Eén ontdekking verandert wel iets aan het model: **in deze sector is de controle vaak
vrijwillig.** Van die 213 opdrachten komen 48 van kantoren zonder Wta-vergunning —
legitiem, want zonder wettelijke controleplicht mag dat, en WITh Accountants is er in
z'n eentje het grootste kantoor van de sector mee. De AFM-lijst als gesloten matchset is
een uitstekend filter voor de zorg, maar structureel te smal voor stichtingen; er staat
nu een tweede kantorenlijst naast. Zie §"De kantorenlijst" en §"Gevolgen voor het
datamodel".

## Waarom deze sector niet als de zorg werkt

| | Zorg | Stichtingen/NGO's |
|---|---|---|
| Centrale plek met documenten | ja (DigiMV-archief) | nee — behalve voor CBF-erkende goede doelen |
| Complete populatielijst | ja (DigiMV-dataset) | ja (ANBI-bestand), maar zonder documenten |
| Grondslag van de controle | wettelijk (Wtza/WMG + BW) | vaak vrijwillig: erkenningsregeling of subsidievoorwaarde |
| Kantoor altijd Wta-vergunninghouder | ja, bij wettelijke controles | nee — ook kantoren buiten het AFM-register |
| Taal van de jaarrekening | Nederlands | 6 van de 38 gemeten verslagen Engels |

Drie dingen zitten daar achter:

1. **Deponeren hoeft niet.** Een stichting of vereniging deponeert alleen bij de KVK als
   ze een onderneming drijft met ten minste €7,5 mln omzet in twee opeenvolgende
   boekjaren. Voor de overgrote meerderheid van de goede doelen is er dus geen
   gedeponeerde jaarrekening — de KvK-route (backlog-item 2) helpt hier niet.
2. **Publiceren moet wél.** Elke ANBI heeft publicatieplicht op internet. Dat levert een
   bijna volledig gevuld websiteveld op in het open ANBI-bestand (45.554 van 45.554
   actieve beschikkingen), maar de vorm is vrij: pdf, html-jaarverslag of
   standaardformulier.
3. **De controleplicht komt van de toezichthouder, niet uit het BW.** Norm 8.1.3 van de
   CBF-Erkenningsregeling eist een controleverklaring vanaf categorie D (baten > €1 mln),
   een beoordelingsverklaring in categorie C en minimaal een samenstellingsverklaring in
   A/B. Precies dezelfde trap zien we terug in de subsidievoorwaarden van ministeries,
   provincies en gemeenten.

## Route 1 — CBF-register + CBF-jaarverslagen (gemeten, aanbevolen)

Vastgelegd in `pipeline/adapters/cbf.py`.

**Register** (openbare JSON-API, geen sleutel):
`GET https://apex.cbf.nl/ords/cbf/publiek/organisaties?limit=10000`

| | Aantal |
|---|---|
| Vermeldingen in het register | 826 |
| — met **actieve** erkenning | **714** |
| — met KvK-nummer én RSIN | 714 (alle) |
| Categorie A / B / C | 117 / 145 / 157 |
| **Categorie D / E** (controleverklaring is harde norm) | **172 / 123 = 295** |

Primaire sector zit erbij: internationale hulp en mensenrechten (237), welzijn (188),
gezondheid (108), natuur en milieu (71), dieren (45), religie en levensbeschouwing (35),
kunst en cultuur (21), onderwijs en wetenschap (9). Dat is meteen de sectorkolom van de
zes MVP-velden, zonder eigen indeling te hoeven verzinnen.

**Documenten** — het CBF host de jaarverslaggeving zelf, op een URL die je uit het
register kunt afleiden:

```
https://static.cbf.nl/documents/<naam>/<boekjaar>/jaarverslag.pdf
```

`<naam>` is het veld `naam` uit de API (url-encoded), `<boekjaar>` het verslagjaar. Er is
precies één bestandsnaam: `jaarrekening.pdf`, `bestuursverslag.pdf` en varianten geven
404. Geen zoekfunctie, geen scraping, geen matching op naam+plaats zoals bij DigiMV —
en dus ook niet de valkuilen daarvan.

**Dekking per boekjaar** (van de 714 actieve erkenningen):

| Boekjaar | 2018 | 2019 | 2020 | 2022 | 2024 | 2025 |
|---|---|---|---|---|---|---|
| Jaarverslag aanwezig | 12 | 514 | 551 | 597 | **666 (93%)** | 246 |

2021 en 2023 zijn niet gemeten; de reeks loopt duidelijk op tot en met 2024, en 2025 is
nog aan het vullen (deponeringstermijn). Boekjaar 2024 per categorie: A 109/117,
B 132/145, C 147/157, D 160/172, E 118/123 — de dekking is dus niet scheef naar groot.

> **Zelfde moat-argument als bij DigiMV.** Boekjaar 2018 is vrijwel leeg (12 treffers) en
> 2019 al 514: het archief lijkt ook hier een voortschrijdend venster. Wat we niet
> oogsten, is later niet gratis in te halen.

**Extractie, eerste steekproef** — 40 organisaties uit categorie D/E, boekjaar 2024, met
de pipeline zoals die er stond (alleen het AFM-register als matchlijst). De volle run met
de uitgebreide kantorenlijst staat verderop; deze steekproef is wat de problemen aan het
licht bracht:

| | Aantal |
|---|---|
| Jaarverslag gedownload | 38 van 40 (2× HTTP-fout bij de bron) |
| Herkend als **controleverklaring** | 33 |
| Samenstellingsverklaring | 1 |
| Geen soort te bepalen (2× gescande pdf zonder tekstlaag) | 4 |
| **Kantoor herleid tot een AFM-vergunninghouder** | **19 van 33 = 58%** |
| Oordeel bepaald | 29× goedkeurend, geen enkele beperking of onthouding |

Gevonden kantoren: Dubois & Co (4), BDO (3), en één elk voor Van Ree, Flynth, Visser &
Visser, Abin, PwC, Eshuis, HLB Den Hartog, aaff (Alfa), Kaap Hoorn, Kreston Lentink,
A.D accountants, Publieke Sector Accountants. Een heel andere kantorenmix dan de zorg:
veel middelgroot en gespecialiseerd, weinig Big 4.

De 14 missers, uitgesplitst:

| Reden | Aantal | Klopt dat? |
|---|---|---|
| Getekend door **WITh Accountants B.V.** | 8 | Staat niet in het AFM-register (zie hieronder) |
| Getekend door **Maas Accountants B.V.** | 1 | Idem |
| Geen kantoornaam in het pdf | 5 | Nee — het CBF-bestand bevat dan alleen het bestuursverslag, of de verklaring staat als afbeelding |

## Route 2 — ANBI-bestand als populatielijst, verslag van de eigen site (gemeten, tegenvallend)

Vastgelegd in `pipeline/adapters/anbi.py`. Het ANBI-bestand van de Belastingdienst is
échte open data (zip met XML, wekelijks bijgewerkt, vrij herbruikbaar):

| | Aantal |
|---|---|
| Beschikkingen met RSIN | 54.819 |
| — **actief** (geen intrekkingsdatum) | **45.554** |
| — met website én vestigingsplaats | 45.554 (alle) |
| Waarvan culturele ANBI | 8.199 |

Dit is de bovengrens van de sector, en de brug naar het CBF: **707 van de 714** erkende
goede doelen zijn op RSIN terug te vinden in het ANBI-bestand.

Getest of we van die websites zelf de verklaring kunnen halen (12 organisaties uit
categorie D/E: homepage ophalen, jaarstuk-achtige links volgen, pdf's analyseren):
**1 van de 12** leverde een kantoor op. Wat er misging:

- 4 sites gaven nul pdf-links op de vindbare paden (menu's via JavaScript, of een
  "online jaarverslag" in html in plaats van een pdf);
- de best scorende pdf was regelmatig een privacyverklaring, meldregeling of
  beleidsplan — niet het jaarstuk;
- waar het jaarverslag wél gevonden werd, zat de controleverklaring er soms niet in;
- 1 site gaf een HTTP-fout.

**Verdict:** het ANBI-bestand is onmisbaar als populatielijst, sectorafbakening en
mutatiesignaal (een ingetrokken ANBI-status is nieuws), maar de eigen-site-crawl is een
vangnet voor losse gevallen, geen bulkroute.

### De crawler die er nu staat (`adapters/anbi_publicatie.py`)

Alle vier de oorzaken hierboven zijn aangepakt: vaste paden proberen (`/anbi`,
`/jaarverslag`, …) omdat de ANBI-publicatiepagina per definitie bestaat, html-verslagen
net zo goed analyseren als pdf's, scoren op jaarstuk-woorden mét strafpunten voor
privacyverklaringen en beleidsplannen, en twee niveaus diep met een harde limiet op het
aantal verzoeken per site.

Gemeten op de 12 organisaties waar de CBF-route in boekjaar 2024 niets opleverde: de
terugval vond bij **1 van de 5** organisaties zonder bruikbaar CBF-bestand alsnog een
jaarverslag mét controleverklaring — en het kantoor daarin kenden we niet, dus die
belandt in de review-queue. Conclusie: de moeite waard als optie (`--terugval`), niet
als standaard. Hij staat daarom uit tenzij je hem aanzet.

Eén ding dat de meting blootlegde en dat nu is dichtgezet: de best scorende pdf op een
eigen site was regelmatig **een andere jaargang** ("gewaarmerkte-jaarverslag-2023"
terwijl we 2024 zochten). Bij het CBF staat het verslagjaar in de URL en is dat de bron
van waarheid; op een eigen site niet. `stichtingen.bevat_boekjaar()` eist daarom dat het
boekjaar in de tekst voorkomt vóór er iets wordt vastgelegd — anders boek je de
accountant van 2023 op boekjaar 2024, en dat is achteraf niet meer van een echt feit te
onderscheiden.

## Route 3 — de andere stichting-verticals via hun eigen toezichthouder

Formeel zijn dit ook stichtingen; praktisch is elk een eigen adapter. Sorteercriterium:
**is er een centrale documentbak?** Dat is wat de zorg en het CBF makkelijk maakt.

| Vertical | Rechtsvorm | Centrale documentbak? | Status |
|---|---|---|---|
| Zorg | overwegend stichting | ja, DigiMV-archief | ✅ Fase 1 |
| Woningcorporaties | vrijwel alle stichting | dVi via SBR-wonen (niet publiek per corporatie); Aw publiceert datasets op data.overheid.nl; jaarverslagen op eigen site | te onderzoeken — kandidaat #1 na de zorg |
| Onderwijsbesturen | overwegend stichting | DUO-XBRL is publiek, maar **bevat de accountant niet** (en is niet accountantsgecontroleerd); jaarverslagen bij de besturen | Fase 4 (al in ROADMAP) |
| Pensioenfondsen | stichting per definitie | DNB-register is publiek; jaarverslagen op eigen site | backlog |
| Cultuur (BIS, rijksfondsen) | stichting | subsidieverantwoording bij OCW/fondsen; 8.199 culturele ANBI's als lijst | backlog |
| Goede doelen | stichting | **ja, CBF** | dit document |

Het patroon is telkens hetzelfde: een toezichthouder of subsidieverstrekker die
verantwoording eist, is óók degene die de documenten verzamelt. Zoek eerst de
toezichthouder, dan de bak.

## Route 4 — KvK-deponeringen

Alleen bruikbaar voor commerciële stichtingen en verenigingen (≥ €7,5 mln omzet uit
onderneming, twee opeenvolgende boekjaren). Dat is een kleine minderheid van deze
sector en het kost ±€4 per stuk. Conclusie: geen route voor stichtingen; laat dit staan
waar het staat (backlog, "data on demand").

## Route 5 — aanbestedingen en subsidies als signaal, niet als dekking

Grote stichtingen met publieke financiering besteden hun accountantsdiensten aan
(TenderNed, CPV rond 79210000) en subsidieverantwoordingen boven de drempels vragen om
een accountantsverklaring. Dat is precies wat Fase 3 nodig heeft: **aangekondigde
wisselingen** vóór ze in een jaarverslag staan. Voor dekking is het niets — voor het
wisselsignaal in deze sector waarschijnlijk de sterkste bron die er is.

## Wat de meting aan de bestaande pipeline blootlegde

De goededoelenverslagen legden drie dingen bloot die in de zorg onzichtbaar bleven. Alle
drie in deze wijziging opgelost, met de zorgmeting als vangrail (38 gecachete
zorg-pdf's: **nul verschillen** vóór en na, en `valideer_extractie.py ziekenhuis 2023 12`
blijft 12/12).

**1. De kantoormatch keek naar substrings en dus naar halve woorden.** De zoeksleutel van
*Audit Pro B.V.* is `audit pro` en dat zit letterlijk in `audit procedures` — de
standaardzin in elk Engelstalig accountantsrapport. Audit Pro tekende zo drie
jaarverslagen die het kantoor nooit gezien heeft; `accura` (Accura B.V.) deed hetzelfde
in `accuraat`. **Vier valse matches op negentien.** Een gemiste match kost een rij in de
review-queue, een valse match zet een verzonnen relatie in de database — precies waar de
guardrail "nooit stil gokken" over gaat. `zoek_kantoor` eist nu hele woorden.

**2. Internationale stichtingen rapporteren in het Engels** (6 van de 38). Die
verklaringen waren geen `controle` en dus ook zonder oordeel, terwijl het gewone
COS-controles zijn. `verklaring.py` kent nu de Engelse termen. Let op de valstrik die
daarbij hoort: `qualified opinion` zit in `unqualified opinion` — het omgekeerde oordeel.
De kenmerkentest eist daarom een woordgrens aan de voorkant.

**3. De aliastabel is opnieuw het verschil.** *Dubois & Co. Registeraccountants* staat in
het AFM-register als *Maatschap Dubois & Co Registeraccountants* en tekent 4 van de 40
verslagen in de steekproef. Alias toegevoegd. Netto effect van fix 1–3 samen: van 9
correcte matches naar **19 correcte matches**, en de 4 valse matches weg.

## De kantorenlijst: het AFM-register is niet genoeg (opgelost)

De oogst over de **hele** categorie D/E van boekjaar 2024 (`verken_stichtingen.py oogst
2024`) maakt duidelijk hoe groot het gat is:

| | Aantal |
|---|---|
| Jaarverslagen gelezen | 278 van 295 |
| Herkend als controleverklaring | 241 |
| Kantoor herleid tegen alléén het AFM-register | 156 |
| **Kantoor onbekend** | **85** |

En de 85 missers zijn niet willekeurig: **47 daarvan noemen WITh Accountants B.V.** —
één kantoor, gespecialiseerd in goede doelen, zonder Wta-vergunning. De rest is een
staart van kleine kantoren plus vier keer *Share Impact Audit & Assurance* (dat blijkt
gewoon een aliaskwestie: de vergunning staat op *Share Impact Accountants B.V.*).

Daarom is de kantorenlijst nu tweeledig:

| Lijst | Wat | `wta_vergunning` |
|---|---|---|
| `seed/kantoren.csv` | 233 vergunninghouders uit het AFM-register | `true` |
| `seed/kantoren_overig.csv` | kantoren zónder Wta-vergunning die controleverklaringen tekenen | `false` |

Spelregels die daarbij horen:

- **Bewijs per rij.** Elke rij in `kantoren_overig.csv` noemt waar de naam is
  aangetroffen (`gevonden_bij`) en dat het kantoor niet in het AFM-register staat
  (stand van de datum). Namen komen uit `verken_stichtingen.py oogst`, altijd met de
  hand nagekeken: het patroon vist ook kostenposten en commissies op ("Bestuurskosten
  Accountants", "De Auditcommissie").
- **Alleen complete namen.** Een kandidaat komt in de seed als hij een rechtsvorm
  heeft en niet generiek is. Twijfelgevallen blijven eruit en komen via de
  review-queue langs — dat is precies waar die tabel voor is.
- **Een vergunninghouder wint altijd.** Bij een botsende zoeksleutel gaat het kantoor
  mét vergunning voor; een kantoor zonder vergunning mag er nooit een mét vergunning
  verdringen.
- **Nieuwe aliassen uit dezelfde oogst:** Share Impact, Borrie, KSG, Stolwijk
  Kelderman — vier keer dezelfde les als bij Dubois: de tekennaam is niet de
  registernaam.

### Wat de volledige run oplevert

`laad_stichtingen.py --boekjaar 2024 --droogloop` over dezelfde 295 organisaties, met de
uitgebreide kantorenlijst en de nieuwe aliassen (29-7-2026, twee minuten):

| Status | Aantal | Wat het is |
|---|---|---|
| **opdracht** | **213** | kantoor herleid; gaat de database in |
| review | 28 | controleverklaring, kantoor onbekend → review-queue met kandidaat-namen |
| geen_controle | 27 | wél een verslag, geen controleverklaring erin |
| geen_verslag | 18 | niets bij het CBF voor dit boekjaar |
| onleesbaar | 9 | gescande pdf zonder tekstlaag |

Op de 241 controleverklaringen is dat **213 herleid = 88%**, tegen 156 = 65% met alleen
het AFM-register. Van die 213 opdrachten komen **48 van kantoren zonder Wta-vergunning**
(22%) — precies het stuk markt dat eerder onzichtbaar was.

Verdeling die daaruit rolt: 199 `vrijwillige_controle` tegen 14 `wettelijke_controle`
(die laatste hebben een Wta-verwijzing in de tekst), en 201 goedkeurende oordelen tegen
5 met beperking. De kantorenmix wordt geleid door WITh (42) en Dubois & Co (30), met
Van Ree (18) en BDO (13) daarachter — een heel andere markt dan de zorg.

## Gevolgen voor het datamodel

1. **`opdrachttype` moet vrijwillige controle kunnen zijn.** 9 van de 33
   controleverklaringen komen van kantoren zonder Wta-vergunning (WITh Accountants,
   Maas Accountants). Dat is geen fout in de bron en geen gemiste match: zonder
   wettelijke controleplicht mag elk kantoor een controleverklaring afgeven. Zulke
   opdrachten wegfilteren zou de goededoelensector voor een derde leegmaken — inclusief
   namen als Amnesty en War Child, waar juist naar gezocht wordt.
2. **`kantoren` heeft rijen zonder AFM-nummer nodig.** Doorgevoerd in
   `20260730000000_kantoren_zonder_wta.sql`: `wta_vergunning` (boolean),
   `sleutel` (AFM-nummer of `overig_…`, de upsert-sleutel), plus `kvk_nummer` en
   `toelichting` voor de verantwoording. De UI kan het verschil al laten zien —
   `OPDRACHT_LABEL` in `web/lib/paden.ts` kent "vrijwillige controle".
3. **De views moesten mee.** `v_relatieduur`, `v_wisselingen` en `v_marktaandeel`
   filterden op `type_opdracht = 'wettelijke_controle'`. Daarmee zou de hele
   goededoelensector uit de relatieduur, de wisselingen én de marktaandelen vallen —
   precies de cijfers waar het product om draait. Ze tellen nu beide vormen van
   jaarrekeningcontrole mee; WNT-, productie- en subsidieverantwoordingen blijven er
   bewust buiten, want dat zijn andere opdrachten.
4. **Sector komt gratis mee** uit het CBF-register (8 sectoren, als `subsector`) en het
   onderscheid cultureel/niet-cultureel uit het ANBI-bestand. `sector` wordt
   `goede doelen`, `grootteklasse` de CBF-categorie.
5. **Nieuwe bron_types:** `cbf` (register + jaarverslag) en `anbi` (populatielijst).
6. **Boekjaar = verslagjaar in de URL.** Voor AAP staat op het paspoort letterlijk "alle
   cijfers komen uit het jaarverslag 2025" bij `/2025/jaarverslag.pdf`. Bij de terugval
   via een eigen website ontbreekt die zekerheid, en daar controleert
   `stichtingen.bevat_boekjaar()` het boekjaar in de tekst.

## Voorwaarden en guardrails

- **CBF-data is geen open data.** Het CBF stelt voorwaarden aan hergebruik: correcte
  bronvermelding verplicht, en paspoortteksten, logo's, afbeeldingen, financiële cijfers,
  datasets en API zijn niet vrij herbruikbaar ("Algemene Voorwaarden Gebruik CBF-data",
  contact data@cbf.nl). Wat wij willen vastleggen — welk kantoor de verklaring tekende —
  is een feit uit het jaarverslag van de stichting zelf, een openbaar stuk; het CBF is
  daarbij de vindplaats. Dat onderscheid is verdedigbaar, maar het is een keuze en geen
  gegeven: **nieuw punt 7 in `docs/beslissingen.md`**, met als advies vooraf even met
  data@cbf.nl te overleggen. Neem in geen geval CBF-paspoortteksten of -cijfers over.
- **ANBI-bestand:** vrij te gebruiken, bronvermelding niet verplicht (Belastingdienst
  open data). Geen enkel bezwaar.
- **AVG onveranderd:** alleen kantoornamen, nooit de tekenend accountant. In deze sector
  is dat extra opletten: kleine stichtingen noemen bestuurders bij naam in hetzelfde pdf.
- **Vriendelijk oogsten:** `cbf.py` pauzeert tussen requests; de bulk-run hoort in
  GitHub Actions, niet interactief.

## Zo laad je de sector (de pipeline staat klaar)

```
Actions -> "Stichtingendata laden" -> Run workflow
   boekjaren    2025,2024,2023,2022,2021,2020,2019   (nieuwste eerst)
   categorieen  D,E                                   (controleverklaring = harde norm)
   terugval     uit                                   (aan = ook eigen websites)
```

De workflow (`.github/workflows/stichtingendata.yml`) zet eerst de kantorenlijsten in de
database (`laad_kantoren.py --offline`, inclusief de kantoren zonder Wta-vergunning) en
draait daarna `laad_stichtingen.py` per boekjaar. Idempotent, dus opnieuw starten pikt op
waar het gebleven was; met `vanaf`/`aantal` knip je een lange run op. Het CSV-rapport per
boekjaar komt als artifact mee.

Lokaal hetzelfde, zonder database:

```
python3 pipeline/laad_stichtingen.py --boekjaar 2024 --droogloop
python3 pipeline/verken_stichtingen.py oogst 2024      # welke kantoren kennen we nog niet?
```

Verwachting voor de volle run over 2019–2025: boekjaar 2024 leverde 213 opdrachten op
295 organisaties; met de lagere dekking van de oudere jaren komt dat neer op in de orde
van **1.200–1.300 opdrachtrijen** — genoeg voor een sectorpagina, marktaandelen en een
wisselingenoverzicht in deze sector. Reken op een paar uur en ±1 GB aan downloads (de
lader gooit de pdf's na het lezen weg, tenzij je `--bewaar-pdf` meegeeft).

## Aanbevolen volgorde

1. **Eerst de zorgsector afmaken** (Mijlpaal B). De visie zegt: één sector compleet vóór
   verbreding, en dat blijft het advies — de pipeline hieronder verandert daar niets aan,
   die staat nu alleen klaar.
2. **Dan categorie D+E laden** (295 organisaties × 7 boekjaren, één workflow-run van een
   paar uur). Klein genoeg om na te lopen, groot genoeg om iets te laten zien.
3. **Daarna pas verbreden** naar categorie C (beoordelingsverklaringen — ander
   opdrachttype, geen jaarrekeningcontrole) en naar de verticals uit route 3.
4. **De review-queue leeghalen** hoort bij het werk: elke onbekende kantoornaam die
   erin belandt, komt met kandidaat-namen uit de tekst en kan met één regel in
   `seed/kantoren_overig.csv` (of `kantoor_alias.csv`) worden afgehandeld. Zo wordt de
   lijst met elke run een stukje completer.

## Open punten

- [ ] Overleg met data@cbf.nl over gebruik van register-API en jaarverslagen (beslissing 7)
- [ ] Boekjaren 2021 en 2023 meemeten in de dekkingsmeting (nu overgeslagen)
- [ ] Vaststellen of het CBF-archief echt een voortschrijdend venster is, of 2018 gewoon
      het eerste jaar van de regeling was
- [x] Kantoorlijst buiten het AFM-register: bottom-up opgebouwd uit de oogst
      (`seed/kantoren_overig.csv`), nooit stil gemerged — de rest via de review-queue
- [ ] Bestaat er een bruikbaar publiek overzicht van kantoren zonder Wta-vergunning
      (NBA/SRA/Novak)? Dat zou de bottom-up-lijst kunnen aanvullen
- [x] Terugvalroute via de eigen site gebouwd (`adapters/anbi_publicatie.py`); meet 1 op
      5 waar het CBF niets bruikbaars heeft, dus optioneel (`--terugval`)
- [ ] Ongeveer 15% van de verklaringen noemt de kantoornaam alleen in een logo of scan:
      zelfde OCR-/LLM-vraag als in de zorg, Fase 4
- [ ] KvK-nummers bij de kantoren zonder Wta-vergunning opzoeken (nu leeg)
- [ ] Ingetrokken CBF-erkenningen (112 in het register) als signaaltype uitwerken
- [ ] Woningcorporaties uitzoeken: staat de accountant in de dVi-data of alleen in het
      jaarverslag?

## Bronnen

- CBF register-API: <https://cbf.nl/api-register-erkende-goede-doelen>
- CBF datavoorwaarden: <https://cbf.nl/data>
- Normen voor de erkenning van Goede Doelen (ingaande 1-1-2026), norm 8.1.3 en de
  categoriegrenzen: <https://commissienormstelling.nl/normen>
- ANBI open data: <https://www.belastingdienst.nl/wps/wcm/connect/bldcontentnl/themaoverstijgend/brochures_en_publicaties/open_data_anbi>
- Deponeringsplicht stichting/vereniging: <https://www.kvk.nl/deponeren/jaarrekening-wel-of-niet-deponeren/>
- DUO financiële verantwoording XBRL: <https://duo.nl/open_onderwijsdata/onderwijs-algemeen/financiele-overzichten/financiele-verantwoording-xbrl.jsp>
- Open data woningcorporaties (Aw/ILT): <https://www.ilent.nl/onderwerpen/autoriteit-woningcorporaties/publicaties-cijfers-en-wetgeving-autoriteit-woningcorporaties/publicaties-en-data/open-data>
