# Bron: controleverklaringen uit raadsstukken

*Gebouwd 5-8-2026. Adapter `pipeline/adapters/raadsinformatie.py`, lader
`pipeline/laad_raadsinformatie.py`, workflow "Raadsinformatie laden".*

## Waarom deze bron

Gemeenten, provincies, waterschappen en gemeenschappelijke regelingen leggen hun
jaarstukken voor aan een raad of algemeen bestuur. Die stukken zijn openbaar, en
Open Raadsinformatie ontsluit ze met een zoek-API die **de volledige
documenttekst meelevert**. Geen pdf's downloaden, geen tekstherkenning.

    POST https://api.openraadsinformatie.nl/v1/elastic/_search

Meer dan tienduizend documenten bevatten letterlijk de zin "controleverklaring
van de onafhankelijke accountant".

Deze bron opent bovendien een populatie die nergens anders vandaan komt:
gemeenschappelijke regelingen, omgevingsdiensten, veiligheidsregio's,
recreatieschappen, afvalverwijderingsbedrijven en samenwerkingsverbanden. Die
staan in geen enkel register dat WhoSigns al gebruikt.

## De valkuil: de publicerende raad is niet de gecontroleerde partij

Het ligt voor de hand om de organisatie te nemen die het document publiceerde.
Dat is fout, en het is niet zeldzaam.

Een gemeenteraad bespreekt niet alleen de eigen jaarstukken maar ook die van
elke gemeenschappelijke regeling waarin de gemeente deelneemt. In één zitting
van een Noord-Hollandse raad kwamen langs: CAW, SSC DeSom, GGD Hollands
Noorden, Veiligheidsregio NHN, WerkSaam Westfriesland, Omgevingsdienst NHN en
het Westfries Archief. Wie de raad als gecontroleerde partij neemt, schrijft
zeven controles toe aan één gemeente die er geen enkele van heeft gehad.

Daarnaast staat de zoekzin ook in inhoudsopgaven en aanbiedingsbrieven, waar
helemaal geen verklaring in staat.

## Wat we in plaats daarvan lezen

Eén zin — de standaardformulering waarmee elke Nederlandse controleverklaring
bij een decentrale overheid begint:

> Wij hebben de jaarrekening **2018** van de **Gemeenschappelijke regeling
> WerkSaam Westfriesland** te **Hoorn** gecontroleerd.

Die zin levert alle drie de feiten die nodig zijn — organisatie, boekjaar,
plaats — en hij staat er alleen als er ook echt een verklaring is. Een document
zonder die zin levert dus niets op, en dat is de bedoeling: liever een
verklaring missen dan een controle toeschrijven aan de verkeerde organisatie.

## Twee dingen die daarna nog mis kunnen gaan

**Het handtekeningblok van de buurman.** Een raadsbundel zet de jaarstukken van
vijf regelingen achter elkaar in één pdf. Zoek je het kantoor in een vast
venster van een paar duizend tekens, dan vind je de handtekening van de
volgende verklaring. Gemeten: met een venster van 20.000 tekens kreeg SSC DeSom
de accountant van Omgevingsdienst Noord-Holland Noord. Daarom loopt het venster
van elke verklaring tot aan de vólgende "…gecontroleerd"-zin, en niet verder.

**Koppeltekens die uit de pdf-tekst vallen.** "Veiligheidsregio Noord-Holland
Noord" en "Veiligheidsregio NoordHolland Noord" staan allebei in de bron, net
als "Regio West-Brabant" naast "Regio WestBrabant". Op de gewone normalisatie
zijn dat verschillende organisaties, en dan splitst de geschiedenis van één
veiligheidsregio zich over twee rijen — dezelfde fout die de woningcorporaties
dubbel in de database zette. Vandaar `matchsleutel()`: alleen letters en
cijfers. Die wordt alleen gebruikt als hij naar precies één bestaande
organisatie wijst.

## Opbrengst

Droogloop over de **volledige bron** — alle 21.339 documenten die de zoekzin
bevatten, dus niet een steekproef (8-8-2026):

| Uitkomst | Aantal |
|---|---|
| controle met ondertekening | 3.784 |
| al gezien in deze run | 6.750 |
| geen kantoor gevonden | 1.640 |
| kantoornaam zonder ondertekening | 370 |
| naam onbruikbaar | 71 |

**1.575 organisaties, 73 kantoren, boekjaren 2010 t/m 2025.** Deloitte 946,
Baker Tilly 531, BDO 332, EY 257, PwC 199, Publieke Sector Accountants 191,
Eshuis 170, Verstegen 121, Flynth 115, Stolwijk Kelderman 99.

Twee dingen aan die tabel zijn het vermelden waard. De 3.784 opdrachten zijn
3.784 *verschillende* combinaties van organisatie en boekjaar — geen enkele
dubbeling. En geen enkele organisatie kreeg over hetzelfde boekjaar twee
verschillende kantoren toegeschreven. Dat is de controle die ertoe doet: als het
venster of de kantoormatch systematisch zou misgrijpen, zou juist dáár de ruis
zichtbaar worden, want dezelfde jaarrekening komt in meerdere raadsbundels langs.

## Wat er nog open ligt, en wat het waard is

Het verleidelijke antwoord is "die 1.640 + 370 weggevallen rijen". Maar de meeste
daarvan gaan over een organisatie en boekjaar die elders in de oogst *wel* een
ondertekend kantoor kregen — dezelfde jaarrekening ligt nu eenmaal bij meerdere
raden. Wat er echt nog te halen valt, gemeten:

| Restgroep | Rijen | Nieuwe org+jaar | Organisaties die nu nergens staan |
|---|---|---|---|
| geen kantoor gevonden | 1.640 | 632 | 333 |
| kantoornaam zonder ondertekening | 370 | 160 | 76 |

De eerste groep is dus vier keer zoveel waard als de tweede, en dat is precies
omgekeerd aan waar het onderzoek intuïtief naartoe trekt — een bijna-treffer
mét kantoornaam voelt als laaghangend fruit, en dat is het niet.

**Gemeten en verworpen: de onafhankelijkheidsparagraaf.** "Ons zijn geen relaties
bekend tussen Deloitte Accountants B.V. en haar zuster- en/of
dochterondernemingen" is de grootste enkele oorzaak binnen de tweede groep (18
van de 63 in een steekproef van 4.000 stukken). Toch leverde de regel over
diezelfde 4.000 documenten **één** rij op — corpusbreed een stuk of vijf — omdat
die organisaties hun kantoor al via een andere vermelding kregen. Nul
toeschrijvingen klapten om, dus de regel is veilig; hij is alleen de moeite niet
waard. Zie de toelichting bij `_ONDERTEKENING` in
`pipeline/extractie/kantoor_match.py`.

**Nog niet onderzocht: het briefpapier.** De rest van de tweede groep is de
kantoornaam in een adresblok — Stolwijk, Hofsteenge, Ipa-Acon, Van der Meer,
Baker Tilly, met postbus en vestigingsplaats eronder. Soms staat dat blok ónder
een echte verklaring (dan is het een gemiste opdracht), soms op een begeleidende
brief bij een boardletter (dan is het terecht geen opdracht). Zonder dat
onderscheid levert de regel valse opdrachten op, en dat is een duurdere fout dan
een ontbrekende rij. Plafond: 160 rijen.

## Uitbreiden

De zoekzin is nu de Nederlandse standaardformulering. Een tweede zin die
hetzelfde doet — "hebben wij de jaarrekening … gecontroleerd" in een andere
woordvolgorde — zou de opbrengst verhogen, maar elke variant moet eerst gemeten
worden op vals-positieven. Wat nu afvalt staat in het rapport
(`pipeline/.cache/resultaat_raadsinformatie.csv`), inclusief de organisaties
waarvoor geen kantoor te vinden was.

## De kantorenlijst was het grotere gat (gemeten 5-8-2026)

Het restruimte-onderzoek mat over de volle oogst dat 795 gelezen paren verloren
gingen: 624 zonder enig kantoor in het venster, 171 met een kantoornaam zonder
ondertekeningsscore. Dat is vijf keer zoveel als er met extra zoekzinnen te
halen valt (~4%). In die vensters staan echte tekenaars die de lijst niet
kende — gemeenten en regelingen worden ook gecontroleerd door kantoren zonder
Wta-vergunning (daar niet nodig) en door gemeentelijke diensten.

Toegevoegd na verificatie per naam (registercontrole, briefpapier in de
verklaringen zelf, en waar nodig extern bewijs):

| naam | soort | bewijs |
|---|---|---|
| FSV Accountants + Adviseurs B.V. (Zaltbommel) | overig | briefpapier met adres onder de verklaringen, Rivierenland-cluster |
| UNP accountants adviseurs B.V. (Breda) | overig | briefpapier Cosunpark 10 |
| ACAM Accountancy en Advies / Auditdienst ACAM | gemeentelijke dienst | ondertekent Amsterdam, stadsdelen en diensten 2010-2013 |
| Gemeentelijke Accountantsorganisatie Den Haag | gemeentelijke dienst | denhaag.nl; tekent de Haagse jaarrekeningen |
| Zirkzee Audit B.V. (Oegstgeest) | overig | oude AFM-vermelding verwijderd; 99 vindplaatsen |
| Koenen en Co Audit & Assurance (Maastricht) | overig | per 15-4-2024 opgegaan in Newtone; bewust geen alias naar 13000027 |
| A12 Registeraccountants → RA12 (13020095) | alias | de verklaring legt zelf de merknaam-relatie uit, met KvK-nummer |
| CROP registeraccountants → 13020228 | alias | briefpapier crop.nl, KvK 32166733, zelfde vestigingen |

Hertoets op de 324 bewaarde verloren paren uit de meting: **128 krijgen nu wél
een ondertekend kantoor** (CROP 33, FSV 31, ACAM 28, RA12 9, Koenen 9, Grant
Thornton 8 — via de alias uit de zorg-hoek — UNP 5, GAD 3, EY 1, Bentacera 1).
De voorbeelden kloppen geografisch: Koenen bij de Limburgse Omnibuzz, CROP bij
Amersfoortse regelingen, ACAM bij Amsterdam.

Niet toegevoegd: "Accountants voor de non-profit" (1 vindplaats, niet extern te
verifiëren).

## De tussenzin: waarom de krappe versie het werd (7-8-2026)

"Wij hebben de jaarrekening 2020 **(inclusief erratum)** van de gemeente Renkum
gecontroleerd." Zulke tussenzinnen vielen weg omdat er iets tussen het jaartal en
"van" stond. De voor de hand liggende oplossing is een vrij gat: laat er van
alles tussen staan, zoek dan de "van".

Dat werkt niet, en de reden is de Nederlandse taal. Organisatienamen zitten vól
"van" — Vereniging **van** Nederlandse Gemeenten, Regio Hart **van** Brabant. Met
een vrij gat slaat de zoeker het échte "van" over en haakt hij aan het "van"
binnenín de naam. Gemeten op 4.000 documenten: **113 namen werden gehalveerd.**
"Vereniging van Nederlandse Gemeenten" werd "Nederlandse Gemeenten". Een naam die
stilletjes de helft mist is erger dan een naam die ontbreekt, want hij ziet er
geloofwaardig uit en wordt een tweede organisatie naast de echte.

De versie die het werd staat alleen een tussenzin toe die zelf géén "van" bevat:
tussen haakjes, of ingeleid met "inclusief" / "en de daarbij behorende". Beide
kanten staan in `pipeline/test_raadsinformatie.py` — de drie schrijfwijzen die
mee moeten, en de twee namen mét "van" die heel moeten blijven.

In dezelfde meting kwam een tweede fout aan het licht die niets met de tussenzin
te maken had: de naam liep door over een kopje heen ("Ons oordeel"), waardoor er
26 verzonnen organisaties ontstonden en Den Haag zijn eigen boekjaar kwijtraakte.
Ook dat staat nu in de tests.
