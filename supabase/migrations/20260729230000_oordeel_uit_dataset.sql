-- WhoSigns — het oordeel uit de dataset ernaast leggen
--
-- Het oordeel was ons zwakste veld: tekstinterpretatie van een pdf, met twee
-- reparatierondes achter de rug. De dataset heeft het óók, gestructureerd, en de
-- twee blijken het grotendeels eens:
--
--   686 opdrachten boekjaar 2023 vergeleken
--     666  eens          (97%)
--      17  oneens
--       3  geen dataset-waarde
--
-- Dat is de eerste onafhankelijke bevestiging dat de extractie werkt. De 17
-- afwijkingen zijn geen ruis maar werk: waar twee bronnen elkaar tegenspreken
-- hoort een mens te kijken. Daarvoor is v_oordeel_afwijking.
--
-- LET OP: de bron heeft twéé oordeelvelden en die zijn oneens met elkaar.
--   bestandAccVerklSoortControleVerkl_N  (per document)   8 oordeelonthoudingen
--   qAccVerklVorm                        (vragenlijst)   46 oordeelonthoudingen
-- Onze pdf-extractie vond er 5. Het documentveld is dus het betrouwbare; het
-- vragenlijstveld wordt kennelijk verkeerd ingevuld. We nemen alleen het eerste.

-- Het oordeel zoals de bron het meldt. Blijft náást `oordeel`, dat uit de
-- gedeponeerde verklaring zelf komt -- de verklaring is het stuk dat is
-- ondertekend, het datasetveld is een formulierantwoord. Waar wij niets hebben
-- (gescande pdf) is dit veld het enige dat er is; de website laat dan zien dat
-- het zelfgerapporteerd is.
alter table opdrachten add column if not exists oordeel_gerapporteerd text
  check (oordeel_gerapporteerd in
    ('goedkeurend', 'beperking', 'oordeelonthouding', 'afkeurend'));

-- Datum waarop de accountantsverklaring is ondertekend. Interessant omdat laat
-- deponeren zelf een signaal is; nog niet in de UI.
alter table opdrachten add column if not exists verklaring_datum date;

-- ---------- afgeleide: waar spreken de twee oordeelbronnen elkaar tegen? ----------

-- Bedoeld voor intern nakijken, niet voor de site. Dit is de review-lijst waar de
-- roadmap om vraagt ("25 organisaties handmatig naleggen"), maar gericht: alleen
-- de gevallen waar er werkelijk iets te kiezen valt.
create or replace view v_oordeel_afwijking with (security_invoker = on) as
select o.organisatie_id,
       org.naam            as organisatie,
       o.boekjaar,
       o.oordeel           as oordeel_uit_verklaring,
       o.oordeel_gerapporteerd,
       o.kantoor_id
from opdrachten o
join organisaties org on org.id = o.organisatie_id
where o.oordeel_gerapporteerd is not null
  and o.oordeel is not null
  and o.oordeel <> o.oordeel_gerapporteerd;
