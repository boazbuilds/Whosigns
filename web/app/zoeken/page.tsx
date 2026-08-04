import type { Metadata } from "next";
import Link from "next/link";
import { alleOrganisaties, zoekKantoren, zoekOrganisaties } from "@/lib/db";
import {
  aantalKantoren,
  aantalOrganisaties,
  kantoorPad,
  organisatiePad,
  sectorPad,
} from "@/lib/paden";
import { Doorklik, Foutmelding, Leeg } from "@/components/onderdelen";

export const metadata: Metadata = { title: "Zoeken" };

type Props = { searchParams: Promise<{ q?: string | string[] }> };

export default async function Zoekpagina({ searchParams }: Props) {
  const { q } = await searchParams;
  // Bij `?q=a&q=b` levert Next een array; zonder deze regel crashte .trim().
  const term = (Array.isArray(q) ? q[0] : (q ?? "")).trim();

  if (term.length < 2) {
    const organisaties = await alleOrganisaties(4).catch(() => []);
    return (
      <>
        <div className="paginakop">
          <h1>Zoeken</h1>
          <p className="zacht" style={{ margin: "0.4rem 0 0" }}>
            Typ minimaal twee letters van een organisatie of een accountantskantoor.
          </p>
        </div>
        <Doorklik
          titel="Of begin hier"
          items={[
            ...organisaties.slice(0, 4).map((org) => ({
              naar: organisatiePad(org),
              tekst: org.naam,
              toelichting: org.gemeente ?? undefined,
            })),
            { naar: "/wisselingen", tekst: "Alle accountantswisselingen" },
            { naar: sectorPad("zorg"), tekst: "Sector zorg" },
          ]}
        />
      </>
    );
  }

  let orgTreffers;
  let kantoorTreffers;
  try {
    [orgTreffers, kantoorTreffers] = await Promise.all([
      zoekOrganisaties(term),
      zoekKantoren(term),
    ]);
  } catch (fout) {
    return <Foutmelding fout={fout} />;
  }

  // De lijsten zijn afgekapt (er passen er geen 300 op een pagina), de aantallen
  // in de kop zijn dat niet: die komen uit een echte telling. Staat er meer dan er
  // te zien is, dan zegt de pagina dat erbij in plaats van het te verzwijgen.
  const organisaties = orgTreffers.rijen;
  const kantoren = kantoorTreffers.rijen;
  const totaal = orgTreffers.totaal + kantoorTreffers.totaal;
  const afgekapt = orgTreffers.afgekapt || kantoorTreffers.afgekapt;

  return (
    <>
      <div className="paginakop">
        <h1>&ldquo;{term}&rdquo;</h1>
        <p className="metaregel">
          <span>{aantalOrganisaties(orgTreffers.totaal)}</span>
          <span>{aantalKantoren(kantoorTreffers.totaal)}</span>
        </p>
        {afgekapt ? (
          <p className="zacht klein" style={{ margin: "0.4rem 0 0" }}>
            Hieronder staan de eerste {organisaties.length + kantoren.length}; maak de
            zoekterm specifieker om de rest te zien.
          </p>
        ) : null}
      </div>

      {totaal === 0 ? (
        <section className="kaart">
          <Leeg tekst={`Niets gevonden voor "${term}".`} />
        </section>
      ) : null}

      {organisaties.length > 0 ? (
        <section className="kaart">
          <h2>Organisaties</h2>
          <div className="tabel-omhulsel">
            <table>
              <thead>
                <tr>
                  <th>Organisatie</th>
                  <th>Plaats</th>
                  <th>Sector</th>
                </tr>
              </thead>
              <tbody>
                {organisaties.map((org) => (
                  <tr key={org.id}>
                    <td>
                      <Link href={organisatiePad(org)}>{org.naam}</Link>
                    </td>
                    <td className="zacht">{org.gemeente ?? "—"}</td>
                    <td>
                      {org.sector ? (
                        <Link href={sectorPad(org.sector)}>{org.sector}</Link>
                      ) : (
                        "—"
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      ) : null}

      {kantoren.length > 0 ? (
        <section className="kaart">
          <h2>Accountantskantoren</h2>
          <div className="tabel-omhulsel">
            <table>
              <thead>
                <tr>
                  <th>Kantoor</th>
                  <th>AFM-nummer</th>
                  <th>Vergunning</th>
                </tr>
              </thead>
              <tbody>
                {kantoren.map((kantoor) => (
                  <tr key={kantoor.id}>
                    <td>
                      <Link href={kantoorPad(kantoor)}>{kantoor.naam}</Link>
                    </td>
                    <td className="getal zacht">{kantoor.afm_nummer ?? "—"}</td>
                    <td>
                      {kantoor.oob_vergunning ? (
                        <span className="label label-oob">OOB</span>
                      ) : (
                        <span className="zacht klein">Wta</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      ) : null}

      <Doorklik
        items={[
          ...organisaties.slice(0, 3).map((org) => ({
            naar: organisatiePad(org),
            tekst: org.naam,
            toelichting: org.gemeente ?? undefined,
          })),
          ...kantoren.slice(0, 2).map((kantoor) => ({
            naar: kantoorPad(kantoor),
            tekst: kantoor.naam,
            toelichting: "cliënten en wisselingen",
          })),
          // De sectoren van de treffers zelf, en anders niets: een zoekopdracht met
          // één treffer kwam op drie vervolgklikken uit, en de regel uit
          // docs/visie.md is minimaal vijf. Vandaar ook de twee vaste ingangen.
          ...[...new Set(organisaties.map((o) => o.sector).filter(Boolean))].map(
            (sector) => ({
              naar: sectorPad(sector as string),
              tekst: `Sector ${sector}: marktaandelen`,
            }),
          ),
          { naar: "/wisselingen", tekst: "Alle accountantswisselingen" },
          { naar: "/organisaties", tekst: "Alle organisaties op naam" },
          { naar: "/", tekst: "Naar het overzicht" },
        ]}
      />
    </>
  );
}
