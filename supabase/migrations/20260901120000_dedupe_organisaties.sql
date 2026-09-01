-- Zeven dubbel aangemaakte organisaties samenvoegen (1-9-2026).
--
-- Hoe de dubbelen ontstonden: de documentroutes (transparantieverslagen,
-- gunningen, raadsinformatie, jaarverslagen) maken organisaties op náám aan,
-- zonder KvK-nummer; het aangeleverde marktonderzoek maakt ze op KvK-nummer
-- aan. Dezelfde organisatie kreeg zo twee rijen, en de jaarverslag-lader
-- weigerde er terecht bij te laden ("staat 2x in de database").
--
-- Per paar is met de hand vastgesteld dat het écht dezelfde organisatie is;
-- Shell is bewust NIET samengevoegd (Stichting Shell Pensioenfonds en Shell
-- Nederland Pensioenfonds Stichting zijn twee verschillende fondsen, SSPF en
-- SNPS). De id's zijn hard: er is één productiedatabase en dit bestand hoort
-- bij de stand van die database; op een lege database doet de lus niets,
-- want beide rijen van een paar moeten bestaan.
--
-- Spelregels bij het samenvoegen:
-- 1. De rij mét KvK-nummer blijft (stabiele sleutel voor alle latere ladingen);
--    bij twee naamrijen blijft de rij met de officiële naam.
-- 2. Opdrachten, gunningen en signalen verhuizen mee. Een opdracht die door de
--    verhuizing dubbel zou worden (zelfde boekjaar en type bestaat al bij de
--    bewaarde rij) vervalt aan de kant van de weg-rij.
-- 3. "Controle, voorwerp onbekend" (marktonderzoek) vervalt zodra hetzelfde
--    boekjaar op de samengevoegde rij een echte gelezen controle heeft —
--    dezelfde regel die de lader bij het laden hanteert, hier met
--    terugwerkende kracht.

do $$
declare
  paar record;
begin
  for paar in
    select * from (values
      (19385, 32633, null),         -- Stichting Pensioenfonds PGB
      (19371, 32468, 'OOB'),        -- PostNL N.V.: beursfonds, het curated
                                    -- OOB-label wint van het SBI-hokje
      (19449, 37086, null),         -- Stichting Pensioenfonds PostNL
      (19522, 32785, null),         -- Stichting Bedrijfstakpensioenfonds voor de
                                    -- Detailhandel = Stichting Pensioenfonds
                                    -- Detailhandel (zelfde fonds, oude naam)
      (20240, 24077, 'onderwijs'),  -- Tilburg University ("/ Universiteit van
                                    -- Tilburg"-variant weg; sector was overheid)
      (24985, 32719, null),         -- Universiteit Twente
      (25392, 20093, null)          -- Gemeente Tilburg ("Gemeente Tilburg
                                    -- Tilburg"-variant uit raadsinformatie weg)
    ) as p(weg_id, houd_id, sector_nieuw)
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

    -- Gunningen en signalen hebben ook unieke sleutels met organisatie_id
    -- erin; zelfde patroon: wat door de verhuizing dubbel zou worden vervalt
    -- eerst aan de kant van de weg-rij.
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

    if paar.sector_nieuw is not null then
      update organisaties set sector = paar.sector_nieuw
      where id = paar.houd_id;
    end if;

    delete from organisaties where id = paar.weg_id;
  end loop;
end $$;
