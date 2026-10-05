-- WhoSigns — honoraria: drie eenheidsfouten uit beeld, en wat op de verkeerde
-- opdracht stond terug naar de controle.
--
-- 1. Eenheidsfouten
-- -----------------
-- Drie zorgorganisaties verantwoordden in één jaargang hun honoraria in
-- duizenden euro's in plaats van euro's. Gemeten op 5-10-2026, tegen hun eigen
-- opgave in de jaardataset van het jaar erna (het vergelijkende cijfer):
--
--     KvK 01170406  boekjaar 2020  € 327.805.000  (2021: € 336.000)
--     KvK 69554307  boekjaar 2023  € 231          (2022: € 161.000, 2024: € 251.000)
--     KvK 41177808  boekjaar 2021  € 1.211        (2022: € 888.000)
--
-- Het eerste bedrag zette /honoraria op een gemiddeld controlehonorarium van
-- € 521.917 voor 2020 (zonder die ene rij: € 98.524) en gaf de prijsontwikkeling
-- sprongen van ±99,9%. Delen of vermenigvuldigen met duizend zou een gok zijn,
-- ook al ligt hij voor de hand: alle vier de bedragen van zo'n
-- organisatie-boekjaar gaan op leeg, en het geval gaat naar de review-queue met
-- de oorspronkelijke bedragen erbij. pipeline/vul_extra_velden.py schrijft de
-- foute bedragen daarna niet opnieuw: die toetst elk controlehonorarium nu aan
-- de andere jaren van dezelfde organisatie (factor 50). Wat er wél in komt, is
-- het vergelijkende cijfer uit de jaarverantwoording van het jaar erna — de
-- organisatie heeft daar zelf het juiste bedrag opgegeven (Treant 2020:
-- € 328.000). Dat is haar eigen correctie en geen gok van ons; het review-geval
-- kan dan dicht.
--
-- 2. De verkeerde opdracht
-- ------------------------
-- De vuller schreef de honoraria en het gerapporteerde oordeel op álle
-- opdrachten van een organisatie-boekjaar, dus ook op een WNT- of
-- productieverantwoording. Waar datzelfde organisatie-boekjaar ook een controle
-- heeft, horen ze daar: ze worden verplaatst (alleen naar een leeg veld; in de
-- praktijk stonden ze er al) en op de andere opdracht leeggemaakt. Waar géén
-- controle bestaat, blijven ze staan — er is dan geen betere plek, en weggooien
-- zou een opgave van de organisatie zelf wissen. De site toont ze daar niet
-- meer (web/lib/db.ts, HONORARIUM_FILTER). Wisselvlag en verklaringsdatum
-- blijven ongemoeid; die gebruikt alleen de interne afwijkingenview.

-- 3. Dubbel: gelezen controle én marktonderzoek
-- ----------------------------------------------
-- In 11 organisatie-boekjaren stond hetzelfde honorarium op de gelezen
-- controle én op een "voorwerp onbekend"-rij uit het marktonderzoek ernaast, en
-- /honoraria telde het twee keer. Waar de gelezen controle een honorarium
-- heeft, gaan die op de marktonderzoekrij op leeg. De vuller schrijft daar ook
-- niet meer naartoe zolang er een gelezen controle is.
--
-- 4. Negatieve bedragen
-- --------------------
-- Vier honoraria "niet-controle" waren negatief (-1.699 tot -42.000): een
-- vrijval of correctie op een eerder jaar, geen honorarium. De dataset-lezer
-- slaat ze voortaan over (adapters/digimv_dataset.py, _bedrag); de bestaande
-- gaan op leeg.

alter table review_queue drop constraint if exists review_queue_soort_check;
alter table review_queue add constraint review_queue_soort_check
  check (soort in ('ai_extractie', 'naam_match', 'plausibiliteit'));

create temporary table eenheidsfout (kvk text, boekjaar int) on commit drop;
insert into eenheidsfout values
  ('01170406', 2020),
  ('69554307', 2023),
  ('41177808', 2021);

-- Eerst vastleggen wat er stond, dan pas leegmaken: de review-queue moet de
-- oorspronkelijke bedragen hebben, anders valt er niets na te kijken.
insert into review_queue (soort, payload)
select 'plausibiliteit',
       jsonb_build_object(
         'bron', 'migratie 20261005150000',
         'kvk_nummer', org.kvk_nummer,
         'boekjaar', o.boekjaar,
         'honoraria', jsonb_build_object(
           'honorarium_controle', o.honorarium_controle_eur,
           'honorarium_overig', o.honorarium_overig_eur,
           'honorarium_fiscaal', o.honorarium_fiscaal_eur,
           'honorarium_nietcontrole', o.honorarium_nietcontrole_eur),
         'reden', 'eenheidsfout: wijkt een factor ~1.000 af van de andere jaren')
  from opdrachten o
  join organisaties org on org.id = o.organisatie_id
  join eenheidsfout f on f.kvk = org.kvk_nummer and f.boekjaar = o.boekjaar
 where o.honorarium_controle_eur is not null
   and not exists (
     select 1 from review_queue r
      where r.soort = 'plausibiliteit' and r.status = 'open'
        and r.payload->>'kvk_nummer' = org.kvk_nummer
        and r.payload->>'boekjaar' = o.boekjaar::text);

update opdrachten o
   set honorarium_controle_eur = null,
       honorarium_overig_eur = null,
       honorarium_fiscaal_eur = null,
       honorarium_nietcontrole_eur = null
  from organisaties org, eenheidsfout f
 where org.id = o.organisatie_id
   and f.kvk = org.kvk_nummer
   and f.boekjaar = o.boekjaar;

update opdrachten c
   set honorarium_controle_eur     = coalesce(c.honorarium_controle_eur, w.honorarium_controle_eur),
       honorarium_overig_eur       = coalesce(c.honorarium_overig_eur, w.honorarium_overig_eur),
       honorarium_fiscaal_eur      = coalesce(c.honorarium_fiscaal_eur, w.honorarium_fiscaal_eur),
       honorarium_nietcontrole_eur = coalesce(c.honorarium_nietcontrole_eur, w.honorarium_nietcontrole_eur),
       oordeel_gerapporteerd       = coalesce(c.oordeel_gerapporteerd, w.oordeel_gerapporteerd)
  from opdrachten w
 where w.organisatie_id = c.organisatie_id
   and w.boekjaar = c.boekjaar
   and w.type_opdracht in ('wnt_verantwoording', 'productieverantwoording')
   and c.type_opdracht in ('wettelijke_controle', 'vrijwillige_controle', 'controle_onbepaald')
   and (w.honorarium_controle_eur is not null or w.honorarium_overig_eur is not null
        or w.honorarium_fiscaal_eur is not null or w.honorarium_nietcontrole_eur is not null
        or w.oordeel_gerapporteerd is not null);

update opdrachten w
   set honorarium_controle_eur = null,
       honorarium_overig_eur = null,
       honorarium_fiscaal_eur = null,
       honorarium_nietcontrole_eur = null,
       oordeel_gerapporteerd = null
 where w.type_opdracht in ('wnt_verantwoording', 'productieverantwoording')
   and exists (
     select 1 from opdrachten c
      where c.organisatie_id = w.organisatie_id
        and c.boekjaar = w.boekjaar
        and c.type_opdracht in ('wettelijke_controle', 'vrijwillige_controle', 'controle_onbepaald'));

update opdrachten set honorarium_controle_eur = null where honorarium_controle_eur <= 0;
update opdrachten set honorarium_overig_eur = null where honorarium_overig_eur <= 0;
update opdrachten set honorarium_fiscaal_eur = null where honorarium_fiscaal_eur <= 0;
update opdrachten set honorarium_nietcontrole_eur = null where honorarium_nietcontrole_eur <= 0;

update opdrachten m
   set honorarium_controle_eur = null,
       honorarium_overig_eur = null,
       honorarium_fiscaal_eur = null,
       honorarium_nietcontrole_eur = null
 where m.type_opdracht = 'controle_onbepaald'
   and exists (
     select 1 from opdrachten g
      where g.organisatie_id = m.organisatie_id
        and g.boekjaar = m.boekjaar
        and g.type_opdracht in ('wettelijke_controle', 'vrijwillige_controle')
        and (g.honorarium_controle_eur is not null or g.honorarium_overig_eur is not null
             or g.honorarium_fiscaal_eur is not null or g.honorarium_nietcontrole_eur is not null));
