-- Kantoorprofiel: vestigingsplaats, rechtsvorm en vergunningsdatum.
--
-- Waarom: een kantoorpagina die alleen een naam en een AFM-nummer toont, is geen
-- profiel. Deze drie velden stonden al in de AFM-seed (seed/kantoren.csv, alle 233
-- rijen gevuld) maar werden niet weggeschreven — nu wel, zodat elk kantoor een
-- eigen paginaatje met basisinformatie krijgt.
--
-- vergunning_sinds is niet hetzelfde als de oprichtingsdatum: het is de datum
-- waarop de AFM de Wta-vergunning verleende. Voor de kantoren die er vanaf het
-- begin bij waren staat daar 13-8-2007 of 29-9-2008 (de invoering van de Wta);
-- daarna is het een echte startdatum. De kolomtoelichting zegt dat erbij, zodat
-- niemand het per ongeluk als "opgericht in" op de site zet.

alter table kantoren add column if not exists plaats text;
comment on column kantoren.plaats is
  'Vestigingsplaats volgens het AFM-vergunningenregister.';

alter table kantoren add column if not exists rechtsvorm text;
comment on column kantoren.rechtsvorm is
  'Rechtsvorm volgens het AFM-vergunningenregister (Besloten Vennootschap, Maatschap, ...).';

alter table kantoren add column if not exists vergunning_sinds date;
comment on column kantoren.vergunning_sinds is
  'Datum waarop de AFM de Wta-vergunning verleende — NIET de oprichtingsdatum. '
  'Voor kantoren van het eerste uur staat hier de invoeringsdatum van de Wta '
  '(2007-08-13 of 2008-09-29); daarna is het de echte startdatum van de vergunning.';
