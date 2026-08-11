-- Een opdracht over boekjaar 2077, en een ondergrens zodat dat niet terugkomt.
--
-- Wat er stond
-- ------------
-- Opdracht 28489: boekjaar 2077, wettelijke controle, bron raadsinformatie,
-- geladen op 5-8-2026. De organisatie eronder (23938) heette
-- "GemeenschappelÍjke regeling Openbaar Lichaam Crematoria Twente" — met een
-- hoofdletter Í midden in "Gemeenschappelijke". Dat is dezelfde verhaspelde
-- regel: de OCR heeft van een gewone "i" een "Í" gemaakt en van het jaartal
-- 2077 iets wat er in het document niet stond. Het echte Openbaar Lichaam
-- Crematoria Twente staat er los in (organisatie 25834) met zijn eigen
-- opdrachten; deze rij was een spookkopie met één onmogelijk jaar.
--
-- Nagemeten op 11-8-2026 over alle 23.017 opdrachten: dit was de enige rij met
-- een boekjaar buiten 2000-2026. De rest loopt van 2007 tot en met 2025.
--
-- De adapter weigert zo'n jaartal inmiddels zelf (`verklaringen_uit` in
-- pipeline/adapters/raadsinformatie.py laat alleen 2000 t/m HUIDIG_JAAR door),
-- dus een volgende lading maakt hem niet opnieuw aan. Deze migratie ruimt op
-- wat er van vóór die controle nog stond, en legt de grens ook in de database
-- vast — een adapter die morgen wordt aangepast kan er dan nog steeds niet
-- omheen.
--
-- Waarom de bovengrens 2035 is en niet "dit jaar"
-- -----------------------------------------------
-- Een check-voorwaarde mag in Postgres niet naar de klok kijken (now() is niet
-- onveranderlijk), dus "niet in de toekomst" kan hier niet. 2035 is ruim genoeg
-- om er tien jaar niet naar om te hoeven kijken en streng genoeg voor waar het
-- om gaat: verhaspelde jaartallen zitten er ver naast (2077, 2177, 7017), niet
-- één jaar. De echte "niet in de toekomst"-controle blijft in de adapter staan,
-- waar de klok wél mag meedoen.

-- 1. Onthouden aan wie deze opdrachten hingen, vóórdat ze weg zijn.
create temporary table geraakte_organisaties as
select distinct organisatie_id as id
  from opdrachten
 where boekjaar < 1990
    or boekjaar > 2035;

-- 2. De opdracht zelf.
delete from opdrachten
 where boekjaar < 1990
    or boekjaar > 2035;

-- 3. De organisatie die dáárdoor leeg achterblijft. Bewust alleen deze ene
--    lijst en geen bredere opruiming: een organisatie zonder opdrachten is op
--    zichzelf niet fout (ze kan uit een register komen en nog op haar eerste
--    verklaring wachten). Weg mag ze alleen als ze door stap 2 haar laatste
--    regel verloor én nergens anders meer aan hangt én geen KvK-nummer heeft —
--    met nummer komt ze uit een register en is ze geen spookkopie.
delete from organisaties o
 using geraakte_organisaties g
 where o.id = g.id
   and o.kvk_nummer is null
   and not exists (select 1 from opdrachten x where x.organisatie_id = o.id)
   and not exists (select 1 from gunningen x where x.organisatie_id = o.id)
   and not exists (select 1 from signalen x where x.organisatie_id = o.id);

drop table geraakte_organisaties;

-- 4. De grens vastleggen. Bewust niet "valid" achteraf toevoegen: als er ooit
--    tóch zo'n rij in staat, wil je dat de migratie stukloopt en niet dat de
--    voorwaarde er ongecontroleerd bij komt te hangen.
alter table opdrachten
  drop constraint if exists opdrachten_boekjaar_plausibel;

alter table opdrachten
  add constraint opdrachten_boekjaar_plausibel
  check (boekjaar between 1990 and 2035);
