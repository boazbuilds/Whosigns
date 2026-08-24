# Aanleveringen

Door de eigenaar aangeleverde accountantsrelaties, geschoond tot precies de
velden die de database publiek serveert: `kvk,naam,boekjaar,accountant`,
sinds formaat v2 optioneel aangevuld met `sbi,plaats`. Eén bestand per
aanlevering, naam `marktonderzoek_<label>.csv`.

De SBI-code en plaats verrijken de organisatie (kolommen `sbi_code`,
`gemeente`) en bepalen via een kleine vaste indeling de sector — alleen op
organisaties waar die velden nog leeg zijn; wat een documentbron al invulde
blijft staan.

Zodra een bestand hier op main landt draait de workflow **Marktonderzoek
laden** vanzelf (zie `.github/workflows/marktonderzoek.yml`). De lader
(`pipeline/laad_marktonderzoek.py`) herleidt de accountantsnaam naar de
AFM-lijst; velden met meerdere of onherleidbare kantoren gaan naar de
review-queue. Opdrachten krijgen type `controle_onbepaald` en bron
`marktonderzoek` (betrouwbaarheid `zelf_aangeleverd`) — zie het colofon van
de site voor wat die categorie betekent.

De test `pipeline/test_marktonderzoek.py` bewaakt dat elke rij hier door de
validatie komt; een kapotte aanlevering sneuvelt dus in CI.
