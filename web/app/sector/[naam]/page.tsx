import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { marktaandeel, organisatiesInSector, wisselingen } from "@/lib/db";
import { kantoorPad, organisatiePad } from "@/lib/paden";
import { Doorklik, Foutmelding, Leeg } from "@/components/onderdelen";

type Params = { params: Promise<{ naam: string }> };

/**
 * Sectoren zijn nu nog enkele woorden ("zorg"), dus de URL-slug is gelijk aan de
 * waarde in de database. Komen er sectoren met spaties of leestekens bij, dan
 * hoort hier een echte vertaaltabel slug → sectorwaarde.
 */
function sectorUitSlug(slug: string): string {
  return decodeURIComponent(slug).toLowerCase();
}

export async function generateMetadata({ params }: Params): Promise<Metadata> {
  const { naam } = await params;
  const sector = sectorUitSlug(naam);
  return {
    title: `Accountants in de sector ${sector}`,
    description:
      `Welke accountantskantoren controleren organisaties in de sector ${sector}, ` +
      `met marktaandelen per boekjaar en recente wisselingen.`,
  };
}

export default async function Sectorpagina({ params }: Params) {
  const { naam } = await params;
  const sector = sectorUitSlug(naam);

  let organisaties;
  let aandelen;
  try {
    [organisaties, aandelen] = await Promise.all([
      organisatiesInSector(sector),
      marktaandeel(sector),
    ]);
  } catch (fout) {
    return <Foutmelding fout={fout} />;
  }
  if (organisaties.length === 0) notFound();

  const sectorWisselingen = (await wisselingen({ limiet: 100 })).filter((w) =>
    organisaties.some((o) => o.id === w.organisatie_id),
  );

  // Kruistabel: kantoren als rijen, boekjaren als kolommen. Zo zie je in één
  // oogopslag wie er over de jaren wint en wie krimpt.
  const boekjaren = [...new Set(aandelen.map((a) => a.boekjaar))].sort((a, b) => b - a);
  const perKantoor = new Map<
    number,
    { naam: string; afm: string | null; cellen: Map<number, number>; totaal: number }
  >();
  for (const rij of aandelen) {
    if (!rij.kantoor) continue;
    const bestaand = perKantoor.get(rij.kantoor_id) ?? {
      naam: rij.kantoor.naam,
      afm: rij.kantoor.afm_nummer,
      cellen: new Map<number, number>(),
      totaal: 0,
    };
    bestaand.cellen.set(rij.boekjaar, rij.aantal_controles);
    bestaand.totaal += rij.aantal_controles;
    perKantoor.set(rij.kantoor_id, bestaand);
  }
  const kantoorrijen = [...perKantoor.entries()].sort(
    (a, b) => b[1].totaal - a[1].totaal,
  );

  return (
    <>
      <div className="paginakop">
        <h1>Sector {sector}</h1>
        <p className="metaregel">
          <span>{organisaties.length} organisaties</span>
          <span>{kantoorrijen.length} accountantskantoren</span>
          <span>{sectorWisselingen.length} wisselingen</span>
        </p>
      </div>

      <section className="kaart">
        <h2>Controles per kantoor per boekjaar</h2>
        {kantoorrijen.length === 0 ? (
          <Leeg tekst="Nog geen opdrachten in deze sector." />
        ) : (
          <div className="tabel-omhulsel">
            <table>
              <thead>
                <tr>
                  <th>Kantoor</th>
                  {boekjaren.map((jaar) => (
                    <th key={jaar} className="getal">
                      {jaar}
                    </th>
                  ))}
                  <th className="getal">Totaal</th>
                </tr>
              </thead>
              <tbody>
                {kantoorrijen.map(([id, rij]) => (
                  <tr key={id}>
                    <td>
                      <Link href={kantoorPad({ afm_nummer: rij.afm, naam: rij.naam })}>
                        {rij.naam}
                      </Link>
                    </td>
                    {boekjaren.map((jaar) => (
                      <td key={jaar} className="getal">
                        {rij.cellen.get(jaar) ?? <span className="zacht">·</span>}
                      </td>
                    ))}
                    <td className="getal">
                      <strong>{rij.totaal}</strong>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <div className="kolommen">
        <section className="kaart">
          <h2>Wisselingen in deze sector</h2>
          {sectorWisselingen.length === 0 ? (
            <Leeg tekst="Geen wisselingen gevonden." />
          ) : (
            <table>
              <tbody>
                {sectorWisselingen.map((w) => (
                  <tr key={`${w.organisatie_id}-${w.boekjaar_wissel}`}>
                    <td className="jaar">{w.boekjaar_wissel}</td>
                    <td>
                      {w.organisatie ? (
                        <Link href={organisatiePad(w.organisatie)}>
                          {w.organisatie.naam}
                        </Link>
                      ) : (
                        "onbekend"
                      )}
                      <div className="klein zacht">
                        {w.van ? <Link href={kantoorPad(w.van)}>{w.van.naam}</Link> : "?"}{" "}
                        → {w.naar ? <Link href={kantoorPad(w.naar)}>{w.naar.naam}</Link> : "?"}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </section>

        <section className="kaart">
          <h2>Organisaties</h2>
          <table>
            <tbody>
              {organisaties.map((org) => (
                <tr key={org.id}>
                  <td>
                    <Link href={organisatiePad(org)}>{org.naam}</Link>
                  </td>
                  <td className="zacht klein">{org.gemeente ?? "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      </div>

      <Doorklik
        items={[
          ...kantoorrijen.slice(0, 3).map(([id, rij]) => ({
            naar: kantoorPad({ afm_nummer: rij.afm, naam: rij.naam }),
            tekst: rij.naam,
            toelichting: `${rij.totaal} controles in deze sector`,
          })),
          ...organisaties.slice(0, 2).map((org) => ({
            naar: organisatiePad(org),
            tekst: org.naam,
            toelichting: org.gemeente ?? undefined,
          })),
          { naar: "/wisselingen", tekst: "Alle wisselingen, alle sectoren" },
          { naar: "/", tekst: "Alle organisaties" },
        ]}
      />
    </>
  );
}
