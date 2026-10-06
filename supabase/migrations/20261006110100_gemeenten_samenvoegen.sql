-- Dubbele gemeenten samenvoegen: "Gemeentehuis X", "Gemeente X te X
-- ('de gemeente')" en "Gemeente X" zijn dezelfde gemeente.
--
-- Hoe de dubbelen ontstonden: het marktonderzoek levert een gemeente aan onder
-- de handelsnaam van een vestiging ("Gemeentehuis Best", "Stadhuis Zutphen",
-- "Gemeente Leudal, vestiging Heythuysen"), mét KvK-nummer. Raadsinformatie
-- leest de naam uit de verklaring ("Gemeente Best"), zonder nummer, en nam soms
-- de zinsstaart mee ("Gemeente Ede te Ede ('de gemeente')", "Gemeente Oss,
-- opgesteld onder verantwoordelijkheid van het college van burgemeester en
-- wethouders"). Migratie 20260922160000 voegde samen op exact dezelfde naam,
-- en dat zijn deze niet.
--
-- Wat het kostte, gemeten op 5-10-2026: 55 gemeenten stonden twee of drie keer
-- in de database (63 rijen te veel). De geschiedenis van zo'n gemeente was in
-- stukken geknipt, dus een wisseling tussen de stukken was niet te zien, en 24
-- marktonderzoekregels ("controle, voorwerp onbekend") stonden naast een
-- gelezen controle van dezelfde gemeente in hetzelfde jaar — alle 24 bij
-- hetzelfde kantoor.
--
-- De regel, offline toegepast en hieronder als id-paren vastgelegd
-- ------------------------------------------------------------------
-- * De sleutel is de gemeentenaam zonder "Gemeentehuis/Stadhuis/Raadhuis/
--   Gemeentekantoor", zonder plaatsstaart ("te X", ", gevestigd te X"), zonder
--   "('de gemeente')" en zonder de "opgesteld onder verantwoordelijkheid"-staart
--   — alleen letters en cijfers. Een provincie-aanduiding hoort bij de naam:
--   "Bergen (L)" is een andere sleutel dan "Bergen", en de kale "Gemeente
--   Bergen" (KvK 37159392, Noord-Holland) blijft daardoor apart.
-- * Samenvoegen alleen bij exact dezelfde sleutel én geen tegenstrijdige
--   plaats. Twee plaatsen die allebei bekend zijn (de kolom gemeente, of de
--   "te X"-staart) moeten gelijk zijn. Bij "Gemeente Bergen (L)" zei de ene rij
--   Nieuw-Bergen en de andere "te Bergen (L)": niet samengevoegd, naar de
--   review-queue.
-- * Nooit twee verschillende KvK-nummers in één groep (kwam niet voor), en
--   geen opdracht die in hetzelfde boekjaar bij een ánder kantoor ligt (kwam
--   ook niet voor; dan was het een review-geval geweest).
-- * Namen met meer dan één gemeente erin ("Gemeente Diemen, Gemeente
--   Uithoorn, Gemeente Ouder-Amstel (DUO gemeenten)", een regeling) of een
--   kaal "Gemeentehuis" doen niet mee. "Gemeente Leiden namens Gemeente
--   Oegstgeest" gaat naar de review-queue: welke van de twee de klant is, staat
--   er niet.
--
-- Welke rij blijft: die met het KvK-nummer, zoals in 20260922160000. Zonder
-- nummer de rij met de schone naam, anders de oudste. En de bewaarde rij
-- krijgt de schone naam "Gemeente X" als hij nu "Gemeentehuis X" heet: anders
-- vindt laad_raadsinformatie.py hem bij de volgende run niet op naam, maakt
-- "Gemeente X" opnieuw aan en staat de dubbeling er weer. Het marktonderzoek
-- herkent op KvK-nummer en overschrijft geen naam.
--
-- Verder het samenvoegpatroon van 20260922160000: opdrachten, gunningen en
-- signalen verhuizen, wat door de verhuizing dubbel zou worden vervalt aan de
-- kant van de rij die weggaat, en een lege sector of plaats erft van de rij
-- die weggaat. Op twee punten strenger dan dat patroon:
--
-- * Een "controle_onbepaald" vervalt alleen als de gelezen controle van dat
--   boekjaar bij hetzelfde kantoor ligt: de staande regel van 20260922180000.
--   Noemt het marktonderzoek een ánder kantoor, dan is dat een tegenspraak, en
--   die blijft zichtbaar in v_kantoor_afwijking. De 23 regels die hier
--   vervallen, wezen alle 23 naar hetzelfde kantoor (de 24e uit de meting
--   hoort bij het Oosterhout-paar dat hieronder niet meedoet).
-- * Ligt dezelfde soort opdracht in hetzelfde boekjaar op de twee rijen bij
--   verschillende kantoren, dan zou samenvoegen er één stil laten vallen. Zo'n
--   paar gaat niet samen maar naar de review-queue. Bij de meting kwam het niet
--   voor; de controle is er voor wat er tussen meting en migratie nog bijkomt.
--
-- Draait ná 20261006110000, die de KvK-rijen van "overig bedrijfsleven" naar
-- overheid zette; de bewaarde rij staat dus al goed.
--
-- Op 6-10-2026 opnieuw gemeten en nagelopen: dezelfde regel gaf dezelfde 63
-- paren. Van de 37 bewaarde rijen met een KvK-nummer is dat bij 36 volgens
-- organisaties.overheid.nl het nummer van precies die gemeente; Dijk en Waard
-- staat daar nog zonder nummer, de rij heeft SBI 84.11 en dezelfde naam. Elke
-- nieuwe naam hieronder is de gemeentenaam zoals organisaties.overheid.nl hem
-- schrijft.
--
-- Twee van de 63 paren doen niet mee: 20107 "Stadhuis Doesburg" (een
-- TED-opdrachtgever) en 25577 "Gemeente Oosterhout te Oosterhout
-- (NoordBrabant)" (uit raadsinformatie). De lader die zo'n rij aanmaakte zoekt
-- bij de volgende run op precies die naam, vindt na het samenvoegen niets en
-- maakt de rij opnieuw aan — en dan staat de dubbeling er weer. Bij de andere
-- paren vindt de lader de bewaarde rij wél op naam (de schone "Gemeente X").
-- Die twee wachten op een naamregel in de lader zelf. Hieronder dus 61 paren.
--
-- Idempotent: een paar waarvan een van beide rijen niet (meer) bestaat, wordt
-- overgeslagen; een tweede run vindt niets. Nagespeeld op een lokale Postgres
-- 16 met de hele migratieketen, op een proefopstelling met verzonnen namen
-- (botsende opdracht en gunning, een rij met een ander KvK-nummer, een naam die
-- al bezet is, een ontbrekende rij, een ander kantoor in hetzelfde boekjaar)
-- en op een kopie van de openbare tabellen van 6-10-2026: 61 rijen
-- samengevoegd, 169 opdrachten verhuisd, 23 marktonderzoekregels weg, 32
-- bewaarde rijen hernoemd, 2 review-regels, en daarna geen enkele gemeentenaam
-- meer dubbel.

do $$
declare
  paar record;
  geraakt int;
  aantal_paren int := 0;
  aantal_opdrachten int := 0;
  aantal_hernoemd int := 0;
begin
  for paar in
    select * from (values
      (24167, 38274, 'Gemeente Aalsmeer'),                    -- Gemeente Aalsmeer
      (25755, 35894, 'Gemeente Alphen-Chaam'),                -- Gemeente Alphen-Chaam
      (25868, 35894, 'Gemeente Alphen-Chaam'),                -- Gemeente Alphen-Chaam te Alphen (NB)
      (24244, 35858, null),                                   -- Gemeente Assen ('de gemeente')
      (24247, 35858, null),                                   -- Gemeente Assen, te Assen ('de gemeente')
      (25118, 35859, null),                                   -- Gemeente Bernheze, te Heesch ('de gemeente')
      (25119, 35859, null),                                   -- Gemeente Bernheze ('de gemeente')
      (23965, 34439, 'Gemeente Best'),                        -- Gemeente Best
      (20142, 38255, 'Gemeente Bloemendaal'),                 -- Gemeente Bloemendaal
      (20220, 38275, 'Gemeente Borsele'),                     -- Gemeente Borsele
      (25144, 20682, null),                                   -- Gemeente Bronckhorst te Hengelo (Gld.)
      (20226, 38933, 'Gemeente Bunnik'),                      -- Gemeente Bunnik
      (30433, 33047, 'Gemeente Cranendonck'),                 -- Gemeente Cranendonck
      (24049, 20140, null),                                   -- Gemeente Gemeente De Ronde Venen
      (24051, 24057, null),                                   -- Gemeente De Wolden ('de gemeente')
      (25210, 38257, 'Gemeente Dijk en Waard'),               -- Gemeente Dijk en Waard
      (25624, 38932, 'Gemeente Dinkelland'),                  -- Gemeente Dinkelland
      (25048, 35889, 'Gemeente Drimmelen'),                   -- Gemeente Drimmelen
      (24186, 20152, null),                                   -- Gemeente Ede te Ede ('de gemeente')
      (25303, 25015, null),                                   -- Gemeente Haarlemmermeer ('de gemeente')
      (25022, 35890, 'Gemeente Heemskerk'),                   -- Gemeente Heemskerk
      (24330, 24335, null),                                   -- Gemeente Hoogeveen, te Hoogeveen ('de gemeente')
      (24331, 24335, null),                                   -- Gemeente Hoogeveen ('de gemeente')
      (24997, 38935, 'Gemeente Kampen'),                      -- Gemeente Kampen
      (25125, 41540, 'Gemeente Krimpen aan den IJssel'),      -- Gemeente Krimpen aan den IJssel
      (25436, 35870, null),                                   -- Gemeente Krimpenerwaard ('de gemeente')
      (20188, 34436, 'Gemeente Leudal'),                      -- Gemeente Leudal
      (23845, 35891, 'Gemeente Leusden'),                     -- Gemeente Leusden
      (25029, 41646, 'Gemeente Moerdijk'),                    -- Gemeente Moerdijk
      (25551, 35892, 'Gemeente Noordenveld'),                 -- Gemeente Noordenveld
      (23861, 38276, 'Gemeente Noordoostpolder'),             -- Gemeente Noordoostpolder
      (20130, 38277, 'Gemeente Noordwijk'),                   -- Gemeente Noordwijk
      (25223, 38278, 'Gemeente Nunspeet'),                    -- Gemeente Nunspeet
      (25261, 39111, 'Gemeente Oldenzaal'),                   -- Gemeente Oldenzaal
      (25031, 36989, 'Gemeente Oosterhout'),                  -- Gemeente Oosterhout
      (25270, 24092, null),                                   -- Gemeente Oost Gelre, opgesteld onder verantwoordelijkhe…
      (25607, 38265, null),                                   -- Gemeente Oss, opgesteld onder verantwoordelijkheid van …
      (27205, 38265, null),                                   -- Gemeente Oss, te Oss ('de gemeente')
      (23893, 40280, 'Gemeente Oudewater'),                   -- Gemeente Oudewater
      (20075, 35893, 'Gemeente Papendrecht'),                 -- Gemeente Papendrecht
      (25614, 38268, 'Gemeente Rheden'),                      -- Gemeente Rheden
      (25630, 24978, null),                                   -- Gemeente Rotterdam ('de gemeente')
      (24080, 20225, null),                                   -- Gemeente 's-Hertogenbosch ('de gemeente')
      (25638, 35881, null),                                   -- Gemeente Soest te Soest ('de gemeente')
      (25639, 25641, null),                                   -- Gemeente Staphorst ('de gemeente')
      (25640, 25641, null),                                   -- Gemeente Staphorst, te Staphorst ('de gemeente')
      (23952, 38279, 'Gemeente Steenbergen'),                 -- Gemeente Steenbergen
      (24151, 24155, null),                                   -- Gemeente Steenwijkerland, te Steenwijk ('de gemeente')
      (24153, 24155, null),                                   -- Gemeente Steenwijkerland ('de gemeente')
      (25427, 20683, null),                                   -- Gemeente Veenendaal, opgesteld onder verantwoordelijkhe…
      (23989, 20090, null),                                   -- Gemeente Venlo ('de gemeente')
      (25812, 20085, null),                                   -- Gemeente Venray ('de gemeente')
      (25445, 20128, null),                                   -- Gemeente Vlaardingen ('de gemeente')
      (25674, 38280, 'Gemeente Voorschoten'),                 -- Gemeente Voorschoten
      (25466, 20095, null),                                   -- Gemeente Waalwijk ('de gemeente')
      (20181, 36990, 'Gemeente Weert'),                       -- Gemeente Weert
      (20254, 38934, 'Gemeente Westerveld'),                  -- Gemeente Westerveld
      (25027, 41539, 'Gemeente Woerden'),                     -- Gemeente Woerden
      (25512, 38283, 'Gemeente Zaltbommel'),                  -- Gemeente Zaltbommel
      (20677, 38620, 'Gemeente Zutphen'),                     -- Gemeente Zutphen
      (25715, 24142, null)                                    -- Gemeente Zwolle, te Zwolle (hierna: 'de gemeente')
    ) as p(weg, houd, naam_nieuw)
  loop
    if not exists (select 1 from organisaties where id = paar.weg)
       or not exists (select 1 from organisaties where id = paar.houd) then
      continue;  -- al samengevoegd, of andere database: niets te doen
    end if;
    -- Een harde sleutel gaat voor: heeft de rij die weg zou gaan intussen een
    -- ánder KvK-nummer gekregen, dan zijn het twee rechtspersonen.
    if exists (
      select 1 from organisaties w, organisaties h
       where w.id = paar.weg and h.id = paar.houd
         and w.kvk_nummer is not null
         and w.kvk_nummer is distinct from h.kvk_nummer) then
      raise notice 'overgeslagen: % en % hebben verschillende KvK-nummers', paar.weg, paar.houd;
      continue;
    end if;
    -- Twee kantoren voor dezelfde opdracht in hetzelfde boekjaar: samenvoegen
    -- zou er één stil laten vallen (de unieke sleutel laat er maar één toe).
    -- Dan liever twee rijen en een mens die kijkt.
    if exists (
      select 1
        from opdrachten w
        join opdrachten h
          on h.organisatie_id = paar.houd
         and h.boekjaar = w.boekjaar
         and h.type_opdracht = w.type_opdracht
       where w.organisatie_id = paar.weg
         and h.kantoor_id is distinct from w.kantoor_id) then
      raise notice 'overgeslagen: % en % noemen in hetzelfde boekjaar een ander kantoor', paar.weg, paar.houd;
      insert into review_queue (soort, payload)
      select 'naam_match',
             jsonb_build_object(
               'bron', 'migratie 20261006110100',
               'reden', 'mogelijk dubbel',
               'organisatie_ids', to_jsonb(t.ids),
               'toelichting', 'zelfde gemeentenaam, maar in hetzelfde boekjaar '
                              'een ander kantoor; niet samengevoegd')
        from (select array[least(paar.weg, paar.houd),
                           greatest(paar.weg, paar.houd)]::bigint[] as ids) t
       where not exists (
         select 1 from review_queue r
          where r.soort = 'naam_match' and r.status = 'open'
            and r.payload->>'reden' = 'mogelijk dubbel'
            and r.payload->'organisatie_ids' = to_jsonb(t.ids));
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
    update opdrachten set organisatie_id = paar.houd
    where organisatie_id = paar.weg;
    get diagnostics geraakt = row_count;
    aantal_opdrachten := aantal_opdrachten + geraakt;

    delete from gunningen g
    where g.organisatie_id = paar.weg
      and exists (
        select 1 from gunningen h
        where h.organisatie_id = paar.houd
          and h.publicatienummer = g.publicatienummer
          and h.kantoor_id = g.kantoor_id
      );
    update gunningen set organisatie_id = paar.houd
    where organisatie_id = paar.weg;

    delete from signalen s
    where s.organisatie_id = paar.weg
      and exists (
        select 1 from signalen h
        where h.organisatie_id = paar.houd
          and h.type_signaal = s.type_signaal
          and h.datum = s.datum
      );
    update signalen set organisatie_id = paar.houd
    where organisatie_id = paar.weg;

    -- Alleen bij hetzelfde kantoor, zoals 20260922180000: een ander kantoor
    -- is een tegenspraak en geen dubbeling.
    delete from opdrachten o
    where o.organisatie_id = paar.houd
      and o.type_opdracht = 'controle_onbepaald'
      and exists (
        select 1 from opdrachten d
        where d.organisatie_id = paar.houd
          and d.boekjaar = o.boekjaar
          and d.type_opdracht in ('wettelijke_controle', 'vrijwillige_controle')
          and d.kantoor_id is not distinct from o.kantoor_id
      );

    update organisaties h
       set sector = coalesce(h.sector, w.sector),
           gemeente = coalesce(h.gemeente, w.gemeente)
      from organisaties w
     where h.id = paar.houd and w.id = paar.weg;

    delete from organisaties where id = paar.weg;
    aantal_paren := aantal_paren + 1;

    -- Pas na het weghalen: anders staat de schone naam even twee keer in de
    -- tabel. En niet als een andere rij die naam intussen draagt.
    if paar.naam_nieuw is not null then
      update organisaties h
         set naam = paar.naam_nieuw
       where h.id = paar.houd
         and h.naam <> paar.naam_nieuw
         and not exists (
           select 1 from organisaties x
            where x.id <> paar.houd
              and lower(x.naam) = lower(paar.naam_nieuw));
      get diagnostics geraakt = row_count;
      aantal_hernoemd := aantal_hernoemd + geraakt;
    end if;
  end loop;

  raise notice 'samengevoegd: % rijen; opdrachten verhuisd: %; hernoemd: %',
    aantal_paren, aantal_opdrachten, aantal_hernoemd;
end $$;

-- De twijfelgevallen: niet samengevoegd, wel in de review-queue. Alleen id's.
insert into review_queue (soort, payload)
select 'naam_match',
       jsonb_build_object(
         'bron', 'migratie 20261006110100',
         'reden', 'mogelijk dubbel',
         'organisatie_ids', to_jsonb(t.ids),
         'toelichting', t.toelichting)
  from (values
    (array[23950, 23951]::bigint[],
     'zelfde gemeentenaam met provincie, maar de plaatsen verschillen '
     '(Nieuw-Bergen tegen "te Bergen (L)")'),
    (array[20182, 25134, 25234]::bigint[],
     'aanbesteding door de ene gemeente namens de andere; welke de klant is, '
     'staat er niet')
  ) as t(ids, toelichting)
 where (select count(*) from organisaties o where o.id = any(t.ids)) > 1
   and not exists (
     select 1 from review_queue r
      where r.soort = 'naam_match' and r.status = 'open'
        and r.payload->>'reden' = 'mogelijk dubbel'
        and r.payload->'organisatie_ids' = to_jsonb(t.ids));
