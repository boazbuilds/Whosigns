# Beleggingsinstellingen en fondsbeheerders — bronverkenning

*Uitgezocht op 30-7-2026. **Conclusie: bron is werkbaar en gratis, maar niet gebouwd.**
Geparkeerd omdat de aanleiding (de portefeuille van één specifiek kantoor in beeld
krijgen) er niet mee te vullen is. Wie de vermogensbeheermarkt zelf wil toevoegen,
kan hier verder.*

## Aanleiding

De vraag was of we de cliënten van Confinant Audit & Assurance (AFM 13020070,
Amsterdam, geen OOB, 10–49 medewerkers) in de database kunnen krijgen. Confinant
noemt zich een audit-only boetiek voor **private equity, venture capital, fintech en
(platform based) scale-ups**. Geen van die vier zit in DigiMV of het CBF, en dat is de
reden dat de kantoorpagina leeg is — niet een fout in de matching.

Zoeken op "alle cliënten van kantoor X" kan bij geen enkele bron: je pakt een
populatie en het kantoor valt eruit.

## Vindplaats

Overzicht: `afm.nl/nl-nl/sector/registers/vergunningenregisters/beleggingsinstellingen`

| Bestand | Inhoud | Beheerders | Fondsen |
|---|---|---|---|
| `afm.nl/~/profmedia/files/registers/register-aifm.xlsx` | AIFM's mét vergunning | **123** | 1.528 vermeldingen |
| `afm.nl/~/profmedia/files/registers/register-aifmd-light.xlsx` | uitgezonderde/geregistreerde beheerders | 892 | 1.981 |
| `afm.nl/export.aspx?type=883bcff1-0f26-442f-9faf-a39ff911b109` | ICBE-notificaties (XML/CSV) | — | 1.252 |

**Val niet in de XML-export.** Die lijkt de logische ingang (zelfde patroon als
`afm_register.py` voor de accountantsorganisaties) maar bevat de grensoverschrijdende
notificaties: van 1.252 fondsen zijn er **16 Nederlands** — Luxemburg 460, Ierland
337, Frankrijk 296, Duitsland 74. Die worden in het buitenland gecontroleerd.

De xlsx-bestanden hebben geen KvK-nummer, alleen naam + vergunningnummer. Entity
resolution op KvK — de sleutel in de rest van de pipeline — kan dus niet zonder een
extra stap.

### Formaat

Een xlsx is een zip met XML; `openpyxl` staat niet in deze omgeving en is er ook niet
voor nodig. Let op twee dingen:

- Lees cellen **op kolomindex** (uit het `r`-attribuut, `A1` → 0), niet op volgorde
  van de `<c>`-elementen. Lege cellen worden overgeslagen en dan schuift alles op.
- In `register-aifm.xlsx` staat "Naam Beheerder" **alleen op de eerste regel van elk
  blok**; de volgende regels zijn extra fondsen van diezelfde beheerder. Wie dat
  negeert telt fondsnamen als beheerders — mijn eerste telling gaf zo 817 in plaats
  van 123.

## Wie erin staan

Precies de markt waar het om ging: Waterland, Bencis, Gilde Equity, Gilde Healthcare,
Egeria, Main Capital, Parcom, Rivean, AlpInvest, Avedon, HPE Growth, Finch Capital,
Carbon Equity, Marktlink, Ice Lake, Juno, Capital A. Plus de vermogensbeheerders:
Robeco, Triodos, Van Lanschot Kempen, APG, PGGM, Achmea, ASR, Aegon, en de
vastgoedfondsen (Annexum, Holland Immo Group, Bouwinvest, Vesteda, ZIB).

## Is het jaarverslag publiek? Ja voor retail, nee voor professioneel

Het register zegt het zelf, in de kolom `Aanbod professionals/retail`:

| Aanbod | Fondsvermeldingen |
|---|---|
| professionele beleggers | **752** |
| professioneel én retail | 562 |
| retail | 214 |

Een fonds dat aan retail wordt aangeboden moet zijn jaarverslag beschikbaar stellen;
professioneel-only hoeft dat niet. **86 van de 123 beheerders** hebben minstens één
retailfonds.

Getoetst:

- **Annexum Beheer B.V.** (retail) zet de jaarrekening als pdf op de eigen site
  (`a.storyblok.com/f/343297/...`). Onze bestaande extractie haalt daar zonder één
  regel nieuwe code het juiste antwoord uit: soort `controle`, opdrachttype
  `wettelijke_controle`, oordeel `goedkeurend`, kantoor **Deloitte Accountants B.V.
  (AFM 13000015)**. De verklaringstekst in een fondsjaarrekening is dus hetzelfde
  materiaal als in de zorg.
- **Waterland en Bencis** (professioneel-only): niets publiek. Alleen KVK, of via
  commerciële doorverkopers (northdata, jaarrekening.be) — dat laatste willen we niet.

## Waarom dit Confinant niet vult

Private equity, venture capital en scale-ups zijn per definitie professioneel-only, en
dat is exact de 752 die niets publiceren. Er is geen gratis route naar die
portefeuille. KVK is bewust afgeschreven (kosten per document, en ons principe verbiedt
het herpubliceren van hele gedeponeerde stukken).

Merk op: als je precies één kantoorportefeuille publiceert en niets daarbuiten, heb je
de cliëntenlijst gepubliceerd — ook al kwam elk los feit uit een openbaar stuk. Bij een
populatiebrede oogst valt het aandeel van een kantoor eruit als bijproduct, en dat is
wél verdedigbaar. Zie principe 1 en 3 in `docs/visie.md`.

## Wat het zou kosten om het wél te bouwen

De populatie is gratis en het formaat is opgelost. Het werk zit in de documenten:

- **Geen centraal archief.** DigiMV had één URL per KvK-nummer per boekjaar. Hier zijn
  het 86 verschillende websites met elk hun eigen indeling. Dat is linkzoekwerk, geen
  API — rommeliger dan alles wat er nu in de pipeline zit.
- **Eén hoopvol detail:** `npex.nl` host jaarberichten van meerdere fondsen op één
  plek. Daar zit misschien een klein archief in de zin van DigiMV.
- **Geen KvK in het register**, dus entity resolution moet op naam of via een aparte
  KvK-opzoeking.

Opbrengst: de vermogensbeheermarkt, ~86 beheerders en 776 retail-fondsvermeldingen,
voor €0. Een markt met eigen rotatieregels en eigen concurrentieverhoudingen.
