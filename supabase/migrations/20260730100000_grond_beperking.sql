-- Waar gaat een oordeel met beperking over?
--
-- Aanleiding: het aandeel niet-goedkeurende oordelen springt van 0,8% in boekjaar
-- 2022 naar 10,5% in 2023. Dat leek een extractiefout, maar 26 opgehaalde
-- verklaringen wijzen anders uit: de beperkingen zijn echt, en 23 van de 26 gaan
-- over WNT-aangelegenheden bij intragroepdetachering. De accountant kan de
-- WNT-gegevens van binnen een groep gedetacheerde topfunctionarissen niet
-- vaststellen; dat is een beperking in de informatie, geen bevinding over de
-- jaarrekening.
--
-- Zonder dit veld toont de site "oordeel met beperking" naast de naam van een
-- ziekenhuis en leest iedereen daar iets in wat er niet staat.
--
--   wnt          de beperking betreft WNT/anticumulatie/topinkomens
--   inhoudelijk  de beperking betreft de jaarrekening zelf
--   NULL         grond niet vastgesteld -- een echte uitkomst, geen fout

alter table opdrachten
  add column if not exists grond_beperking text
    check (grond_beperking in ('wnt', 'inhoudelijk'));

comment on column opdrachten.grond_beperking is
  'Grond van het oordeel met beperking: wnt | inhoudelijk | NULL (niet vastgesteld). '
  'Alleen gevuld bij oordeel = beperking.';

-- Beperkingen op een rij, met de grond erbij. Dit is de lijst waar de website de
-- pagina /oordelen op bouwt en waarmee je in één blik ziet of een golf beperkingen
-- over de jaarrekening gaat of over WNT.
create or replace view v_beperkingen with (security_invoker = on) as
select o.boekjaar,
       o.organisatie_id,
       o.kantoor_id,
       o.type_opdracht,
       o.oordeel,
       o.grond_beperking,
       o.continuiteitsonzekerheid,
       org.naam    as organisatie_naam,
       org.sector,
       org.subsector,
       org.gemeente
from opdrachten o
join organisaties org on org.id = o.organisatie_id
where o.oordeel in ('beperking', 'oordeelonthouding', 'afkeurend')
   or o.continuiteitsonzekerheid;
