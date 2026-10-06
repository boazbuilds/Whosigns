-- WhoSigns — de tekenend accountant erbij
--
-- Besluit van de opdrachtgever, 20-8-2026: de naam van de accountant die de
-- verklaring ondertekent mag worden opgeslagen en getoond, mits hij uit een
-- openbare bron komt — de gedeponeerde controleverklaring zelf, een eigen
-- publicatie van het kantoor, of een openbaar register (AFM, NBA). Dat draait de
-- guardrail van juli om ("nooit natuurlijke personen"), en het kopcommentaar van
-- 20260727000000_init.sql is daarop bijgewerkt.
--
-- De grondslag is uitdrukkelijk níét "accountants vallen buiten de AVG"; zo'n
-- uitzondering per beroepsgroep bestaat niet. De AVG geldt gewoon. Wat de
-- verwerking draagt is het gerechtvaardigd belang (art. 6 lid 1 sub f) van een
-- publiek naslagwerk over wie welke jaarrekening tekent, versterkt doordat het
-- gegeven al openbaar ís: de organisatie móét de verklaring deponeren en de
-- accountant staat in het openbare accountantsregister. Zie docs/concept.md §9,
-- inclusief wat er tegenover staat (privacyalinea, bezwaar, correctie).
--
-- Waarom een tekstkolom en nog geen tabel `accountants`
-- ----------------------------------------------------
-- Een eigen tabel met een sleutel per persoon is journalistiek het interessantst:
-- daarmee is partnerroulatie te volgen, en die is bij OOB's wettelijk verplicht.
-- Maar één persoon staat in de stukken in meerdere schrijfwijzen ("J. Jansen RA",
-- "drs. J. Jansen RA", met of zonder tussenvoegsel), en die samenvoegen is precies
-- het stille mergen dat dit project niet doet (docs/concept.md §9, punt
-- "Datakwaliteit"). Daarom eerst de naam zoals hij in het stuk staat, letterlijk.
-- Een genormaliseerde laag kan er later bovenop, met dezelfde review-queue-regel
-- als voor kantoornamen.
--
-- De vindplaats is die van de opdracht zelf (`bron_id`): de naam komt uit dezelfde
-- ondertekende verklaring als het oordeel. Komt hij ooit ergens anders vandaan,
-- dan hoort daar een eigen bronrij bij en pas dan een eigen kolom.
--
-- Leeg is een geldige waarde en betekent "niet vastgesteld", nooit "niet
-- getekend". Bij een gescande pdf zonder leesbare ondertekening, of bij twijfel
-- tussen twee namen, blijft dit veld leeg en gaat het geval naar review_queue.
-- Een verkeerde naam onder een niet-goedkeurend oordeel is geen leemte maar een
-- beschuldiging.

alter table opdrachten add column if not exists tekenend_accountant text;

comment on column opdrachten.tekenend_accountant is
  'Naam van de ondertekenende accountant, letterlijk zoals in de gedeponeerde '
  'verklaring. Leeg = niet vastgesteld, niet "niet getekend". Alleen uit '
  'openbare bronnen; zie docs/concept.md paragraaf 9.';
