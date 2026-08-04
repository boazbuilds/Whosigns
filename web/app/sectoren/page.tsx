import type { Metadata } from "next";
import Link from "next/link";
import {
  kantoorRanglijst,
  nieuwsteBoekjaar,
  sectoren,
  subsectoren,
  tel,
} from "@/lib/db";
import {
  aantalOrganisaties,
  hoofdletter,
  SECTOR_UITLEG,
  sectorPad,
  subsectorPad,
} from "@/lib/paden";
import {
  Doorklik,
  Foutmelding,
  Inklapbaar,
  Kerncijfer,
  Kruimels,
  Tegel,
} from "@/components/onderdelen";

export const metadata: Metadata = {
  title: "Sectoren: waar zit welke accountant?",
  description:
    "Alle sectoren in de database — zorg, organisaties van openbaar belang, " +
    "woningcorporaties en goede doelen — met de kantoren die er de dienst uitmaken.",
};

/** Zoveel wapens onder een sectortegel: de kantoren die de sector maken. */
const WAPENS_PER_TEGEL = 5;
/** Zoveel subsectoren staan open; de staart zit achter een klik. */
const SUBSECTOREN_OPEN = 8;

export default async function Sectorenpagina() {
  let sectorlijst;
  let subsectorlijst;
  let boekjaar;
  let organisatieTotaal;
  try {
    [sectorlijst, subsectorlijst, boekjaar, organisatieTotaal] = await Promise.all([
      sectoren(),
      subsectoren().catch(() => []),
      nieuwsteBoekjaar(),
      tel("organisaties"),
    ]);
  } catch (fout) {
    return <Foutmelding fout={fout} />;
  }

  // Eén ranglijst over alle boekjaren, hier per sector uitgesplitst. Zo staat er
  // onder elke tegel wie daar de grootste zijn — dat maakt de keuze pas leuk.
  const ranglijst = await kantoorRanglijst().catch(() => []);
  const topPerSector = new Map<string, string[]>();
  for (const sector of sectorlijst) {
    const top = ranglijst
      .map((rij) => ({
        naam: rij.kantoor.naam,
        aantal: rij.perSector.find(([naam]) => naam === sector.naam)?.[1] ?? 0,
      }))
      .filter((rij) => rij.aantal > 0)
      .sort((a, b) => b.aantal - a.aantal)
      .slice(0, WAPENS_PER_TEGEL)
      .map((rij) => rij.naam);
    topPerSector.set(sector.naam, top);
  }

  return (
    <>
      <Kruimels paden={[{ naar: "/", tekst: "Start" }, { tekst: "Sectoren" }]} />

      <div className="paginakop">
        <h1>Sectoren</h1>
        <p className="metaregel">
          <span>{sectorlijst.length} sectoren</span>
          <span>{aantalOrganisaties(organisatieTotaal)}</span>
          {boekjaar ? <span>t/m boekjaar {boekjaar}</span> : null}
        </p>
        <p className="klein zacht" style={{ marginBottom: 0, marginTop: "0.6rem" }}>
          Elke sector heeft zijn eigen openbare bron, en daarmee zijn eigen
          spelers. Klik door voor de ranglijst, de marktaandelen per boekjaar en
          de wisselingen.
        </p>
      </div>

      <section className="kaart">
        <h2>Kies een sector</h2>
        <div className="tegels">
          {sectorlijst.map((sector) => (
            <Tegel
              key={sector.naam}
              naar={sectorPad(sector.naam)}
              naam={hoofdletter(sector.naam)}
              meta={
                SECTOR_UITLEG[sector.naam] ??
                `${aantalOrganisaties(sector.aantal)} in de database`
              }
              wapens={topPerSector.get(sector.naam) ?? []}
            />
          ))}
        </div>
      </section>

      <div className="kolommen">
        <section className="kaart">
          <h2>Sectoren op omvang</h2>
          <table>
            <thead>
              <tr>
                <th>Sector</th>
                <th className="getal">Organisaties</th>
              </tr>
            </thead>
            <tbody>
              {sectorlijst.map((sector) => (
                <tr key={sector.naam}>
                  <td>
                    <Link href={sectorPad(sector.naam)}>{hoofdletter(sector.naam)}</Link>
                  </td>
                  <td className="getal">{sector.aantal}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <div className="kerncijfers">
            <Kerncijfer
              waarde={organisatieTotaal}
              naam="organisaties totaal"
              naar="/organisaties"
            />
            <Kerncijfer
              waarde={ranglijst.length}
              naam="kantoren met controles"
              naar="/kantoren"
            />
          </div>
        </section>

        <section className="kaart">
          <h2>Grootste subsectoren</h2>
          {subsectorlijst.length === 0 ? (
            <p className="leeg">De subsectoren worden nog bijgewerkt.</p>
          ) : (
            <>
              <div className="tabel-omhulsel">
                <table>
                  <thead>
                    <tr>
                      <th>Subsector</th>
                      <th className="getal">Organisaties</th>
                    </tr>
                  </thead>
                  <tbody>
                    {subsectorlijst.slice(0, SUBSECTOREN_OPEN).map((rij) => (
                      <tr key={rij.naam}>
                        <td>
                          <Link href={subsectorPad(rij.naam)}>{rij.naam}</Link>
                        </td>
                        <td className="getal">{rij.aantal}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              {subsectorlijst.length > SUBSECTOREN_OPEN ? (
                <Inklapbaar
                  samenvatting={`Nog ${subsectorlijst.length - SUBSECTOREN_OPEN} subsectoren`}
                >
                  <table>
                    <tbody>
                      {subsectorlijst.slice(SUBSECTOREN_OPEN).map((rij) => (
                        <tr key={rij.naam}>
                          <td>
                            <Link href={subsectorPad(rij.naam)}>{rij.naam}</Link>
                          </td>
                          <td className="getal">{rij.aantal}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </Inklapbaar>
              ) : null}
            </>
          )}
        </section>
      </div>

      <Doorklik
        items={[
          ...sectorlijst.map((sector) => ({
            naar: sectorPad(sector.naam),
            tekst: `Sector ${sector.naam}`,
            toelichting: aantalOrganisaties(sector.aantal),
          })),
          { naar: "/kantoren", tekst: "Ranglijst van alle kantoren" },
          { naar: "/wisselingen", tekst: "Alle accountantswisselingen" },
          { naar: "/organisaties", tekst: "Alle organisaties op naam" },
        ]}
      />
    </>
  );
}
