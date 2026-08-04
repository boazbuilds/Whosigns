import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import {
  marktaandeel,
  organisatiesInSector,
  sectoren,
  wisselingen,
} from "@/lib/db";
import {
  aantalKantoren,
  aantalOrganisaties,
  aantalWisselingen,
  kantoorPad,
  organisatiePad,
  slug,
  subsectorPad,
  veiligGedecodeerd,
} from "@/lib/paden";
import { Doorklik, Foutmelding, Inklapbaar, Leeg } from "@/components/onderdelen";

type Params = { params: Promise<{ naam: string }> };

/** Zoveel organisaties staan open in de zijkolom; de rest zit achter een klik. */
const ORGANISATIES_OPEN = 15;

/**
 * De echte sectorwaarde bij een slug.
 *
 * Dit stond hier eerst als `slug.toLowerCase()`, met de aantekening dat het zou
 * breken zodra er een sector met een spatie bij kwam. Dat gebeurde: "goede doelen"
 * werd `goede-doelen` en die pagina gaf een 404, terwijl elke organisatiepagina van
 * een goed doel er wél naar linkte. Nu zoeken we de waarde op in de lijst die de
 * database kent — dezelfde aanpak als op de subsectorpagina.
 */
async function vindSector(naamSlug: string): Promise<string | null> {
  const lijst = await sectoren();
  return lijst.find((s) => slug(s.naam) === naamSlug)?.naam ?? null;
}

export async function generateMetadata({ params }: Params): Promise<Metadata> {
  const { naam } = await params;
  const sector = await vindSector(veiligGedecodeerd(naam)).catch(() => null);
  if (!sector) return { title: "Sector niet gevonden" };
  return {
    title: `Accountants in de sector ${sector}`,
    description:
      `Welke accountantskantoren controleren organisaties in de sector ${sector}, ` +
      `met marktaandelen per boekjaar en recente wisselingen.`,
  };
}

export default async function Sectorpagina({ params }: Params) {
  const { naam } = await params;

  let sector: string | null = null;
  let organisaties;
  let aandelen;
  let sectorWisselingen;
  try {
    sector = await vindSector(veiligGedecodeerd(naam));
    [organisaties, aandelen] = sector
      ? await Promise.all([organisatiesInSector(sector), marktaandeel(sector)])
      : [[], []];
    // Alle wisselingen ophalen en hier filteren: v_wisselingen kent geen sector, en
    // met een limiet vooraf vielen de wisselingen van deze sector buiten beeld zodra
    // een andere sector de nieuwste regels vulde.
    const organisatieIds = new Set(organisaties.map((o) => o.id));
    sectorWisselingen = (await wisselingen()).filter((w) =>
      organisatieIds.has(w.organisatie_id),
    );
  } catch (fout) {
    return <Foutmelding fout={fout} />;
  }
  // Buiten de try: notFound() werkt met een uitzondering die Next zelf opvangt.
  // Binnen de try zou onze eigen catch die opslokken en kreeg de bezoeker een
  // foutmelding met http-status 200 in plaats van een nette 404.
  if (!sector || organisaties.length === 0) notFound();

  // De subsectoren van déze sector, geteld uit de eigen organisaties. Hier werd
  // eerst de wereldwijde subsectorenlijst getoond, dus op de zorgpagina stonden
  // ook de subsectoren van de goede doelen — met aantallen van de hele database.
  const perSubsector = new Map<string, number>();
  for (const org of organisaties) {
    if (org.subsector) {
      perSubsector.set(org.subsector, (perSubsector.get(org.subsector) ?? 0) + 1);
    }
  }
  const subsectorlijst = [...perSubsector.entries()]
    .map(([naam2, aantal]) => ({ naam: naam2, aantal }))
    .sort((a, b) => b.aantal - a.aantal);

  // Kruistabel: kantoren als rijen, boekjaren als kolommen. Zo zie je in één
  // oogopslag wie er over de jaren wint en wie krimpt.
  const boekjaren = [...new Set(aandelen.map((a) => a.boekjaar))].sort((a, b) => b - a);
  const perKantoor = new Map<
    number,
    {
      id: number;
      naam: string;
      afm: string | null;
      cellen: Map<number, number>;
      totaal: number;
    }
  >();
  for (const rij of aandelen) {
    if (!rij.kantoor) continue;
    const bestaand = perKantoor.get(rij.kantoor_id) ?? {
      id: rij.kantoor_id,
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

  const organisatierijen = organisaties.map((org) => (
    <tr key={org.id}>
      <td>
        <Link href={organisatiePad(org)}>{org.naam}</Link>
      </td>
      <td className="zacht klein">{org.gemeente ?? "—"}</td>
    </tr>
  ));

  return (
    <>
      <div className="paginakop">
        <h1>Sector {sector}</h1>
        <p className="metaregel">
          <span>{aantalOrganisaties(organisaties.length)}</span>
          <span>{aantalKantoren(kantoorrijen.length)}</span>
          <span>{aantalWisselingen(sectorWisselingen.length)}</span>
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
                      <Link
                        href={kantoorPad({ id: rij.id, afm_nummer: rij.afm, naam: rij.naam })}
                      >
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

      {subsectorlijst.length > 0 ? (
        <section className="kaart">
          <h2>Subsectoren</h2>
          <div className="tabel-omhulsel">
            <table>
              <thead>
                <tr>
                  <th>Subsector</th>
                  <th className="getal">Organisaties</th>
                </tr>
              </thead>
              <tbody>
                {subsectorlijst.map((rij) => (
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
        </section>
      ) : null}

      <div className="kolommen">
        <section className="kaart">
          <h2>Wisselingen in deze sector</h2>
          {sectorWisselingen.length === 0 ? (
            <Leeg tekst="Geen wisselingen gevonden." />
          ) : (
            <div className="tabel-omhulsel">
            <table>
              <tbody>
                {sectorWisselingen.map((w) => (
                  <tr
                    key={`${w.organisatie_id}-${w.boekjaar_wissel}-${w.van_kantoor_id}-${w.naar_kantoor_id}`}
                  >
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
            </div>
          )}
        </section>

        <section className="kaart">
          <h2>Organisaties</h2>
          <div className="tabel-omhulsel">
            <table>
              <tbody>{organisatierijen.slice(0, ORGANISATIES_OPEN)}</tbody>
            </table>
          </div>
          {organisatierijen.length > ORGANISATIES_OPEN ? (
            <Inklapbaar
              samenvatting={`Nog ${organisatierijen.length - ORGANISATIES_OPEN} organisaties`}
            >
              <div className="tabel-omhulsel">
                <table>
                  <tbody>{organisatierijen.slice(ORGANISATIES_OPEN)}</tbody>
                </table>
              </div>
            </Inklapbaar>
          ) : null}
          <p className="klein" style={{ marginBottom: 0 }}>
            <Link href="/organisaties">Alle organisaties, alle sectoren →</Link>
          </p>
        </section>
      </div>

      <Doorklik
        items={[
          ...subsectorlijst.slice(0, 3).map((rij) => ({
            naar: subsectorPad(rij.naam),
            tekst: rij.naam,
            toelichting: `${rij.aantal} organisaties`,
          })),
          ...kantoorrijen.slice(0, 3).map(([id, rij]) => ({
            naar: kantoorPad({ id, afm_nummer: rij.afm, naam: rij.naam }),
            tekst: rij.naam,
            toelichting: `${rij.totaal} controles in deze sector`,
          })),
          ...organisaties.slice(0, 2).map((org) => ({
            naar: organisatiePad(org),
            tekst: org.naam,
            toelichting: org.gemeente ?? undefined,
          })),
          { naar: "/wisselingen", tekst: "Alle wisselingen, alle sectoren" },
          { naar: "/organisaties", tekst: "Alle organisaties" },
        ]}
      />
    </>
  );
}
