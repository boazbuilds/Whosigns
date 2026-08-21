"use client";

/**
 * Het vangnet voor een pagina die onderweg omvalt.
 *
 * Waarom dit bestaat: op 21-8-2026 zag een bezoeker de kale zwarte
 * "A server error occurred"-pagina van het platform zelf. De aanleiding was
 * geen kapotte code maar een venster van seconden: "Alles verversen" bouwt
 * views opnieuw op (drop + create, zie de migraties) terwijl Vercel tegelijk
 * de nieuwe versie uitrolde. Elke pagina vangt databasefouten al zelf af met
 * <Foutmelding>, maar wat er buiten die try's omvalt — een storing in de
 * verbinding zelf, een fout tijdens het renderen — viel tot nu toe door naar
 * de standaardpagina van het platform: Engels, zwart, en zonder één doorklik.
 *
 * Dit bestand moet een client component zijn (eis van Next bij error.tsx) en
 * mag dus niets uit de database halen — juist goed, want de database is
 * waarschijnlijk het probleem.
 */

import Link from "next/link";

export default function Fout({ reset }: { error: Error; reset: () => void }) {
  return (
    <div className="paginakop" style={{ maxWidth: "44rem" }}>
      <h1>Even niet</h1>
      <p className="zacht" style={{ marginTop: "0.4rem" }}>
        Deze pagina kon niet worden opgebouwd. Meestal is dat een storing van
        seconden — bijvoorbeeld omdat de database net wordt bijgewerkt — en
        helpt opnieuw proberen direct.
      </p>
      <p style={{ marginTop: "1rem", display: "flex", gap: "0.75rem" }}>
        <button type="button" className="knop" onClick={() => reset()}>
          Opnieuw proberen
        </button>
        <Link href="/">Naar de startpagina</Link>
      </p>
      <p className="klein zacht" style={{ marginTop: "1.5rem" }}>
        Blijft dit terugkomen, dan is er echt iets stuk en wordt er aan
        gewerkt. Er gaat bij zo'n storing niets verloren: alle gegevens staan
        los van de website opgeslagen.
      </p>
    </div>
  );
}
