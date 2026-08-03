-- Namen en plaatsen opschonen zoals het DigiMV-archief ze had moeten leveren.
--
-- Aanleiding (nagemeten 3-8-2026, over 1.142 organisaties): 394 gemeenten stonden
-- volledig in KAPITALEN ("GOOR", "DEN HAAG"), elf namen hadden losse spaties
-- ("Amarant ", "Treant Zorggroep  (Stichting)") en één naam stond er dubbel in:
-- "Woon & Zorgcentrum HerfstzonWoon & Zorgcentrum Herfstzon (Stichting)"
-- (KvK 41032279). Dat komt zo uit de bron; de pipeline schoont het voortaan bij
-- binnenkomst op (adapters/digimv.py: schoon_naam/schoon_plaats). Deze migratie
-- doet hetzelfde eenmalig voor wat er al staat.
--
-- De kapitalenfix is niet alleen cosmetisch: de site zoekt plaatsgenoten met
-- gemeente=eq., en "GOOR" is daarvoor een andere plaats dan "Goor".

-- 1. Witruimte samenvouwen en trimmen, in naam én gemeente.
update organisaties
   set naam = btrim(regexp_replace(naam, '\s+', ' ', 'g'))
 where naam <> btrim(regexp_replace(naam, '\s+', ' ', 'g'));

update organisaties
   set gemeente = btrim(regexp_replace(gemeente, '\s+', ' ', 'g'))
 where gemeente is not null
   and gemeente <> btrim(regexp_replace(gemeente, '\s+', ' ', 'g'));

-- 2. Dubbel geplakte naam: begint de rest van de naam met exact de kop ervoor
--    (minstens acht tekens, tegen toeval), dan vervalt die kop.
update organisaties
   set naam = regexp_replace(naam, '^(.{8,})\1', '\1')
 where naam ~ '^(.{8,})\1';

-- 3. Gemeenten in KAPITALEN naar normale schrijfwijze. Zelfde regels als in
--    adapters/digimv.py: tussenwoorden klein (Alphen aan den Rijn), de
--    IJ-lettergreep heel (IJsselstein), 's en 't blijven klein en de soms
--    ontbrekende apostrof van 's-Hertogenbosch komt terug. Alleen namen die
--    geheel in kapitalen staan worden aangeraakt.
create function pg_temp.zet_plaats(p text) returns text
language plpgsql as $$
declare
  klein constant text[] := array['aan','bij','de','den','der','en','het','in','op','ter','van'];
  woord text;
  delen text[];
  d text;
  j int;
  uit text[] := '{}';
begin
  foreach woord in array string_to_array(lower(p), ' ') loop
    if array_length(uit, 1) is not null and woord = any(klein) then
      uit := uit || woord;
      continue;
    end if;
    delen := string_to_array(woord, '-');
    if delen[1] = 's' and array_length(delen, 1) > 1 then
      delen[1] := '''s';
    end if;
    for j in 1 .. array_length(delen, 1) loop
      d := delen[j];
      if d in ('''s', '''t') then
        null;  -- 's-Gravenhage, 't Zand
      elsif d like 'ij%' then
        d := 'IJ' || substr(d, 3);
      else
        d := upper(substr(d, 1, 1)) || substr(d, 2);
      end if;
      delen[j] := d;
    end loop;
    uit := uit || array_to_string(delen, '-');
  end loop;
  return array_to_string(uit, ' ');
end $$;

update organisaties
   set gemeente = pg_temp.zet_plaats(gemeente)
 where gemeente is not null
   and gemeente <> ''
   and gemeente = upper(gemeente)
   and gemeente <> pg_temp.zet_plaats(gemeente);
