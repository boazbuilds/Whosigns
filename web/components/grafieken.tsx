/**
 * Grafieken, als gewone HTML en CSS.
 *
 * Geen grafiekbibliotheek en geen JavaScript in de browser: een kolom is een
 * vlak met een hoogte in procenten, en de tooltip een verborgen regel die
 * verschijnt bij aanwijzen of bij toetsenbordfocus. Zo blijft alles
 * server-gerenderd en snel, net als de rest van de site, en werkt het zonder
 * scripts.
 *
 * Kleur staat in globals.css (blok "grafieken"): één neutrale inkt voor
 * gewone waarden, rood voor de waarde waar het verhaal over gaat, en blauw
 * tegenover rood als er twee kanten zijn. Getallen staan altijd in
 * teksttinten, nooit in de kleur van de balk. Elke grafiek krijgt op de pagina
 * een tabel met dezelfde getallen: de tooltip is gemak, geen vindplaats.
 */

import type { CSSProperties, ReactNode } from "react";
import { nl } from "@/lib/paden";

// ------------------------------------------------------------ kolommen

export type Kolom = {
  /** Voluit, voor de tooltip en de schermlezer: "2016". */
  label: string;
  /** Kort, onder de kolom: "’16". Zonder: het volledige label. */
  kort?: string;
  waarde: number;
  /** Het getal zoals het er staat: "15,6%". */
  weergave: string;
  /** Tweede regel van de tooltip: waar het getal op rust. */
  toelichting?: string;
  /** De kolom waar het verhaal over gaat: rood in plaats van inkt. */
  nadruk?: boolean;
  /** Het getal ook boven de kolom zetten. Spaarzaam: alleen waar het verhaal zit. */
  opschrift?: boolean;
};

/**
 * Staafjes naast elkaar, één reeks. De rasterlijnen komen uit `raster`, zodat
 * de pagina ronde stappen kiest (0, 5, 10, 15%) in plaats van dat de grafiek
 * rare getallen op de as zet.
 */
export function Kolomgrafiek({
  titel,
  kolommen,
  raster,
  rasterweergave,
  hoogte = 140,
}: {
  titel: string;
  kolommen: Kolom[];
  raster: number[];
  rasterweergave: (waarde: number) => string;
  hoogte?: number;
}) {
  if (!kolommen.length) return null;
  const waarden = kolommen.map((k) => k.waarde);
  const laag = Math.min(0, ...waarden, ...raster);
  const hoog = Math.max(...waarden, ...raster);
  const bereik = hoog - laag || 1;
  const y = (waarde: number) => ((waarde - laag) / bereik) * 100;
  const nul = y(0);

  return (
    <figure className="grafiek">
      <div
        // Bij veel kolommen krijgt op een smal scherm alleen elke tweede een
        // jaartal; de tooltip en de tabel hebben ze allemaal.
        className={kolommen.length > 10 ? "kolomgrafiek dicht" : "kolomgrafiek"}
        style={{ "--plot": `${hoogte}px` } as CSSProperties}
      >
        <div className="raster" aria-hidden="true">
          {raster.map((stap) => (
            <span
              key={stap}
              className={stap === 0 ? "rasterlijn nullijn" : "rasterlijn"}
              style={{ bottom: `${y(stap)}%` }}
            >
              <span className="rasterlabel">{rasterweergave(stap)}</span>
            </span>
          ))}
        </div>
        <ol className="kolomreeks" aria-label={titel}>
          {kolommen.map((kolom, i) => {
            const boven = Math.max(y(kolom.waarde), nul);
            const onder = Math.min(y(kolom.waarde), nul);
            // Aan de randen klapt de tooltip naar binnen, anders valt hij
            // buiten de kaart of het scherm.
            const rand =
              i < 2 ? " tip-links" : i >= kolommen.length - 2 ? " tip-rechts" : "";
            const uitleg = kolom.toelichting ? `, ${kolom.toelichting}` : "";
            return (
              <li
                key={kolom.label}
                className={`kolom${kolom.nadruk ? " nadruk" : ""}${rand}`}
                tabIndex={0}
                aria-label={`${kolom.label}: ${kolom.weergave}${uitleg}`}
              >
                <span
                  className="kolomvlak"
                  style={{ "--boven": `${boven}%` } as CSSProperties}
                >
                  <span
                    className={kolom.waarde < 0 ? "kolombalk negatief" : "kolombalk"}
                    style={{ bottom: `${onder}%`, height: `${boven - onder}%` }}
                  />
                  {kolom.opschrift ? (
                    <span className="opschrift" aria-hidden="true">
                      {kolom.weergave}
                    </span>
                  ) : null}
                  <span className="tip" aria-hidden="true">
                    <strong>{kolom.weergave}</strong>
                    <span>
                      {kolom.label}
                      {kolom.toelichting ? ` · ${kolom.toelichting}` : ""}
                    </span>
                  </span>
                </span>
                <span className="kolomlabel" aria-hidden="true">
                  {kolom.kort ?? kolom.label}
                </span>
              </li>
            );
          })}
        </ol>
      </div>
    </figure>
  );
}

// ------------------------------------------------------------- balans

export type Balansrij = {
  sleutel: string;
  /** Wat er links in de rij staat, meestal een link naar het kantoor. */
  naam: ReactNode;
  /** Dezelfde naam als tekst, voor de tooltip en de schermlezer. */
  naamTekst: string;
  links: number;
  rechts: number;
};

/**
 * Twee kanten van één as: links wat er afging, rechts wat erbij kwam, en het
 * saldo als getal aan het eind. De kant zegt al welke richting het op gaat;
 * de kleur herhaalt dat alleen, zodat ook wie rood en blauw niet uit elkaar
 * houdt de grafiek kan lezen.
 */
export function Balansgrafiek({
  titel,
  rijen,
  links,
  rechts,
}: {
  titel: string;
  rijen: Balansrij[];
  /** Wat de linkerkant telt, als woord: "verloren". */
  links: string;
  rechts: string;
}) {
  if (!rijen.length) return null;
  const grootste = Math.max(1, ...rijen.flatMap((r) => [r.links, r.rechts]));
  const breedte = (aantal: number) => `${(aantal / grootste) * 100}%`;

  return (
    <figure className="grafiek">
      {/* De legenda staat in hetzelfde raster als de rijen: elk woord recht
          boven zijn eigen kant van de as. */}
      <div className="balansraster legenda-balans" aria-hidden="true">
        <span />
        <span>
          {links} <i className="sleutel sleutel-links" />
        </span>
        <span>
          <i className="sleutel sleutel-rechts" /> {rechts}
        </span>
        <span>saldo</span>
      </div>
      <ol className="balans" aria-label={titel}>
        {rijen.map((rij) => {
          const saldo = rij.rechts - rij.links;
          return (
            <li key={rij.sleutel} className="balansraster balansrij">
              <span className="balansnaam" title={rij.naamTekst}>
                {rij.naam}
              </span>
              <span
                className="balanskant balans-links"
                tabIndex={0}
                aria-label={`${rij.naamTekst}: ${rij.links} ${links}`}
              >
                <span className="balansbalk" style={{ width: breedte(rij.links) }} />
                <span className="tip" aria-hidden="true">
                  <strong>{nl(rij.links)}</strong>
                  <span>
                    {links} · {rij.naamTekst}
                  </span>
                </span>
              </span>
              <span
                className="balanskant balans-rechts"
                tabIndex={0}
                aria-label={`${rij.naamTekst}: ${rij.rechts} ${rechts}`}
              >
                <span className="balansbalk" style={{ width: breedte(rij.rechts) }} />
                <span className="tip" aria-hidden="true">
                  <strong>{nl(rij.rechts)}</strong>
                  <span>
                    {rechts} · {rij.naamTekst}
                  </span>
                </span>
              </span>
              <span className="balanssaldo">{metTeken(saldo)}</span>
            </li>
          );
        })}
      </ol>
    </figure>
  );
}

/** +12, 0 of −5 — met een echt minteken, dat in tabelcijfers net zo breed is
 *  als het plusteken. */
export function metTeken(getal: number, weergave: (n: number) => string = nl): string {
  if (getal > 0) return `+${weergave(getal)}`;
  if (getal < 0) return `−${weergave(-getal)}`;
  return weergave(0);
}

// ---------------------------------------------------------- warmtekaart

/**
 * Een tabel waarin elke cel een tint krijgt naar zijn grootte: één kleur, van
 * licht naar donker. Het getal staat er zelf in, dus de tint is een hulp om
 * het patroon te zien, niet de enige drager van de waarde.
 */
export function Warmtekaart({
  titel,
  kolommen,
  rijen,
  totaal,
  klasse,
  eenheid,
}: {
  titel: string;
  kolommen: { label: string; kort: string }[];
  rijen: { sleutel: string; kop: ReactNode; kopTekst: string; waarden: number[] }[];
  totaal?: { kop: string; waarden: number[] };
  /** 0 voor leeg, 1 tot en met 5 voor licht tot donker. */
  klasse: (waarde: number) => number;
  /** "816 controles" */
  eenheid: (waarde: number) => string;
}) {
  return (
    <div className="tabel-omhulsel">
      <table className="warmtekaart">
        <caption className="verborgen">{titel}</caption>
        <thead>
          <tr>
            <th scope="col">Sector</th>
            {kolommen.map((kolom) => (
              <th key={kolom.label} scope="col">
                <abbr title={kolom.label}>{kolom.kort}</abbr>
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rijen.map((rij) => (
            <tr key={rij.sleutel}>
              <th scope="row">{rij.kop}</th>
              {rij.waarden.map((waarde, i) => (
                <td
                  key={kolommen[i].label}
                  className={`warm warm-${klasse(waarde)}`}
                  title={
                    waarde
                      ? `${rij.kopTekst} · ${kolommen[i].label}: ${eenheid(waarde)}`
                      : undefined
                  }
                >
                  {waarde ? nl(waarde) : ""}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
        {totaal ? (
          <tfoot>
            <tr>
              <th scope="row">{totaal.kop}</th>
              {totaal.waarden.map((waarde, i) => (
                <td key={kolommen[i].label}>{waarde ? nl(waarde) : ""}</td>
              ))}
            </tr>
          </tfoot>
        ) : null}
      </table>
    </div>
  );
}

/** De sleutel onder een warmtekaart: welke tint bij welk bereik hoort. */
export function Schaal({ titel, stappen }: { titel: string; stappen: string[] }) {
  return (
    <div className="schaal" aria-hidden="true">
      <span className="schaaltitel">{titel}</span>
      {stappen.map((stap, i) => (
        <span key={stap} className="schaalstap">
          <i className={`warm-${i + 1}`} />
          {stap}
        </span>
      ))}
    </div>
  );
}
