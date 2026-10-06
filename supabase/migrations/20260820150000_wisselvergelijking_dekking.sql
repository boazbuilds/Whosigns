-- WhoSigns — "geen wisseling afgeleid" is niet hetzelfde als "geen wisseling"
--
-- v_wissel_afwijking legt het wisselantwoord uit de jaardataset naast wat onze
-- eigen historie zegt. De view keek daarbij alleen naar de uitkomst, niet naar
-- de vraag of we die uitkomst überhaupt kónden afleiden. Een wisseling volgt uit
-- twee opeenvolgende boekjaren met een jaarrekeningcontrole; ontbreekt één van
-- die twee, dan levert de afleiding "geen wisseling" op omdat er niets staat --
-- niet omdat er niets gebeurd is.
--
-- Wat er in de lijst stond (gemeten 20-8-2026)
-- -------------------------------------------
-- 104 opdrachtrijen dragen een wisselantwoord, allemaal boekjaar 2023 (het enige
-- jaar waarvan de jaardataset is ingelezen): 92 keer "nee", 12 keer "ja". Van die
-- 104 zijn er 71 vergelijkbaar -- een jaarrekeningcontrole in zowel 2023 als 2022
-- -- en 33 niet.
--
-- De view meldde zes afwijkingen, alle zes "wél gemeld, niet afgeleid". Vijf
-- ervan hebben in geen van beide jaren een jaarrekeningcontrole in de database:
--
--   103   H.A.J. van de Ven en M.S. van de Ven-Blom  alleen productieverantwoording
--   142   Moai Seldsum B.V.                          alleen WNT-verantwoording
--   151   Opgroeiconsult V.O.F.                      alleen productieverantwoording
--   158   Praktijk Forza B.V.                        alleen WNT-verantwoording
--   19752 SenseZorg B.V.                             alleen productieverantwoording
--
-- Voor die vijf zegt "niet afgeleid" niets over de organisatie; het zegt iets
-- over onze dekking. Het is wel een aanwijzing: de organisatie meldt zelf een
-- wisseling van accountant, dus er is een jaarrekeningcontrole die wij nog niet
-- gevonden hebben. Daarom blijven ze in de lijst staan, maar nu met een kolom
-- erbij die zegt dat ze niet vergelijkbaar zijn.
--
-- Praktijk Forza (158) is het aardigste geval: SMK Audit in 2022, Eshuis in 2023
-- -- er ís een kantoorwissel, maar op de WNT-verantwoording, en die telt niet mee
-- voor v_wisselingen. Het antwoord van de organisatie klopt dus vermoedelijk,
-- alleen niet op het stuk waar deze view naar kijkt.
--
-- Eén geval blijft over als echte tegenspraak: Stichting Centrum voor Jeugd en
-- Gezin Midden (249). Wettelijke controle door Crowe Foederer in 2022, 2023, 2024
-- én 2025, onafgebroken, terwijl de organisatie over 2023 "ja, gewisseld" meldt.
-- De pdf's van 2022 en 2023 stonden niet meer in de cache, dus dit is nog niet
-- uitgezocht. Wat wel meeweegt: `wissel_gerapporteerd` komt uit
-- `qAccountantWissel_qAccVerklVorm`, een vragenlijstveld -- dezelfde familie waar
-- dit project het oordeel al niet meer van overneemt (zie de LET OP in
-- 20260729230000_oordeel_uit_dataset.sql, en de meting van 20-8-2026 waarin
-- twaalf van de twaalf nagekeken oordeelafwijkingen in ons voordeel uitvielen).
--
-- Eerst weg, dan opnieuw: `create or replace view` mag alleen kolommen achteraan
-- toevoegen, en hier komen `organisatie` en `vergelijkbaar` er middenin bij. Het
-- bestand draait in één transactie (zie .github/workflows/migraties.yml). Niets
-- anders leest deze view -- de site niet, de pipeline niet.

drop view if exists v_wissel_afwijking;

create view v_wissel_afwijking with (security_invoker = on) as
with jaarrekening as (
  -- Dezelfde afbakening als v_wisselingen: een WNT- of productieverantwoording
  -- is een eigen opdracht en zegt niets over wie de jaarrekening controleert.
  select organisatie_id, boekjaar
  from opdrachten
  where type_opdracht in ('wettelijke_controle', 'vrijwillige_controle')
    and kantoor_id is not null
)
-- distinct: het wisselantwoord hangt aan een opdrachtrij, en één
-- organisatie-boekjaar mag meer dan één rij hebben (de unieke sleutel is
-- organisatie + boekjaar + type). Vandaag komt dat niet voor; dit houdt het zo.
select distinct
       o.organisatie_id,
       org.naam                        as organisatie,
       o.boekjaar,
       o.wissel_gerapporteerd,
       (w.organisatie_id is not null)  as wissel_afgeleid,
       (exists (select 1 from jaarrekening j
                 where j.organisatie_id = o.organisatie_id
                   and j.boekjaar = o.boekjaar)
        and exists (select 1 from jaarrekening j
                     where j.organisatie_id = o.organisatie_id
                       and j.boekjaar = o.boekjaar - 1)) as vergelijkbaar
from opdrachten o
join organisaties org on org.id = o.organisatie_id
left join v_wisselingen w
  on  w.organisatie_id = o.organisatie_id
  and w.boekjaar_wissel = o.boekjaar
where o.wissel_gerapporteerd is not null
  and o.wissel_gerapporteerd <> (w.organisatie_id is not null);

comment on view v_wissel_afwijking is
  'Nakijklijst: het gemelde wisselantwoord naast de afgeleide wisseling. '
  'Kijk eerst naar vergelijkbaar = true; is die false, dan ontbreekt een van '
  'de twee boekjaren en zegt de afleiding niets over de organisatie.';
