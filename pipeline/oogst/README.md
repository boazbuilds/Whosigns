# Oogstrapporten

Resultaat-csv's van `laad_zorg.py --droogloop`, klaargezet om door de workflow
**Zorgoogst inladen** (of `laad_zorg_rapport.py`) in de database te worden gezet.

Waarom deze map bestaat: het dure deel van de zorgroute — pdf's downloaden,
lezen, zo nodig OCR — kost ±24 seconden per organisatie en dus uren per
boekjaar. Dat werk draait buiten GitHub Actions om; alleen het wegschrijven
(seconden) gebeurt nog op een runner. Zo kost de inhaalslag vrijwel geen
Actions-minuten. Zie docs/draaiboek-acties.md.

Spelregels:

- **Bron**: alle rijen komen uit het openbare DigiMV-archief
  (digimv13.desan.nl); de bron-rij wordt bij het inladen gezet, net als bij de
  directe route.
- Eén bestand per boekjaar: `zorg_<boekjaar>.csv`. De kolommen zijn die van
  `resultaat_<boekjaar>.csv` — een bestand van vóór de kolomuitbreiding (zonder
  `type_opdracht`) wordt door de lader geweigerd, niet gegokt.
- Inladen is idempotent: organisatie-boekjaren die al een opdracht hebben,
  worden overgeslagen. Een bestand mag dus blijven staan en groeien; de
  volgende run pakt alleen het nieuwe.
