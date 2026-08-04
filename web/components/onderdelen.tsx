/** Gedeelde bouwstenen voor de pagina's. */

import Link from "next/link";
import { OORDEEL_LABEL, oordeelOpvallend } from "@/lib/paden";

/**
 * Het oordeel als label; niet-goedkeurend krijgt nadruk.
 *
 * `waarde` komt uit de gedeponeerde verklaring zelf en gaat voor. `gerapporteerd`
 * is wat de organisatie in de jaardataset heeft opgegeven en dient als vangnet:
 * bij een ingescande pdf zonder tekstlaag is dat het enige dat er is. Zo'n
 * oordeel wordt gemarkeerd als opgave, want het is niet uit het ondertekende
 * stuk gelezen.
 */
export function Oordeel({
  waarde,
  gerapporteerd = null,
}: {
  waarde: string | null;
  gerapporteerd?: string | null;
}) {
  const oordeel = waarde ?? gerapporteerd;
  if (!oordeel) return <span className="zacht">—</span>;
  const tekst = OORDEEL_LABEL[oordeel] ?? oordeel;
  return (
    <>
      <span className={oordeelOpvallend(oordeel) ? "label label-let-op" : "label"}>
        {tekst}
      </span>
      {waarde === null ? (
        <>
          {" "}
          <span className="zacht klein" title="Opgave van de organisatie zelf; de verklaring was niet machinaal leesbaar">
            (opgave)
          </span>
        </>
      ) : null}
    </>
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
  // Dubbelen eruit (zelfde link én tekst): de relatiegeschiedenis A→B→A leverde
  // hetzelfde kantoor twee keer aan, en dat gaf twee identieke regels met
  // botsende React-sleutels.
  const zichtbaar = [
    ...new Map(
      items
        .filter((item) => item.naar)
        .map((item) => [`${item.naar}|${item.tekst}`, item] as const),
    ).values(),
  ];
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

/**
 * De staart van een lange lijst, achter één klik.
 *
 * Een tabel van honderden regels is op een telefoon geen lijst meer maar een muur:
 * je scrolt eindeloos langs iets waar je niet om vroeg, en de rest van de pagina
 * raakt onbereikbaar. De eerste regels staan open, de staart zit hierin.
 *
 * Bewust `<details>` en geen uitklap-knop in JavaScript: het werkt zonder, het is
 * met toetsenbord te openen, en de links blijven in de HTML staan — zoekmachines
 * en Ctrl-F vinden ze dus alsnog. Dat laatste is precies waarom we de staart
 * inklappen en niet weglaten.
 */
export function Inklapbaar({
  samenvatting,
  children,
}: {
  samenvatting: string;
  children: React.ReactNode;
}) {
  return (
    <details className="inklapbaar">
      <summary>{samenvatting}</summary>
      {children}
    </details>
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
