-- Drie AFM-nummers die het register niet meer kent, maar de database nog wel.
--
-- laad_kantoren.py kon tot 5-10-2026 alleen toevoegen: wat uit de wekelijkse
-- AFM-snapshot verdween, bleef in `kantoren` staan met actief = true en met de
-- vlaggen van de laatste week waarin het er nog wel in stond. Gemeten op
-- 5-10-2026 via PostgREST:
--
--     13020232  Stichting Autoriteit Financiële Markten  OOB  0 opdrachten  weg sinds 31-8-2026
--     13000575  VBWA B.V.                                     0 opdrachten  weg sinds 31-8-2026
--     13000055  Maatschap Steens & Partners                   1 opdracht    weg sinds 28-9-2026
--               Accountants en Adviseurs
--
-- De eerste is de ergste. De toezichthouder stond van 15-8 tot 31-8-2026 met
-- wettelijkecontrole=Ja in haar eigen export, en daarmee op de site als zevende
-- OOB-kantoor naast de Big Four, BDO en Forvis Mazars — ook nog vijf weken nadat
-- de AFM het zelf had rechtgezet. De database telde 7 OOB-kantoren, het
-- register 6.
--
-- Vanaf nu doet de lader dit zelf: seed/kantoren_vervallen.csv voor wie
-- destijds bevoegd tekende, en elk AFM-nummer dat in geen van beide AFM-lijsten
-- staat gaat op inactief. Deze migratie zet de stand van vandaag recht, zodat de
-- site niet hoeft te wachten op de eerstvolgende lading.
--
-- Bewust niets verwijderd. Aan 13000055 hangt een opdracht over 2024 die de
-- maatschap bevoegd tekende, en een verwijderde rij is niet terug te halen. Ook
-- de AFM-rij heeft geen opdrachten, maar of die weg mag is een keuze en geen
-- correctie. wta_vergunning gaat wél uit: de kolom zegt "staat in het
-- AFM-register", in de tegenwoordige tijd — net als bij Accon avm en Astrium.
--
-- Op naam en nummer, niet alleen op nummer: is een van deze nummers inmiddels
-- opnieuw uitgegeven of hernoemd, dan blijft die rij met rust en lost de lader
-- het bij de volgende run op.

update kantoren
set actief = false,
    oob_vergunning = false,
    wta_vergunning = false
where (afm_nummer, naam) in (
  ('13020232', 'Stichting Autoriteit Financiële Markten'),
  ('13000575', 'VBWA B.V.'),
  ('13000055', 'Maatschap Steens & Partners Accountants en Adviseurs')
);

-- De lader schrijft de toelichting van 13000055 en 13000575 uit
-- kantoren_vervallen.csv; de AFM staat daar bewust niet in (zie
-- GEEN_ACCOUNTANTSORGANISATIE in pipeline/adapters/afm_register.py), dus haar
-- verklaring komt hier.
update kantoren
set toelichting = 'Geen accountantsorganisatie. De AFM stond van 15-8 tot 31-8-2026 '
                  'zelf in haar register van accountantsorganisaties, met een '
                  'vergunning voor wettelijke controles bij organisaties van openbaar '
                  'belang — vrijwel zeker een fout in de bron; in de export van '
                  '31-8-2026 was de vermelding weer verdwenen.'
where afm_nummer = '13020232'
  and naam = 'Stichting Autoriteit Financiële Markten';
