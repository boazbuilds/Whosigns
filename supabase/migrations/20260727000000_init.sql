-- WhoSigns — kernschema v1
-- Eén kernmodel waar alle bron-adapters naartoe schrijven (docs/concept.md §4–5).
-- Guardrail (AVG): uitsluitend accountantsORGANISATIES, nooit natuurlijke personen.

-- Referentietabel accountantsorganisaties (seed: AFM-vergunningenregister, Fase 0).
create table kantoren (
  id             bigint generated always as identity primary key,
  afm_nummer     text unique,
  naam           text not null,
  oob_vergunning boolean not null default false,
  actief         boolean not null default true,
  website        text,
  created_at     timestamptz not null default now()
);

-- Handelsnamen, spelvarianten en oude namen na fusie; aliassen in kleine letters opslaan.
create table kantoor_alias (
  alias      text primary key,
  kantoor_id bigint not null references kantoren (id)
);

create table organisaties (
  id            bigint generated always as identity primary key,
  kvk_nummer    text unique,
  naam          text not null,
  rechtsvorm    text,
  sector        text,
  sbi_code      text,
  grootteklasse text,
  gemeente      text,
  created_at    timestamptz not null default now()
);

-- Herkomst per feit (docs/concept.md §4, principe 3).
create table bronnen (
  id              bigint generated always as identity primary key,
  bron_type       text not null,  -- digimv | duo | kvk_xbrl | kvk_pdf |
                                  -- transparantieverslag | tenderned |
                                  -- afm_register | zelf_aangeleverd
  url             text,
  opgehaald_op    timestamptz not null default now(),
  betrouwbaarheid text not null default 'publiek'
                  check (betrouwbaarheid in ('publiek', 'zelf_aangeleverd'))
);

-- Ruwe bronbestanden in Supabase Storage (principe 1: bron bewaren vóór verwerking).
create table bronbestanden (
  id           bigint generated always as identity primary key,
  bron_id      bigint not null references bronnen (id),
  storage_pad  text not null,
  bestandstype text,
  sha256       text
);
create index bronbestanden_bron_idx on bronbestanden (bron_id);

-- Kernobject: de assurance-opdracht per organisatie per boekjaar.
create table opdrachten (
  id                       bigint generated always as identity primary key,
  organisatie_id           bigint not null references organisaties (id),
  kantoor_id               bigint references kantoren (id),  -- null tot kantoor is herleid
  boekjaar                 int not null,
  type_opdracht            text not null default 'wettelijke_controle',
  standaard                text,  -- bijv. 'NV COS 700'
  oordeel                  text check (oordeel in
                             ('goedkeurend', 'beperking', 'oordeelonthouding', 'afkeurend')),
  -- Gesplitst conform art. 2:382a BW; DigiMV/DUO leveren de splitsing vaak mee.
  honorarium_controle_eur  numeric,
  honorarium_overig_eur    numeric,
  continuiteitsonzekerheid boolean,  -- paragraaf materiële onzekerheid continuïteit
  bron_id                  bigint not null references bronnen (id),
  created_at               timestamptz not null default now(),
  unique (organisatie_id, boekjaar, type_opdracht)
);
create index opdrachten_kantoor_idx on opdrachten (kantoor_id, boekjaar);

-- Wisselsignalen; de unieke sleutel maakt signaaldetectie idempotent.
create table signalen (
  id             bigint generated always as identity primary key,
  organisatie_id bigint not null references organisaties (id),
  type_signaal   text not null,  -- aanbesteding | lange_relatie |
                                 -- niet_goedkeurend_oordeel |
                                 -- kantoor_vergunning_beeindigd |
                                 -- verplichte_roulatie | kantoor_overgenomen
  omschrijving   text,
  datum          date not null,
  status         text not null default 'actief'
                 check (status in ('actief', 'afgehandeld')),
  bron_id        bigint references bronnen (id),  -- null bij afgeleide signalen
  created_at     timestamptz not null default now(),
  unique (organisatie_id, type_signaal, datum)
);
create index signalen_status_idx on signalen (status, type_signaal);

-- Wachtrij voor menselijke controle: onzekere AI-extracties en fuzzy naam-matches.
-- Guardrail: nooit stil automatisch mergen (docs/concept.md §4).
create table review_queue (
  id             bigint generated always as identity primary key,
  soort          text not null check (soort in ('ai_extractie', 'naam_match')),
  payload        jsonb not null,
  status         text not null default 'open'
                 check (status in ('open', 'akkoord', 'afgewezen')),
  aangemaakt_op  timestamptz not null default now(),
  afgehandeld_op timestamptz
);

-- ---------- Afgeleiden als views, niet opslaan (docs/concept.md §5) ----------

-- Aaneengesloten relaties organisatie×kantoor (opeenvolgende boekjaren zelfde kantoor).
create view v_relatieduur with (security_invoker = on) as
with wc as (
  select organisatie_id, kantoor_id, boekjaar,
         boekjaar - row_number() over (
           partition by organisatie_id, kantoor_id order by boekjaar
         ) as reeks
  from opdrachten
  where type_opdracht = 'wettelijke_controle' and kantoor_id is not null
)
select organisatie_id, kantoor_id,
       min(boekjaar) as eerste_boekjaar,
       max(boekjaar) as laatste_boekjaar,
       count(*)::int as duur_jaren
from wc
group by organisatie_id, kantoor_id, reeks;

-- Wisseling: ander kantoor in boekjaar n+1.
create view v_wisselingen with (security_invoker = on) as
with wc as (
  select organisatie_id, kantoor_id, boekjaar
  from opdrachten
  where type_opdracht = 'wettelijke_controle' and kantoor_id is not null
)
select oud.organisatie_id,
       oud.kantoor_id   as van_kantoor_id,
       nieuw.kantoor_id as naar_kantoor_id,
       nieuw.boekjaar   as boekjaar_wissel
from wc oud
join wc nieuw
  on  nieuw.organisatie_id = oud.organisatie_id
  and nieuw.boekjaar = oud.boekjaar + 1
  and nieuw.kantoor_id <> oud.kantoor_id;

-- Marktaandeel per kantoor per sector per boekjaar.
create view v_marktaandeel with (security_invoker = on) as
select o.boekjaar,
       org.sector,
       o.kantoor_id,
       count(*)::int as aantal_controles,
       round(100.0 * count(*) / sum(count(*)) over (partition by o.boekjaar, org.sector), 1)
         as marktaandeel_pct
from opdrachten o
join organisaties org on org.id = o.organisatie_id
where o.type_opdracht = 'wettelijke_controle' and o.kantoor_id is not null
group by o.boekjaar, org.sector, o.kantoor_id;

-- ---------- Row Level Security ----------
-- v1 bevat uitsluitend openbare data: iedereen mag lezen. Schrijven kan alleen met de
-- service-role-key (de pipeline); er zijn bewust géén insert/update/delete-policies.
-- De review_queue is intern en heeft ook geen leespolicy.

alter table kantoren      enable row level security;
alter table kantoor_alias enable row level security;
alter table organisaties  enable row level security;
alter table bronnen       enable row level security;
alter table bronbestanden enable row level security;
alter table opdrachten    enable row level security;
alter table signalen      enable row level security;
alter table review_queue  enable row level security;

create policy publiek_lezen on kantoren      for select using (true);
create policy publiek_lezen on kantoor_alias for select using (true);
create policy publiek_lezen on organisaties  for select using (true);
create policy publiek_lezen on bronnen       for select using (true);
create policy publiek_lezen on bronbestanden for select using (true);
create policy publiek_lezen on opdrachten    for select using (true);
create policy publiek_lezen on signalen      for select using (true);
