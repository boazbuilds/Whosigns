-- WhoSigns — extra velden uit de DigiMV-dataset
--
-- Deze gegevens zitten gestructureerd in de jaardataset en zijn dus gratis mee te
-- nemen; het pdf-spoor is er niet voor nodig. Opslaan is bewust ruimer dan tonen:
-- de website blijft bij de zes velden uit docs/visie.md. Honoraria, omzet en de
-- zelfgerapporteerde wisselvlag gaan alleen de database in, zodat ze er zijn zodra
-- een latere fase ze mag gebruiken.
--
-- Vulgraad gemeten op boekjaar 2023 (6.131 organisaties):
--   rechtsvorm     6.131  (100%)
--   zorgsoort      5.552
--   baten zorg     4.198
--   wisselvlag       992  (waarvan 75 × "ja")
--   honoraria        425
--
-- Alles wat de bron niet levert blijft leeg. Niets wordt geschat of afgeleid.

-- ---------- organisatieniveau ----------

-- Subsector: de AGB-zorgsoort uit de dataset, teruggebracht tot negen groepen
-- (zie SUBSECTOR in pipeline/adapters/digimv_dataset.py). De 61 ruwe waarden zijn
-- te fijnmazig om op te navigeren; `sector` blijft 'zorg' zodat bestaande links
-- blijven werken.
alter table organisaties add column if not exists subsector text;
create index if not exists organisaties_subsector_idx on organisaties (subsector);

-- Totale baten uit zorg over het boekjaar. Maakt marktaandeel naar omvang mogelijk
-- in plaats van naar aantal cliënten — een kantoor met 134 kleine praktijken is
-- iets anders dan een kantoor met 92 grote instellingen.
alter table organisaties add column if not exists omzet_eur numeric;

-- ---------- opdrachtniveau ----------

-- Honoraria conform art. 2:382a BW. De bron levert de vier posten gescheiden;
-- honorarium_controle_eur en honorarium_overig_eur bestonden al.
comment on column opdrachten.honorarium_controle_eur is
  'Controle van de jaarrekening (art. 2:382a lid 1 sub a BW)';
comment on column opdrachten.honorarium_overig_eur is
  'Andere controleopdrachten, waaronder WNT (art. 2:382a lid 1 sub b BW)';
alter table opdrachten add column if not exists honorarium_fiscaal_eur numeric;
comment on column opdrachten.honorarium_fiscaal_eur is
  'Fiscale adviesdiensten (art. 2:382a lid 1 sub c BW)';
alter table opdrachten add column if not exists honorarium_nietcontrole_eur numeric;
comment on column opdrachten.honorarium_nietcontrole_eur is
  'Andere niet-controlediensten (art. 2:382a lid 1 sub d BW)';

-- Zelfgerapporteerd: "Bent u van accountant gewisseld?" Dit is een tweede,
-- onafhankelijke bron naast de uit de historie afgeleide wisseling in
-- v_wisselingen. Waar de twee van elkaar afwijken, is er iets om na te kijken —
-- een gratis controle op onze eigen extractie.
alter table opdrachten add column if not exists wissel_gerapporteerd boolean;

-- ---------- afgeleide: waar spreken de twee bronnen elkaar tegen? ----------

-- Geen opgeslagen tabel maar een view (docs/concept.md §5). Bedoeld voor intern
-- nakijken, niet voor de site.
create or replace view v_wissel_afwijking with (security_invoker = on) as
select o.organisatie_id,
       o.boekjaar,
       o.wissel_gerapporteerd,
       (w.organisatie_id is not null) as wissel_afgeleid
from opdrachten o
left join v_wisselingen w
  on  w.organisatie_id = o.organisatie_id
  and w.boekjaar_wissel = o.boekjaar
where o.wissel_gerapporteerd is not null
  and o.wissel_gerapporteerd <> (w.organisatie_id is not null);
