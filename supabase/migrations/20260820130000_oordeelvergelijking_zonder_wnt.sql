-- WhoSigns — de oordeelvergelijking mag geen appels met peren vergelijken
--
-- v_oordeel_afwijking legt ons oordeel uit de gedeponeerde verklaring naast het
-- oordeel dat de bron meldt (`bestandAccVerklSoortControleVerkl_N`, het veld per
-- document). Die vergelijking liep tot nu toe over álle opdrachtsoorten, en dat
-- klopt niet: een WNT-verantwoording en een productieverantwoording zijn eigen
-- oordelen over een ánder stuk. Het datasetveld gaat over de controleverklaring
-- bij de jaarrekening. Een WNT-oordeel met beperking náást een goedkeurende
-- jaarrekening is dus geen tegenspraak maar de normale gang van zaken, en stond
-- er toch in.
--
-- Wat het handmatige nakijken opleverde (20-8-2026, boekjaar 2023, 15 rijen)
-- ------------------------------------------------------------------------
-- Van de vijftien afwijkingen zijn er twaalf met de gedeponeerde pdf ernaast
-- gelezen. Alle twaalf keer bleek onze extractie goed en het datasetveld mis:
--
--   wij 'beperking', bron 'goedkeurend'  (8 van de 11 nagekeken)
--     HagaZiekenhuis, Treant Care, Boba Groep, Max Ernst, Jan Arends,
--     Incluzio Hollands Kroon, Vitaal Thuiszorg, De Buitenwereld.
--     Alle acht dragen letterlijk de kop "Ons oordeel met beperking"; de grond
--     is telkens een WNT-aangelegenheid, maar het oordeel over de jaarrekening
--     zélf is aangepast ("uitgezonderd de gevolgen van de aangelegenheid
--     beschreven in de paragraaf 'De basis voor ons oordeel met beperking'").
--     De twee die niet zijn nagekeken (Eurofins Medische Microbiologie, Leids
--     Cytologisch en Pathologisch Laboratorium) zijn gescande pdf's zonder
--     tekstlaag; de bewaarde OCR-tekst was er niet meer.
--
--   wij 'goedkeurend', bron 'beperking'  (3 van de 3 nagekeken)
--     Stichting Dignis, Het Poortje Jeugdinrichtingen, Stichting Kalorama.
--     Alle drie hebben een schone kop "Ons oordeel" plus een aparte alinea
--     "Benadrukking van oordeel met beperking aangaande WNT-gegevens", met de
--     zin "Ons oordeel is niet aangepast als gevolg van deze aangelegenheid".
--     Dat is een benadrukking, geen beperking.
--
--   wij 'beperking' op een wnt_verantwoording, bron 'goedkeurend'  (1)
--     Kayra Zorg en Welzijn. Geen tegenspraak: onze rij gaat over het
--     WNT-stuk, het datasetveld over de jaarrekening. Deze migratie haalt zulke
--     rijen eruit.
--
--   wij 'goedkeurend', bron 'oordeelonthouding'  (1, niet nagekeken)
--     Hervormde Stichting NEBOPLUS. De pdf stond niet meer in de cache.
--
-- De conclusie is dus niet "de extractie moet worden bijgesteld" maar het
-- omgekeerde: het datasetveld haalt het WNT-oordeel en het jaarrekeningoordeel
-- door elkaar, in beide richtingen. Wie hier later naar kijkt: pas de extractie
-- niet aan om de bron te volgen.
--
-- De vergelijking bestaat vandaag alleen voor boekjaar 2023, want dat is het
-- enige boekjaar waarvan de jaardataset is ingelezen (zie
-- pipeline/adapters/digimv.md).

-- Eerst weg, dan opnieuw. `create or replace view` mag alleen kolommen áchteraan
-- toevoegen; `type_opdracht` komt hier middenin de lijst te staan en dan valt
-- psql eruit met "cannot change name of view column". Het hele bestand draait in
-- één transactie (zie .github/workflows/migraties.yml), dus tussen de drop en de
-- create bestaat er geen moment waarop de view weg is. Niets anders leest deze
-- view: de site niet, de pipeline niet -- hij is er om met de hand naar te kijken.
drop view if exists v_oordeel_afwijking;

create view v_oordeel_afwijking with (security_invoker = on) as
select o.organisatie_id,
       org.naam            as organisatie,
       o.boekjaar,
       o.type_opdracht,
       o.oordeel           as oordeel_uit_verklaring,
       o.oordeel_gerapporteerd,
       o.kantoor_id
from opdrachten o
join organisaties org on org.id = o.organisatie_id
where o.oordeel_gerapporteerd is not null
  and o.oordeel is not null
  and o.oordeel <> o.oordeel_gerapporteerd
  -- Alleen de soorten die over de jaarrekening gaan. 'controle_onbepaald' hoort
  -- erbij: dat is ook een oordeel over de jaarrekening, alleen wisten we de
  -- wettelijke grondslag niet -- een afwijking daar is echt review-werk.
  and o.type_opdracht in
      ('wettelijke_controle', 'vrijwillige_controle', 'controle_onbepaald');
