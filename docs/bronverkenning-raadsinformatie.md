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

Gemeten op de eerste 600 documenten (droogloop, 5-8-2026):

| Uitkomst | Aantal |
|---|---|
| controle met ondertekening | 173 |
| al gezien in deze run | 131 |
| geen kantoor gevonden | 39 |
| kantoornaam zonder ondertekening | 4 |

68 unieke organisaties, boekjaren 2010 t/m 2023. De kantoren zijn precies wat je
in dit segment verwacht: Baker Tilly, Deloitte, Publieke Sector Accountants,
BDO, EY, Verstegen, Astrium, Flynth, Kaap Hoorn, Eshuis.

## Uitbreiden

De zoekzin is nu de Nederlandse standaardformulering. Een tweede zin die
hetzelfde doet — "hebben wij de jaarrekening … gecontroleerd" in een andere
woordvolgorde — zou de opbrengst verhogen, maar elke variant moet eerst gemeten
worden op vals-positieven. Wat nu afvalt staat in het rapport
(`pipeline/.cache/resultaat_raadsinformatie.csv`), inclusief de organisaties
waarvoor geen kantoor te vinden was.
