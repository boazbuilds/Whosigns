import type { Metadata } from "next";
import { alleOrganisaties } from "@/lib/db";
import { organisatiePad, sectorPad } from "@/lib/paden";
import { Doorklik } from "@/components/onderdelen";

export const metadata: Metadata = { title: "Niet gevonden" };

/**
 * Ook de 404 krijgt vervolgklikken mee — "nooit een doodlopende pagina"
 * (docs/visie.md) geldt juist hier, want dit is de plek waar iemand anders
 * weggaat.
 */
export default async function NietGevonden() {
  const organisaties = await alleOrganisaties(4).catch(() => []);

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
          { naar: sectorPad("zorg"), tekst: "Sector zorg" },
          { naar: "/", tekst: "Naar het overzicht" },
        ]}
      />
    </>
  );
}
