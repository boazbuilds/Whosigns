-- Gunningen van accountantsdiensten door aanbestedende overheden.
--
-- Waarom een eigen tabel en niet gewoon een opdracht
-- --------------------------------------------------
-- Een gunning is een BENOEMING VOORAF, geen handtekening achteraf. De gemeente
-- kiest een kantoor voor doorgaans vier jaar; of die controle er ook echt kwam,
-- en met welk oordeel, staat er niet in. Het aanbestede pakket heet vaak
-- "accountantsdiensten" en is breder dan de wettelijke controle.
--
-- Als we dit als `opdrachten` zouden wegschrijven, zou de database beweren dat
-- er in vier boekjaren is gecontroleerd terwijl we dat niet hebben waargenomen —
-- precies het soort stille gok dat dit project niet doet. Vandaar een aparte
-- tabel met een eigen betekenis: "hier is een kantoor benoemd, op deze datum".
--
-- Wat deze bron uniek toevoegt: het MOMENT van wisselen, met een datum. De
-- bestaande bronnen leiden een wisseling af uit twee opeenvolgende boekjaren en
-- weten dus nooit wanneer het besluit viel. En hij opent een populatie die
-- WhoSigns tot nu toe helemaal niet had: gemeenten, provincies, waterschappen,
-- veiligheidsregio's en gemeenschappelijke regelingen.

create table if not exists gunningen (
  id               bigint generated always as identity primary key,
  organisatie_id   bigint not null references organisaties (id),
  kantoor_id       bigint not null references kantoren (id),
  -- Datum waarop het contract is gesloten. Kan leeg zijn: onder de oude
  -- TED-structuur (vóór 2023) is dit veld niet altijd gevuld.
  gunningsdatum    date,
  -- Het TED-publicatienummer, bijvoorbeeld "534507-2026". Samen met
  -- organisatie en kantoor de natuurlijke sleutel: één bericht kan meerdere
  -- percelen aan meerdere kantoren gunnen.
  publicatienummer text not null,
  titel            text,
  bron_id          bigint references bronnen (id),
  created_at       timestamptz not null default now(),
  unique (publicatienummer, organisatie_id, kantoor_id)
);

create index if not exists gunningen_organisatie_idx on gunningen (organisatie_id);
create index if not exists gunningen_kantoor_idx on gunningen (kantoor_id);
create index if not exists gunningen_datum_idx on gunningen (gunningsdatum desc);

comment on table gunningen is
  'Aanbestede accountantsdiensten: welk kantoor is wanneer benoemd. Een '
  'benoeming vooraf, géén waargenomen controle — daarom niet in opdrachten.';
comment on column gunningen.gunningsdatum is
  'Datum contractsluiting volgens TED; leeg bij oudere berichten.';

alter table gunningen enable row level security;
create policy publiek_lezen on gunningen for select using (true);
