-- Dubbele organisaties samenvoegen, nu op regel in plaats van met de hand.
--
-- Waarom dit nodig is
-- -------------------
-- Twee eerdere migraties (20260901120000 en 20260901140000) voegden achttien
-- paren samen die met de hand waren nagelopen. Dat dekte de gevallen die toen
-- opvielen. Op 22-9-2026 bleek de omvang een andere: 686 namen komen meer dan
-- één keer voor in `organisaties`, samen 1.386 rijen.
--
-- Het is dezelfde oorzaak, alleen vaker. De documentroutes
-- (transparantieverslagen, gunningen, raadsinformatie, jaarverslagen) maken een
-- organisatie op náám aan, zonder KvK-nummer; het aangeleverde marktonderzoek
-- maakt ze op KvK-nummer aan. Dezelfde organisatie kreeg zo twee rijen.
--
-- Wat het kostte, gemeten voordat deze migratie draaide:
--
-- * 2.803 opdrachten hangen aan zo'n naamrij. De geschiedenis van die
--   organisaties is dus in tweeën geknipt, en een wisseling tussen de helften
--   is niet te zien — terwijl juist dát is wat deze site laat zien.
-- * De laders wéigeren bij een dubbele naam, en terecht: ze mogen niet gokken
--   aan welke van de twee rijen een nieuwe opdracht hoort. De beursfondsenrun
--   van 22-9-2026 las 110 deponeringen over boekjaar 2025, kwam tot 45
--   opdrachten — en schreef er nul, omdat elke instelling inmiddels een
--   tweelingrij had. De hele OOB-route stond daarmee stil zonder dat iets
--   roodkleurde.
--
-- Wat deze migratie wél en niet samenvoegt
-- ----------------------------------------
-- De sleutel is de naam zonder hoofdletters en zonder leestekens, precies zoals
-- migratie 20260805190000 hem al gebruikte. Twee gevallen worden samengevoegd:
--
-- 1. **Eén rij met KvK-nummer, de rest zonder** (541 groepen, 2.803
--    opdrachten). De rij mét nummer blijft: dat is de stabiele sleutel waarop
--    elke latere lading aanhaakt.
-- 2. **Geen enkele rij met KvK-nummer** (15 groepen). Dan blijft de oudste rij;
--    er is niets om op te kiezen en ze zijn voor een bezoeker niet uit elkaar
--    te houden.
-- 3. **Een afgerond KvK-nummer naast het echte** (78 paren). Zelfde klasse als
--    20260805190000: dVi2010-2012 bewaarde het nummer met te weinig precisie,
--    waardoor het laatste cijfer op nul kwam. Die migratie draaide één keer en
--    latere corporatieladingen maakten ze opnieuw aan. Zelfde drievoudige eis:
--    dezelfde naam, het ene nummer eindigt op nul, én het is precies de
--    afronding van het andere.
--
-- Niet samengevoegd: 47 paren met twee écht verschillende KvK-nummers
-- ("Woonbron" 24108291 naast 24373580, "Woningstichting PWS Rotterdam"
-- 24108317 naast 00108317). Sommige zijn zichtbaar beschadigd, andere kunnen
-- twee rechtspersonen zijn na een fusie of splitsing. Uit de gegevens die hier
-- staan is dat niet te zien, en dan blijven ze staan. Liever een gat dan een
-- gok.
--
-- De sector van de samengevoegde rij
-- ----------------------------------
-- De rijen die verdwijnen dragen 313 keer 'OOB' en 235 keer 'overheid'. Dat
-- zijn herkomstlabels: de transparantieverslagen noemen elke cliënt OOB, de
-- aanbestedingen noemen elke aanbestedende dienst overheid.
--
-- 'overheid' verliest daarom van wat de bewaarde rij al heeft — dezelfde keuze
-- als bij Tilburg University in 20260901120000.
--
-- 'OOB' wint juist van een SBI-hokje. Dat hokje is afgeleid uit één SBI-code
-- ("Heineken N.V." wordt zo 'zakelijke dienstverlening', "Koninklijke Vopak
-- N.V." 'financiële dienstverlening'), terwijl OOB een juridische status is die
-- uit het AFM-register komt — precies de afweging die in 20260901120000 bij
-- PostNL met de hand werd gemaakt. Wint alleen van de SBI-hokjes en van een
-- lege sector, niet van de sectoren met een eigen lader en een eigen pagina
-- (zorg, onderwijs, pensioenfondsen, woningcorporaties, goede doelen).
--
-- Idempotent: twee keer draaien verandert niets, want na de eerste keer is er
-- per naam nog maar één rij.
--
-- Nagespeeld op een lege Postgres 16 met de hele migratieketen erop en een
-- proefopstelling van veertien organisaties, één per geval (22-9-2026). De
-- uitkomst: de naamrij van "Heineken N.V." verhuisde naar de KvK-rij en die
-- werd OOB; "Gemeente Testdam" hield zorg; van twee rijen zonder nummer bleef
-- de oudste; het afgeronde 14614730 ging op in 14614733; de twee "Woonbron
-- Test"-rijen met verschillende nummers bleven allebei staan, net als de
-- tweeletternaam; een botsende opdracht, gunning en signaal vervielen aan de
-- kant van de rij die wegging en de rest verhuisde; de controle_onbepaald van
-- een boekjaar dat na de verhuizing een echte controle had, verdween. Een
-- tweede run meldde nul.

do $$
declare
  paar record;
  geraakt int;
  aantal_paren int := 0;
  aantal_opdrachten int := 0;
  aantal_sector int := 0;
begin
  create temporary table samen_te_voegen (weg bigint, houd bigint) on commit drop;

  -- Geval 1 en 2: één rij met nummer (of geen enkele), de rest gaat mee.
  insert into samen_te_voegen (weg, houd)
  with kern as (
    select id, kvk_nummer,
           regexp_replace(lower(naam), '[^a-z0-9]', '', 'g') as sleutel
    from organisaties
    -- Een sleutel van één of twee tekens zegt te weinig om op samen te voegen.
    where length(regexp_replace(lower(naam), '[^a-z0-9]', '', 'g')) >= 3
  ),
  groep as (
    select sleutel,
           count(*)                                         as rijen,
           count(kvk_nummer)                                as met_nummer,
           min(id) filter (where kvk_nummer is not null)    as houd_met_nummer,
           min(id)                                          as oudste
    from kern
    group by sleutel
    having count(*) > 1
  )
  select k.id, coalesce(g.houd_met_nummer, g.oudste)
  from kern k
  join groep g using (sleutel)
  where (g.met_nummer = 1 and k.kvk_nummer is null)
     or (g.met_nummer = 0 and k.id <> g.oudste);

  -- Geval 3: het afgeronde nummer naast het echte.
  insert into samen_te_voegen (weg, houd)
  select afgerond.id, echt.id
  from organisaties afgerond
  join organisaties echt
    on echt.id <> afgerond.id
   and regexp_replace(lower(echt.naam), '[^a-z0-9]', '', 'g')
     = regexp_replace(lower(afgerond.naam), '[^a-z0-9]', '', 'g')
   and afgerond.kvk_nummer ~ '^[0-9]+0$'
   and echt.kvk_nummer !~ '0$'
   and round(echt.kvk_nummer::numeric / 10) * 10 = afgerond.kvk_nummer::numeric;

  for paar in select * from samen_te_voegen loop
    if not exists (select 1 from organisaties where id = paar.weg)
       or not exists (select 1 from organisaties where id = paar.houd) then
      continue;  -- al samengevoegd in een eerdere ronde van deze lus
    end if;

    -- Een opdracht die door de verhuizing dubbel zou worden vervalt aan de
    -- kant van de rij die weggaat; de bewaarde rij wint.
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

    -- "Controle, voorwerp onbekend" (marktonderzoek) vervalt zodra hetzelfde
    -- boekjaar op de samengevoegde rij een echte gelezen controle heeft.
    delete from opdrachten o
    where o.organisatie_id = paar.houd
      and o.type_opdracht = 'controle_onbepaald'
      and exists (
        select 1 from opdrachten d
        where d.organisatie_id = paar.houd
          and d.boekjaar = o.boekjaar
          and d.type_opdracht in ('wettelijke_controle', 'vrijwillige_controle')
      );

    -- Sector: een lege bewaarde rij erft, en 'OOB' wint van een SBI-hokje.
    update organisaties h
    set sector = w.sector
    from organisaties w
    where h.id = paar.houd and w.id = paar.weg
      and h.sector is null and w.sector is not null;
    get diagnostics geraakt = row_count;
    aantal_sector := aantal_sector + geraakt;

    update organisaties h
    set sector = 'OOB'
    from organisaties w
    where h.id = paar.houd and w.id = paar.weg
      and w.sector = 'OOB'
      and (h.sector is null or h.sector in (
        'landbouw en visserij', 'industrie en bouw', 'handel',
        'transport en logistiek', 'ict en media', 'financiële dienstverlening',
        'vastgoed', 'zakelijke dienstverlening', 'overig bedrijfsleven'
      ));
    get diagnostics geraakt = row_count;
    aantal_sector := aantal_sector + geraakt;

    delete from organisaties where id = paar.weg;
    aantal_paren := aantal_paren + 1;
  end loop;

  raise notice 'samengevoegd: % organisaties; opdrachten verhuisd: %; sector bijgesteld: %',
    aantal_paren, aantal_opdrachten, aantal_sector;
end $$;
