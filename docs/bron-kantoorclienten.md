# Bron: cliënten van één kantoor, uit losse openbare jaarstukken

*Gebouwd 4-8-2026. Adapter `pipeline/adapters/kantoorclienten.py`, lader
`pipeline/laad_kantoorclienten.py`, workflow "Kantoorcliënten laden".*

## Waarom deze bron anders werkt dan de andere

Alle andere bronnen in dit project werken **populatie-eerst**: één partij
publiceert voor een hele sector, en daaruit rolt vanzelf wie welke accountant
heeft.

| Bron | Publiceert voor |
|---|---|
| DigiMV | alle zorgaanbieders |
| dVi (Aw) | alle woningcorporaties |
| CBF | erkende goede doelen |
| AFM-register verslaggeving | beursfondsen |
| Transparantieverslagen | cliënten van de zes OOB-kantoren |

Voor een kantoor **zonder OOB-vergunning** bestaat zo'n lijst niet. Zulke
kantoren hoeven geen transparantieverslag met cliëntenlijst te publiceren, en
hun cliënten zijn meestal besloten vennootschappen die hun jaarrekening bij de
Kamer van Koophandel deponeren — en de KvK is voor dit project uitgesloten
(besluit van de opdrachtgever).

Wat dan overblijft is **document-eerst**: per organisatie een openbaar jaarstuk
zoeken waarin de accountant met naam wordt genoemd. Dat is handwerk, maar het
levert harde, controleerbare feiten op.

## De guardrail: de seed is een bewering, geen feit

Een regel in `seed/kantoorclienten.csv` zegt niet meer dan: *"in dit document
staat dat kantoor X tekende bij organisatie Y over boekjaar Z"*. De lader haalt
dat document er zelf bij en controleert de bewering vóórdat er iets wordt
weggeschreven. Drie uitkomsten:

| Status | Betekenis | Gevolg |
|---|---|---|
| `bevestigd` | document opgehaald, kantoornaam staat erin | opdracht wordt geschreven |
| `onbevestigd` | document bestaat, maar noemt dit kantoor niet | **niets** |
| `onbereikbaar` | document weg, achter een inlog, of 404 | **niets** |
| `bron geweigerd` | vindplaats is (een afgeleide van) het Handelsregister | **niets** |

Dat is strenger dan bij de andere bronnen, en met reden: daar staat een centrale
uitgever garant voor de inhoud, hier is het document zelf de enige garantie. Een
seed-regel die verouderd raakt — het jaarverslag wordt van de site gehaald —
verdwijnt zo vanzelf uit beeld, in plaats van stilletjes een onbewijsbaar feit
in de database te houden.

Nagemeten met vier proefregels tegen één echt document (het
BDO-transparantieverslag 2024): het kantoor dat er wél in staat werd bevestigd,
hetzelfde document onder een ánder kantoor werd afgekeurd, een
company.info-adres werd geweigerd en een 404 schreef niets weg.

## Wat wél en niet als vindplaats telt

**Wel:** een jaarverslag of jaarrekening op de site van de organisatie zelf, een
ANBI-publicatie, een prospectus of jaarbericht van een fonds, of een ander vrij
toegankelijk document.

**Niet:** de Kamer van Koophandel in welke vorm dan ook, inclusief doorverkopers
van uittreksels (company.info, drimble, opencorporates en soortgelijke). Die
zijn in de adapter hard geblokkeerd, zodat het niet van oplettendheid afhangt.
Ook niet: LinkedIn, vacatures of nieuwsberichten zonder onderliggend jaarstuk,
en niets achter een inlog of betaalmuur.

## Uitbreiden

Eén regel per bewezen document in `seed/kantoorclienten.csv`, dan de workflow
draaien — eerst met droogloop aan, dan zie je in het rapport wat er zou
gebeuren. De seed begint leeg: deze bron groeit per gevonden document, niet per
jaargang.

Kolommen: `kantoor_sleutel` (AFM-nummer), `organisatie` (statutaire naam zoals
in het document), `kvk_nummer` (alleen als het ín het document staat), `sector`,
`boekjaar`, `type_opdracht` (`controle`, `vrijwillige_controle`, `beoordeling`
of `samenstelling`), `url`, `vindplaats_toelichting`.
