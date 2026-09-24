/**
 * De dashboardblokken van de voorpagina. Elk blok krijgt zijn getallen
 * kant-en-klaar binnen en tekent er een grafiek of tabel van, met de uitleg
 * die nodig is om het getal niet verkeerd te lezen.
 *
 * Elke grafiek heeft een tabel met dezelfde getallen onder "Als tabel": wie
 * geen muis heeft, geen kleur ziet of het precieze getal wil, vindt het daar.
 */

import Link from "next/link";
import type { Bevinding, Gunning, Kantoor, OordelenJaar, WisselJaar } from "@/lib/db";
import type { PrijsJaar } from "@/lib/analyse";
import {
  DEKKING_GRENZEN,
  dekkingsklasse,
  LEIDER_COMPLEET,
  LEIDER_MINIMUM,
  rasterstappen,
  type Dekking,
  type Sectorleider,
  type Transferbalans,
} from "@/lib/voorpagina";
import {
  Balansgrafiek,
  Kolomgrafiek,
  metTeken,
  Schaal,
  Warmtekaart,
  type Kolom,
} from "@/components/grafieken";
import {
  Inklapbaar,
  KantoorLink,
  KortKantoorLink,
  Oordeel,
} from "@/components/onderdelen";
import {
  hoofdletter,
  kantoorPad,
  kortKantoor,
  nl,
  organisatiePad,
  procent,
  sectorPad,
} from "@/lib/paden";

/** "’16" onder een kolom; het volle jaartal staat in de tooltip en de tabel. */
function kortJaar(jaar: number): string {
  return `’${String(jaar).slice(2)}`;
}

// ------------------------------------------------------------ wisselkans

/**
 * Het boekjaar waarin de verplichte kantoorroulatie voor organisaties van
 * openbaar belang inging: de Wta schrijft sinds 1 januari 2016 voor dat een
 * OOB na hoogstens tien jaar een ander accountantskantoor neemt (eerst acht;
 * de Wijzigingswet financiële markten 2016 maakte er tien van, in lijn met
 * EU-verordening 537/2014). De piek in de wisselgrafiek valt precies in dat
 * jaar: in de data van september 2026 kwamen 86 van de 150 wisselingen van
 * 2016 van OOB's. Een wettelijk gegeven en geen afgeleide, dus een constante.
 */
const ROULATIEJAAR = 2016;

/** Onder zoveel organisaties met een controle in beide jaren is een
 *  wisselpercentage te grillig om te tekenen. */
const MINIMUM_PAREN = 100;

export function Wisselkans({ jaren }: { jaren: WisselJaar[] }) {
  const getekend = jaren.filter((j) => j.paren >= MINIMUM_PAREN);
  if (!getekend.length) return null;
  const kansen = getekend.map((j) => (100 * j.wisselingen) / j.paren);
  const kolommen: Kolom[] = getekend.map((j, i) => ({
    label: String(j.boekjaar),
    kort: kortJaar(j.boekjaar),
    waarde: kansen[i],
    weergave: procent(kansen[i]),
    toelichting: `${nl(j.wisselingen)} van ${nl(j.paren)} organisaties wisselden`,
    nadruk: j.boekjaar === ROULATIEJAAR,
    opschrift: j.boekjaar === ROULATIEJAAR || i === getekend.length - 1,
  }));
  const metRoulatie = getekend.some((j) => j.boekjaar === ROULATIEJAAR);

  // Opinion shopping: wisselen organisaties vaker na slecht nieuws? Over alle
  // jaren samen, want per jaar zijn de aantallen na slecht nieuws te klein.
  const som = (veld: Exclude<keyof WisselJaar, "boekjaar">) =>
    jaren.reduce((totaal, j) => totaal + j[veld], 0);
  const naGoed = { paren: som("paren_na_goedkeurend"), wissels: som("wisselingen_na_goedkeurend") };
  const naSlecht = {
    paren: som("paren_na_slecht_nieuws"),
    wissels: som("wisselingen_na_slecht_nieuws"),
  };
  const vergelijkbaar = naGoed.paren >= MINIMUM_PAREN && naSlecht.paren >= MINIMUM_PAREN;
  const kansGoed = vergelijkbaar ? (100 * naGoed.wissels) / naGoed.paren : 0;
  const kansSlecht = vergelijkbaar ? (100 * naSlecht.wissels) / naSlecht.paren : 0;
  // Twee procentpunt is ruwweg de onzekerheid van een percentage over een paar
  // honderd paren; daaronder noemen we het geen verschil.
  const conclusie =
    Math.abs(kansSlecht - kansGoed) < 2
      ? "Vrijwel geen verschil: in deze gegevens wisselen organisaties na slecht nieuws niet vaker van kantoor dan na een goedkeurende verklaring."
      : kansSlecht > kansGoed
        ? "Na slecht nieuws wisselen organisaties hier vaker van kantoor."
        : "Na slecht nieuws wisselen organisaties hier juist minder vaak van kantoor.";

  return (
    <section className="kaart">
      <div className="kaartkop">
        <h2>Hoe vaak wordt er gewisseld?</h2>
        <Link href="/wisselingen">Alle wisselingen →</Link>
      </div>
      <p className="klein zacht" style={{ marginTop: 0 }}>
        Deel van de organisaties met een controle in twee opeenvolgende
        boekjaren dat van kantoor wisselde.
      </p>
      <Kolomgrafiek
        titel="Wisselkans per boekjaar"
        kolommen={kolommen}
        raster={rasterstappen(Math.max(...kansen))}
        rasterweergave={(n) => procent(n, 0)}
      />
      {metRoulatie ? (
        <p className="grafiekvoet">
          <i className="sleutel sleutel-nadruk" />
          {ROULATIEJAAR}: het jaar waarin de verplichte kantoorroulatie voor
          organisaties van openbaar belang inging.
        </p>
      ) : null}

      {vergelijkbaar ? (
        <>
          <div className="vergelijking">
            <div>
              <span className="waarde">{procent(kansGoed)}</span>
              <span className="naam">
                wisselde na een goedkeurend oordeel ({nl(naGoed.wissels)} van{" "}
                {nl(naGoed.paren)})
              </span>
            </div>
            <div>
              <span className="waarde">{procent(kansSlecht)}</span>
              <span className="naam">
                wisselde na slecht nieuws ({nl(naSlecht.wissels)} van {nl(naSlecht.paren)})
              </span>
            </div>
          </div>
          <p className="grafiekvoet">
            {conclusie} Slecht nieuws is hier een niet-goedkeurend oordeel of een
            continuïteitsparagraaf in het boekjaar vóór de wissel; veel daarvan is
            een beperking om de WNT, niet om de jaarrekening zelf.
          </p>
        </>
      ) : null}

      <Inklapbaar samenvatting="Als tabel">
        <div className="tabel-omhulsel">
          <table>
            <thead>
              <tr>
                <th>Boekjaar</th>
                <th className="getal">Organisaties</th>
                <th className="getal">Wisselden</th>
                <th className="getal">Kans</th>
              </tr>
            </thead>
            <tbody>
              {jaren.map((j) => (
                <tr key={j.boekjaar}>
                  <td className="jaar">{j.boekjaar}</td>
                  <td className="getal">{nl(j.paren)}</td>
                  <td className="getal">{nl(j.wisselingen)}</td>
                  <td className="getal">
                    {j.paren ? procent((100 * j.wisselingen) / j.paren) : "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Inklapbaar>
    </section>
  );
}

// -------------------------------------------------------- transferbalans

export function Transfermarkt({
  balans,
  kantoorPerId,
}: {
  balans: Transferbalans;
  kantoorPerId: Map<number, Kantoor>;
}) {
  if (!balans.rijen.length) return null;
  const periode = balans.vanaf === balans.tot ? `${balans.tot}` : `${balans.vanaf}–${balans.tot}`;
  const pad = (id: number, naam: string, afm: string | null) =>
    kantoorPad(kantoorPerId.get(id) ?? { id, naam, afm_nummer: afm });
  return (
    <section className="kaart">
      <div className="kaartkop">
        <h2>Transferbalans {periode}</h2>
        <Link href="/kantoren">Alle kantoren →</Link>
      </div>
      <p className="klein zacht" style={{ marginTop: 0 }}>
        Gewonnen en verloren cliënten van de {balans.rijen.length} kantoren met
        de meeste beweging, uit {nl(balans.wisselingen)} wisselingen in deze
        boekjaren.
      </p>
      <Balansgrafiek
        titel={`Gewonnen en verloren cliënten per kantoor, boekjaar ${periode}`}
        links="verloren"
        rechts="gewonnen"
        rijen={balans.rijen.map((rij) => ({
          sleutel: String(rij.kantoorId),
          naam: <Link href={pad(rij.kantoorId, rij.naam, rij.afmNummer)}>{kortKantoor(rij.naam)}</Link>,
          naamTekst: rij.naam,
          links: rij.verloren,
          rechts: rij.gewonnen,
        }))}
      />
      <Inklapbaar samenvatting="Als tabel">
        <div className="tabel-omhulsel">
          <table>
            <thead>
              <tr>
                <th>Kantoor</th>
                <th className="getal">Gewonnen</th>
                <th className="getal">Verloren</th>
                <th className="getal">Saldo</th>
              </tr>
            </thead>
            <tbody>
              {balans.rijen.map((rij) => (
                <tr key={rij.kantoorId}>
                  <td>
                    <Link href={pad(rij.kantoorId, rij.naam, rij.afmNummer)}>{rij.naam}</Link>
                  </td>
                  <td className="getal">{nl(rij.gewonnen)}</td>
                  <td className="getal">{nl(rij.verloren)}</td>
                  <td className="getal">
                    <strong>{metTeken(rij.saldo)}</strong>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Inklapbaar>
    </section>
  );
}

// --------------------------------------------------------- sectorleiders

export function Sectorleiders({
  leiders,
  kantoorPerId,
}: {
  leiders: Sectorleider[];
  kantoorPerId: Map<number, Kantoor>;
}) {
  const getoond = leiders.filter((l) => kantoorPerId.has(l.kantoorId));
  if (!getoond.length) return null;
  return (
    <section className="kaart">
      <div className="kaartkop">
        <h2>Wie leidt per sector</h2>
        <Link href="/sectoren">Sectoren vergelijken →</Link>
      </div>
      <div className="tabel-omhulsel">
        <table>
          <thead>
            <tr>
              <th>Sector</th>
              <th>Boekjaar</th>
              <th className="getal">Controles</th>
              <th>Grootste kantoor</th>
              <th className="getal">Aandeel</th>
              <th className="getal" title="Aandeel van hetzelfde kantoor een boekjaar eerder">
                Jaar ervoor
              </th>
              <th className="getal" title="Aandeel van de vier grootste kantoren samen">
                Top 4 samen
              </th>
              <th className="getal">Kantoren</th>
            </tr>
          </thead>
          <tbody>
            {getoond.map((leider) => {
              const kantoor = kantoorPerId.get(leider.kantoorId)!;
              return (
                <tr key={leider.sector}>
                  <td>
                    <Link href={sectorPad(leider.sector)}>{hoofdletter(leider.sector)}</Link>
                  </td>
                  <td className="jaar">{leider.boekjaar}</td>
                  <td className="getal">{nl(leider.controles)}</td>
                  <td>
                    <KantoorLink naam={kantoor.naam} naar={kantoorPad(kantoor)} />
                    {leider.gedeeld ? (
                      <span
                        className="klein zacht"
                        title="Een ander kantoor heeft in deze sector evenveel controles."
                      >
                        {" "}
                        (gedeeld)
                      </span>
                    ) : null}
                  </td>
                  <td className="getal">
                    <strong>{procent(100 * leider.aandeel)}</strong>
                  </td>
                  <td className="getal zacht">
                    {leider.aandeelVorigJaar === null
                      ? "—"
                      : procent(100 * leider.aandeelVorigJaar)}
                  </td>
                  <td className="getal">{procent(100 * leider.top4)}</td>
                  <td className="getal">{nl(leider.kantoren)}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <p className="grafiekvoet">
        Per sector het nieuwste boekjaar dat al vrijwel compleet in de database
        staat: minstens {procent(100 * LEIDER_COMPLEET, 0)} van het aantal
        controles van het jaar ervoor, en minstens {LEIDER_MINIMUM}. Een aandeel
        geldt binnen zijn sector; tussen sectoren zegt het niets.
      </p>
    </section>
  );
}

// --------------------------------------------------------------- dekking

export function Dekkingskaart({ dekking }: { dekking: Dekking }) {
  if (!dekking.rijen.length || !dekking.jaren.length) return null;
  const grenzen = [1, ...DEKKING_GRENZEN];
  const stappen = grenzen.map((onder, i) =>
    i + 1 < grenzen.length ? `${nl(onder)}–${nl(grenzen[i + 1] - 1)}` : `${nl(onder)}+`,
  );
  return (
    <section className="kaart">
      <div className="kaartkop">
        <h2>Wat staat er in het register</h2>
        <Link href="/sectoren">Alle sectoren →</Link>
      </div>
      <p className="klein zacht" style={{ marginTop: 0, maxWidth: "46rem" }}>
        Controles per sector en boekjaar. Waar een rij begint, begint de bron;
        waar een kolom licht is, staat dat boekjaar nog niet compleet in de
        database. Daarom vergelijkt deze site marktaandelen alleen binnen één
        sector en één boekjaar.
      </p>
      <Warmtekaart
        titel="Controles per sector en boekjaar"
        kolommen={dekking.jaren.map((jaar) => ({ label: String(jaar), kort: kortJaar(jaar) }))}
        rijen={dekking.rijen.map((rij) => ({
          sleutel: rij.sector,
          kop: rij.verzameld ? (
            <span title={dekking.verzameldeSectoren.join(", ")}>Overige sectoren</span>
          ) : (
            <Link href={sectorPad(rij.sector)}>{hoofdletter(rij.sector)}</Link>
          ),
          kopTekst: rij.verzameld ? "Overige sectoren" : hoofdletter(rij.sector),
          waarden: dekking.jaren.map((jaar) => rij.perJaar.get(jaar) ?? 0),
        }))}
        totaal={{
          kop: "Totaal",
          waarden: dekking.jaren.map((jaar) => dekking.totaalPerJaar.get(jaar) ?? 0),
        }}
        klasse={dekkingsklasse}
        eenheid={(n) => `${nl(n)} ${n === 1 ? "controle" : "controles"}`}
      />
      <Schaal titel="controles" stappen={stappen} />
      {dekking.verzameldeSectoren.length ? (
        <p className="grafiekvoet">
          Overige sectoren: {dekking.verzameldeSectoren.join(", ")}.
        </p>
      ) : null}
    </section>
  );
}

// ---------------------------------------------------------------- oordelen

/**
 * Onder zoveel gelezen verklaringen in één boekjaar is een percentage
 * niet-goedkeurend te grillig voor de grafiek; zo'n jaar staat alleen in de
 * tabel.
 */
const MINIMUM_GELEZEN = 100;

/**
 * De reeks begint bij het eerste boekjaar met een brede basis. Daarvoor lezen
 * we ruim honderd verklaringen per jaar, vooral van beursfondsen; daarna ruim
 * duizend, vooral van zorginstellingen. Eén percentage over die twee groepen
 * in één reeks zou vooral de wissel van groep laten zien.
 */
const BREDE_BASIS = 500;

export function OordelenPerJaar({ jaren }: { jaren: OordelenJaar[] }) {
  const eerste = jaren.find((j) => j.gelezen >= BREDE_BASIS)?.boekjaar;
  if (eerste === undefined) return null;
  const getekend = jaren.filter((j) => j.boekjaar >= eerste && j.gelezen >= MINIMUM_GELEZEN);
  const ervoor = jaren.filter((j) => j.boekjaar < eerste);
  const niet = (j: OordelenJaar) => j.beperking + j.oordeelonthouding + j.afkeurend;
  const kolommen: Kolom[] = getekend.map((j) => {
    const aandeel = (100 * niet(j)) / j.gelezen;
    const wnt = j.beperking_wnt ? `, ${nl(j.beperking_wnt)} met WNT als grond` : "";
    return {
      label: String(j.boekjaar),
      kort: kortJaar(j.boekjaar),
      waarde: aandeel,
      weergave: procent(aandeel),
      toelichting: `${nl(niet(j))} van ${nl(j.gelezen)} verklaringen${wnt}`,
      opschrift: true,
    };
  });
  const gemiddeldErvoor = ervoor.length
    ? Math.round(ervoor.reduce((t, j) => t + j.gelezen, 0) / ervoor.length)
    : 0;

  return (
    <section className="kaart">
      <div className="kaartkop">
        <h2>Niet-goedkeurende oordelen</h2>
        <Link href="/bevindingen">Bevindingen →</Link>
      </div>
      <p className="klein zacht" style={{ marginTop: 0 }}>
        Deel van de gelezen controleverklaringen bij jaarrekeningen met een
        beperking, oordeelonthouding of afkeurend oordeel.
      </p>
      <Kolomgrafiek
        titel="Aandeel niet-goedkeurende oordelen per boekjaar"
        kolommen={kolommen}
        raster={[0]}
        rasterweergave={(n) => procent(n, 0)}
      />
      <p className="grafiekvoet">
        De sprong vanaf 2023 komt vooral van beperkingen om de WNT (zie de
        bevindingen): de accountant kon de topinkomens van binnen een groep
        gedetacheerde functionarissen niet vaststellen. Dat is geen bevinding
        over de jaarrekening zelf.
        {ervoor.length
          ? ` Vóór ${eerste} lazen we zo'n ${nl(gemiddeldErvoor)} verklaringen per jaar, vooral van beursfondsen; die jaren staan alleen in de tabel.`
          : ""}
      </p>
      <Inklapbaar samenvatting="Als tabel">
        <div className="tabel-omhulsel">
          <table>
            <thead>
              <tr>
                <th>Boekjaar</th>
                <th className="getal">Gelezen</th>
                <th className="getal">Niet goedkeurend</th>
                <th className="getal" title="Beperking met de WNT als vastgestelde grond">
                  waarvan WNT
                </th>
                <th className="getal">Continuïteit</th>
              </tr>
            </thead>
            <tbody>
              {jaren.map((j) => (
                <tr key={j.boekjaar}>
                  <td className="jaar">{j.boekjaar}</td>
                  <td className="getal">{nl(j.gelezen)}</td>
                  <td className="getal">
                    {nl(niet(j))}{" "}
                    <span className="zacht">({procent((100 * niet(j)) / j.gelezen)})</span>
                  </td>
                  <td className="getal">{nl(j.beperking_wnt)}</td>
                  <td className="getal">{nl(j.continuiteit)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Inklapbaar>
    </section>
  );
}

// ------------------------------------------------------------- honoraria

export function Prijsontwikkeling({ jaren }: { jaren: PrijsJaar[] }) {
  if (!jaren.length) return null;
  const kolommen: Kolom[] = jaren.map((j) => {
    const pct = 100 * j.mediaanVerandering;
    return {
      label: `${j.boekjaar - 1} → ${j.boekjaar}`,
      kort: kortJaar(j.boekjaar),
      waarde: pct,
      weergave: metTeken(pct, (n) => procent(n)),
      toelichting: `mediaan van ${nl(j.paren)} paren`,
      opschrift: true,
    };
  });
  const dun = jaren.filter((j) => j.paren < MINIMUM_PAREN);
  return (
    <section className="kaart">
      <div className="kaartkop">
        <h2>Prijs van de controle</h2>
        <Link href="/honoraria">Honoraria →</Link>
      </div>
      <p className="klein zacht" style={{ marginTop: 0 }}>
        Mediane verandering van het controlehonorarium ten opzichte van het jaar
        ervoor, bij dezelfde organisatie en hetzelfde kantoor.
      </p>
      <Kolomgrafiek
        titel="Mediane jaarlijkse verandering van het controlehonorarium"
        kolommen={kolommen}
        raster={[0]}
        rasterweergave={(n) => procent(n, 0)}
      />
      <p className="grafiekvoet">
        Gemeten op paren, omdat een gemiddelde per jaar vooral zou meten wélke
        organisaties dat jaar in de database staan.
        {dun.length
          ? ` De kolommen vanaf ${dun[0].boekjaar} rusten op minder dan ${MINIMUM_PAREN} paren per jaar: een indicatie, geen marktgemiddelde.`
          : ""}
      </p>
      <Inklapbaar samenvatting="Als tabel">
        <div className="tabel-omhulsel">
          <table>
            <thead>
              <tr>
                <th>Boekjaren</th>
                <th className="getal">Paren</th>
                <th className="getal">Mediane verandering</th>
              </tr>
            </thead>
            <tbody>
              {jaren.map((j) => (
                <tr key={j.boekjaar}>
                  <td className="jaar">
                    {j.boekjaar - 1} → {j.boekjaar}
                  </td>
                  <td className="getal">{nl(j.paren)}</td>
                  <td className="getal">
                    {metTeken(100 * j.mediaanVerandering, (n) => procent(n))}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Inklapbaar>
    </section>
  );
}

// ---------------------------------------------------------------- lijstjes

export function OpvallendeOordelen({ rijen }: { rijen: Bevinding[] }) {
  if (!rijen.length) return null;
  return (
    <section className="kaart">
      <div className="kaartkop">
        <h2>Zwaarste oordelen</h2>
        <Link href="/bevindingen">Alle →</Link>
      </div>
      <p className="klein zacht" style={{ marginTop: 0 }}>
        Nieuwste eerst: afkeurend, oordeelonthouding, of een beperking die over
        de jaarrekening zelf gaat.
      </p>
      <table>
        <tbody>
          {rijen.map((rij, i) => (
            <tr key={`${rij.organisaties?.id ?? "?"}-${rij.boekjaar}-${i}`}>
              <td className="jaar">{rij.boekjaar}</td>
              <td>
                {rij.organisaties ? (
                  <Link href={organisatiePad(rij.organisaties)}>{rij.organisaties.naam}</Link>
                ) : (
                  "onbekend"
                )}
                <div className="klein zacht">
                  <KortKantoorLink kantoor={rij.kantoren} /> ·{" "}
                  <Oordeel waarde={rij.oordeel} />
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}

/** "13 aug 2026": kort genoeg voor de kantlijn van een lijstje. */
function korteDatum(waarde: string | null): string {
  if (!waarde) return "—";
  const datum = new Date(waarde);
  if (Number.isNaN(datum.getTime())) return waarde;
  return datum.toLocaleDateString("nl-NL", {
    day: "numeric",
    month: "short",
    year: "numeric",
    timeZone: "UTC",
  });
}

export function RecentGegund({ rijen }: { rijen: Gunning[] }) {
  if (!rijen.length) return null;
  return (
    <section className="kaart">
      <div className="kaartkop">
        <h2>Recent gegund</h2>
      </div>
      <p className="klein zacht" style={{ marginTop: 0 }}>
        Europees aanbestede accountantsopdrachten, nieuwste gunning eerst: wie
        er benoemd is, nog vóór de eerste controle.
      </p>
      <table>
        <tbody>
          {rijen.map((rij, i) => (
            <tr key={`${rij.publicatienummer}-${rij.organisaties?.id ?? "?"}-${rij.kantoren?.id ?? "?"}-${i}`}>
              <td className="jaar">{korteDatum(rij.gunningsdatum)}</td>
              <td>
                {rij.organisaties ? (
                  <Link href={organisatiePad(rij.organisaties)}>{rij.organisaties.naam}</Link>
                ) : (
                  "onbekend"
                )}
                <div className="klein zacht">
                  gegund aan <KortKantoorLink kantoor={rij.kantoren} />
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}
