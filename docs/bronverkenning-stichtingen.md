# Stichtingen en NGO's — hoe halen we die sector op?

*Bronverkenning van 29-7-2026. Alle cijfers in dit document zijn gemeten, niet geschat;
`pipeline/verken_stichtingen.py` herhaalt de metingen. Backlog-item 3 in `ROADMAP.md`.*

## Kort antwoord

**Het CBF is voor de goededoelensector wat DigiMV voor de zorg is.** Eén openbare API
geeft de complete lijst erkende goede doelen mét KvK-nummer, RSIN, sector en
omvangcategorie; het CBF host de bijbehorende jaarverslagen zelf op een voorspelbare
URL, zeven boekjaren diep. De bestaande extractieketen (pdftotext + stringmatch tegen
de AFM-lijst) werkt daar zonder aanpassing op: **19 van de 33 controleverklaringen** in
een steekproef van 40 organisaties werden meteen aan een kantoor gekoppeld.

Eén ontdekking verandert wel iets aan het model: **in deze sector is de controle vaak
vrijwillig.** Negen van die 33 verklaringen zijn getekend door een kantoor zonder
Wta-vergunning — legitiem, want zonder wettelijke controleplicht mag dat. De AFM-lijst
als gesloten matchset is een uitstekend filter voor de zorg, maar structureel te smal
voor stichtingen. Zie §"Gevolgen voor het datamodel".

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

**Extractie** — steekproef van 40 organisaties uit categorie D/E, boekjaar 2024,
met de bestaande pipeline:

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
vangnet voor losse gevallen, geen bulkroute. Wie de crawl tóch wil, moet mikken op de
verplichte ANBI-publicatiepagina (`/anbi`) — die is er per definitie, alleen niet op een
vaste URL.

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

## Gevolgen voor het datamodel

1. **`opdrachttype` moet vrijwillige controle kunnen zijn.** 9 van de 33
   controleverklaringen komen van kantoren zonder Wta-vergunning (WITh Accountants,
   Maas Accountants). Dat is geen fout in de bron en geen gemiste match: zonder
   wettelijke controleplicht mag elk kantoor een controleverklaring afgeven. Zulke
   opdrachten wegfilteren zou de goededoelensector voor een derde leegmaken — inclusief
   namen als Amnesty en War Child, waar juist naar gezocht wordt.
2. **`kantoren` heeft rijen zonder AFM-nummer nodig.** Vandaag is `afm_nummer` de sleutel
   en de matchlijst. Voor deze sector is een tweede soort kantoorrij nodig
   (`wta_vergunning = false`, sleutel dan KvK-nummer of genormaliseerde naam), en de
   UI moet het verschil kunnen laten zien: "wettelijke controle" en "vrijwillige
   controle" zijn niet hetzelfde product.
3. **Sector komt gratis mee** uit het CBF-register (8 sectoren) en het onderscheid
   cultureel/niet-cultureel uit het ANBI-bestand.
4. **Nieuwe bron_types:** `cbf` (register + jaarverslag) en `anbi` (populatielijst).
5. **Boekjaar = verslagjaar in de URL.** Voor AAP staat op het paspoort letterlijk "alle
   cijfers komen uit het jaarverslag 2025" bij `/2025/jaarverslag.pdf`. Dat is dus geen
   indieningsjaar; per organisatie blijft controle op het boekjaar in de tekst nodig
   (gebroken boekjaren komen voor, bijvoorbeeld schooljaren).

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

## Aanbevolen volgorde

1. **Nu niets bouwen.** De zorgsector is nog niet af (Mijlpaal B) en de visie zegt: één
   sector compleet vóór verbreding. Deze verkenning is er om de route vast te leggen
   terwijl hij helder is.
2. **Zodra er een tweede sector bij mag:** begin met categorie D+E (295 organisaties,
   boekjaren 2019–2025). Met de gemeten dekking per jaar zijn dat ±1.700 jaarverslagen,
   waaruit bij de huidige trefkans naar schatting **±850 opdrachtrijen** met een
   AFM-kantoor komen — en ±1.250 als de vrijwillige controles van niet-Wta-kantoren
   meedoen. Eén GitHub Actions-run van een paar uur: klein genoeg om na te lopen, groot
   genoeg voor een sectorpagina en een wisselingenoverzicht.
3. **Daarna pas verbreden** naar categorie C (beoordelingsverklaringen — ander
   opdrachttype, geen wettelijke controle) en naar de verticals uit route 3.

## Open punten

- [ ] Overleg met data@cbf.nl over gebruik van register-API en jaarverslagen (beslissing 7)
- [ ] Boekjaren 2021 en 2023 meemeten in de dekkingsmeting (nu overgeslagen)
- [ ] Vaststellen of het CBF-archief echt een voortschrijdend venster is, of 2018 gewoon
      het eerste jaar van de regeling was
- [ ] Kantoorlijst buiten het AFM-register: bottom-up opbouwen uit de extractie, of
      bestaat er een bruikbaar publiek kantorenoverzicht (NBA/SRA)? Nooit stil mergen —
      review-queue
- [ ] 5 van de 33 jaarverslagen bevatten geen verklaring: is dat structureel (CBF vraagt
      alleen het bestuursverslag) of incident? Zo ja: terugvalroute via de eigen site
- [ ] Gescande pdf's (2 van de 38): zelfde OCR-/LLM-vraag als in de zorg, Fase 4
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
