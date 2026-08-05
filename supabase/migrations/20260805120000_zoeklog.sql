-- Wat bezoekers in de zoekbalk typen.
--
-- Waarom dit geen "analytics" is
-- ------------------------------
-- Deze tabel houdt geen bezoekers bij. Er staat geen IP-adres in, geen
-- browser, geen sessie en niets waarmee twee zoekopdrachten aan dezelfde
-- persoon zijn te knopen. Alleen: welk woord is er ingetypt, hoeveel
-- resultaten gaf dat, en wanneer. Daarmee is het geen persoonsgegeven en
-- hoeft er niets geregeld te worden dat bij bezoekersstatistiek wél moet.
--
-- Waar het wél voor is: een zoekopdracht met NUL resultaten is een gat in de
-- database. Iemand zoekt een organisatie die er nog niet in staat. Dat is
-- precies de werklijst waar dit project op draait — welke bron er als
-- volgende bij moet. Vandaar dat het aantal resultaten wordt meegeschreven;
-- zonder dat getal is de lijst een weetje in plaats van een opdracht.
--
-- Waarom de website hier wél mag schrijven
-- ----------------------------------------
-- Overal elders geldt: de site leest, de pipeline schrijft, en de secret key
-- komt nooit buiten GitHub Secrets. Die regel blijft staan. Voor deze ene
-- tabel is er een insert-policy voor iedereen, want de website heeft alleen
-- de publishable key en er is geen andere manier om vanaf de site iets weg te
-- schrijven zonder die regel te breken.
--
-- De prijs daarvan, eerlijk opgeschreven: de publishable key staat in de
-- broncode van elke pagina, dus wie hem overneemt kan rijen in deze tabel
-- zetten. Er is bewust géén select-policy — niemand kan de lijst lezen via de
-- API, alleen jij in het Supabase-dashboard. En de lengte van het zoekwoord is
-- afgetopt, zodat de tabel niet als opslag te misbruiken is. Loopt het toch
-- vol met rommel, dan is de rem één regel:
--
--     drop policy publiek_loggen on zoekopdrachten;
--
-- Dan stopt het loggen en blijft de rest van de site gewoon werken.

create table if not exists zoekopdrachten (
  id          bigint generated always as identity primary key,
  -- Het ingetypte woord, zoals ingetypt. Afgetopt op 120 tekens: langer is
  -- geen zoekopdracht meer.
  term        text not null check (length(term) between 1 and 120),
  -- Hoeveel treffers de zoekpagina toonde (organisaties plus kantoren).
  -- 0 betekent: hier ontbreekt data.
  resultaten  integer not null default 0 check (resultaten >= 0),
  moment      timestamptz not null default now()
);

create index if not exists zoekopdrachten_moment_idx on zoekopdrachten (moment desc);
-- Voor de vraag die je het vaakst stelt: welk woord levert steeds niets op?
create index if not exists zoekopdrachten_leeg_idx on zoekopdrachten (term)
  where resultaten = 0;

comment on table zoekopdrachten is
  'Ingetypte zoekwoorden met het aantal treffers. Geen bezoekersgegevens: '
  'geen IP, geen sessie. Nul treffers = gat in de database.';

alter table zoekopdrachten enable row level security;

-- Alleen schrijven. Geen select-policy, dus de lijst is niet openbaar op te
-- vragen; lezen doe je in het Supabase-dashboard.
create policy publiek_loggen on zoekopdrachten for insert with check (true);
