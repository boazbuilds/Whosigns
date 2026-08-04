import type { Metadata } from "next";
import Link from "next/link";
import { alleOrganisaties } from "@/lib/db";
import {
  aantalOrganisaties,
  aantalPlaatsen,
  organisatiePad,
  sectorPad,
  subsectorPad,
} from "@/lib/paden";
import { Doorklik, Foutmelding, Kruimels, Leeg } from "@/components/onderdelen";

export const metadata: Metadata = {
  title: "Alle organisaties",
  description:
    "Alle organisaties in de database, alfabetisch op naam, met plaats en " +
    "subsector — uit openbare bronnen.",
};

/**
 * Onder welke letter een naam hoort.
 *
 * Namen die niet met een letter beginnen — 't Boerderijtje, "Gezellig Stralen" —
 * gaan samen onder "#". Ze onder de eerste échte letter zetten zou netter lezen,
 * maar dan staat een naam niet waar de bron hem sorteert en is hij twee keer zoek.
 */
function beginletter(naam: string): string {
  // NFKD + accenten weg: "École" hoort onder de E (waar de database hem ook
  // sorteert), niet bij "Overig". De Ĳ-ligatuur wordt zo I.
  const eerste = naam
    .trim()
    .charAt(0)
    .normalize("NFKD")
    .replace(/[̀-ͯ]/g, "")
    .charAt(0)
    .toUpperCase();
  return eerste >= "A" && eerste <= "Z" ? eerste : "#";
}

export default async function Organisatieoverzicht() {
  let organisaties;
  try {
    organisaties = await alleOrganisaties();
  } catch (fout) {
    return <Foutmelding fout={fout} />;
  }

  // De lijst komt al op naam gesorteerd binnen, dus groeperen houdt die volgorde.
  const perLetter = new Map<string, typeof organisaties>();
  for (const org of organisaties) {
    const letter = beginletter(org.naam);
    perLetter.set(letter, [...(perLetter.get(letter) ?? []), org]);
  }
  // A–Z eerst, de vreemde beginletters achteraan.
  const letters = [...perLetter.keys()].sort((a, b) =>
    a === "#" ? 1 : b === "#" ? -1 : a.localeCompare(b),
  );

  const plaatsen = new Set(organisaties.map((o) => o.gemeente).filter(Boolean));

  return (
    <>
      <Kruimels paden={[{ naar: "/", tekst: "Start" }, { tekst: "Organisaties" }]} />

      <div className="paginakop">
        <h1>Alle organisaties</h1>
        <p className="metaregel">
          <span>{aantalOrganisaties(organisaties.length)}</span>
          <span>{aantalPlaatsen(plaatsen.size)}</span>
        </p>
        {/* Een nav en geen p: op een alinea negeren schermlezers het label. */}
        {letters.length > 1 ? (
          <nav className="letterbalk" aria-label="Spring naar een letter">
            {letters.map((letter) => (
              <Link key={letter} href={`#${letter === "#" ? "overig" : letter}`}>
                {letter}
              </Link>
            ))}
          </nav>
        ) : null}
      </div>

      {organisaties.length === 0 ? (
        <section className="kaart">
          <Leeg tekst="Nog geen organisaties in de database." />
        </section>
      ) : (
        letters.map((letter) => (
          <section
            className="kaart"
            key={letter}
            id={letter === "#" ? "overig" : letter}
          >
            <h2>{letter === "#" ? "Overig" : letter}</h2>
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
                  {perLetter.get(letter)!.map((org) => (
                    <tr key={org.id}>
                      <td>
                        <Link href={organisatiePad(org)}>{org.naam}</Link>
                      </td>
                      <td className="zacht">{org.gemeente ?? "—"}</td>
                      <td>
                        {org.subsector ? (
                          <Link href={subsectorPad(org.subsector)}>
                            {org.subsector}
                          </Link>
                        ) : (
                          <span className="zacht">—</span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        ))
      )}

      <Doorklik
        items={[
          ...organisaties.slice(0, 3).map((org) => ({
            naar: organisatiePad(org),
            tekst: org.naam,
            toelichting: org.gemeente ?? undefined,
          })),
          { naar: "/wisselingen", tekst: "Alle accountantswisselingen" },
          // De sectoren die in deze lijst voorkomen; niet "zorg" hardgecodeerd.
          ...[...new Set(organisaties.map((o) => o.sector).filter(Boolean))].map(
            (sector) => ({
              naar: sectorPad(sector as string),
              tekst: `Sector ${sector}: marktaandelen`,
            }),
          ),
          { naar: "/", tekst: "Naar het overzicht" },
        ]}
      />
    </>
  );
}
