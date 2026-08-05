-- Dubbele corporaties samenvoegen: KvK-nummers die in de bron zijn afgerond.
--
-- Wat er mis ging
-- ---------------
-- De jaargangen dVi2010, dVi2011 en dVi2012 slaan het KvK-nummer op als getal
-- met te weinig precisie, waardoor het laatste cijfer wegvalt:
--
--     dVi2010  14614730   16024740   36003600
--     dVi2013  14614733   16024737   36003604   <- de echte nummers
--
-- Gemeten over alle jaargangen eindigt in 2010 t/m 2012 82-83% van de nummers
-- op een nul, tegen twaalf procent in 2013 en 2014 — en dat laatste is gewoon
-- toeval. Het KvK-nummer is de sleutel waarop organisaties worden samengevoegd,
-- dus zo'n afgerond nummer wees naar niemand en kwam er als nieuwe organisatie
-- bij. 164 corporaties stonden er daardoor twee keer in, elk met een deel van
-- hun geschiedenis en dus zonder zichtbare wisselingen.
--
-- Dit is dezelfde klasse fout als de voorloopnullen (migratie 20260805150000),
-- maar met een andere oorzaak: daar schreef de bron hetzelfde nummer anders op,
-- hier is het nummer zelf beschadigd.
--
-- Wat deze migratie doet
-- ----------------------
-- De rij met het onafgeronde nummer is de blijver. Een dubbelganger herken je
-- aan drie dingen tegelijk: dezelfde naam, een KvK-nummer dat op nul eindigt,
-- en een nummer dat precies de afronding op tientallen is van dat van de
-- blijver. Alle drie moeten kloppen — een corporatie waarvan het echte
-- KvK-nummer toevallig op nul eindigt heeft geen dubbelganger en blijft dus
-- met rust.
--
-- De adapter weigert zo'n kolom nu (`kvk_kolom_is_afgerond` in
-- adapters/aw_dvi.py), dus een volgende lading maakt ze niet opnieuw aan; die
-- vult het nummer via het corporatienummer aan.

create temporary table samen_te_voegen as
select nieuw.id as weg, oud.id as blijft
from organisaties nieuw
join organisaties oud
  on oud.id <> nieuw.id
 and oud.sector = 'woningcorporaties'
 and nieuw.sector = 'woningcorporaties'
 and regexp_replace(lower(oud.naam), '[^a-z0-9]', '', 'g')
   = regexp_replace(lower(nieuw.naam), '[^a-z0-9]', '', 'g')
 -- de dubbelganger eindigt op nul, de blijver niet
 and nieuw.kvk_nummer ~ '^[0-9]+0$'
 and oud.kvk_nummer !~ '0$'
 -- en het nummer van de dubbelganger is de afronding van dat van de blijver
 and round(oud.kvk_nummer::numeric / 10) * 10 = nieuw.kvk_nummer::numeric;

-- 1. Opdrachten verhuizen, zonder de unieke sleutel te schenden.
update opdrachten o
set organisatie_id = s.blijft
from samen_te_voegen s
where o.organisatie_id = s.weg
  and not exists (
    select 1 from opdrachten bestaand
    where bestaand.organisatie_id = s.blijft
      and bestaand.boekjaar = o.boekjaar
      and bestaand.type_opdracht = o.type_opdracht
  );

delete from opdrachten o
using samen_te_voegen s
where o.organisatie_id = s.weg;

-- 2. Hetzelfde voor gunningen.
update gunningen g
set organisatie_id = s.blijft
from samen_te_voegen s
where g.organisatie_id = s.weg
  and not exists (
    select 1 from gunningen bestaand
    where bestaand.publicatienummer = g.publicatienummer
      and bestaand.organisatie_id = s.blijft
      and bestaand.kantoor_id = g.kantoor_id
  );

delete from gunningen g
using samen_te_voegen s
where g.organisatie_id = s.weg;

-- 3. De dubbelgangers zelf.
delete from organisaties o
using samen_te_voegen s
where o.id = s.weg;

drop table samen_te_voegen;
