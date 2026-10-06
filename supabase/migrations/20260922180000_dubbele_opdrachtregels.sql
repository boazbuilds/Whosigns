-- "Controle, voorwerp onbekend" opruimen waar de verklaring zelf gelezen is,
-- en de vier gevallen waar de twee bronnen elkaar tegenspreken zichtbaar maken.
--
-- De regel bestond al, maar alleen met terugwerkende kracht
-- ------------------------------------------------------------------------
-- Het aangeleverde marktonderzoek levert `controle_onbepaald`: er wás een
-- accountant, maar niet is vastgesteld waarover. Zodra van hetzelfde
-- organisatie-boekjaar de verklaring zélf is gelezen, is die rij overbodig —
-- en dat staat ook zo in 20260901120000 en 20260922160000, maar die pasten
-- het alleen toe op de paren die ze samenvoegden.
--
-- `laad_marktonderzoek.py` kijkt bij het laden of er al een controle staat en
-- slaat dan over, dus in die richting gaat het goed. Andersom niet: een
-- documentroute die later een gelezen controle toevoegt laat de oude rij
-- staan. Gemeten op 22-9-2026: 681 organisatie-boekjaren dragen allebei, en op
-- de organisatiepagina staat datzelfde jaar dus twee keer.
--
-- Wat hier níét wordt weggegooid
-- ------------------------------
-- Van die 681 wijzen er 677 naar hetzelfde kantoor; dat is enkel dubbel. Vier
-- wijzen naar een ánder kantoor:
--
--     organisatie 9173  boekjaar 2024
--     organisatie 9180  boekjaar 2024
--     organisatie 9217  boekjaar 2024
--     organisatie 14765 boekjaar 2024
--
-- Daar zegt het marktonderzoek een andere naam dan de gedeponeerde verklaring.
-- Dat is geen dubbeling maar een tegenspraak, en die hoort niet stil te
-- verdwijnen. Deze migratie laat ze staan en zet er een view omheen, zoals
-- v_oordeel_afwijking dat doet voor het oordeel: tonen en zeggen, niet
-- kiezen. De verklaring is het sterkere bewijs — wij hebben hem zelf gelezen
-- — maar welke van de twee bij een fusiejaar of een gebroken boekjaar klopt,
-- is uit deze gegevens niet te zeggen.

delete from opdrachten onbepaald
where onbepaald.type_opdracht = 'controle_onbepaald'
  and exists (
    select 1
    from opdrachten gelezen
    where gelezen.organisatie_id = onbepaald.organisatie_id
      and gelezen.boekjaar = onbepaald.boekjaar
      and gelezen.type_opdracht in ('wettelijke_controle', 'vrijwillige_controle')
      and gelezen.kantoor_id is not distinct from onbepaald.kantoor_id
  );

-- Waar de twee bronnen een ánder kantoor noemen voor hetzelfde boekjaar.
create or replace view v_kantoor_afwijking with (security_invoker = on) as
select onbepaald.organisatie_id,
       onbepaald.boekjaar,
       onbepaald.kantoor_id  as kantoor_gemeld,
       gelezen.kantoor_id    as kantoor_gelezen,
       gelezen.type_opdracht as type_gelezen
from opdrachten onbepaald
join opdrachten gelezen
  on gelezen.organisatie_id = onbepaald.organisatie_id
 and gelezen.boekjaar = onbepaald.boekjaar
 and gelezen.type_opdracht in ('wettelijke_controle', 'vrijwillige_controle')
where onbepaald.type_opdracht = 'controle_onbepaald'
  and onbepaald.kantoor_id is distinct from gelezen.kantoor_id;

comment on view v_kantoor_afwijking is
  'Organisatie-boekjaren waar het aangeleverde marktonderzoek een ander '
  'kantoor noemt dan de gedeponeerde verklaring die wij zelf lazen. Geen '
  'dubbeling maar een tegenspraak: tonen, niet kiezen. Zie '
  'v_oordeel_afwijking voor dezelfde aanpak bij het oordeel.';
