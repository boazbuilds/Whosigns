# Werkpakketten na de verbeterronde van oktober 2026

*Opgesteld 6-10-2026. In de ronde van 5 en 6 oktober zijn 83 verbeterkansen
verkend en gemeten. Wat daarvan op `main` is geland, staat in de git-log
(#109 t/m #119: dashboard, AFM-register, honoraria 2019, eerlijke website,
nieuwe pagina's, snelheid, goede doelen, sectorindeling, raadsinformatie).
Hier staat wat **niet** is geland, met de winst zoals die op 5-10-2026 gemeten
of geschat is. Meet opnieuw voordat je bouwt: de database is sindsdien
gegroeid, en de laders schrijven nu meer velden.*

Vier pakketten waren gebouwd of half gebouwd toen de sessie werd afgerond.
Daarvan staat niets op `main`, en de code is niet bewaard: ze was nog niet
volledig getest of gereviewd. Wat er wél van bewaard is, staat hieronder: de
meting, de aanpak die werkte, en de valkuilen die de review vond.

## Gebouwd en gereviewd, niet geland

### Zorg: Verzameldocumenten, late indieners en tekenaars 2019–2025

Gemeten op 5-10-2026 met een lokale OCR-oogst (tesseract, poppler):

| Onderdeel | Winst | Hoe |
|---|---|---|
| Organisaties die alleen een **Verzameldocument** deponeren (2023: 260, 2024: 381, 2025: 390) werden nooit gelezen, omdat `digimv_archief.heeft_verklaring()` dat documenttype niet kende | +~250 wettelijke controles 2023–2025, waarvan ~40% Verstegen (verklaart de Verstegen-dip in de zorg) | `heeft_verklaring()` ook 'Verzameldocument' laten tellen, boven én onder `locations[]`; daarna oogsten met `laad_zorg.py --droogloop --hervat --uit-archief` en de rijen aan `pipeline/oogst/zorg_<jaar>.csv` toevoegen |
| **Late indieners 2025** (123) en de **2020-vestigingen** (295 organisaties met de verklaring onder `locations[]`) | +~180 rijen | Zelfde oogstroute |
| **Tekenend accountant** herlezen voor rijen zonder naam: 2019 608/783, 2020 679/807, 2021 706/864, 2022 512/822, 2023–2025 nog 334 | +~2.900 namen; alleen als kantoor, opdrachttype én oordeel van de herlezing gelijk zijn aan de rij (0 afwijkingen gemeten) | Nieuw `vul_ondertekenaar.py --archief`, hervatbaar, pdf's na elke organisatie weg |
| Een **marktonderzoekrij** (`controle_onbepaald`) telt in `laad_zorg.py`, `laad_zorg_rapport.py` en `laad_corporaties.py` als 'al geladen' | Ontgrendelt het bovenstaande; 137 corporaties 2025 hebben alleen zo'n rij | Helper naar het model van `laad_pensioenfondsen.gelezen_controles`; na een gelezen controle de onbepaalde rij bij hetzelfde kantoor weghalen, honoraria eerst overzetten |

**Wat de review vond en wat nog moest:** (1) `opdrachttype_van()` moet de
`wta_ooit`-uitzondering uit #111 houden (een wettelijke controle van een
kantoor waarvan de vergunning sindsdien verviel blijft wettelijk); (2) vier
nieuwe rijen voor 2025 kwamen uit één concernverklaring over een andere
rechtspersoon — zoek dat patroon systematisch in alle nieuwe rijen (één
document bij meerdere organisaties, een verklaring die een andere entiteit
noemt) voordat je de csv's commit; (3) twee rijen stonden op de nieuwe Steens
B.V. terwijl de verklaring van vóór de vergunning dateert. **Let op 1-1-2027:
het DigiMV-archief laat boekjaar 2019 dan vallen.** Doe 2019 eerst.

### AVG: de bewaarde OCR-teksten

De 4.260 bestanden in `pipeline/oogst/ocr/` zijn volledige jaarstukken
(52 miljoen tekens) met WNT-tabellen, bestuurders en toezichthouders. Dat
botst met de regel dat er naast de ondertekenaar geen personen in de repo
staan. Gebouwd en gemeten op 5-10-2026:

- Alleen het **venster van de controleverklaring** bewaren, van kopregel tot
  ondertekeningsblok, en per lezing toetsen dat `analyseer()` op het venster
  precies hetzelfde zegt als op de hele tekst (anders niets bewaren). Resultaat
  van de eerste snede: 1.451 bestanden, 13 miljoen tekens, nul verschil in
  ondertekenaars en opdrachten.
- **De review vond dat een marge van 600 tekens te ruim is:** in 185 bestanden
  stonden daardoor nog WNT-tabellen en bestuursondertekeningen. Met marge 0
  vóór en ~200 na bleven er 9 over; de tweede ronde maskeerde ook de namen van
  geadresseerden. Meet met een eigen detector (WNT, bezoldiging, 'bestuur',
  'raad van toezicht', initialen zonder RA/AA) en verwijder liever een bestand
  dan dat er een naam blijft staan.
- Verder in dit pakket: `kantoorkandidaten()` weert een persoonsnaam vóór een
  los woord als Committee/commissie/Manager en Engelse aanspreekvormen;
  `oogst_zorg.sh` kopieert alleen nog het venster; **echte personen in
  testfixtures** (`test_kantoor_match.py`: bestuursleden en een voornaam uit
  jaarverslagen) vervangen door verzonnen namen met dezelfde structuur.
- De **zoeklog** bewaart bij nul treffers geen tekst meer (keuze 11 in
  `docs/beslissingen.md`), met zoeken op KvK- en AFM-nummer, en de per ongeluk
  gecommitte pdf's onder `web/pipeline/.cache/` gaan weg met een gitignore-regel
  voor geneste `pipeline/.cache`-mappen.
- Wat HEAD schoonmaakt, blijft in de historie staan: dat is keuze 10, een
  besluit voor de eigenaar.

## Half gebouwd, niet geland

### Beursfondsen en OOB

| Pakket | Winst (5-10-2026) | Let op |
|---|---|---|
| **Een gelezen controle ruimt `controle_onbepaald` op**, ook buiten de laders om, en `v_marktaandeel` telt een organisatie-boekjaar één keer | 9 dubbele jaarregels weg van organisatiepagina's, 5 dubbeltellingen uit `v_marktaandeel` | Alleen bij exact hetzelfde `kantoor_id` (is not distinct from); tegenstrijdige gevallen blijven zichtbaar. Voorwaarde voor de twee ESEF-pakketten hieronder. De zorg- en corporatieladers doen dit sinds deze ronde zelf al |
| **Tekenend accountant uit de ESEF-jaarverslagen** | Nu 0 van de 1.724 OOB-controles met een tekenaar. Zonder aanpassing van de extractor ~+140; met de Engelse kop (*Independent auditor's report*, *signed by*) geschat +500–850, niet gevalideerd | `ondertekenaar.py` is de best bewaakte code van het project. Verplicht: blokken met *limited assurance* of ESRS uitsluiten (bij Heineken Holding stond het patroon alleen in het duurzaamheidsblok), en een regressiemeting over alle bewaarde OCR-vensters: geen naam veranderd, geen naam verdwenen |
| **ESEF-route terugwerkend op 2019–2024**, met een tekstcache | +30–70 OOB-controles met gelezen oordeel; lege oordeel- en tekenaarvelden op ~500 bestaande rijen | Nooit overschrijven; een ander kantoor dan op de bestaande rij gaat naar de review-queue. De eerste run downloadt ~220 documenten van 5–30 MB |
| **36 AFM-deponeringen over 2025 die niets opleveren** | ~10–13 beursfondsen over 2025 met oordeel en tekenaar (OOB 2025: 110 → ~120) | Ze worden elke maand opnieuw gedownload. Dubbele organisaties alleen via de review-queue samenvoegen |
| **Transparantieverslag Deloitte FY26** (105 OOB-cliënten) klaarzetten, met een poort | Direct 0 rijen, met opzet; ~550–600 OOB-rijen voor boekjaar 2025 zodra alle OOB-kantoren hun verslag hebben (EY/PwC okt–nov, KPMG/Forvis Mazars dec–jan, BDO rond april 2027) | Eén kantoor eerder laden maakt de OOB-aandelen van 2025 eenzijdig. De poort is een besluit voor de opdrachtgever (zie `docs/beslissingen.md`) |

### Plaats en KvK

| Pakket | Winst (5-10-2026) | Let op |
|---|---|---|
| **Plaats via GLEIF, het Register van Overheidsorganisaties en alle DigiMV-rijen** | +~3.400 gemeenten (alleen ISSUED-LEI's) tot +~4.700 (ook LAPSED); nu is bij 14.214 organisaties de gemeente leeg | Het ROO-bestand bevat namen van medewerkers: alleen naam, KvK en vestigingsplaats inlezen en het ruwe bestand nergens bewaren, ook niet in een cache of log |
| **KvK-nummer via het ROO (overheid) en een exacte, unieke naammatch in GLEIF (OOB)** | +416 KvK-nummers voor overheid, +~650 voor OOB; 60–90 dubbele organisaties zichtbaar als samenvoegkandidaat | Een KvK dat al bij een andere rij staat nooit toewijzen: dat wordt een review-item "mogelijk dubbel" |

## Niet begonnen

### Laden zonder knop

- **Push- en schedule-triggers** voor de laders die alleen met de knop draaien
  (gunningen, transparantie, kantoorcliënten). Gunningen: ~5–10 per maand die
  nu blijven liggen.
- **Padfilters** die afhankelijkheden missen: TED heeft geen cron en geen push,
  de marktonderzoeklader start zijn eigen workflow niet, en een wijziging in de
  kantoor-seeds raakt geen enkele lader.
- **Corporatie- en beursfondscron ook jaar−2 laten proberen**, en de
  corporatiecron in het vierde kwartaal wekelijks. Zorgt dat de ~270
  corporaties van 2025 gegarandeerd binnenkomen zodra dVi2025 verschijnt.
- **Vaste cache-sleutels** in de pensioen- en onderwijsworkflow: hun cache
  wordt na de eerste keer nooit meer ververst. (Bij de honoraria is dit in #113
  opgelost met een sleutel op de hash van de lezer.)
- **Bronnenwachter**: wekelijks zichtbaar maken wanneer een bron een nieuwe
  jaargang heeft of stilstaat. Open Raadsinformatie stond drie maanden stil
  voordat iemand het merkte.

### Nieuwe bronnen

| Bron | Winst (geschat) | Opmerking |
|---|---|---|
| Politieke partijen, financiële verslagen via open.overheid.nl | +~70 controles bij ~20 partijen, 2019–2024 | Nieuwe sector; trefkans 6 van 8 |
| organisaties.overheid.nl (CC0) als populatie voor waterschappen, provincies en zbo's | +50–150 controles | Niet gemeten |
| Overheid 2025: een tweede vindplaats naast Open Raadsinformatie | ~+100 controles | ORI staat stil sinds 9-7-2026 |
| Zorg: alleen-jaarrekening-deponeringen gericht lezen bij organisaties met externe voorkennis | +120–180 controles over 2023–2025 | Valideert tegelijk de marktonderzoekrijen |
| Stichtingenlus: "klaar" per KvK-nummer in plaats van per offset | ~+15 nu, daarna ±5 nieuwe erkenningen per maand die nu stil buiten beeld vallen | |

### Onderwijs en pensioen

- **Rapport en stille missers** in de onderwijs- en pensioenlader: 29 van de
  150 onderwijs-seedregels leveren geen opdracht en niemand ziet waarom.
- **Onderwijsseed uitbreiden** met alle 14 universiteiten, de overige
  hogescholen en het mbo: onderwijs van ~20 naar ~60–80 controles per jaar.
- **Schoolbesturen** via de DUO-besturenlijst (KvK en website, CC-BY) en de
  controleverklaring uit het jaarverslag op de eigen site: gemeten trefkans
  6 van 30, geschat +200–450 controles. De adapter voor de DUO-lijst ligt er
  sinds deze ronde (`adapters/duo_besturen.py`).
- **Pensioenfondsen**: 69 fondsen hebben alleen marktonderzoekrijen;
  +100–200 controles.

### Datakwaliteit

- **73 woningcorporaties staan ook als OOB-organisatie**, zonder KvK, met 290
  wettelijke controles uit transparantieverslagen (~50 per jaar, 2019–2024).
  Dezelfde entiteit staat zo in twee sectoren en telt mee in het OOB-totaal.
  Samenvoegen alleen op een harde sleutel; anders de review-queue.
- **De review-queue heeft geen afnemer**: niets verwerkt een "akkoord", dus elk
  goedgekeurd twijfelgeval blijft een gat.
- **De kantoorpagina haalt nog alle opdrachten van een kantoor op** (bij BDO
  11.417, 4,6 MB uit PostgREST) om ze op de pagina te tellen. Daar horen views
  voor.
- **Dekking tegen het universum** op de voorpagina kan pas met een noemer die
  een bron heeft en aansluit. De enige kandidaat, de corporaties uit dVi,
  sluit nog niet aan: boekjaar 2011 heeft 391 controles tegen 389 corporaties.

### Documentatie

- README, draaiboek en pipeline-README bijwerken naar de gemeten stand.
- Afgevallen bronnen vastleggen, zodat niemand ze opnieuw verkent: het
  DigiMV-archief geeft vóór 2019 HTTP 500 (zorg 2015–2018 is dus niet meer te
  halen), DUO heeft geen jaarrekening- of accountantdataset, en dVi2024 bevat
  geen honoraria.
