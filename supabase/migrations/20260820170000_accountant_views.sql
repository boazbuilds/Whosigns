-- WhoSigns — doorklikken op de tekenend accountant
--
-- Besluit van de opdrachtgever, 20-8-2026: je moet op de accountant kunnen
-- klikken en dan zien welke jaarrekeningen hij allemaal heeft getekend. Daarmee
-- is ook de open vraag uit docs/concept.md §9 beantwoord — er komt een eigen
-- pagina per accountant.
--
-- `opdrachten.tekenend_accountant` bewaart de naam letterlijk zoals hij in het
-- stuk staat (zie 20260820160000). Voor een pagina is dat niet genoeg: dezelfde
-- persoon tekent de ene keer als "J. Jansen RA" en de andere keer als
-- "drs. J. Jansen RA", en dat zouden twee pagina's worden. Deze migratie legt de
-- groepering vast als view, zodat de site niet zijn eigen definitie verzint —
-- hetzelfde principe als bij v_wisselingen en v_marktaandeel.
--
-- Hoe de sleutel wordt gemaakt, en waarom zo voorzichtig
-- -----------------------------------------------------
-- Kleine letters, punten en komma's eruit, dubbele spaties weg, en hooguit drie
-- titels vooraan (drs, dr, mr, ir, ing, prof, mw, dhr). Meer niet.
--
-- Uitdrukkelijk NIET: titels ergens midden in de naam weghalen. "De Heer" is een
-- Nederlandse achternaam, en een regel die overal het woord "heer" wist maakt
-- daar "de" van. Ook de afsluitende RA/AA/RB blijft staan: "J. Jansen RA" en
-- "J. Jansen AA" zijn twee verschillende beroepstitels en vermoedelijk twee
-- verschillende mensen; ze samenvoegen zou een gok zijn.
--
-- Wat deze sleutel niet kan
-- -------------------------
-- Twee mensen met dezelfde initialen en achternaam vallen samen. Dat is niet op
-- te lossen met de gegevens die in een verklaring staan; een accountantsnummer
-- zou het oplossen, maar dat staat er niet in. De pagina moet daarom laten zien
-- bij welk kantoor elke opdracht hoorde, en waarschuwen zodra één sleutel bij
-- meer dan één kantoor voorkomt. Dat is namelijk óf een partner die is
-- overgestapt — journalistiek juist het interessante geval — óf twee naamgenoten,
-- en welke van de twee het is kunnen wij niet zien. Niet gokken: tonen en zeggen.
--
-- De naam die de pagina als kop draagt is de meest voorkomende schrijfwijze
-- (`mode()`), niet de langste of de eerste: die is het minst afhankelijk van
-- toeval in één document.

-- Eén rij per opdracht mét een vastgestelde ondertekenaar.
create or replace view v_accountant_opdracht with (security_invoker = on) as
with schoon as (
  select o.id            as opdracht_id,
         o.organisatie_id,
         o.kantoor_id,
         o.boekjaar,
         o.type_opdracht,
         o.oordeel,
         btrim(o.tekenend_accountant) as naam_zoals_getekend,
         regexp_replace(lower(btrim(o.tekenend_accountant)), '[.,;]', '', 'g') as kaal
  from opdrachten o
  where o.tekenend_accountant is not null
    and btrim(o.tekenend_accountant) <> ''
)
select opdracht_id,
       organisatie_id,
       kantoor_id,
       boekjaar,
       type_opdracht,
       oordeel,
       naam_zoals_getekend,
       btrim(regexp_replace(
         regexp_replace(
           regexp_replace(
             regexp_replace(kaal, '^\s*(drs|dr|mr|ir|ing|prof|mw|dhr)\s+', ''),
             '^\s*(drs|dr|mr|ir|ing|prof|mw|dhr)\s+', ''),
           '^\s*(drs|dr|mr|ir|ing|prof|mw|dhr)\s+', ''),
         '\s+', ' ', 'g')) as sleutel
from schoon;

-- Eén rij per accountant, voor de ranglijst en de zoekpagina.
create or replace view v_accountant with (security_invoker = on) as
select a.sleutel,
       mode() within group (order by a.naam_zoals_getekend) as naam,
       count(*)::int                        as aantal_opdrachten,
       count(distinct a.organisatie_id)::int as aantal_organisaties,
       count(distinct a.kantoor_id)::int     as aantal_kantoren,
       min(a.boekjaar)                      as eerste_boekjaar,
       max(a.boekjaar)                      as laatste_boekjaar
from v_accountant_opdracht a
where a.sleutel <> ''
group by a.sleutel;

comment on view v_accountant is
  'Eén rij per tekenend accountant, gegroepeerd op een sleutel die alleen '
  'schrijfwijze normaliseert (titels vooraan, punten, dubbele spaties). '
  'aantal_kantoren > 1 betekent overstap OF naamgenoot; dat onderscheid is uit '
  'een verklaring niet te maken. Zie docs/concept.md paragraaf 9.';
