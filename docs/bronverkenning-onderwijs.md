# Onderwijs (DUO) — bronverkenning

*Uitgezocht op 30-7-2026. **Conclusie: populatie ja, accountant nee. Valt af.**
Vastgelegd zodat niemand deze route nog een keer hoeft te verkennen.*

## Waarom onderwijs kansrijk leek

Alle bekostigde onderwijsinstellingen zijn controleplichtig, de populatie is groot
(~1.000 schoolbesturen over po, vo, mbo, hbo, wo) en — het beslissende punt — DUO
publiceert centraal. Dat is hetzelfde patroon dat de zorg werkbaar maakte: één partij
die voor de hele sector publiceert, in plaats van duizend losse websites.

Schoolbesturen moeten hun jaarverslaggeving vóór 1 juli bij DUO aanleveren, **inclusief
de controleverklaring en het eventuele rapport van bevindingen**, als pdf via Mijn DUO.
Dat klinkt als een archief in de zin van DigiMV.

## Waarom het toch afvalt

Wat DUO aanlevert is niet wat DUO publiceert.

| Wat DUO ontvangt | Wat DUO publiceert |
|---|---|
| jaarverslag + controleverklaring als pdf, via Mijn DUO | **alleen de XBRL-cijfers**: balans, baten, lasten, kengetallen per bestuur |

De open data staat op
`duo.nl/open_onderwijsdata/onderwijs-algemeen/financiele-overzichten/financiele-gegevens.jsp`
als vijf pdf-overzichten (po, vo, mbo, hbo, wo, boekjaren 2020–2024). DUO schrijft er
zelf bij: *"Besturen sturen de jaarrekeningen digitaal via het XBRL Onderwijsportaal.
De cijfers zijn niet gecontroleerd door een accountant."*

**Gemeten** op `financiele-gegevens-per-bestuur-wo-2020-2024.pdf` (2,4 MB, 84.057
tekens tekstlaag): **0 keer "accountant", 0 keer "verklaring"**. Het zijn
balans- en exploitatiecijfers per bevoegd gezag, niets over de tekenaar.

`informatieproducten.duo.rijkscloud.nl/public/jaarrekeninggegevens/` ziet uit als een
bestandsmap maar is een Shiny-dashboard op diezelfde cijfers.

## Wat er dan nog over zou zijn

De jaarverslagen zelf zijn openbaar, maar ieder bestuur publiceert ze op zijn eigen
website. Dat is ~1.000 losse sites — exact hetzelfde probleem als bij de
fondsbeheerders (zie `bronverkenning-beleggingsinstellingen.md`), en daar is het om
die reden ook bij gelaten.

## De les uit twee verkenningen op één dag

Voor deze database is niet "is de sector controleplichtig" de vraag, en ook niet "is
de populatie openbaar". Beide waren bij onderwijs én bij de fondsen in orde. De vraag
die telt is:

> **Publiceert één partij de vérklaringen voor de hele sector?**

Bij de zorg (DigiMV) en de goede doelen (CBF) is dat zo. Bij onderwijs, fondsen,
woningcorporaties en gemeenten niet: daar ontvangt de toezichthouder de stukken wel,
maar publiceert hij alleen cijfers. Toets die vraag eerst; de rest is dan pas
interessant.
