import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { marktaandeel, organisatiesInSector, sectoren, wisselingen } from "@/lib/db";
import { saldoPerKantoor } from "@/lib/analyse";
import {
  aantalKantoren,
  aantalOrganisaties,
  aantalWisselingen,
  hoofdletter,
  kantoorPad,
  organisatiePad,
  SECTOR_UITLEG,
  sectorPad,
  slug,
  subsectorPad,
  veiligGedecodeerd,
} from "@/lib/paden";
import {
  Aandeelbalk,
  Doorklik,
  Foutmelding,
  Inklapbaar,
  KantoorLink,
  Kerncijfer,
  KortKantoorLink,
  Kruimels,
  Leeg,
  Podiumplek,
  Rang,
} from "@/components/onderdelen";

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

  let sector: string | null;
  let organisaties;
  let aandelen;
  try {
    sector = await vindSector(veiligGedecodeerd(naam));
    [organisaties, aandelen] = sector
      ? await Promise.all([organisatiesInSector(sector), marktaandeel(sector)])
      : [[], []];
  } catch (fout) {
    return <Foutmelding fout={fout} />;
  }
  // Buiten de try: notFound() werkt met een uitzondering die Next zelf opvangt.
  // Binnen de try zou onze eigen catch die opslokken en kreeg de bezoeker een
  // foutmelding met http-status 200 in plaats van een nette 404.
  if (!sector || organisaties.length === 0) notFound();

  // Alle wisselingen ophalen en hier filteren: v_wisselingen kent geen sector, en
  // met een limiet vooraf vielen de wisselingen van deze sector buiten beeld zodra
  // een andere sector de nieuwste regels vulde.
  const organisatieIds = new Set(organisaties.map((o) => o.id));
  const sectorWisselingen = (await wisselingen()).filter((w) =>
    organisatieIds.has(w.organisatie_id),
  );

  // Subsectoren uit de organisaties van déze sector. Hier stond de landelijke
  // lijst, dus de zorgpagina toonde ook de subsectoren van de goede doelen.
  const perSubsector = new Map<string, number>();
  for (const org of organisaties) {
    if (org.subsector) {
      perSubsector.set(org.subsector, (perSubsector.get(org.subsector) ?? 0) + 1);
    }
  }
  const subsectorlijst = [...perSubsector.entries()].sort((a, b) => b[1] - a[1]);

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
    (a, b) => b[1].totaal - a[1].totaal || a[1].naam.localeCompare(b[1].naam, "nl"),
  );
  const totaalControles = kantoorrijen.reduce((som, [, rij]) => som + rij.totaal, 0);
  const saldi = saldoPerKantoor(sectorWisselingen).filter((rij) => rij.saldo !== 0);

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
      <Kruimels
        paden={[
          { naar: "/", tekst: "Start" },
          { naar: "/sectoren", tekst: "Sectoren" },
          { tekst: hoofdletter(sector) },
        ]}
      />

      <div className="paginakop">
        <h1>{hoofdletter(sector)}</h1>
        {SECTOR_UITLEG[sector] ? (
          <p className="klein zacht" style={{ marginTop: "0.35rem" }}>
            {SECTOR_UITLEG[sector]}
          </p>
        ) : null}
        <div className="kerncijfers">
          <Kerncijfer waarde={organisaties.length} naam="organisaties" />
          <Kerncijfer waarde={kantoorrijen.length} naam="kantoren actief" />
          <Kerncijfer waarde={totaalControles} naam="controles" />
          <Kerncijfer
            waarde={sectorWisselingen.length}
            naam="wisselingen"
            naar="/wisselingen"
          />
          <Kerncijfer
            waarde={boekjaren.length ? `${Math.min(...boekjaren)}–${Math.max(...boekjaren)}` : "—"}
            naam="boekjaren"
          />
        </div>
      </div>

      {kantoorrijen.length >= 3 ? (
        <section className="kaart">
          <h2>Wie is hier de baas?</h2>
          <div className="podium">
            {kantoorrijen.slice(0, 3).map(([id, rij], i) => (
              <Podiumplek
                key={id}
                plek={i + 1}
                naar={kantoorPad({ afm_nummer: rij.afm, naam: rij.naam, id })}
                naam={rij.naam}
                onder={`${((rij.totaal / totaalControles) * 100).toFixed(1)}% van deze sector`}
                groot={String(rij.totaal)}
              />
            ))}
          </div>
        </section>
      ) : null}

      <section className="kaart">
        <div className="kaartkop">
          <h2>Controles per kantoor per boekjaar</h2>
          <Link href="/kantoren">Landelijke ranglijst →</Link>
        </div>
        {kantoorrijen.length === 0 ? (
          <Leeg tekst="Nog geen opdrachten in deze sector." />
        ) : (
          <div className="tabel-omhulsel">
            <table>
              <thead>
                <tr>
                  <th>#</th>
                  <th>Kantoor</th>
                  {boekjaren.map((jaar) => (
                    <th key={jaar} className="getal">
                      {jaar}
                    </th>
                  ))}
                  <th className="getal">Totaal</th>
                  <th>Aandeel</th>
                </tr>
              </thead>
              <tbody>
                {kantoorrijen.map(([id, rij], i) => (
                  <tr key={id}>
                    <td className="rangcel">
                      <Rang nummer={i + 1} />
                    </td>
                    <td>
                      <KantoorLink
                        naam={rij.naam}
                        naar={kantoorPad({ afm_nummer: rij.afm, naam: rij.naam, id })}
                      />
                    </td>
                    {boekjaren.map((jaar) => (
                      <td key={jaar} className="getal">
                        {rij.cellen.get(jaar) ?? <span className="zacht">·</span>}
                      </td>
                    ))}
                    <td className="getal">
                      <strong>{rij.totaal}</strong>
                    </td>
                    <td className="balkcel">
                      <Aandeelbalk deel={rij.totaal} geheel={totaalControles} />
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
          <h2>Subsectoren binnen {hoofdletter(sector)}</h2>
          <div className="tabel-omhulsel">
            <table>
              <thead>
                <tr>
                  <th>Subsector</th>
                  <th className="getal">Organisaties</th>
                  <th>Aandeel in de sector</th>
                </tr>
              </thead>
              <tbody>
                {subsectorlijst.map(([subsector, aantal]) => (
                  <tr key={subsector}>
                    <td>
                      <Link href={subsectorPad(subsector)}>{subsector}</Link>
                    </td>
                    <td className="getal">{aantal}</td>
                    <td className="balkcel">
                      <Aandeelbalk deel={aantal} geheel={organisaties.length} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      ) : null}

      <div className="kolommen">
        <section className="kaart">
          <div className="kaartkop">
            <h2>Wisselingen in deze sector</h2>
            <Link href="/wisselingen">Alle →</Link>
          </div>
          {sectorWisselingen.length === 0 ? (
            <Leeg tekst="Geen wisselingen gevonden." />
          ) : (
            <table>
              <tbody>
                {sectorWisselingen.slice(0, 12).map((w) => (
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
                        <KortKantoorLink kantoor={w.van} /> →{" "}
                        <KortKantoorLink kantoor={w.naar} />
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </section>

        <section className="kaart">
          <h2>Stijgers en dalers in deze sector</h2>
          {saldi.length === 0 ? (
            <Leeg tekst="Nog geen wisselingen om een saldo uit te rekenen." />
          ) : (
            <table>
              <tbody>
                {[...saldi.slice(0, 5), ...saldi.slice(-5).filter((r) => r.saldo < 0)]
                  // Bij weinig wisselingen kunnen kop en staart elkaar overlappen;
                  // dezelfde regel twee keer tonen is verwarrend.
                  .filter(
                    (rij, i, lijst) =>
                      lijst.findIndex((a) => a.kantoorId === rij.kantoorId) === i,
                  )
                  .map((rij) => (
                    <tr key={rij.kantoorId}>
                      <td>
                        <KantoorLink
                          naam={rij.naam}
                          naar={kantoorPad({
                            afm_nummer: rij.afmNummer,
                            naam: rij.naam,
                            id: rij.kantoorId,
                          })}
                        />
                      </td>
                      <td className="getal zacht klein">
                        +{rij.gewonnen} / −{rij.verloren}
                      </td>
                      <td className="getal">
                        <span
                          className={rij.saldo > 0 ? "saldo saldo-plus" : "saldo saldo-min"}
                        >
                          {rij.saldo > 0 ? `+${rij.saldo}` : rij.saldo}
                        </span>
                      </td>
                    </tr>
                  ))}
              </tbody>
            </table>
          )}
        </section>
      </div>

      <section className="kaart">
        <div className="kaartkop">
          <h2>Organisaties in deze sector</h2>
          <Link href="/organisaties">Alle organisaties →</Link>
        </div>
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
      </section>

      <Doorklik
        items={[
          ...subsectorlijst.slice(0, 3).map(([subsector, aantal]) => ({
            naar: subsectorPad(subsector),
            tekst: subsector,
            toelichting: aantalOrganisaties(aantal),
          })),
          ...kantoorrijen.slice(0, 3).map(([id, rij]) => ({
            naar: kantoorPad({ afm_nummer: rij.afm, naam: rij.naam, id }),
            tekst: rij.naam,
            toelichting: `${rij.totaal} controles in deze sector`,
          })),
          ...organisaties.slice(0, 2).map((org) => ({
            naar: organisatiePad(org),
            tekst: org.naam,
            toelichting: org.gemeente ?? undefined,
          })),
          { naar: "/sectoren", tekst: "Alle sectoren vergelijken" },
          {
            naar: "/kantoren",
            tekst: "Landelijke ranglijst van kantoren",
            toelichting: `${aantalKantoren(kantoorrijen.length)} actief in deze sector`,
          },
          {
            naar: "/wisselingen",
            tekst: "Alle accountantswisselingen",
            toelichting: `${aantalWisselingen(sectorWisselingen.length)} in deze sector`,
          },
          { naar: "/bevindingen", tekst: "Waar was het oordeel niet goedkeurend?" },
        ]}
      />
    </>
  );
}
