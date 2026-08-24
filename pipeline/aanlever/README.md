# Aanleveringen

Door de eigenaar aangeleverde accountantsrelaties, geschoond tot precies de
velden die de database publiek serveert: `kvk,naam,boekjaar,accountant`.
Eén bestand per aanlevering, naam `marktonderzoek_<label>.csv`.

Zodra een bestand hier op main landt draait de workflow **Marktonderzoek
laden** vanzelf (zie `.github/workflows/marktonderzoek.yml`). De lader
(`pipeline/laad_marktonderzoek.py`) herleidt de accountantsnaam naar de
AFM-lijst; velden met meerdere of onherleidbare kantoren gaan naar de
review-queue. Opdrachten krijgen type `controle_onbepaald` en bron
`marktonderzoek` (betrouwbaarheid `zelf_aangeleverd`) — zie het colofon van
de site voor wat die categorie betekent.

De test `pipeline/test_marktonderzoek.py` bewaakt dat elke rij hier door de
validatie komt; een kapotte aanlevering sneuvelt dus in CI.
