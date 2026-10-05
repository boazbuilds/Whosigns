import type { Metadata } from "next";
import Link from "next/link";
import { alleGunningen, type Gunning } from "@/lib/db";
import { LEIDER_MINIMUM, rasterstappen } from "@/lib/voorpagina";
import {
  aantalGunningen,
  datumNL,
  hoofdletter,
  kantoorPad,
  kortKantoor,
  nl,
  organisatiePad,
  sectorPad,
} from "@/lib/paden";
import { Kolomgrafiek, type Kolom } from "@/components/grafieken";
import {
  Doorklik,
  Foutmelding,
  Inklapbaar,
  KantoorLink,
  Kerncijfer,
  KortKantoorLink,
  Kruimels,
  Leeg,
  Telbalk,
} from "@/components/onderdelen";

export const metadata: Metadata = {
  title: "Aanbestedingen",
  description:
    "Welke accountantskantoren Europees aanbestede opdrachten wonnen, per " +
    "gunningsjaar en per sector van de opdrachtgever — uit TED.",
};

/** Zoveel gunningen staan open binnen het gekozen jaar; de rest achter een klik. */
const OPEN = 30;

/** Zoveel jaren in de keuzebalk; de reeks begint in 2015, dus voorlopig alle. */
const JAREN_IN_BALK = 12;

/** Organisaties zonder sector komen in de telling per sector onder dit kopje. */
const ZONDER_SECTOR = "zonder sector";

/**
 * Alleen in deze sector een telling per kantoor. Het is de sector die deze bron
 * zelf vult (zie SECTOR_UITLEG), en de enige met genoeg gunningen per jaar:
 * vanaf 2017 35 tot 73, tegen hooguit 22 in een andere sector. En die 22 waren
 * schijn: van de 123 gunningen onder "overig bedrijfsleven" kwamen er op
 * 5-10-2026 86 van gemeenten, veiligheidsregio's en provincies die het register
 * (nog) in die sector indeelt. Een lijst "gewonnen in het overig bedrijfsleven"
 * zou dus over gemeenten gaan.
 */
const SECTOR_MET_TELLING = "overheid";

/** Een naam die op een openbaar lichaam wijst, alleen voor de waarschuwing dat
 *  de sectorindeling niet klopt — nooit om iets in te delen. */
const OVERHEIDSNAAM = /^(gemeente|provincie|waterschap|hoogheemraadschap|veiligheidsregio)\b/i;

type Zoek = { searchParams: Promise<{ jaar?: string }> };

/** "2025" uit "2025-03-14"; null zonder datum. */
function gunningsjaar(gunning: Gunning): number | null {
  return gunning.gunningsdatum ? Number(gunning.gunningsdatum.slice(0, 4)) : null;
}

function sectorVan(gunning: Gunning): string {
  return gunning.organisaties?.sector ?? ZONDER_SECTOR;
}

/** Aantallen per sleutel, grootste eerst en bij gelijke stand op naam. */
function telling<T>(rijen: T[], sleutel: (rij: T) => string): [string, number][] {
  const per = new Map<string, number>();
  for (const rij of rijen) per.set(sleutel(rij), (per.get(sleutel(rij)) ?? 0) + 1);
  return [...per.entries()].sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0], "nl"));
}

export default async function Aanbestedingenpagina({ searchParams }: Zoek) {
  const { jaar } = await searchParams;

  let gunningen: Gunning[];
  try {
    gunningen = await alleGunningen();
  } catch (fout) {
    return <Foutmelding fout={fout} />;
  }

  const perJaar = new Map<number, Gunning[]>();
  const zonderDatum: Gunning[] = [];
  for (const gunning of gunningen) {
    const j = gunningsjaar(gunning);
    if (j === null) zonderDatum.push(gunning);
    else perJaar.set(j, [...(perJaar.get(j) ?? []), gunning]);
  }
  const jaren = [...perJaar.keys()].sort((a, b) => b - a);

  // Het lopende kalenderjaar is per definitie nog niet rond: op 5-10-2026
  // stonden er 66 gunningen in 2026 tegen 102 in 2025. Standaard dus het
  // nieuwste jaar dat al voorbij is; het lopende jaar blijft kiesbaar, met
  // "loopt nog" erbij. Een onzinnig jaartal valt terug op de standaard.
  const ditJaar = Number(
    new Date().toLocaleDateString("sv-SE", { timeZone: "Europe/Amsterdam" }).slice(0, 4),
  );
  const standaard = jaren.find((j) => j < ditJaar) ?? jaren[0] ?? null;
  const gekozen = jaren.includes(Number(jaar)) ? Number(jaar) : standaard;
  const getoond = gekozen === null ? [] : (perJaar.get(gekozen) ?? []);

  const opdrachtgevers = new Set(gunningen.map((g) => g.organisaties?.id).filter(Boolean));
  const kantoren = new Set(gunningen.map((g) => g.kantoren?.id).filter(Boolean));

  // Per sector van de opdrachtgever, in het gekozen jaar. Een telling per
  // kantoor alleen binnen één sector én één gunningsjaar (zie
  // SECTOR_MET_TELLING), en alleen als het er minstens LEIDER_MINIMUM zijn.
  // Over sectoren heen zou zo'n lijst een ranglijst zijn over opdrachtgevers
  // die niets met elkaar te maken hebben.
  const perSector = telling(getoond, sectorVan);
  const metKantoorlijst = perSector.filter(
    ([sector, aantal]) => sector === SECTOR_MET_TELLING && aantal >= LEIDER_MINIMUM,
  );
  const zonderKantoorlijst = perSector.filter(([sector]) => !metKantoorlijst.some(([s]) => s === sector));
  const verkeerdIngedeeld = getoond.filter(
    (g) => sectorVan(g) !== "overheid" && OVERHEIDSNAAM.test(g.organisaties?.naam ?? ""),
  ).length;

  const kolommen: Kolom[] = [...jaren].reverse().map((j) => {
    const aantal = perJaar.get(j)?.length ?? 0;
    return {
      label: String(j),
      kort: `’${String(j).slice(2)}`,
      waarde: aantal,
      weergave: nl(aantal),
      toelichting: j >= ditJaar ? "dit jaar loopt nog" : undefined,
      nadruk: j === gekozen,
      opschrift: j === gekozen,
    };
  });

  const regel = (gunning: Gunning, i: number) => (
    <tr key={`${gunning.publicatienummer}-${gunning.organisaties?.id ?? "?"}-${gunning.kantoren?.id ?? "?"}-${i}`}>
      <td className="jaar">{datumNL(gunning.gunningsdatum)}</td>
      <td>
        {gunning.organisaties ? (
          <Link href={organisatiePad(gunning.organisaties)}>{gunning.organisaties.naam}</Link>
        ) : (
          <span className="zacht">onbekend</span>
        )}
        <div className="klein zacht">
          {gunning.organisaties?.sector ? (
            <Link href={sectorPad(gunning.organisaties.sector)}>
              {hoofdletter(gunning.organisaties.sector)}
            </Link>
          ) : (
            ZONDER_SECTOR
          )}
        </div>
      </td>
      <td>
        {gunning.kantoren ? (
          <KantoorLink naam={gunning.kantoren.naam} naar={kantoorPad(gunning.kantoren)} />
        ) : (
          <span className="zacht">onbekend</span>
        )}
      </td>
      <td className="klein">
        <a
          href={`https://ted.europa.eu/nl/notice/-/detail/${gunning.publicatienummer}`}
          rel="noreferrer nofollow"
          target="_blank"
        >
          {gunning.publicatienummer}
        </a>
      </td>
    </tr>
  );
  const kop = (
    <thead>
      <tr>
        <th>Gegund</th>
        <th>Opdrachtgever</th>
        <th>Kantoor</th>
        <th>Bericht</th>
      </tr>
    </thead>
  );

  return (
    <>
      <Kruimels paden={[{ naar: "/", tekst: "Start" }, { tekst: "Aanbestedingen" }]} />

      <div className="paginakop">
        <h1>Aanbestedingen</h1>
        <p className="zacht klein" style={{ margin: "0.4rem 0 0", maxWidth: "44rem" }}>
          Accountantsdiensten die Europees zijn aanbesteed (TED): welk kantoor
          er benoemd is, door wie en wanneer. Een gunning zegt wie er benoemd is
          en wanneer — niet of de controle er kwam, en met welk oordeel. Daarom
          tellen gunningen nergens mee als controle.
        </p>
        <div className="kerncijfers">
          <Kerncijfer waarde={nl(gunningen.length)} naam="gunningen" />
          <Kerncijfer waarde={nl(opdrachtgevers.size)} naam="opdrachtgevers" />
          <Kerncijfer waarde={nl(kantoren.size)} naam="kantoren" naar="/kantoren" />
          <Kerncijfer
            waarde={jaren.length ? `${Math.min(...jaren)}–${Math.max(...jaren)}` : "—"}
            naam="gunningsjaren"
          />
        </div>
      </div>

      {jaren.length === 0 ? (
        <section className="kaart">
          <Leeg tekst="Nog geen gunningen met een datum in de database." />
        </section>
      ) : (
        <>
          <section className="kaart">
            <div className="kaartkop">
              <h2>Gunningen per jaar</h2>
            </div>
            <Kolomgrafiek
              titel="Aantal gunningen per gunningsjaar"
              kolommen={kolommen}
              raster={rasterstappen(Math.max(...kolommen.map((k) => k.waarde)))}
              rasterweergave={nl}
            />
            <p className="grafiekvoet">
              Het jaar van de gunning, niet een boekjaar: een kantoor dat in{" "}
              {gekozen} is benoemd, controleert doorgaans de boekjaren erna. Het
              aantal per jaar zegt vooral wat er Europees is aanbesteed en hier is
              ingelezen; onder de Europese drempel hoeft een opdrachtgever niet op
              TED te publiceren.
            </p>
            <Inklapbaar samenvatting="Als tabel">
              <div className="tabel-omhulsel">
                <table>
                  <thead>
                    <tr>
                      <th>Gunningsjaar</th>
                      <th className="getal">Gunningen</th>
                      <th className="getal">Opdrachtgevers</th>
                      <th className="getal">Kantoren</th>
                    </tr>
                  </thead>
                  <tbody>
                    {jaren.map((j) => {
                      const rijen = perJaar.get(j) ?? [];
                      return (
                        <tr key={j}>
                          <td className="jaar">
                            {j}
                            {j >= ditJaar ? <span className="zacht"> (loopt nog)</span> : null}
                          </td>
                          <td className="getal">{nl(rijen.length)}</td>
                          <td className="getal">
                            {nl(new Set(rijen.map((g) => g.organisaties?.id)).size)}
                          </td>
                          <td className="getal">
                            {nl(new Set(rijen.map((g) => g.kantoren?.id)).size)}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </Inklapbaar>
          </section>

          {jaren.length > 1 ? (
            <nav className="keuzebalk" aria-label="Kies een gunningsjaar">
              {jaren.slice(0, JAREN_IN_BALK).map((j) => (
                <Link
                  key={j}
                  href={`/aanbestedingen?jaar=${j}`}
                  className={gekozen === j ? "actief" : undefined}
                >
                  {j}{" "}
                  <span className="zacht">
                    ({perJaar.get(j)!.length}
                    {j >= ditJaar ? ", loopt nog" : ""})
                  </span>
                </Link>
              ))}
            </nav>
          ) : null}

          <div className="kolommen">
            <section className="kaart">
              <div className="kaartkop">
                <h2>Gegund in {gekozen}, per sector</h2>
                <span className="klein zacht">van de opdrachtgever</span>
              </div>
              <div className="tabel-omhulsel">
                <table>
                  <thead>
                    <tr>
                      <th>Sector</th>
                      <th className="getal">Gunningen</th>
                    </tr>
                  </thead>
                  <tbody>
                    {perSector.map(([sector, aantal]) => (
                      <tr key={sector}>
                        <td>
                          {sector === ZONDER_SECTOR ? (
                            <span className="zacht">{ZONDER_SECTOR}</span>
                          ) : (
                            <Link href={sectorPad(sector)}>{hoofdletter(sector)}</Link>
                          )}
                        </td>
                        <td className="getal">{nl(aantal)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <p className="klein zacht" style={{ marginBottom: 0 }}>
                Aantallen, geen aandelen: welke opdrachtgevers in een jaar
                aanbesteden, verschilt van jaar tot jaar. De sector is die waarin
                de opdrachtgever in dit register staat
                {verkeerdIngedeeld > 0
                  ? `, en die indeling is niet foutloos: ${verkeerdIngedeeld} van deze ${getoond.length} gunningen komen van een gemeente, provincie, waterschap of veiligheidsregio die (nog) niet onder de overheid staat`
                  : ""}
                .
              </p>
            </section>

            {metKantoorlijst.map(([sector, aantal]) => {
              const perKantoor = telling(
                getoond.filter((g) => sectorVan(g) === sector && g.kantoren),
                (g) => String(g.kantoren!.id),
              );
              const kantoorPerId = new Map(
                getoond.filter((g) => g.kantoren).map((g) => [String(g.kantoren!.id), g.kantoren!]),
              );
              const grootste = perKantoor[0]?.[1] ?? 0;
              return (
                <section className="kaart" key={sector}>
                  <div className="kaartkop">
                    <h2>
                      Gewonnen in de sector {sector}, {gekozen}
                    </h2>
                    <span className="klein zacht">{aantalGunningen(aantal)}</span>
                  </div>
                  <div className="tabel-omhulsel">
                    <table>
                      <thead>
                        <tr>
                          <th>Kantoor</th>
                          <th className="getal">Gunningen</th>
                          <th>
                            <span className="verborgen">Gunningen als balk</span>
                          </th>
                        </tr>
                      </thead>
                      <tbody>
                        {perKantoor.map(([id, n]) => {
                          const kantoor = kantoorPerId.get(id)!;
                          return (
                            <tr key={id}>
                              <td>
                                <KantoorLink naam={kantoor.naam} naar={kantoorPad(kantoor)} />
                              </td>
                              <td className="getal">
                                <strong>{n}</strong>
                              </td>
                              <td className="balkcel">
                                <Telbalk aantal={n} grootste={grootste} />
                              </td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                  <p className="klein zacht" style={{ marginBottom: 0 }}>
                    Gunningen in dit ene gunningsjaar en deze ene sector, van veel
                    naar weinig — geen marktaandeel en geen plek. Een gunning is
                    een benoeming voor doorgaans vier jaar, en wie in een jaar
                    aanbesteedt, verschilt per jaar.
                  </p>
                </section>
              );
            })}
          </div>

          {zonderKantoorlijst.length > 0 ? (
            <p className="klein zacht" style={{ marginTop: 0, maxWidth: "46rem" }}>
              {metKantoorlijst.length > 0
                ? "Een telling per kantoor staat er alleen voor de overheid, de sector die deze bron zelf vult"
                : `Bij de overheid waren het er in ${gekozen} minder dan ${LEIDER_MINIMUM}, te weinig voor een telling per kantoor`}
              ; voor de andere sectoren staan alleen de gunningen zelf hieronder.
            </p>
          ) : null}

          <section className="kaart">
            <div className="kaartkop">
              <h2>
                Alle gunningen in {gekozen} ({getoond.length})
              </h2>
            </div>
            {getoond.length === 0 ? (
              <Leeg tekst="Geen gunningen in dit jaar." />
            ) : (
              <>
                <div className="tabel-omhulsel">
                  <table>
                    {kop}
                    <tbody>{getoond.slice(0, OPEN).map(regel)}</tbody>
                  </table>
                </div>
                {getoond.length > OPEN ? (
                  <Inklapbaar samenvatting={`Nog ${getoond.length - OPEN} gunningen in ${gekozen}`}>
                    <div className="tabel-omhulsel">
                      <table>
                        {kop}
                        <tbody>{getoond.slice(OPEN).map((g, i) => regel(g, i + OPEN))}</tbody>
                      </table>
                    </div>
                  </Inklapbaar>
                ) : null}
              </>
            )}
            {zonderDatum.length > 0 ? (
              <p className="klein zacht" style={{ marginBottom: 0 }}>
                Zonder gunningsdatum (oudere TED-berichten), en daarom in geen
                enkel jaar:{" "}
                {zonderDatum.map((g, i) => (
                  <span key={`${g.publicatienummer}-${i}`}>
                    {i > 0 ? "; " : ""}
                    {g.organisaties ? (
                      <Link href={organisatiePad(g.organisaties)}>{g.organisaties.naam}</Link>
                    ) : (
                      "onbekend"
                    )}{" "}
                    → <KortKantoorLink kantoor={g.kantoren} />
                  </span>
                ))}
                .
              </p>
            ) : null}
          </section>
        </>
      )}

      <Doorklik
        items={[
          ...metKantoorlijst.slice(0, 1).flatMap(([sector]) =>
            telling(
              getoond.filter((g) => sectorVan(g) === sector && g.kantoren),
              (g) => String(g.kantoren!.id),
            )
              .slice(0, 3)
              .map(([id, n]) => {
                const kantoor = getoond.find((g) => String(g.kantoren?.id) === id)!.kantoren!;
                return {
                  naar: kantoorPad(kantoor),
                  tekst: kortKantoor(kantoor.naam),
                  toelichting: `${aantalGunningen(n)} in de sector ${sector}, ${gekozen}`,
                };
              }),
          ),
          ...getoond
            .filter((g) => g.organisaties && g.kantoren)
            .slice(0, 2)
            .map((g) => ({
              naar: organisatiePad(g.organisaties!),
              tekst: g.organisaties!.naam,
              toelichting: `gegund aan ${kortKantoor(g.kantoren!.naam)}`,
            })),
          ...perSector
            .filter(([sector]) => sector !== ZONDER_SECTOR)
            .slice(0, 3)
            .map(([sector]) => ({
              naar: sectorPad(sector),
              tekst: `Sector ${sector}: wie controleert er`,
            })),
          { naar: "/wisselingen", tekst: "Alle accountantswisselingen" },
          { naar: "/kantoren", tekst: "Alle kantoren" },
          { naar: "/sectoren", tekst: "Sectoren vergelijken" },
        ]}
      />
    </>
  );
}
