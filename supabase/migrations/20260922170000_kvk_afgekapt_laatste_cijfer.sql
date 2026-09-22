-- De laatste negen corporaties met een beschadigd KvK-nummer.
--
-- Migratie 20260922160000 voegde de afgeronde nummers samen met de regel uit
-- 20260805190000: `round(echt / 10) * 10 = afgerond`. Die vangt alles behalve
-- de nummers die op een 5 eindigen. 17060165 rondt af op 17060170, maar in de
-- bron staat 17060160 — daar is het laatste cijfer niet afgerond maar
-- wéggevallen. Negen paren bleven daardoor staan, elk een corporatie met een
-- in tweeën geknipte geschiedenis:
--
--     Woningstichting de Zaligheden   17060165  /  17060160
--     Stichting Woonveste             18115545  /  18115540
--     Laurentius                      20024605  /  20024600
--     WonenBreburg                    20067125  /  20067120
--     Woningbouwvereniging Alkemade   28032485  /  28032480
--     SSH Utrecht                     30092565  /  30092560
--     Vitalis                         31036365  /  31036360
--     AWV Eigen Haard                 34090425  /  34090420
--     Woningstichting Nijkerk         41042105  /  41042100
--
-- De regel hier is daarom niet "is de afronding van" maar "is hetzelfde
-- nummer met het laatste cijfer op nul", bij dezelfde naam en dezelfde
-- lengte. Dat is strikt genoeg: twee verschillende corporaties met dezelfde
-- naam verschillen niet in één cijfer. De vijftig groepen die overblijven
-- hebben dan ook echt verschillende nummers — "Woningbouwvereniging Beter
-- Wonen" bestaat vijf keer, in vijf plaatsen, met vijf nummers — en die
-- blijven met rust.
--
-- Zelfde verhuisregels en zelfde volgorde als 20260922160000.

do $$
declare
  paar record;
  aantal int := 0;
begin
  for paar in
    select afgekapt.id as weg, echt.id as houd
    from organisaties afgekapt
    join organisaties echt
      on echt.id <> afgekapt.id
     and regexp_replace(lower(echt.naam), '[^a-z0-9]', '', 'g')
       = regexp_replace(lower(afgekapt.naam), '[^a-z0-9]', '', 'g')
     and afgekapt.kvk_nummer ~ '^[0-9]+0$'
     and echt.kvk_nummer ~ '^[0-9]*[1-9]$'
     and length(echt.kvk_nummer) = length(afgekapt.kvk_nummer)
     and left(echt.kvk_nummer, length(echt.kvk_nummer) - 1)
       = left(afgekapt.kvk_nummer, length(afgekapt.kvk_nummer) - 1)
  loop
    if not exists (select 1 from organisaties where id = paar.weg)
       or not exists (select 1 from organisaties where id = paar.houd) then
      continue;
    end if;

    delete from opdrachten o
    where o.organisatie_id = paar.weg
      and exists (
        select 1 from opdrachten h
        where h.organisatie_id = paar.houd
          and h.boekjaar = o.boekjaar
          and h.type_opdracht = o.type_opdracht
      );
    update opdrachten set organisatie_id = paar.houd where organisatie_id = paar.weg;

    delete from gunningen g
    where g.organisatie_id = paar.weg
      and exists (
        select 1 from gunningen h
        where h.organisatie_id = paar.houd
          and h.publicatienummer = g.publicatienummer
          and h.kantoor_id = g.kantoor_id
      );
    update gunningen set organisatie_id = paar.houd where organisatie_id = paar.weg;

    delete from signalen s
    where s.organisatie_id = paar.weg
      and exists (
        select 1 from signalen h
        where h.organisatie_id = paar.houd
          and h.type_signaal = s.type_signaal
          and h.datum = s.datum
      );
    update signalen set organisatie_id = paar.houd where organisatie_id = paar.weg;

    delete from opdrachten o
    where o.organisatie_id = paar.houd
      and o.type_opdracht = 'controle_onbepaald'
      and exists (
        select 1 from opdrachten d
        where d.organisatie_id = paar.houd
          and d.boekjaar = o.boekjaar
          and d.type_opdracht in ('wettelijke_controle', 'vrijwillige_controle')
      );

    delete from organisaties where id = paar.weg;
    aantal := aantal + 1;
  end loop;

  raise notice 'afgekapte KvK-nummers samengevoegd: %', aantal;
end $$;
