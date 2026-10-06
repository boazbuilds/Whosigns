"use client";

/**
 * "Wie tekende?" — de dagelijkse vraag op de voorpagina.
 *
 * Eén vraag per dag, voor iedereen dezelfde (de server kiest hem
 * deterministisch op de datum), met een reeks die alleen doorloopt als je
 * élke dag terugkomt én goed zit. Dat is het hele verslavingsmechanisme, en
 * meer hoeft het niet te zijn: geen punten, geen deelknoppen, geen account.
 *
 * De reeks staat in localStorage en blijft dus in de browser van de bezoeker;
 * er gaat niets terug naar de server. localStorage kan ontbreken of geweigerd
 * worden (privévenster, ingeperkte browser) — dan werkt de vraag gewoon,
 * alleen zonder onthouden reeks.
 */

import { useEffect, useState } from "react";
import Link from "next/link";

type Props = {
  /** De datum (JJJJ-MM-DD, Nederlandse tijd) waar deze vraag bij hoort. */
  datum: string;
  organisatieNaam: string;
  organisatiePad: string;
  boekjaar: number;
  /** Kantoornamen in getoonde volgorde; de server heeft ze al gehusseld. */
  opties: string[];
  /** Index van het juiste antwoord in `opties`. */
  juist: number;
};

type Stand = { gespeeldOp: string; reeks: number; goed: boolean };

const OPSLAG = "wietekende";

function leesStand(): Stand | null {
  try {
    const ruw = localStorage.getItem(OPSLAG);
    if (!ruw) return null;
    const stand = JSON.parse(ruw);
    return typeof stand?.gespeeldOp === "string" && typeof stand?.reeks === "number"
      ? stand
      : null;
  } catch {
    return null;
  }
}

function bewaarStand(stand: Stand): void {
  try {
    localStorage.setItem(OPSLAG, JSON.stringify(stand));
  } catch {
    // Geen opslag, geen reeks — de vraag zelf werkt gewoon.
  }
}

/** De dag vóór een JJJJ-MM-DD-datum, als JJJJ-MM-DD. Op het middaguur gerekend
 *  zodat zomer- en wintertijd de datum niet kunnen verschuiven. */
function dagErvoor(datum: string): string {
  const d = new Date(`${datum}T12:00:00Z`);
  d.setUTCDate(d.getUTCDate() - 1);
  return d.toISOString().slice(0, 10);
}

export function DagvraagKaart({
  datum,
  organisatieNaam,
  organisatiePad,
  boekjaar,
  opties,
  juist,
}: Props) {
  const [gekozen, setGekozen] = useState<number | null>(null);
  const [reeks, setReeks] = useState(0);
  const [alGespeeld, setAlGespeeld] = useState(false);

  // Pas na het laden in de browser: de server kent localStorage niet, dus dit
  // mag niet in de eerste render meebepalen wat er staat (hydratie).
  useEffect(() => {
    const stand = leesStand();
    if (!stand) return;
    setReeks(stand.reeks);
    if (stand.gespeeldOp === datum) setAlGespeeld(true);
  }, [datum]);

  const kies = (index: number) => {
    if (gekozen !== null || alGespeeld) return;
    setGekozen(index);
    const stand = leesStand();
    // De reeks loopt alleen door wie gisteren óók speelde en goed zat.
    const opRij = stand && stand.gespeeldOp === dagErvoor(datum) ? stand.reeks : 0;
    const nieuw = index === juist ? opRij + 1 : 0;
    bewaarStand({ gespeeldOp: datum, reeks: nieuw, goed: index === juist });
    setReeks(nieuw);
  };

  const klaar = gekozen !== null;
  const goed = klaar && gekozen === juist;

  return (
    <section className="kaart dagvraag">
      <div className="kaartkop">
        <h2>Wie tekende?</h2>
        <span className="klein zacht">de dagelijkse vraag</span>
      </div>

      {alGespeeld ? (
        <>
          <p className="klein">
            Je speelde de vraag van vandaag al
            {reeks > 0 ? (
              <>
                {" "}
                — reeks: <strong>{reeks}</strong> {reeks === 1 ? "dag" : "dagen"} goed
                op rij
              </>
            ) : null}
            . Morgen staat er een nieuwe.
          </p>
          <p className="klein" style={{ marginBottom: 0 }}>
            <Link href={organisatiePad}>Bekijk {organisatieNaam} →</Link>
          </p>
        </>
      ) : (
        <>
          <p>
            Welk kantoor tekende de controleverklaring van{" "}
            <strong>{organisatieNaam}</strong> over boekjaar {boekjaar}?
          </p>
          <div className="dagvraag-opties">
            {opties.map((naam, index) => (
              <button
                key={naam}
                type="button"
                onClick={() => kies(index)}
                disabled={klaar}
                className={
                  !klaar
                    ? undefined
                    : index === juist
                      ? "dagvraag-goed"
                      : index === gekozen
                        ? "dagvraag-fout"
                        : undefined
                }
              >
                {naam}
              </button>
            ))}
          </div>
          {klaar ? (
            <>
              <p className="klein">
                {goed ? "Goed." : `Mis — het was ${opties[juist]}.`}
                {reeks > 0 ? (
                  <>
                    {" "}
                    Reeks: <strong>{reeks}</strong> {reeks === 1 ? "dag" : "dagen"}{" "}
                    goed op rij.
                  </>
                ) : null}{" "}
                Morgen een nieuwe.
              </p>
              <p className="klein" style={{ marginBottom: 0 }}>
                <Link href={organisatiePad}>Bekijk {organisatieNaam} →</Link>
              </p>
            </>
          ) : (
            <p className="klein zacht" style={{ marginBottom: 0 }}>
              Elke dag één vraag, uit de database zelf.
            </p>
          )}
        </>
      )}
    </section>
  );
}
