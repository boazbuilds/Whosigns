-- Sectoren rechtzetten: openbaar bestuur naar overheid, schoolbesturen naar
-- onderwijs. Een marktaandeel geldt binnen één sector en één boekjaar; dan moet
-- wat in een sector staat er ook horen.
--
-- Gemeten op 5-10-2026 via PostgREST (17.653 organisaties, 61.700 opdrachten).
-- Telling: wettelijke en vrijwillige controles mét kantoor, zoals v_marktaandeel
-- ze telt.
--
-- 1. Openbaar bestuur stond in "overig bedrijfsleven"
-- ---------------------------------------------------
-- 231 organisaties met een SBI-code die met 84 begint stonden in "overig
-- bedrijfsleven": ruim negentig keer "Gemeente …", dertig keer "Gemeentehuis",
-- "Stadhuis" of "Raadhuis", vier provincies, dertien waterschappen,
-- veiligheidsregio's, omgevingsdiensten. Ze kwamen uit het marktonderzoek, dat
-- de sector uit de SBI-code afleidt, en laad_marktonderzoek.sector_uit_sbi had
-- voor hoofdgroep 84 geen hokje. Migratie 20260922160000 voegde daarna de
-- raadsinformatie-rij van dezelfde gemeente samen met de KvK-rij, en daar
-- verloor "overheid" van het SBI-hokje. Gevolg: 401 controles van gemeenten en
-- provincies telden mee in het marktaandeel van "overig bedrijfsleven", en
-- maakten daar ~93% van uit (2023: 35 van de 39).
--
-- Overheid wordt wat SBI 84.1 (openbaar bestuur) en 84.2 (defensie, justitie,
-- openbare orde, brandweer) heeft: 220 organisaties. Ook zbo's als het
-- Zorginstituut, ZonMW en de Koninklijke Bibliotheek; dat is inhoudelijk juist,
-- het zijn overheidsorganisaties zonder gemeenteraad. 84.3 (verplichte
-- sociale verzekeringen) blijft waar het staat: dat zijn naast het UWV vooral
-- sociale fondsen van cao-partijen. Twee bedrijfstakpensioenfondsen met 84.3
-- gaan naar pensioenfondsen; dat staat in hun naam en hun SBI-code zegt niets
-- anders dan dat de deelname verplicht is. De vier SBI-84-organisaties die al
-- in zorg stonden (GGD, RAV) blijven daar: alleen "overig bedrijfsleven" gaat
-- om.
--
-- pipeline/laad_marktonderzoek.py doet voortaan hetzelfde bij het laden.
--
-- 2. Schoolbesturen stonden in overheid
-- -------------------------------------
-- Een openbaar schoolbestuur legt zijn jaarrekening aan de gemeenteraad voor,
-- dus raadsinformatie vindt de verklaring; TED-gunningen noemen ook
-- onderwijsbesturen als aanbestedende dienst. Beide laders maakten elke nieuwe
-- organisatie aan als "overheid". Onderwijs telde daardoor 19 tot 21 controles
-- per jaar (2021-2024), terwijl er nog 5 tot 13 per jaar van schoolbesturen
-- elders meetelden, vooral in overheid.
--
-- Wat hier verhuist, staat hieronder per id. Twee bronnen, allebei DUO
-- (CC BY 4.0), allebei vastgelegd in pipeline/seed/duo_besturen.csv:
--
-- a. **Op KvK-nummer** (12): organisaties met een KvK-nummer dat in de
--    besturenlijsten van DUO staat, maar met een SBI-hokje als sector
--    ("Stichting ARCHIPEL SCHOLEN" stond in zakelijke dienstverlening).
--    Zorginstellingen met een eigen school (Visio, Kempenhaeghe) blijven in
--    zorg.
-- b. **Op naam** (96): organisaties in overheid zonder KvK-nummer waarvan de
--    naam in de DUO-lijsten bij precies één schoolbestuur hoort. Zie
--    pipeline/adapters/duo_besturen.py voor de regels: geen gemeenten, de
--    rechtsvorm telt mee, en een naam die ooit bij een tweede KvK-nummer hoorde
--    levert niets op.
--
--    71 krijgen ook het KvK-nummer. Bij 24 staat dat nummer al op een andere
--    rij, of wijzen twee overheidsrijen naar hetzelfde bestuur ("Stichting
--    Limburgs Voortgezet Onderwijs" en dezelfde naam met een staart erachter).
--    Die krijgen alleen de sector; het nummer niet, want de kolom is uniek en
--    een naam is geen harde sleutel om op samen te voegen. Ze gaan als
--    "mogelijk dubbel" naar de review-queue, één regel per KvK-nummer met de
--    id's erbij. Samenvoegen botst nergens: op geen enkel boekjaar hebben twee
--    van die rijen allebei een controle (gemeten). Eén rij (27206, "OSG De
--    Hogeberg") krijgt alleen de sector: de stichting achter het DUO-nummer
--    bestaat pas sinds 27-7-2018, en de enige controle van de rij is boekjaar
--    2017 — toen was de school nog van een ander bevoegd gezag.
-- c. **Met de hand** (23): mbo-instellingen en hogescholen die DUO niet op naam
--    vond omdat de naam te kort is ("Curio", "Stichting Albeda") of een staart
--    uit het aanbestedingsbericht draagt. Alleen wat zonder twijfel een
--    instelling is. Bewust NIET: gemeentelijke onderwijsdiensten ("Openbaar
--    Onderwijs Gemeente Terschelling"), bestuurscommissies van een gemeente,
--    muziekscholen, "N.V. Sport, Recreatie en Onderwijsvoorzieningen",
--    Wageningen University & Research (universiteit én onderzoeksinstituut),
--    de universitaire medische centra (zorg), en po/vo-besturen die DUO niet
--    eenduidig vond. Liever een gat dan een gok.
--
-- Effect (2019-2024, per boekjaar):
--     onderwijs              16 17 21 19 19 20  ->  26 27 26 25 32 30
--     overheid              306 325 301 315 297 307 -> 333 367 340 351 319 331
--     overig bedrijfsleven   41 53 47 45 39 39  ->   4  1  3  3  4  5
--
-- Volgorde met de laders
-- ----------------------
-- De laders zetten de sector alleen bij het aanmaken; een bestaande rij houdt
-- wat hier gezet wordt. Raadsinformatie met --vervang ruimt wel organisaties
-- zonder KvK-nummer op als hun opdrachten bij een herlezing een andere naam
-- krijgen, en maakt ze dan opnieuw aan. Daarom hoort elke lader die op naam
-- aanmaakt zelf "onderwijs" te kiezen voor een schoolbestuur, via
-- duo_besturen.bij_aanmaak (laad_gunningen.py doet dat sinds deze migratie),
-- en krijgen 71 van deze rijen hier hun KvK-nummer: een rij mét nummer ruimt
-- --vervang nooit op. De laders zelf kennen op naam géén nummer toe (op
-- 6-10-2026 wees de naamregel bij 4 van 161 rijen mét nummer naar een ander
-- nummer dan het echte); zij zetten de kandidaat in de review-queue. De
-- nummers hieronder zijn stuk voor stuk met de hand nagelopen.
--
-- De id's zijn hard: er is één productiedatabase en deze lijsten horen bij de
-- stand van 5-10-2026. Op 6-10-2026 opnieuw gemeten, ook met de strengere
-- regel voor de plaatsstaart die de adapter sindsdien heeft: dezelfde
-- lijsten, geen nieuwe botsing. Toen ook elke toewijzing hieronder
-- naast de besturenlijsten en RIO van die dag gelegd: de 12 van 2a staan met
-- hun eigen nummer in een besturenlijst, en bij alle 96 van 2b staat de naam
-- (of een oudere naam van hetzelfde bestuur) onder precies dat KvK-nummer. Een
-- RIO-bestuur draagt nooit twee nummers.
--
-- Idempotent: elke stap filtert op de sector die hij verandert, en een
-- review-regel komt er alleen bij als er voor dat KvK-nummer nog geen open
-- regel is. Nagespeeld op een lokale Postgres 16 met de hele migratieketen,
-- eerst op een proefopstelling met verzonnen namen en daarna op een kopie van
-- de openbare tabellen: 12 + 96 sectoren naar onderwijs, 71 KvK-nummers, 21
-- review-regels, 23 met de hand, 2 naar pensioenfondsen, 220 naar overheid.
-- Een tweede run veranderde niets.

-- 2a. Schoolbestuur op KvK-nummer: sector uit een SBI-hokje (of leeg) naar onderwijs.
update organisaties o
   set sector = 'onderwijs'
  from (values
    (33405, '41238611'),    -- Stichting Alkmaarse Katholieke Scholen
    (33406, '54224446'),    -- Stichting ARCHIPEL SCHOLEN
    (33462, '40507708'),    -- Stichting voor Christelijk Voortgezet Onderwijs in Baarn/So…
    (33846, '34319180'),    -- Algemene Bijzondere Scholengroep Amsterdam ABSA Scholengroep
    (34066, '09124577'),    -- Stichting Alliantie Voortgezet Onderwijs voor Nijmegen en h…
    (34092, '41194761'),    -- Stichting Gooise Scholen Federatie
    (34140, '53232747'),    -- Stichting Samenwerkingsschool Rivierenwijk
    (37933, '41158916'),    -- Stichting Lucas Onderwijs
    (39116, '41027077'),    -- Stg. Konot
    (39232, '41213974'),    -- Wijzer aan de Amstel
    (41617, '27308764'),    -- 'De Haagse Scholen', stichting voor primair en speciaal ope…
    (41685, '41046798')     -- Stichting Essentius
  ) as v(id, kvk)
 where o.id = v.id
   and o.kvk_nummer = v.kvk
   and (o.sector is null or o.sector in (
     'overheid', 'landbouw en visserij', 'industrie en bouw', 'handel',
     'transport en logistiek', 'ict en media', 'financiële dienstverlening',
     'vastgoed', 'zakelijke dienstverlening', 'overig bedrijfsleven'));

-- 2b. Schoolbestuur op naam: eerst de sector, dan waar het kan het KvK-nummer.
--     Een null als nummer: wel de sector, geen nummer (zie 27206 hierboven).
create temporary table schoolbestuur_op_naam (id bigint, kvk text) on commit drop;
insert into schoolbestuur_op_naam (id, kvk) values
  (20074, '41013432'),    -- Noorderpoort
  (20081, '41084408'),    -- Stichting HAS Den Bosch
  (20137, '41210838'),    -- Stichting Amsterdamse Hogeschool voor de Kunsten
  (20150, '32124769'),    -- Stichting voor Onderwijs op Reformatorische Grondslag
  (20159, '41002686'),    -- Stichting NHL Stenden Hogeschool
  (20217, '41051951'),    -- De Onderwijsspecialisten
  (20264, '41131797'),    -- Stichting voor Educatie en Beroepsonderwijs Zadkine
  (20287, '55757278'),    -- MBO Utrecht
  (20290, '34277470'),    -- Stichting Dunamare Onderwijsgroep
  (20670, '41088091'),    -- Stichting Design Academy Eindhoven
  (20672, '41106257'),    -- Lowys Porquinstichting
  (20685, '41241789'),    -- Stichting Talland College
  (23866, '18086732'),    -- Stichting Openbaar Onderwijs Land van Altena
  (23946, '17160875'),    -- Stichting Invitare Openbaar Onderwijs
  (23992, '41105340'),    -- Stichting ROC West-Brabant
  (24086, '34102519'),    -- Onderwijsstichting Zelfstandige Gymnasia
  (24117, '12041226'),    -- Stichting Onderwijs Midden-Limburg
  (24123, '51614286'),    -- Stichting Achterhoek VO
  (24143, '41186931'),    -- Stichting ROC Midden Nederland
  (24253, '34317570'),    -- Stichting Spaarnesant
  (24920, '41025299'),    -- Landstede
  (24923, '41261341'),    -- Stichting ROC Nijmegen e.o.
  (24927, '41095199'),    -- Scholengemeenschap De Rooi Pannen
  (24954, '41159510'),    -- mboRijnland
  (24958, '41246832'),    -- Aeres groep
  (24960, '55752330'),    -- Stichting Zaam, Interconfessioneel Voortgezet Onderwijs
  (25013, '41030828'),    -- Stichting Het Assink Lyceum
  (25016, '41126201'),    -- Grafisch Lyceum Rotterdam
  (25026, '41027871'),    -- Stichting Carmelcollege
  (25045, '41150857'),    -- Stichting "Het Rijnlands Lyceum"
  (25061, '41064644'),    -- Samenwerkingsstichting voortgezet onderwijs regio Venlo
  (25104, '17234696'),    -- "Stichting PlatOO, bestuur voor openbaar en algemeen toegan…
  (25145, '09132117'),    -- Stichting IJsselgraaf
  (25187, '24391113'),    -- Stichting Onderwijsgroep Galilei
  (25204, '24405279'),    -- Stichting Nissewijs
  (25295, '34107734'),    -- Stichting Openbaar Primair Onderwijs Haarlemmermeer
  (25307, '08111837'),    -- Stichting Proo Noord-Veluw/e
  (25335, '24387240'),    -- Stichting Openbare Scholengroep Vlaardingen Schiedam
  (25365, '01123270'),    -- Stichting Openbaar Primair Onderwijs Furore
  (25373, '01102489'),    -- Stichting RSG Magister Alvinus
  (25417, '67188877'),    -- Stichting Winkler Prins
  (25419, '01123358'),    -- Scholengroep OPRON, stichting voor openbaar primair onderwi…
  (25439, '24349878'),    -- Stichting Onderwijs Primair
  (25450, '01123254'),    -- Elan Onderwijsgroep
  (25451, '01140932'),    -- Stichting Samenwerkingsbestuur Kyk
  (25452, '59619295'),    -- Stichting Speciaal Onderwijs Fryslân
  (25478, '09113954'),    -- Stichting voor openbaar voortgezet onderwijs van Wageningen…
  (25560, '51350963'),    -- Stichting scholengroep openbaar onderwijs Lelystad
  (25616, '09161451'),    -- Stichting Scholengroep Veluwezoom
  (25625, '27263332'),    -- Stichting Librijn openbaar onderwijs
  (25655, '41244139'),    -- Stichting Varietas
  (25684, '27323857'),    -- Stichting Openbaar Primair Onderwijs Wassenaar
  (25688, '02090846'),    -- Stichting Quadraten
  (25775, '41234200'),    -- Stichting Katholiek Onderwijs Volendam
  (25786, '20116029'),    -- Stichting Openbaar Basisonderwijs West-Brabant, gevestigd t…
  (25787, '28082157'),    -- Stichting Openbaar Basisonderwijs Duin- en Bollenstreek
  (25797, '88084167'),    -- Stichting Openbaar Primair Onderwijs Noordenveld
  (25818, '01167668'),    -- Stichting Openbaar Primair Onderwijs Aa en Hunze
  (25821, '88820793'),    -- Stichting Onderwijsgroep Midden Friesland
  (25869, '24362372'),    -- Stichting Openbaar Primair Onderwijs Albrandswaard
  (27163, '08155806'),    -- Stichting Openbaar Primair Onderwijs Apeldoorn
  (27172, '32112275'),    -- Stichting Florente
  (27185, '24387235'),    -- Stichting Primo Schiedam
  (27206, null),          -- OSG De Hogeberg: stichting 72241713 pas sinds 2018, controle 2017
  (29268, '51386216'),    -- Stichting Openbaar Primair Onderwijs Borger-Odoorn
  (30412, '41068501'),    -- Stichting Gilde Opleidingen
  (30413, '41046206'),    -- LiemersNovum
  (30417, '08126099'),    -- Stichting Regionaal Opleidingencentrum van Twente
  (30427, '14060995'),    -- Stichting Zuyd Hogeschool
  (30430, '40342087'),    -- Vereniging Christelijk Voortgezet Onderwijs Rotterdam en om…
  (30434, '30156443'),    -- Stichting Grafisch Lyceum Utrecht
  (30435, '41213992')     -- Onderwijsstichting Esprit
;

create temporary table mogelijk_dubbel (id bigint, kvk text, anderen bigint[]) on commit drop;
insert into mogelijk_dubbel (id, kvk, anderen) values
  (20073, '41020699', array[32616]),              -- Stichting Regionaal Opleidingen Centrum Drenthe
  (20104, '41095503', array[33610]),              -- Stichting Xpect Primair
  (20221, '30199604', array[33264]),              -- Stichting Openbaar Voortgezet Onderwijs Utrecht
  (20251, '41053607', array[34049]),              -- Stichting Quadraam
  (20675, '56004028', array[34118]),              -- Openbaar Onderwijs Zwolle en Regio
  (24053, '01166182', array[24056, 34120]),       -- Stichting Openbaar Primair Onderwijs Wolderwijs
  (24056, '01166182', array[24053, 34120]),       -- Stichting openbaar primair onderwijs Wolderwijs…
  (24147, '14077279', array[30460]),              -- Stichting Limburgs Voortgezet Onderwijs
  (25010, '08184425', array[37327]),              -- Stichting Veluwse Onderwijsgroep
  (25032, '41093932', array[37944]),              -- ROC Summa College
  (25046, '09124577', array[34066]),              -- Stichting @voCampus
  (25050, '41194761', array[34092]),              -- Gooise Scholen Federatie
  (25170, '41115393', array[33361]),              -- Stichting voor Openbaar Voortgezet Onderwijs op…
  (25340, '01111331', array[39118]),              -- Stichting Openbaar Primair Onderwijs De Basis
  (25348, '22043910', array[33465]),              -- Stichting Scholengroep Pontes
  (25358, '32105543', array[39168]),              -- Stichting Openbaar Basisonderwijs Hilversum
  (25425, '30200523', array[34117]),              -- Stichting Stichting Openbaar Onderwijs Rijn- en…
  (25454, '01140506', array[39151]),              -- Stichting Proloog voor primair openbaar onderwi…
  (25471, '28106428', array[34142]),              -- Stichting Openbaar Voortgezet Onderwijs Alphen …
  (25719, '24349808', array[42104]),              -- Stichting voor Openbaar Onderwijs in Dordrecht
  (25729, '32137060', array[33850]),              -- Stichting Openbaar Basisonderwijs Dronten
  (25756, '24374006', array[27211]),              -- Stichting Nestas Scholengroep voor Katholiek en…
  (27211, '24374006', array[25756]),              -- Stichting Openbaar Primair Onderwijs Dordrecht
  (30460, '14077279', array[24147])               -- Stichting Limburgs Voortgezet Onderwijs, SWbest…
;

update organisaties o
   set sector = 'onderwijs'
 where o.sector = 'overheid'
   and (o.id in (select id from schoolbestuur_op_naam)
        or o.id in (select id from mogelijk_dubbel));

-- Rij voor rij en niet in één update: twee rijen met hetzelfde nummer in één
-- statement zou de unieke sleutel breken, en een nummer dat intussen ergens
-- anders is opgedoken (een aanlevering tussen meting en migratie) moet de rij
-- laten staan in plaats van de migratie te laten vallen.
do $$
declare
  rij record;
begin
  for rij in select * from schoolbestuur_op_naam where kvk is not null order by id loop
    update organisaties o
       set kvk_nummer = rij.kvk
     where o.id = rij.id
       -- Alleen waar de sectorstap hierboven ook gold: een rij die intussen
       -- in een andere sector terechtkwam krijgt het nummer niet zonder de
       -- sectorbeslissing.
       and o.sector = 'onderwijs'
       and o.kvk_nummer is null
       and not exists (select 1 from organisaties x where x.kvk_nummer = rij.kvk);
  end loop;
end $$;

-- Wat het nummer niet kreeg omdat het al bezet is, gaat ook naar de review:
-- het geval van 2b hierboven, nu op de stand van het moment zelf.
insert into mogelijk_dubbel (id, kvk, anderen)
select s.id, s.kvk, array_agg(x.id order by x.id)
  from schoolbestuur_op_naam s
  join organisaties o on o.id = s.id and o.kvk_nummer is null
  join organisaties x on x.kvk_nummer = s.kvk and x.id <> s.id
 group by s.id, s.kvk;

-- Eén review-regel per KvK-nummer, met alle id's die erbij lijken te horen.
-- Alleen id's en het nummer: de namen staan in de database en een mens zoekt
-- ze daar op.
insert into review_queue (soort, payload)
select 'naam_match',
       jsonb_build_object(
         'bron', 'migratie 20261006110000',
         'reden', 'mogelijk dubbel',
         'kvk_nummer', g.kvk,
         'organisatie_ids', to_jsonb(g.ids),
         'toelichting', 'naam wijst in de DUO-besturenlijsten naar dit '
                        'KvK-nummer, dat al bij een andere rij staat of door '
                        'meer rijen wordt geclaimd; niet samengevoegd')
  from (
    select d.kvk, array_agg(distinct x order by x) as ids
      from mogelijk_dubbel d
     cross join lateral unnest(d.anderen || d.id) as x
     where exists (select 1 from organisaties o where o.id = x)
     group by d.kvk
  ) g
 where cardinality(g.ids) > 1
   and not exists (
     select 1 from review_queue r
      where r.soort = 'naam_match' and r.status = 'open'
        and r.payload->>'reden' = 'mogelijk dubbel'
        and r.payload->>'kvk_nummer' = g.kvk);

-- 2c. Mbo-instellingen en hogescholen, met de hand nagelopen.
update organisaties
   set sector = 'onderwijs'
 where sector = 'overheid'
   and id in (
     (20089),  -- Graafschap College
     (20102),  -- Stichting Albeda
     (20103),  -- Stichting Yuverta
     (20171),  -- ROC van Amsterdam - Flevoland en Voortgezet Onderwijs van A…
     (20281),  -- Stichting Groen Onderwijs Oost Nederland handelsnaam Zone.c…
     (24091),  -- MBO Utrecht (uit een aanbestedingsbericht)
     (24095),  -- Stichting Regionaal Opleidingen Centrum De Leijgraaf
     (24146),  -- Da Vinci college (aanbestedende dienst)
     (24896),  -- Stichting voor Beroepsonderwijs en VE Westelijk Zuid-Limburg
     (24924),  -- Stichting Arcus College
     (24928),  -- ROC Friese Poort
     (24931),  -- ROC van Amsterdam, VOvA en ROC Flevoland
     (24956),  -- Rijn IJssel
     (24961),  -- Stichting voor Interconfessioneel Beroeps- en Algemeen Vorm…
     (24974),  -- Helicon Opleidingen
     (24990),  -- Scalda Stichting voor middelbaar beroepsonderwijs en volwas…
     (24991),  -- Stichting Regionaal Opleidingen Centrum Noord- Kennemerland…
     (25025),  -- Stichting Regionaal Opleidingen Centrum TOP
     (25028),  -- ROC Friese Poort, Centrale Diensten
     (30416),  -- ROC Tilburg: School voor VAVO, School voor logistiek en Mob…
     (30429),  -- Hotelschool The Hague
     (30432),  -- Stichting Gerrit Rietveld Academie te Amsterdam, Hogeschool…
     (30453)   -- Curio
   );

-- 1. Openbaar bestuur (SBI 84.1 en 84.2) uit "overig bedrijfsleven" naar
--    overheid. Ná 2a, zodat de drie schoolbesturen met SBI 84.12 al in
--    onderwijs staan.
update organisaties
   set sector = 'pensioenfondsen'
 where sector = 'overig bedrijfsleven'
   and sbi_code like '843%'
   and id in (
     41354,  -- Stichting Bedrijfstakpensioenfonds voor de Particuliere Beveiliging
     41770   -- Stichting Bedrijfstakpensioenfonds TrueBlue
   );

update organisaties
   set sector = 'overheid'
 where sector = 'overig bedrijfsleven'
   and sbi_code ~ '^84[12]';
