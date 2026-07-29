/** Gedeelde bouwstenen voor de pagina's. */

import Link from "next/link";
import { OORDEEL_LABEL, oordeelOpvallend } from "@/lib/paden";

/** Het oordeel als label; niet-goedkeurend krijgt nadruk. */
export function Oordeel({ waarde }: { waarde: string | null }) {
  if (!waarde) return <span className="zacht">—</span>;
  const tekst = OORDEEL_LABEL[waarde] ?? waarde;
  return (
    <span className={oordeelOpvallend(waarde) ? "label label-let-op" : "label"}>
      {tekst}
    </span>
  );
}

export type Doorklikje = {
  naar: string;
  tekst: string;
  toelichting?: string;
};

/**
 * Het blok onderaan elke pagina.
 *
 * Harde UI-regel uit docs/visie.md: **minimaal 5 interessante vervolgklikken per
 * pagina, nooit een doodlopende pagina.** Tijdens ontwikkelen waarschuwt dit
 * onderdeel in de console als een pagina onder de vijf zakt, zodat de regel niet
 * stilletjes sneuvelt als er een link wegvalt bij weinig data.
 */
export function Doorklik({
  titel = "Verder klikken",
  items,
}: {
  titel?: string;
  items: Doorklikje[];
}) {
  const zichtbaar = items.filter((item) => item.naar);
  if (process.env.NODE_ENV !== "production" && zichtbaar.length < 5) {
    console.warn(
      `[visie] Deze pagina heeft ${zichtbaar.length} vervolgklikken; de regel is minimaal 5.`,
    );
  }
  if (!zichtbaar.length) return null;
  return (
    <nav className="doorklik" aria-label={titel}>
      <h2>{titel}</h2>
      <ul>
        {zichtbaar.map((item) => (
          <li key={item.naar + item.tekst}>
            <Link href={item.naar}>{item.tekst}</Link>
            {item.toelichting ? (
              <span className="zacht klein"> — {item.toelichting}</span>
            ) : null}
          </li>
        ))}
      </ul>
    </nav>
  );
}

/** Nette melding als de database niet bereikbaar is of leeg blijkt. */
export function Foutmelding({ fout }: { fout: unknown }) {
  const tekst = fout instanceof Error ? fout.message : String(fout);
  return (
    <div className="foutvlak">
      <strong>De gegevens konden niet worden opgehaald.</strong>
      <p className="klein">
        <code>{tekst}</code>
      </p>
    </div>
  );
}

export function Leeg({ tekst }: { tekst: string }) {
  return <p className="leeg">{tekst}</p>;
}
