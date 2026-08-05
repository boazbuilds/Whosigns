# Wat er gemeten wordt, en waar je het ziet

*Ingericht 5-8-2026.*

Twee vragen, twee verschillende plekken. Ze zitten niet in dezelfde hoek omdat
ze technisch niets met elkaar te maken hebben.

## "Wie komt er op de website?" → Vercel

Niet in Supabase, en dat kán ook niet. De website wordt op de server van Vercel
in elkaar gezet; pas het resultaat gaat naar de browser van de bezoeker.
Supabase ziet dus alleen Vercel, nooit een bezoeker. Sterker nog: het antwoord
van de database wordt een uur hergebruikt, dus honderd bezoekers op dezelfde
pagina leveren bij Supabase één verzoek op.

Daarom staat er in `web/app/layout.tsx` één regel `<Analytics />` van Vercel.
Die telt paginaweergaven, land en van welke pagina iemand kwam — zonder
cookies en zonder de bezoeker over andere sites heen te volgen, dus er hoeft
geen cookiemelding bij.

**Aanzetten:** Vercel-project → tabblad *Analytics* → *Enable*. Zolang dat uit
staat doet de regel niets. Kijken doe je op datzelfde tabblad.

**Weghalen:** de regel `<Analytics />` en de import eruit, plus
`npm remove @vercel/analytics`.

## "Waar zoeken mensen naar?" → tabel `zoekopdrachten`

Wél in Supabase, in een eigen tabel. Elke zoekopdracht schrijft één regel: het
ingetypte woord, hoeveel treffers het gaf, en wanneer.

Geen IP-adres, geen browser, geen sessie — niets waarmee twee zoekopdrachten
aan dezelfde persoon zijn te knopen. Daarmee is het geen persoonsgegeven en
hoeft er niets omheen geregeld te worden.

De reden dat dit er is, is niet nieuwsgierigheid maar werkvoorraad: **een
zoekopdracht met nul treffers is een gat in de database.** Iemand zoekt een
organisatie die er nog niet in staat. Dat is de directe aanwijzing welke bron
er als volgende bij moet.

Kijken doe je in het Supabase-dashboard, onder *SQL Editor*:

```sql
-- Waar wordt naar gezocht zonder dat we het hebben?
select term, count(*) as keer, max(moment) as laatst
from zoekopdrachten
where resultaten = 0
group by term
order by keer desc, laatst desc
limit 50;

-- En waar wél, zodat je ziet wat er gebruikt wordt
select term, count(*) as keer
from zoekopdrachten
where resultaten > 0
group by term
order by keer desc
limit 50;
```

De lijst is niet openbaar op te vragen: de tabel heeft bewust wél een
insert-policy en géén select-policy, dus via de API komt er niets uit. Het
dashboard leest eromheen.

### De keerzijde, eerlijk opgeschreven

Overal elders geldt: de site leest, de pipeline schrijft, en de secret key komt
nooit buiten GitHub Secrets. Die regel blijft staan. Maar de site heeft alleen
de publishable key, en die staat in de broncode van elke pagina. Wie hem
overneemt kan dus rijen in deze ene tabel zetten.

Daarom: geen leesrechten, en de lengte van het zoekwoord afgetopt op 120 tekens
zodat de tabel niet als opslag te misbruiken is. Loopt hij toch vol met rommel,
dan is de rem één regel in de SQL Editor:

```sql
drop policy publiek_loggen on zoekopdrachten;
```

Daarna stopt het meeschrijven en werkt de rest van de site gewoon door.

## Wat er níét gemeten wordt

Geen sessies, geen klikpaden binnen de site, geen bezoekers die over meerdere
bezoeken herkend worden, en geen koppeling tussen "wie" en "wat gezocht".
Zolang de site op `noindex` staat en alleen jij hem kent, zou dat toch vooral
jouw eigen verkeer meten.
