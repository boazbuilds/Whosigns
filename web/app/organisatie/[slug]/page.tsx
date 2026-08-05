import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import {
  gunningenVanOrganisatie,
  opdrachtenVanOrganisatie,
  organisatieOpId,
  organisatieOpKvk,
  organisatiesInGemeente,
  organisatiesInSector,
  organisatiesInSubsector,
  tel,
} from "@/lib/db";
import { periodes, wisseljaren } from "@/lib/analyse";
import {
  aantalJaren,
  jarenReeks,
  kantoorPad,
  datumNL,
  hoofdletter,
  nummerUitSlug,
  OPDRACHT_LABEL,
  organisatiePad,
  sectorPad,
  subsectorPad,
} from "@/lib/paden";
import {
  Doorklik,
  Foutmelding,
  KantoorLink,
  Kruimels,
  Leeg,
  Oordeel,
} from "@/components/onderdelen";

type Params = { params: Promise<{ slug: string }> };

/** `o<id>` vooraan de slug = organisatie zonder KvK-nummer (zie paden.ts). */
function vindOrganisatie(slugdeel: string) {
  const sleutel = nummerUitSlug(slugdeel);
  const viaId = /^o(\d+)$/.exec(sleutel);
  return viaId ? organisatieOpId(Number(viaId[1])) : organisatieOpKvk(sleutel);
}

export async function generateMetadata({ params }: Params): Promise<Metadata> {
  const { slug } = await params;
  const org = await vindOrganisatie(slug).catch(() => null);
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

  // Alle databasewerk binnen één try: een hapering ná de eerste vraag gaf
  // eerst een kale Next-500 in plaats van onze eigen foutmelding.
  let org;
  let opdrachten: Awaited<ReturnType<typeof opdrachtenVanOrganisatie>> = [];
  let plaatsgenoten: Awaited<ReturnType<typeof organisatiesInGemeente>> = [];
  let sectorgenoten: typeof plaatsgenoten = [];
  let aantalZelfdeJaar = 0;
  let reeksen: ReturnType<typeof periodes> = [];
  let aanbestedingen: Awaited<ReturnType<typeof gunningenVanOrganisatie>> = [];
  let wissels: ReturnType<typeof wisseljaren> = new Set();
  try {
    org = await vindOrganisatie(slug);
    if (org) {
      [opdrachten, aanbestedingen] = await Promise.all([
        opdrachtenVanOrganisatie(org.id),
        gunningenVanOrganisatie(org.id),
      ]);
      reeksen = periodes(opdrachten);
      wissels = wisseljaren(opdrachten);

      // Organisaties uit dezelfde subsector zijn interessanter om naar door te
      // klikken dan willekeurige zorgorganisaties: een ziekenhuis naast een
      // tandartspraktijk zegt niets. Alleen als de subsector ontbreekt vallen we
      // terug op de sector. De limieten van 20 en 30 mogen hier: dit zijn bewust
      // kleine steekproeven voor een paar doorklikken (`.slice(0, 2)` en
      // `.slice(0, 3)` hieronder), en er wordt nergens een aantal uit afgeleid.
      //
      // Voor het aantal wisselingen in hetzelfde boekjaar geldt dat niet: dat
      // getal stáát op de pagina. Daarom een echte telling in plaats van de
      // lengte van een afgekapte lijst.
      [plaatsgenoten, sectorgenoten, aantalZelfdeJaar] = await Promise.all([
        org.gemeente ? organisatiesInGemeente(org.gemeente) : Promise.resolve([]),
        org.subsector
          ? organisatiesInSubsector(org.subsector, 30)
          : org.sector
            ? organisatiesInSector(org.sector, 30)
            : Promise.resolve([]),
        wissels.size
          ? tel("v_wisselingen", `boekjaar_wissel=eq.${Math.max(...wissels)}`)
          : Promise.resolve(0),
      ]);
    }
  } catch (fout) {
    return <Foutmelding fout={fout} />;
  }
  if (!org) notFound();

  const huidige = reeksen[0];
  const alleJaren = opdrachten.map((o) => o.boekjaar);

  const anderePlaatsgenoten = plaatsgenoten.filter((o) => o.id !== org.id);
  const andereSectorgenoten = sectorgenoten.filter((o) => o.id !== org.id);
  const laatsteWisseljaar = wissels.size ? Math.max(...wissels) : null;

  return (
    <>
      <Kruimels
        paden={[
          { naar: "/", tekst: "Start" },
          ...(org.sector
            ? [{ naar: sectorPad(org.sector), tekst: hoofdletter(org.sector) }]
            : [{ naar: "/organisaties", tekst: "Organisaties" }]),
          { tekst: org.naam },
        ]}
      />

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
                  id: huidige.kantoorId,
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
                      <Oordeel
                        waarde={opdracht.oordeel}
                        gerapporteerd={opdracht.oordeel_gerapporteerd}
                      />
                      {opdracht.continuiteitsonzekerheid ? (
                        <> <span className="label label-let-op">continuïteit</span></>
                      ) : null}
                    </td>
                    <td className="klein">
                      {opdracht.bronnen?.url ? (
                        <>
                          <a
                            href={opdracht.bronnen.url}
                            rel="noreferrer nofollow"
                            target="_blank"
                          >
                            {opdracht.bronnen.bron_type}
                          </a>
                          {/* De labelplicht uit docs/concept.md: bij elk gegeven
                              hoort zichtbaar te zijn of het uit een openbare bron
                              komt of door iemand zelf is aangeleverd. */}
                          {opdracht.bronnen.betrouwbaarheid ? (
                            <span className="zacht klein">
                              {" "}
                              ({opdracht.bronnen.betrouwbaarheid.replace("_", " ")})
                            </span>
                          ) : null}
                        </>
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

      {aanbestedingen.length > 0 ? (
        <section className="kaart">
          <div className="kaartkop">
            <h2>Aanbestede accountantsdiensten</h2>
            <span className="klein zacht">bron: TED</span>
          </div>
          {/* Een gunning is een benoeming vooraf, geen waargenomen controle.
              Dat onderscheid staat hier expliciet, want anders leest een
              bezoeker het als "hier is gecontroleerd". */}
          <p className="klein zacht" style={{ marginTop: 0 }}>
            De opdracht is Europees aanbesteed. Een gunning zegt wie er benoemd
            is en wanneer — niet of de controle er kwam, en met welk oordeel.
          </p>
          <div className="tabel-omhulsel">
            <table>
              <thead>
                <tr>
                  <th>Gegund</th>
                  <th>Kantoor</th>
                  <th>Aanbesteding</th>
                  <th>Bericht</th>
                </tr>
              </thead>
              <tbody>
                {aanbestedingen.map((gunning) => (
                  <tr key={gunning.publicatienummer + (gunning.kantoren?.id ?? "")}>
                    <td className="jaar">{datumNL(gunning.gunningsdatum)}</td>
                    <td>
                      {gunning.kantoren ? (
                        <KantoorLink
                          naam={gunning.kantoren.naam}
                          naar={kantoorPad(gunning.kantoren)}
                          voluit
                        />
                      ) : (
                        <span className="zacht">onbekend</span>
                      )}
                    </td>
                    <td className="klein zacht">{gunning.titel ?? "—"}</td>
                    <td className="klein">
                      {gunning.bronnen?.url ? (
                        <a
                          href={`https://ted.europa.eu/nl/notice/-/detail/${gunning.publicatienummer}`}
                          rel="noreferrer nofollow"
                          target="_blank"
                        >
                          {gunning.publicatienummer}
                        </a>
                      ) : (
                        gunning.publicatienummer
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      ) : null}

      {reeksen.length > 1 ? (
        <section className="kaart">
          <h2>Relatiegeschiedenis</h2>
          <div className="tabel-omhulsel">
          <table>
            <tbody>
              {reeksen.map((reeks) => (
                <tr key={`${reeks.kantoorId}-${reeks.jaren[0]}`}>
                  <td className="jaar">{jarenReeks(reeks.jaren)}</td>
                  <td>
                    <Link
                      href={kantoorPad({
                        id: reeks.kantoorId,
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
          </div>
        </section>
      ) : null}

      <Doorklik
        items={[
          ...reeksen.map((reeks) => ({
            naar: kantoorPad({
              id: reeks.kantoorId,
              afm_nummer: reeks.afmNummer,
              naam: reeks.kantoorNaam,
            }),
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
                  // Min één: de telling omvat de wisseling van deze organisatie
                  // zelf, en "nog meer" hoort over de ánderen te gaan.
                  toelichting:
                    aantalZelfdeJaar > 1
                      ? `${aantalZelfdeJaar - 1} andere in de database`
                      : "tot nu toe de enige in dat boekjaar",
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
