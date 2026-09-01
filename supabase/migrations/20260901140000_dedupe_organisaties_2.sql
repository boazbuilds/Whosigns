-- Elf dubbel aangemaakte organisaties samenvoegen, ronde 2 (1-9-2026).
--
-- Zelfde oorzaak en zelfde spelregels als 20260901120000: documentroutes
-- maakten naam-rijen zonder KvK, het marktonderzoek KvK-rijen — de
-- hogescholen en de KLM-fondsen bleken bij het voorbereiden van de nieuwe
-- seeds allemaal zo'n tweeling te hebben, en de jaarverslag-lader weigert
-- dan terecht ("staat 2x in de database"). Elk paar is met de hand
-- geverifieerd; de id's horen bij de productiedatabase.
--
-- Nieuw hier: een hernoemveld. Waar de bewaarde KvK-rij een register- of
-- exportnaam draagt ("Stichting Fontys", "Saxion Hogeschool / Saxion",
-- "Avans Hogeschool te Tilburg") krijgt hij de publieksnaam, zodat de
-- seeds en de site dezelfde naam gebruiken. Dat is een leesbaarheids-
-- keuze tussen twee even echte namen, geen datawijziging; de herkomst
-- staat hier.

do $$
declare
  paar record;
begin
  for paar in
    select * from (values
      (20067, 37625, 'Avans Hogeschool'),
      (24941, 32621, 'Hogeschool Utrecht'),
      (30449, 37756, 'Hogeschool Inholland'),
      (24083, 37757, null),                    -- Hogeschool Windesheim
      (25024, 32539, 'Saxion Hogeschool'),
      (30454, 37926, 'Hanzehogeschool Groningen'),
      (24950, 32620, 'Hogeschool Leiden'),
      (20160, 41118, 'Fontys Hogeschool'),
      (20673, 37929, null),                    -- Stichting Hogeschool van Arnhem en Nijmegen
      (19382, 32608, null),                    -- Stichting Algemeen Pensioenfonds KLM
      (19386, 32638, null)                     -- Stichting Pensioenfonds Vliegend Personeel KLM
    ) as p(weg_id, houd_id, naam_nieuw)
  loop
    if not exists (select 1 from organisaties where id = paar.weg_id)
       or not exists (select 1 from organisaties where id = paar.houd_id) then
      continue;  -- al samengevoegd, of andere database: niets te doen
    end if;

    delete from opdrachten o
    where o.organisatie_id = paar.weg_id
      and exists (
        select 1 from opdrachten h
        where h.organisatie_id = paar.houd_id
          and h.boekjaar = o.boekjaar
          and h.type_opdracht = o.type_opdracht
      );
    update opdrachten set organisatie_id = paar.houd_id
    where organisatie_id = paar.weg_id;

    delete from gunningen g
    where g.organisatie_id = paar.weg_id
      and exists (
        select 1 from gunningen h
        where h.organisatie_id = paar.houd_id
          and h.publicatienummer = g.publicatienummer
          and h.kantoor_id = g.kantoor_id
      );
    update gunningen set organisatie_id = paar.houd_id
    where organisatie_id = paar.weg_id;

    delete from signalen s
    where s.organisatie_id = paar.weg_id
      and exists (
        select 1 from signalen h
        where h.organisatie_id = paar.houd_id
          and h.type_signaal = s.type_signaal
          and h.datum = s.datum
      );
    update signalen set organisatie_id = paar.houd_id
    where organisatie_id = paar.weg_id;

    delete from opdrachten o
    where o.organisatie_id = paar.houd_id
      and o.type_opdracht = 'controle_onbepaald'
      and exists (
        select 1 from opdrachten d
        where d.organisatie_id = paar.houd_id
          and d.boekjaar = o.boekjaar
          and d.type_opdracht in ('wettelijke_controle', 'vrijwillige_controle')
      );

    -- Hogescholen horen op de onderwijspagina; een generiek "overheid" van
    -- de weg-rij mag de bewaarde rij niet naar beneden trekken.
    if paar.naam_nieuw is not null then
      update organisaties set naam = paar.naam_nieuw where id = paar.houd_id;
    end if;

    delete from organisaties where id = paar.weg_id;
  end loop;
end $$;
