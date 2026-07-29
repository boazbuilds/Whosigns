import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import {
  opdrachtenVanOrganisatie,
  organisatieOpKvk,
  organisatiesInGemeente,
  organisatiesInSector,
  organisatiesInSubsector,
  wisselingen,
} from "@/lib/db";
import { periodes, wisseljaren } from "@/lib/analyse";
import {
  aantalJaren,
  jarenReeks,
  kantoorPad,
  nummerUitSlug,
  OPDRACHT_LABEL,
  organisatiePad,
  sectorPad,
  subsectorPad,
} from "@/lib/paden";
import { Doorklik, Foutmelding, Leeg, Oordeel } from "@/components/onderdelen";

type Params = { params: Promise<{ slug: string }> };

export async function generateMetadata({ params }: Params): Promise<Metadata> {
  const { slug } = await params;
  const org = await organisatieOpKvk(nummerUitSlug(slug)).catch(() => null);
  if (!org) return { title: "Organisatie niet gevonden" };
  // De noordster uit docs/visie.md, letterlijk als paginatitel: wie dit googelt
  // hoort hier uit te komen.
  return {
    title: `Wie is de accountant van ${org.naam}?`,
    description:
      `Alle accountants van ${org.naam} (KvK ${org.kvk_nummer}) per boekjaar, ` +
      `inclusief wisselingen en het oordeel bij de jaarrekening.`,
  };
}

export default async function Organisatiepagina({ params }: Params) {
  const { slug } = await params;
  const kvk = nummerUitSlug(slug);

  let org;
  try {
    org = await organisatieOpKvk(kvk);
  } catch (fout) {
    return <Foutmelding fout={fout} />;
  }
  if (!org) notFound();

  const opdrachten = await opdrachtenVanOrganisatie(org.id);
  const reeksen = periodes(opdrachten);
  const wissels = wisseljaren(opdrachten);
  const huidige = reeksen[0];
  const alleJaren = opdrachten.map((o) => o.boekjaar);

  // Organisaties uit dezelfde subsector zijn interessanter om naar door te klikken
  // dan willekeurige zorgorganisaties: een ziekenhuis naast een tandartspraktijk
  // zegt niets. Alleen als de subsector ontbreekt vallen we terug op de sector.
  const [plaatsgenoten, sectorgenoten, wisselingenZelfdeJaar] = await Promise.all([
    org.gemeente ? organisatiesInGemeente(org.gemeente) : Promise.resolve([]),
    org.subsector
      ? organisatiesInSubsector(org.subsector, 30)
      : org.sector
        ? organisatiesInSector(org.sector, 30)
        : Promise.resolve([]),
    wissels.size
      ? wisselingen({ boekjaar: Math.max(...wissels), limiet: 20 })
      : Promise.resolve([]),
  ]);

  const anderePlaatsgenoten = plaatsgenoten.filter((o) => o.id !== org.id);
  const andereSectorgenoten = sectorgenoten.filter((o) => o.id !== org.id);
  const laatsteWisseljaar = wissels.size ? Math.max(...wissels) : null;

  return (
    <>
      <div className="paginakop">
        <h1>{org.naam}</h1>
        <p className="metaregel">
          <span>KvK {org.kvk_nummer ?? "onbekend"}</span>
          {org.gemeente ? <span>{org.gemeente}</span> : null}
          {org.subsector ? (
            <span>
              <Link href={subsectorPad(org.subsector)}>{org.subsector}</Link>
            </span>
          ) : org.sector ? (
            <span>
              <Link href={sectorPad(org.sector)}>{org.sector}</Link>
            </span>
          ) : null}
          <span>{jarenReeks(alleJaren)}</span>
        </p>

        {huidige ? (
          <p className="samenvatting">
            Huidige accountant:{" "}
            <strong>
              <Link
                href={kantoorPad({
                  afm_nummer: huidige.afmNummer,
                  naam: huidige.kantoorNaam,
                })}
              >
                {huidige.kantoorNaam}
              </Link>
            </strong>{" "}
            <span className="zacht">
              — {aantalJaren(huidige.jaren.length)} ({jarenReeks(huidige.jaren)})
              {reeksen.length > 1 && laatsteWisseljaar
                ? `, gewisseld in boekjaar ${laatsteWisseljaar}`
                : ", geen wisseling in deze periode"}
            </span>
          </p>
        ) : null}
      </div>

      <section className="kaart">
        <h2>Accountant per boekjaar</h2>
        {opdrachten.length === 0 ? (
          <Leeg tekst="Voor deze organisatie staat nog geen opdracht in de database." />
        ) : (
          <div className="tabel-omhulsel">
            <table>
              <thead>
                <tr>
                  <th>Boekjaar</th>
                  <th>Accountantskantoor</th>
                  <th>Opdracht</th>
                  <th>Oordeel</th>
                  <th>Bron</th>
                </tr>
              </thead>
              <tbody>
                {opdrachten.map((opdracht) => (
                  <tr
                    key={`${opdracht.boekjaar}-${opdracht.type_opdracht}`}
                    className={wissels.has(opdracht.boekjaar) ? "wissel" : undefined}
                  >
                    <td className="jaar">{opdracht.boekjaar}</td>
                    <td>
                      {opdracht.kantoren ? (
                        <Link href={kantoorPad(opdracht.kantoren)}>
                          {opdracht.kantoren.naam}
                        </Link>
                      ) : (
                        <span className="zacht">niet herleid</span>
                      )}
                      {wissels.has(opdracht.boekjaar) ? (
                        <> <span className="label label-let-op">wisseling</span></>
                      ) : null}
                    </td>
                    <td className="zacht">
                      {OPDRACHT_LABEL[opdracht.type_opdracht] ?? opdracht.type_opdracht}
                    </td>
                    <td>
                      <Oordeel waarde={opdracht.oordeel} />
                      {opdracht.continuiteitsonzekerheid ? (
                        <> <span className="label label-let-op">continuïteit</span></>
                      ) : null}
                    </td>
                    <td className="klein">
                      {opdracht.bronnen?.url ? (
                        <a
                          href={opdracht.bronnen.url}
                          rel="noreferrer nofollow"
                          target="_blank"
                        >
                          {opdracht.bronnen.bron_type}
                        </a>
                      ) : (
                        <span className="zacht">—</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {reeksen.length > 1 ? (
        <section className="kaart">
          <h2>Relatiegeschiedenis</h2>
          <table>
            <tbody>
              {reeksen.map((reeks) => (
                <tr key={`${reeks.kantoorId}-${reeks.jaren[0]}`}>
                  <td className="jaar">{jarenReeks(reeks.jaren)}</td>
                  <td>
                    <Link
                      href={kantoorPad({
                        afm_nummer: reeks.afmNummer,
                        naam: reeks.kantoorNaam,
                      })}
                    >
                      {reeks.kantoorNaam}
                    </Link>
                  </td>
                  <td className="zacht klein">{aantalJaren(reeks.jaren.length)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      ) : null}

      <Doorklik
        items={[
          ...reeksen.map((reeks) => ({
            naar: kantoorPad({ afm_nummer: reeks.afmNummer, naam: reeks.kantoorNaam }),
            tekst: `${reeks.kantoorNaam}: andere cliënten`,
          })),
          ...(org.subsector
            ? [
                {
                  naar: subsectorPad(org.subsector),
                  tekst: `Accountants in de ${org.subsector.toLowerCase()}`,
                },
              ]
            : []),
          ...(org.sector
            ? [
                {
                  naar: sectorPad(org.sector),
                  tekst: `Marktaandelen in de sector ${org.sector}`,
                },
              ]
            : []),
          ...(laatsteWisseljaar
            ? [
                {
                  naar: "/wisselingen",
                  tekst: `Wie wisselde er nog meer in ${laatsteWisseljaar}?`,
                  toelichting: `${wisselingenZelfdeJaar.length} in de database`,
                },
              ]
            : [{ naar: "/wisselingen", tekst: "Alle accountantswisselingen" }]),
          ...anderePlaatsgenoten.slice(0, 2).map((buur) => ({
            naar: organisatiePad(buur),
            tekst: buur.naam,
            toelichting: `ook in ${org.gemeente}`,
          })),
          ...andereSectorgenoten
            .filter((o) => !anderePlaatsgenoten.some((b) => b.id === o.id))
            .slice(0, 3)
            .map((genoot) => ({
              naar: organisatiePad(genoot),
              tekst: genoot.naam,
              toelichting: genoot.gemeente ?? undefined,
            })),
        ]}
      />
    </>
  );
}
