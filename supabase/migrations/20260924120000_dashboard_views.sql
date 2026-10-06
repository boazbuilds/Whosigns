-- WhoSigns — samenvattingen per boekjaar voor de voorpagina
--
-- De voorpagina laat voortaan per boekjaar zien hoe vaak er werd gewisseld en
-- hoe vaak een oordeel niet goedkeurend was. PostgREST kan niet groeperen, en
-- de ruwe rijen ophalen om in de website te tellen kost bij 9.500 gelezen
-- oordelen tien verzoeken per paginabouw. Daarom twee kleine views van een
-- rij of twintig — en de definitie staat daarmee in SQL, naast v_wisselingen
-- en v_marktaandeel, zodat database en website hetzelfde antwoord geven.

-- Oordelen per boekjaar
-- ---------------------
-- Alleen jaarrekeningcontroles (wettelijk en vrijwillig, dezelfde set als
-- v_marktaandeel) en alleen het oordeel uit de verklaring zélf: een eigen
-- opgave van de organisatie (`oordeel_gerapporteerd`) is geen gelezen
-- verklaring. WNT- en productieverantwoordingen blijven erbuiten; hun oordeel
-- gaat niet over de jaarrekening. /bevindingen telt die wél mee, want daar
-- gaat het om elke bijzondere verklaring — vandaar dat de aantallen daar iets
-- hoger zijn.
--
-- De grond van een beperking staat er apart bij. Vanaf boekjaar 2023 is de
-- sprong in beperkingen grotendeels een golf WNT-beperkingen, geen
-- verslechtering van de jaarrekeningen (zie /bevindingen); wie alleen het
-- totaal ziet, leest dat verkeerd. Bij veel beperkingen is de grond nog niet
-- vastgesteld — die tellen dan in geen van beide deelkolommen.
create or replace view v_oordelen_per_jaar with (security_invoker = on) as
select boekjaar,
       count(*)::int as gelezen,
       count(*) filter (where oordeel = 'goedkeurend')::int as goedkeurend,
       count(*) filter (where oordeel = 'beperking')::int as beperking,
       count(*) filter (where oordeel = 'beperking'
                          and grond_beperking = 'wnt')::int as beperking_wnt,
       count(*) filter (where oordeel = 'beperking'
                          and grond_beperking = 'inhoudelijk')::int as beperking_inhoudelijk,
       count(*) filter (where oordeel = 'oordeelonthouding')::int as oordeelonthouding,
       count(*) filter (where oordeel = 'afkeurend')::int as afkeurend,
       count(*) filter (where continuiteitsonzekerheid)::int as continuiteit
from opdrachten
where type_opdracht in ('wettelijke_controle', 'vrijwillige_controle')
  and oordeel is not null
group by boekjaar;

comment on view v_oordelen_per_jaar is
  'Gelezen oordelen bij jaarrekeningcontroles per boekjaar, uitgesplitst naar soort oordeel en grond van de beperking.';

-- Wisselingen per boekjaar, met de noemer erbij
-- ---------------------------------------------
-- Het aantal wisselingen per jaar zegt op zichzelf weinig: het groeit mee met
-- hoeveel organisaties er voor dat jaar in de database staan. De noemer maakt
-- er een kans van: organisaties met een controle in het jaar ervóór én in dit
-- jaar — precies de paren waartussen v_wisselingen een wisseling kán vinden.
--
-- Daarnaast dezelfde vraag als het label "na slecht nieuws" op /wisselingen
-- (Chow & Rice 1982; Lennox 2000): wisselen organisaties vaker na een
-- niet-goedkeurende verklaring of een continuïteitspassage? Het oordeel vooraf
-- komt uit het boekjaar vóór de wisseling, met dezelfde voorrang als
-- `oordelenVoorafAanWissels` in web/lib/db.ts: de wettelijke controle gaat voor
-- de vrijwillige, en die voor "voorwerp onbekend". Paren zonder gelezen
-- oordeel vooraf vallen in geen van beide groepen; de vergelijking gaat dus
-- alleen over jaren waarin de verklaring echt is gelezen.
create or replace view v_wisselingen_per_jaar with (security_invoker = on) as
with controles as (
  select distinct organisatie_id, boekjaar
  from opdrachten
  where type_opdracht in ('wettelijke_controle', 'vrijwillige_controle')
    and kantoor_id is not null
),
paren as (
  select nu.organisatie_id, nu.boekjaar
  from controles nu
  join controles vorig
    on  vorig.organisatie_id = nu.organisatie_id
    and vorig.boekjaar = nu.boekjaar - 1
),
gewisseld as (
  select distinct organisatie_id, boekjaar_wissel as boekjaar
  from v_wisselingen
),
vooraf as (
  select distinct on (organisatie_id, boekjaar)
         organisatie_id,
         boekjaar as boekjaar_vooraf,
         (oordeel is not null and oordeel <> 'goedkeurend')
           or coalesce(continuiteitsonzekerheid, false) as slecht,
         coalesce(oordeel = 'goedkeurend', false)
           and not coalesce(continuiteitsonzekerheid, false) as goedkeurend
  from opdrachten
  where type_opdracht in ('wettelijke_controle', 'vrijwillige_controle', 'controle_onbepaald')
  order by organisatie_id,
           boekjaar,
           array_position(
             array['wettelijke_controle', 'vrijwillige_controle', 'controle_onbepaald'],
             type_opdracht
           ),
           id
)
select p.boekjaar,
       count(*)::int as paren,
       count(g.organisatie_id)::int as wisselingen,
       count(*) filter (where v.slecht)::int as paren_na_slecht_nieuws,
       count(g.organisatie_id) filter (where v.slecht)::int as wisselingen_na_slecht_nieuws,
       count(*) filter (where v.goedkeurend)::int as paren_na_goedkeurend,
       count(g.organisatie_id) filter (where v.goedkeurend)::int as wisselingen_na_goedkeurend
from paren p
left join gewisseld g
  on g.organisatie_id = p.organisatie_id and g.boekjaar = p.boekjaar
left join vooraf v
  on v.organisatie_id = p.organisatie_id and v.boekjaar_vooraf = p.boekjaar - 1
group by p.boekjaar;

comment on view v_wisselingen_per_jaar is
  'Per boekjaar: organisaties met een controle in dit en het vorige jaar, hoeveel daarvan van kantoor wisselden, en dezelfde telling na een niet-goedkeurend respectievelijk goedkeurend oordeel vooraf.';
