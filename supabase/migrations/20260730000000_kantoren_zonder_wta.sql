-- WhoSigns — kantoren zonder Wta-vergunning, en vrijwillige controles
--
-- Waarom: buiten de zorg is de accountantscontrole vaak niet wettelijk verplicht.
-- Bij CBF-erkende goede doelen komt de verplichting uit norm 8.1.3 van de
-- Erkenningsregeling (categorie D en E) en niet uit Titel 9 BW; een stichting hoeft
-- pas te deponeren bij €7,5 mln omzet uit onderneming. Voor zulke vrijwillige
-- controles is géén Wta-vergunning nodig, en dus tekent een deel van de markt dat
-- het AFM-register niet kent.
--
-- Gemeten op boekjaar 2024, 40 goede doelen in categorie D/E: 9 van de 33
-- controleverklaringen kwamen van een kantoor buiten het AFM-register (vooral WITh
-- Accountants). Wie alleen op het AFM-register matcht, mist die opdrachten — dat is
-- bijna een derde van de sector. Zie docs/bronverkenning-stichtingen.md.
--
-- Wat dit NIET verandert: bij een wettelijke controle blijft het AFM-register de
-- gesloten verzameling. Een kantoor zonder vergunning mag daar nooit in belanden;
-- vandaar het onderscheid in kolom én in opdrachttype.

-- ---------- kantoren ----------

-- Heeft dit kantoor een Wta-vergunning? True voor alles wat uit het AFM-register komt.
alter table kantoren add column if not exists wta_vergunning boolean not null default true;
comment on column kantoren.wta_vergunning is
  'True = staat in het AFM-register en mag wettelijke controles doen. '
  'False = kantoor zonder Wta-vergunning; kan alleen vrijwillige controles, '
  'beoordelingen en samenstellingen doen.';

-- Eén sleutel voor alle kantoren: het AFM-nummer waar dat bestaat, anders een
-- handmatig toegekende sleutel uit seed/kantoren_overig.csv ('overig_...').
-- Nodig omdat afm_nummer voor deze rijen leeg blijft en de lader iets moet hebben
-- om op te upserten.
alter table kantoren add column if not exists sleutel text;
update kantoren set sleutel = afm_nummer where sleutel is null and afm_nummer is not null;
create unique index if not exists kantoren_sleutel_idx on kantoren (sleutel);
comment on column kantoren.sleutel is
  'Upsert-sleutel: AFM-nummer, of "overig_<naam>" voor kantoren zonder vergunning.';

-- Herkomst per feit (principe 3): waar hebben we dit kantoor gezien? Bij het
-- AFM-register is dat het register zelf; bij een overig kantoor de verklaring waarin
-- de naam stond. Vrije tekst, want het is een verantwoording en geen sleutel.
alter table kantoren add column if not exists toelichting text;

-- KvK-nummer van het kantoor: voor kantoren buiten het AFM-register is dat het enige
-- officiële nummer dat er is. Blijft leeg tot iemand het opzoekt.
alter table kantoren add column if not exists kvk_nummer text;

-- ---------- afgeleiden: vrijwillige controles meetellen ----------
--
-- De views filterden op type_opdracht = 'wettelijke_controle'. Daarmee zou de hele
-- goededoelensector uit de relatieduur, de wisselingen en de marktaandelen vallen —
-- precies de cijfers waar het product om draait. Ze tellen nu beide vormen van
-- jaarrekeningcontrole mee. Andere opdrachttypen (WNT-verantwoording,
-- productieverantwoording, beoordeling, samenstelling) blijven er bewust buiten:
-- dat zijn andere opdrachten, geen jaarrekeningcontrole.
--
-- Het onderscheid zelf blijft overal beschikbaar via opdrachten.type_opdracht en
-- kantoren.wta_vergunning, zodat de site "wettelijke controle" en "vrijwillige
-- controle" apart kan labelen (dat doet web/lib/paden.ts al).

create or replace view v_relatieduur with (security_invoker = on) as
with wc as (
  select organisatie_id, kantoor_id, boekjaar,
         boekjaar - row_number() over (
           partition by organisatie_id, kantoor_id order by boekjaar
         ) as reeks
  from opdrachten
  where type_opdracht in ('wettelijke_controle', 'vrijwillige_controle')
    and kantoor_id is not null
)
select organisatie_id, kantoor_id,
       min(boekjaar) as eerste_boekjaar,
       max(boekjaar) as laatste_boekjaar,
       count(*)::int as duur_jaren
from wc
group by organisatie_id, kantoor_id, reeks;

create or replace view v_wisselingen with (security_invoker = on) as
with wc as (
  select organisatie_id, kantoor_id, boekjaar
  from opdrachten
  where type_opdracht in ('wettelijke_controle', 'vrijwillige_controle')
    and kantoor_id is not null
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

create or replace view v_marktaandeel with (security_invoker = on) as
select o.boekjaar,
       org.sector,
       o.kantoor_id,
       count(*)::int as aantal_controles,
       round(100.0 * count(*) / sum(count(*)) over (partition by o.boekjaar, org.sector), 1)
         as marktaandeel_pct
from opdrachten o
join organisaties org on org.id = o.organisatie_id
where o.type_opdracht in ('wettelijke_controle', 'vrijwillige_controle')
  and o.kantoor_id is not null
group by o.boekjaar, org.sector, o.kantoor_id;
