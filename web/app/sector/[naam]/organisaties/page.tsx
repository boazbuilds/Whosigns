import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { organisatiesInSectorPagina, sectoren } from "@/lib/db";
import {
  hoofdletter,
  nl,
  organisatiePad,
  paginaUitZoek,
  sectorOrganisatiesPad,
  sectorPad,
  slug,
  subsectorPad,
  veiligGedecodeerd,
  wisselingenPad,
} from "@/lib/paden";
import { Doorklik, Foutmelding, Kruimels, Paginering } from "@/components/onderdelen";

type Params = {
  params: Promise<{ naam: string }>;
  searchParams: Promise<{ pagina?: string | string[] }>;
};

/**
 * Zoveel organisaties per pagina. Honderd regels is een lijst die je nog
 * doorleest; de 4.165 van de financiële dienstverlening waren dat niet, en
 * stonden tot 5-10-2026 met zijn allen in de HTML van de sectorpagina (1,8 MB).
 */
const PER_PAGINA = 100;

function aantalPaginasVan(totaal: number): number {
  return Math.ceil(totaal / PER_PAGINA);
}

/** Dezelfde opzoeking als de sectorpagina: de slug is niet omkeerbaar. Met het
 *  aantal erbij, want dat is ook het totaal van deze lijst. */
async function vindSector(naamSlug: string) {
  const lijst = await sectoren();
  return lijst.find((s) => slug(s.naam) === naamSlug) ?? null;
}

export async function generateMetadata({ params, searchParams }: Params): Promise<Metadata> {
  const { naam } = await params;
  const pagina = paginaUitZoek((await searchParams).pagina);
  const gevonden = await vindSector(veiligGedecodeerd(naam)).catch(() => null);
  if (!gevonden) return { title: "Sector niet gevonden" };
  if (pagina > aantalPaginasVan(gevonden.aantal)) return { title: "Pagina niet gevonden" };
  const sector = gevonden.naam;
  return {
    title:
      `Organisaties in de sector ${sector}` + (pagina > 1 ? `, pagina ${pagina}` : ""),
    description: `Alle organisaties in de sector ${sector} in de database, alfabetisch.`,
  };
}

/**
 * De volledige organisatielijst van een sector, honderd per pagina.
 *
 * Een eigen pagina en niet ?pagina= op de sectorpagina zelf: die staat een uur
 * in de cache (ISR), en een zoekparameter zou haar bij elke weergave opnieuw
 * laten opbouwen. Deze lijst wordt weinig bezocht; dat hij per weergave wordt
 * opgebouwd kost niets, want beide verzoeken komen uit de datacache.
 */
export default async function SectorOrganisaties({ params, searchParams }: Params) {
  const { naam } = await params;
  const pagina = paginaUitZoek((await searchParams).pagina);

  // Deze pagina is dynamisch en komt dus niet in de cache: een <Foutmelding>
  // kan hier gewoon, zoals op /kantoren en /wisselingen.
  let gevonden;
  let rijen;
  try {
    gevonden = await vindSector(veiligGedecodeerd(naam));
    // Voorbij de laatste pagina niet eens vragen: het totaal staat al in
    // sectoren(). Een reusachtig paginanummer werd anders een offset die
    // PostgREST negeerde, en dan kwam pagina 1 terug onder de verkeerde kop
    // (zie paginaUitZoek). De lege lijst hieronder is de vangrail voor als
    // het totaal uit de cache iets ouder is dan de organisaties zelf.
    rijen =
      gevonden && pagina <= aantalPaginasVan(gevonden.aantal)
        ? await organisatiesInSectorPagina(gevonden.naam, pagina, PER_PAGINA)
        : [];
  } catch (fout) {
    return <Foutmelding fout={fout} />;
  }
  // Buiten de try: notFound() werkt met een uitzondering die Next zelf
  // opvangt. Voorbij de laatste pagina ook een 404, geen lege lijst die zich
  // voordoet als "geen organisaties".
  if (!gevonden || rijen.length === 0) notFound();
  const { naam: sector, aantal: totaal } = gevonden;

  const aantalPaginas = aantalPaginasVan(totaal);
  const eerste = (pagina - 1) * PER_PAGINA + 1;
  const laatste = eerste + rijen.length - 1;
  const subsectoren = [
    ...new Set(rijen.map((o) => o.subsector).filter((s): s is string => !!s)),
  ];

  return (
    <>
      <Kruimels
        paden={[
          { naar: "/", tekst: "Start" },
          { naar: "/sectoren", tekst: "Sectoren" },
          { naar: sectorPad(sector), tekst: hoofdletter(sector) },
          { tekst: "Organisaties" },
        ]}
      />

      <div className="paginakop">
        <h1>Organisaties in de sector {sector}</h1>
        <p className="metaregel">
          <span>{nl(totaal)} organisaties</span>
          <span>
            {nl(eerste)}–{nl(laatste)}, alfabetisch
          </span>
          {aantalPaginas > 1 ? (
            <span>
              pagina {pagina} van {aantalPaginas}
            </span>
          ) : null}
        </p>
      </div>

      <Paginering
        pagina={pagina}
        aantalPaginas={aantalPaginas}
        pad={(n) => sectorOrganisatiesPad(sector, n)}
      />

      <section className="kaart">
        <div className="tabel-omhulsel">
          <table>
            <thead>
              <tr>
                <th>Organisatie</th>
                <th>Plaats</th>
                <th>Subsector</th>
              </tr>
            </thead>
            <tbody>
              {rijen.map((org) => (
                <tr key={org.id}>
                  <td>
                    <Link href={organisatiePad(org)}>{org.naam}</Link>
                  </td>
                  <td className="zacht klein">{org.gemeente ?? "—"}</td>
                  <td className="zacht klein">
                    {org.subsector ? (
                      <Link href={subsectorPad(org.subsector)}>{org.subsector}</Link>
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

      <Paginering
        pagina={pagina}
        aantalPaginas={aantalPaginas}
        pad={(n) => sectorOrganisatiesPad(sector, n)}
      />

      <Doorklik
        items={[
          { naar: sectorPad(sector), tekst: `Sector ${sector}: wie controleert er` },
          ...subsectoren.slice(0, 2).map((subsector) => ({
            naar: subsectorPad(subsector),
            tekst: subsector,
          })),
          ...rijen.slice(0, 2).map((org) => ({
            naar: organisatiePad(org),
            tekst: org.naam,
            toelichting: org.gemeente ?? undefined,
          })),
          {
            naar: wisselingenPad({ sector }),
            tekst: `Accountantswisselingen in de sector ${sector}`,
          },
          { naar: "/sectoren", tekst: "Alle sectoren vergelijken" },
          { naar: "/kantoren", tekst: "Alle kantoren" },
        ]}
      />
    </>
  );
}
