-- WhoSigns — wisselingen met de sector van de organisatie erbij
--
-- v_wisselingen kent geen sector, en een view heeft geen foreign keys waar
-- PostgREST langs kan filteren. De sector- en subsectorpagina haalden daarom
-- álle wisselingen op (1.709 op 5-10-2026), zochten van alle 1.305
-- organisaties de naam op in zeven verzoeken, en gooiden daarna alles weg wat
-- niet in de sector viel — bij de zorg 296 van de 1.709. En /wisselingen kon
-- niet op sector filteren, dus het kerncijfer "wisselingen" op een
-- sectorpagina linkte naar de lijst van alle sectoren samen.
--
-- De definitie van een wisseling blijft waar hij is, in v_wisselingen; hier
-- komt alleen de sector en subsector van de organisatie bij, zoals die nu in
-- organisaties staat. Dat is dezelfde indeling als de sectorpagina gebruikt
-- (organisatiesInSector filtert ook op de huidige sector).
--
-- Zolang deze migratie niet heeft gedraaid, valt de website terug op de oude
-- weg (zolangNieuw in web/lib/db.ts).

create or replace view v_wisselingen_sector with (security_invoker = on) as
select w.organisatie_id,
       w.van_kantoor_id,
       w.naar_kantoor_id,
       w.boekjaar_wissel,
       o.sector,
       o.subsector
from v_wisselingen w
join organisaties o on o.id = w.organisatie_id;

comment on view v_wisselingen_sector is
  'v_wisselingen met de huidige sector en subsector van de organisatie, om op te filteren.';
