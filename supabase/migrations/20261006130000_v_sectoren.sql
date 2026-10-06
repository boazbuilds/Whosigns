-- WhoSigns — sectoren en subsectoren met hun aantal organisaties
--
-- Het sectormenu staat in de layout, dus op élke pagina. Om het te vullen
-- haalde de website de sectorkolom van alle organisaties op en telde in
-- TypeScript: op 5-10-2026 17.230 rijen in 18 verzoeken van duizend, na
-- elkaar, ~410 KB. Een organisatiepagina die koud werd opgebouwd deed 27
-- verzoeken naar Supabase, waarvan 18 voor dit menu. PostgREST kan niet
-- groeperen, dus hoort hier een view tegenover te staan — zoals web/lib/db.ts
-- bij subsectoren() al aankondigde.
--
-- De website valt terug op de oude telling zolang deze migratie niet heeft
-- gedraaid (zolangNieuw in web/lib/db.ts): site en migratie komen bij een
-- merge niet op dezelfde seconde aan.
--
-- Zelfde voorwaarde als de oude telling: een lege sector telt niet mee. Er
-- staan op 5-10-2026 geen lege tekenreeksen in, maar een sector "" zou in het
-- menu een knop zonder naam worden.

create or replace view v_sectoren with (security_invoker = on) as
select sector as naam,
       count(*)::int as aantal
from organisaties
where sector is not null
  and sector <> ''
group by sector;

comment on view v_sectoren is
  'Sectoren met het aantal organisaties erin, voor het sectormenu en /sectoren.';

create or replace view v_subsectoren with (security_invoker = on) as
select subsector as naam,
       count(*)::int as aantal
from organisaties
where subsector is not null
  and subsector <> ''
group by subsector;

comment on view v_subsectoren is
  'Subsectoren met het aantal organisaties erin, voor /sectoren en de subsectorpagina.';
