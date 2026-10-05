"use client";

/**
 * Het vangnet voor een pagina die onderweg omvalt.
 *
 * Waarom dit bestaat: op 21-8-2026 zag een bezoeker de kale zwarte
 * "A server error occurred"-pagina van het platform zelf. De aanleiding was
 * geen kapotte code maar een venster van seconden: "Alles verversen" bouwt
 * views opnieuw op (drop + create, zie de migraties) terwijl Vercel tegelijk
 * de nieuwe versie uitrolde. Wat er buiten de eigen try's omvalt — een storing
 * in de verbinding zelf, een fout tijdens het renderen — viel tot dan toe door
 * naar de standaardpagina van het platform: Engels, zwart, en zonder één
 * doorklik.
 *
 * Sinds 5-10-2026 komen de pagina's die Next in de cache bewaart (ISR: de
 * voorpagina, /honoraria, /accountants, /sectoren en de organisatie-, sector-,
 * subsector- en accountantpagina's) hier bewust terecht. Ze vingen een
 * databasefout zelf af en toonden <Foutmelding> — en voor Next is dat een
 * geslaagde versie. Mislukte de verversing op de achtergrond, dan ging die
 * foutpagina de cache in en zag iedereen een uur lang "De gegevens konden
 * niet worden opgehaald". Een geworpen fout houdt Next tegen: de vorige versie
 * blijft staan en er wordt na hooguit dertig seconden opnieuw geprobeerd
 * (handleRevalidate in next/dist/server/response-cache, Next 16.2). Nagemeten
 * op 5-10-2026 met een nagedane storing: na een mislukte verversing kreeg een
 * bezoeker van /honoraria gewoon de vorige versie, met 's-maxage=30'.
 *
 * De keerzijde, ook gemeten: is er van een adres nog géén versie (het eerste
 * bezoek aan een organisatiepagina, midden in een storing), dan geeft Next
 * een kale 500 "Internal Server Error" en niet dit scherm. Die gaat niet de
 * cache in; het volgende bezoek na de storing bouwt de pagina gewoon op. Een
 * <Foutmelding> met connection() erbij, om alleen díe versie buiten de cache te
 * houden, gaf precies dezelfde kale 500 (DYNAMIC_SERVER_USAGE). Dit scherm
 * verschijnt bij de dynamische pagina's die een fout doorgooien.
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
