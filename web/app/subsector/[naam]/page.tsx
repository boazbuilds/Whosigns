import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import {
  organisatiesInSubsector,
  opdrachtenVanOrganisaties,
  subsectoren,
  wisselingen,
} from "@/lib/db";
import {
  aantalControles,
  aantalKantoren,
  aantalOrganisaties,
  aantalWisselingen,
  CONTROLE_TYPES,
  kantoorPad,
  organisatiePad,
  sectorPad,
  slug,
  veiligGedecodeerd,
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
  const subsector = await vindSubsector(veiligGedecodeerd(naam)).catch(() => null);
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

  let subsector: string | null = null;
  let organisaties;
  let subsectorOpdrachten;
  let subsectorWisselingen;
  try {
    subsector = await vindSubsector(veiligGedecodeerd(naam));
    organisaties = subsector ? await organisatiesInSubsector(subsector) : [];
    // Alle organisaties, in een handvol gebundelde verzoeken. Hier stond een
    // stille afkapping op de eerste 250 (alfabetisch): de kop meldde het echte
    // aantal, maar de kantorentabel en de aandelen gingen over A tot ergens
    // halverwege — en niets op de pagina zei dat.
    subsectorOpdrachten = await opdrachtenVanOrganisaties(organisaties.map((o) => o.id));
    const organisatieIds = new Set(organisaties.map((o) => o.id));
    subsectorWisselingen = (await wisselingen()).filter((w) =>
      organisatieIds.has(w.organisatie_id),
    );
  } catch (fout) {
    return <Foutmelding fout={fout} />;
  }
  // Buiten de try: notFound() werkt met een uitzondering die Next zelf opvangt.
  // Binnen de try slokte onze eigen catch die op, en kreeg de bezoeker bij een
  // onbekende subsector een foutmelding met http-status 200 in plaats van een 404.
  if (!subsector || organisaties.length === 0) notFound();

  // Marktaandeel binnen een subsector kan niet uit v_marktaandeel komen: die view
  // groepeert op sector. Daarom hier optellen over de opdrachten van deze
  // organisaties — met dezélfde typeset als die views (wettelijke én vrijwillige
  // controles, migratie 20260730000000). Met alleen wettelijke sprak deze tabel
  // de sectorpagina tegen: ruim duizend vrijwillige controles telden daar wél
  // mee en hier niet. Gegroepeerd op kantoor-id, niet op naam: twee kantoren
  // kunnen dezelfde naam dragen (doorstart na fusie).
  const perKantoor = new Map<
    number,
    { id: number; naam: string; afm: string | null; aantal: number; jaren: Set<number> }
  >();
  for (const opdracht of subsectorOpdrachten) {
    const kantoor = opdracht.kantoren;
    if (!kantoor) continue;
    if (!CONTROLE_TYPES.includes(opdracht.type_opdracht)) continue;
    const rij = perKantoor.get(kantoor.id) ?? {
      id: kantoor.id,
      naam: kantoor.naam,
      afm: kantoor.afm_nummer,
      aantal: 0,
      jaren: new Set<number>(),
    };
    rij.aantal += 1;
    rij.jaren.add(opdracht.boekjaar);
    perKantoor.set(kantoor.id, rij);
  }
  const kantoren = [...perKantoor.values()].sort((a, b) => b.aantal - a.aantal);
  const totaal = kantoren.reduce((som, k) => som + k.aantal, 0);

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
                  <tr key={rij.id}>
                    <td>
                      <Link
                        href={kantoorPad({ id: rij.id, afm_nummer: rij.afm, naam: rij.naam })}
                      >
                        {rij.naam}
                      </Link>
                    </td>
                    <td className="getal">{rij.aantal}</td>
                    <td className="getal">
                      {totaal ? `${Math.round((100 * rij.aantal) / totaal)}%` : "—"}
                    </td>
                    <td className="getal">{rij.jaren.size}</td>
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
            naar: kantoorPad({ id: rij.id, afm_nummer: rij.afm, naam: rij.naam }),
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
