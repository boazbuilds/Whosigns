-- WhoSigns — het marktonderzoek per sector en boekjaar, als telling
--
-- Waarom
-- ------
-- De sectorpagina's rekenen alleen met wettelijke en vrijwillige controles
-- (v_marktaandeel). In negen sectoren van het bedrijfsleven zijn dat er
-- nauwelijks, en daar zei de pagina "Nog geen opdrachten in deze sector" —
-- terwijl er op 5-10-2026 bij de handel 4.095 opdrachten uit het aangeleverde
-- marktonderzoek stonden, en bij de financiële dienstverlening 12.053 (tegen 11
-- gelezen controles). Die opdrachten hebben als type "controle, voorwerp
-- onbekend": het onderzoek noemt een kantoor, niet waarover de opdracht ging.
-- Ze blijven dus buiten elk aandeel en elke wisseling. Wat deze view geeft, is
-- alleen hoeveel organisaties er per sector en boekjaar zo'n kantoor hebben, en
-- hoeveel daarvan géén gelezen controle in dat boekjaar.
--
-- Bewust zonder kantoor
-- ---------------------
-- Het onderzoek noemt 22 kantoren, en twee van de vier grootste helemaal niet;
-- één kantoor staat op 23% van de 35.582 regels (5-10-2026). Een telling per
-- kantoor zou laten zien wie er in de aanlevering zit, en dat leest als een
-- marktbeeld. De opdrachten zelf, mét kantoor, staan gewoon op de pagina van
-- elke organisatie, met het label "marktonderzoek".
--
-- Alleen bron_type 'marktonderzoek' en alleen 'controle_onbepaald': een
-- vrijwillige controle uit een andere bron hoort in v_marktaandeel, niet hier.
-- Een organisatie telt één keer per boekjaar, ook als het onderzoek haar twee
-- keer noemt. Organisaties zonder sector staan er met sector null in; de
-- website vraagt altijd één sector op.
create or replace view v_marktonderzoek_per_sector with (security_invoker = on) as
with onderzoek as (
  select distinct o.organisatie_id, o.boekjaar, org.sector
  from opdrachten o
  join bronnen b on b.id = o.bron_id
  join organisaties org on org.id = o.organisatie_id
  where b.bron_type = 'marktonderzoek'
    and o.type_opdracht = 'controle_onbepaald'
    and o.kantoor_id is not null
),
gecontroleerd as (
  select distinct organisatie_id, boekjaar
  from opdrachten
  where type_opdracht in ('wettelijke_controle', 'vrijwillige_controle')
    and kantoor_id is not null
)
select ond.boekjaar,
       ond.sector,
       count(*)::int as aantal_organisaties,
       count(*) filter (where g.organisatie_id is null)::int as zonder_controle
from onderzoek ond
left join gecontroleerd g
  on g.organisatie_id = ond.organisatie_id and g.boekjaar = ond.boekjaar
group by ond.boekjaar, ond.sector;

comment on view v_marktonderzoek_per_sector is
  'Per boekjaar en sector: organisaties met een kantoor volgens aangeleverd marktonderzoek (voorwerp onbekend), en hoeveel daarvan zonder gelezen wettelijke of vrijwillige controle. Bewust zonder kantoor.';
