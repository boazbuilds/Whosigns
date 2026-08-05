-- Dubbele corporaties samenvoegen: hetzelfde KvK-nummer met en zonder voorloopnul.
--
-- Wat er mis was
-- --------------
-- Het KvK-nummer is de sleutel waarop organisaties worden samengevoegd, maar de
-- dVi-opgave van de Autoriteit woningcorporaties is er niet consequent in:
-- jaargang 2010 schrijft `1032035`, jaargang 2013 schrijft `01032035` voor
-- dezelfde corporatie. Beide kwamen als eigen organisatie binnen.
--
-- Gemeten op 5-8-2026: 66 corporaties stonden er twee keer in — Stichting
-- Accolade, Stichting Elkien, Stichting WoonFriesland en 63 andere. Dat is 15%
-- van de corporatiepopulatie, en het splitst hun geschiedenis: de ene helft van
-- de boekjaren hing aan de ene rij, de andere helft aan de andere. Op de
-- website zag je daardoor twee organisaties met dezelfde naam, elk met een
-- half verhaal en geen enkele wisseling.
--
-- Alle 66 botsingen zitten in de sector woningcorporaties en alle 66
-- zeven-cijferige nummers ook; andere bronnen leveren netjes acht cijfers.
--
-- Wat deze migratie doet
-- ----------------------
-- De rij mét voorloopnul is de blijver, want acht cijfers is de officiële
-- lengte. Opdrachten en gunningen van de dubbelganger verhuizen daarheen;
-- botst een opdracht op (organisatie, boekjaar, type), dan blijft de bestaande
-- staan en vervalt de dubbele. Daarna verdwijnt de dubbelganger.
--
-- De adapter is tegelijk aangepast (`_schoon_kvk` in adapters/aw_dvi.py), dus
-- een volgende lading maakt de dubbelen niet opnieuw aan.

-- 1. Opdrachten verhuizen naar de rij met acht cijfers, zonder de unieke
--    sleutel (organisatie_id, boekjaar, type_opdracht) te schenden.
update opdrachten o
set organisatie_id = blijver.id
from organisaties dubbel
join organisaties blijver
  on blijver.kvk_nummer = lpad(dubbel.kvk_nummer, 8, '0')
 and blijver.id <> dubbel.id
where o.organisatie_id = dubbel.id
  and length(dubbel.kvk_nummer) = 7
  and not exists (
    select 1 from opdrachten bestaand
    where bestaand.organisatie_id = blijver.id
      and bestaand.boekjaar = o.boekjaar
      and bestaand.type_opdracht = o.type_opdracht
  );

-- 2. Wat na stap 1 nog aan een dubbelganger hangt, was een echte dubbele
--    opdracht (zelfde organisatie, boekjaar en type) en kan weg.
delete from opdrachten o
using organisaties dubbel
where o.organisatie_id = dubbel.id
  and length(dubbel.kvk_nummer) = 7
  and exists (
    select 1 from organisaties blijver
    where blijver.kvk_nummer = lpad(dubbel.kvk_nummer, 8, '0')
      and blijver.id <> dubbel.id
  );

-- 3. Hetzelfde voor gunningen, met hun eigen unieke sleutel.
update gunningen g
set organisatie_id = blijver.id
from organisaties dubbel
join organisaties blijver
  on blijver.kvk_nummer = lpad(dubbel.kvk_nummer, 8, '0')
 and blijver.id <> dubbel.id
where g.organisatie_id = dubbel.id
  and length(dubbel.kvk_nummer) = 7
  and not exists (
    select 1 from gunningen bestaand
    where bestaand.publicatienummer = g.publicatienummer
      and bestaand.organisatie_id = blijver.id
      and bestaand.kantoor_id = g.kantoor_id
  );

delete from gunningen g
using organisaties dubbel
where g.organisatie_id = dubbel.id
  and length(dubbel.kvk_nummer) = 7
  and exists (
    select 1 from organisaties blijver
    where blijver.kvk_nummer = lpad(dubbel.kvk_nummer, 8, '0')
      and blijver.id <> dubbel.id
  );

-- 4. De dubbelgangers zelf.
delete from organisaties dubbel
where length(dubbel.kvk_nummer) = 7
  and exists (
    select 1 from organisaties blijver
    where blijver.kvk_nummer = lpad(dubbel.kvk_nummer, 8, '0')
      and blijver.id <> dubbel.id
  );

-- 5. Een zeven-cijferig nummer zónder tegenhanger krijgt alsnog zijn
--    voorloopnul, zodat een volgende lading hem herkent in plaats van er een
--    nieuwe organisatie naast te zetten.
update organisaties
set kvk_nummer = lpad(kvk_nummer, 8, '0')
where length(kvk_nummer) = 7;
