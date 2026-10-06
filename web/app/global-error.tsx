"use client";

/**
 * Zelfde vangnet als error.tsx, maar voor het geval de fout in de layout zelf
 * zit. Next vervangt dan het hele document, dus dit bestand moet zijn eigen
 * <html> en <body> meebrengen en kan niet op de stylesheet van de site
 * rekenen — vandaar de handvol inline-stijlen. Sober is hier goed: deze
 * pagina bestaat om nooit gezien te worden.
 */

export default function AlgeheleFout({ reset }: { error: Error; reset: () => void }) {
  return (
    <html lang="nl">
      <body
        style={{
          fontFamily: "system-ui, sans-serif",
          maxWidth: "40rem",
          margin: "15vh auto 0",
          padding: "0 1.5rem",
          lineHeight: 1.6,
        }}
      >
        <h1 style={{ fontSize: "1.4rem" }}>WhoSigns doet het even niet</h1>
        <p>
          De site kon niet worden opgebouwd. Meestal is dat een storing van
          seconden; opnieuw proberen helpt vrijwel altijd.
        </p>
        <p>
          <button
            type="button"
            onClick={() => reset()}
            style={{ padding: "0.5rem 1rem", cursor: "pointer" }}
          >
            Opnieuw proberen
          </button>
        </p>
      </body>
    </html>
  );
}
