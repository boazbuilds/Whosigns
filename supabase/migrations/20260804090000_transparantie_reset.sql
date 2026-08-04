-- Alles uit transparantieverslagen wissen, zodat de aangescherpte lader het
-- er in één run weer schoon in zet.
--
-- Aanleiding (nagemeten 4-8-2026): de eerste leesregels plakten losse
-- pdf-regels aan elkaar en lieten halve namen door. In de database staan
-- daardoor organisaties als "Nederlandse organisatie voor wetenschappelijk
-- Stichting Pensioenfonds Medisch Specialisten" (twee cliënten aan elkaar),
-- "Stichting Mooiland van organisaties organisaties van van onder f
-- EU-verordening 537/2014." (naam plus zijbalktekst, als duplicaat naast de
-- echte corporatie Stichting Mooiland) en losse staarten als
-- "Zorgverzekeraar U.A.". De leesregels zijn aangescherpt
-- (pipeline/adapters/transparantie.py, met de meting in de tests); omdat
-- deze bron alleen aanvult wat nergens anders staat, is wissen en opnieuw
-- laden de veiligste schoonmaak: de workflow "Transparantiedata laden"
-- bouwt daarna precies dezelfde rijen weer op, maar dan met schone namen.

-- Eerst de opdrachten die uit deze bron kwamen.
delete from opdrachten o
using bronnen b
where o.bron_id = b.id
  and b.bron_type = 'transparantieverslag';

-- Dan de bronregels zelf (elke run maakte er nieuwe bij; nu wezen).
delete from bronnen b
where b.bron_type = 'transparantieverslag'
  and not exists (select 1 from opdrachten o where o.bron_id = b.id);

-- Open naamtwijfels uit deze bron: de herlaadrun meldt ze zo nodig opnieuw.
delete from review_queue
where soort = 'naam_match'
  and status = 'open'
  and payload->>'bron' = 'transparantieverslag';

-- Tot slot de organisaties die alleen door deze bron zijn aangemaakt
-- (sector OOB, geen KvK-nummer) en nu nergens meer een opdracht hebben.
-- Organisaties die intussen ook uit een andere bron een opdracht kregen,
-- blijven staan.
delete from organisaties o
where o.sector = 'OOB'
  and o.kvk_nummer is null
  and not exists (select 1 from opdrachten op where op.organisatie_id = o.id);
