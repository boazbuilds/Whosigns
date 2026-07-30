import type { Metadata } from "next";
import { alleOrganisaties, sectoren } from "@/lib/db";
import { organisatiePad, sectorPad } from "@/lib/paden";
import { Doorklik } from "@/components/onderdelen";

export const metadata: Metadata = { title: "Niet gevonden" };

/**
 * Ook de 404 krijgt vervolgklikken mee — "nooit een doodlopende pagina"
 * (docs/visie.md) geldt juist hier, want dit is de plek waar iemand anders
 * weggaat.
 */
export default async function NietGevonden() {
  const [organisaties, sectorlijst] = await Promise.all([
    alleOrganisaties(4).catch(() => []),
    sectoren().catch(() => []),
  ]);

  return (
    <>
      <div className="paginakop">
        <h1>Deze pagina bestaat niet</h1>
        <p className="zacht" style={{ margin: "0.4rem 0 0", maxWidth: "42rem" }}>
          Mogelijk staat deze organisatie of dit kantoor nog niet in de database.
        </p>
      </div>

      <Doorklik
        titel="Verder kijken"
        items={[
          ...organisaties.slice(0, 4).map((org) => ({
            naar: organisatiePad(org),
            tekst: org.naam,
            toelichting: org.gemeente ?? undefined,
          })),
          { naar: "/wisselingen", tekst: "Alle accountantswisselingen" },
          { naar: "/organisaties", tekst: "Alle organisaties op naam" },
          ...sectorlijst.map((sector) => ({
            naar: sectorPad(sector.naam),
            tekst: `Sector ${sector.naam}`,
            toelichting: `${sector.aantal} organisaties`,
          })),
          { naar: "/", tekst: "Naar het overzicht" },
        ]}
      />
    </>
  );
}
