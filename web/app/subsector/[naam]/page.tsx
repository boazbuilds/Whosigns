import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import {
  organisatiesInSubsector,
  opdrachtenVanOrganisatie,
  subsectoren,
  wisselingen,
} from "@/lib/db";
import {
  aantalControles,
  aantalKantoren,
  aantalOrganisaties,
  aantalWisselingen,
  kantoorPad,
  organisatiePad,
  sectorPad,
  slug,
  WETTELIJKE_CONTROLE,
} from "@/lib/paden";
import { Doorklik, Foutmelding, Leeg } from "@/components/onderdelen";

type Params = { params: Promise<{ naam: string }> };

/**
 * De slug is niet omkeerbaar ("Jeugd- en pedagogische zorg" → "jeugd-en-
 * pedagogische-zorg"), dus we zoeken de echte waarde op in de lijst die de
 * database kent. Dat is één klein verzoek en het voorkomt een tweede
 * vertaaltabel die uit de pas kan lopen met `SUBSECTOR` in de pipeline.
 */
async function vindSubsector(naamSlug: string): Promise<string | null> {
  const lijst = await subsectoren();
  return lijst.find((s) => slug(s.naam) === naamSlug)?.naam ?? null;
}

export async function generateMetadata({ params }: Params): Promise<Metadata> {
  const { naam } = await params;
  const subsector = await vindSubsector(decodeURIComponent(naam)).catch(() => null);
  if (!subsector) return { title: "Subsector niet gevonden" };
  return {
    title: `Accountants in de ${subsector.toLowerCase()}`,
    description:
      `Welke accountantskantoren controleren organisaties in de ${subsector.toLowerCase()}, ` +
      `wie is er het grootst, en waar werd gewisseld.`,
  };
}

export default async function Subsectorpagina({ params }: Params) {
  const { naam } = await params;

  let subsector: string | null;
  let organisaties;
  try {
    subsector = await vindSubsector(decodeURIComponent(naam));
    organisaties = subsector ? await organisatiesInSubsector(subsector) : [];
  } catch (fout) {
    return <Foutmelding fout={fout} />;
  }
  // Buiten de try: notFound() werkt met een uitzondering die Next zelf opvangt.
  // Binnen de try slokte onze eigen catch die op, en kreeg de bezoeker bij een
  // onbekende subsector een foutmelding met http-status 200 in plaats van een 404.
  if (!subsector || organisaties.length === 0) notFound();

  // Marktaandeel binnen een subsector kan niet uit v_marktaandeel komen: die view
  // groepeert op sector. Daarom hier optellen over de opdrachten van deze
  // organisaties. Bij enkele honderden is dat te overzien; wordt het een vaste
  // pagina met duizenden organisaties, dan hoort er een view tegenover te staan.
  //
  // Wél op dezelfde manier filteren als die views doen: alleen wettelijke
  // controles. Een verklaring bij een WNT- of productieverantwoording is een
  // andere opdracht, en meetellen zou dit percentage laten afwijken van het
  // marktaandeel op de sectorpagina.
  const perKantoor = new Map<
    string,
    { naam: string; afm: string | null; aantal: number; jaren: Set<number> }
  >();
  const opdrachtenPerOrg = await Promise.all(
    organisaties.slice(0, 250).map((org) => opdrachtenVanOrganisatie(org.id)),
  );
  for (const opdrachten of opdrachtenPerOrg) {
    for (const opdracht of opdrachten) {
      const kantoor = opdracht.kantoren;
      if (!kantoor) continue;
      if (opdracht.type_opdracht !== WETTELIJKE_CONTROLE) continue;
      const rij = perKantoor.get(kantoor.naam) ?? {
        naam: kantoor.naam,
        afm: kantoor.afm_nummer,
        aantal: 0,
        jaren: new Set<number>(),
      };
      rij.aantal += 1;
      rij.jaren.add(opdracht.boekjaar);
      perKantoor.set(kantoor.naam, rij);
    }
  }
  const kantoren = [...perKantoor.values()].sort((a, b) => b.aantal - a.aantal);
  const totaal = kantoren.reduce((som, k) => som + k.aantal, 0);

  const organisatieIds = new Set(organisaties.map((o) => o.id));
  const subsectorWisselingen = (await wisselingen()).filter((w) =>
    organisatieIds.has(w.organisatie_id),
  );

  // Onder welke sector deze subsector valt, uit de organisaties zelf. Hier stond
  // "zorg" hardgecodeerd; sinds er ook goede doelen in de database staan beweerde
  // deze pagina dat "Natuur en milieu" een zorgsubsector is.
  const perSector = new Map<string, number>();
  for (const org of organisaties) {
    if (org.sector) perSector.set(org.sector, (perSector.get(org.sector) ?? 0) + 1);
  }
  const sector = [...perSector.entries()].sort((a, b) => b[1] - a[1])[0]?.[0] ?? null;

  return (
    <>
      <div className="paginakop">
        <h1>{subsector}</h1>
        <p className="metaregel">
          {sector ? (
            <span>
              <Link href={sectorPad(sector)}>{sector}</Link>
            </span>
          ) : null}
          <span>{aantalOrganisaties(organisaties.length)}</span>
          <span>{aantalKantoren(kantoren.length)}</span>
          {subsectorWisselingen.length ? (
            <span>{aantalWisselingen(subsectorWisselingen.length)}</span>
          ) : null}
        </p>
      </div>

      <section className="kaart">
        <h2>Accountantskantoren in deze subsector</h2>
        {kantoren.length === 0 ? (
          <Leeg tekst="Nog geen opdrachten in deze subsector." />
        ) : (
          <div className="tabel-omhulsel">
            <table>
              <thead>
                <tr>
                  <th>Kantoor</th>
                  <th className="getal">Controles</th>
                  <th className="getal">Aandeel</th>
                  <th className="getal">Boekjaren</th>
                </tr>
              </thead>
              <tbody>
                {kantoren.map((rij) => (
                  <tr key={rij.naam}>
                    <td>
                      <Link href={kantoorPad({ afm_nummer: rij.afm, naam: rij.naam })}>
                        {rij.naam}
                      </Link>
                    </td>
                    <td className="getal">{rij.aantal}</td>
                    <td className="getal">
                      {totaal ? `${Math.round((100 * rij.aantal) / totaal)}%` : "—"}
                    </td>
                    <td className="jaar">{rij.jaren.size}</td>
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
            <thead>
              <tr>
                <th>Organisatie</th>
                <th>Plaats</th>
              </tr>
            </thead>
            <tbody>
              {organisaties.map((org) => (
                <tr key={org.id}>
                  <td>
                    <Link href={organisatiePad(org)}>{org.naam}</Link>
                  </td>
                  <td className="zacht">{org.gemeente ?? "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <Doorklik
        items={[
          ...kantoren.slice(0, 3).map((rij) => ({
            naar: kantoorPad({ afm_nummer: rij.afm, naam: rij.naam }),
            tekst: rij.naam,
            toelichting: `${aantalControles(rij.aantal)} in deze subsector`,
          })),
          ...organisaties.slice(0, 2).map((org) => ({
            naar: organisatiePad(org),
            tekst: org.naam,
            toelichting: org.gemeente ?? undefined,
          })),
          {
            naar: sector ? sectorPad(sector) : "",
            tekst: sector ? `Alle subsectoren in ${sector}` : "",
          },
          { naar: "/wisselingen", tekst: "Alle accountantswisselingen" },
          { naar: "/organisaties", tekst: "Alle organisaties op naam" },
        ]}
      />
    </>
  );
}
