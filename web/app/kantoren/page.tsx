import type { Metadata } from "next";
import Link from "next/link";
import {
  boekjarenMetControles,
  kantoorRanglijst,
  wisselingen,
} from "@/lib/db";
import { saldoPerKantoor } from "@/lib/analyse";
import {
  aantalControles,
  aantalKantoren,
  hoofdletter,
  kantoorPad,
  nl,
  sectorPad,
} from "@/lib/paden";
import {
  Aandeelbalk,
  Doorklik,
  Foutmelding,
  Kerncijfer,
  Kruimels,
  KantoorLink,
  Leeg,
  Podiumplek,
  Rang,
} from "@/components/onderdelen";

export const metadata: Metadata = {
  title: "Ranglijst van accountantskantoren",
  description:
    "Welke accountantskantoren controleren de meeste organisaties in Nederland, " +
    "per boekjaar en per sector — met gewonnen en verloren opdrachten.",
};

/** Zoveel jaren in de keuzebalk; ouder blijft bereikbaar via de sectorpagina's. */
const JAREN_IN_BALK = 8;
/** Zoveel kantoren staan open; de staart zit in dezelfde tabel eronder. */
const OPEN = 30;

type Zoek = { searchParams: Promise<{ jaar?: string }> };

export default async function Kantorenpagina({ searchParams }: Zoek) {
  const { jaar } = await searchParams;

  let jaren: number[];
  try {
    jaren = await boekjarenMetControles();
  } catch (fout) {
    return <Foutmelding fout={fout} />;
  }

  // "alles" telt alle boekjaren op; een geldig jaartal kiest één jaar. Een
  // onzinnige waarde in de URL valt terug op het nieuwste jaar in plaats van
  // een lege pagina te geven.
  const gekozen =
    jaar === "alles" ? null : jaren.includes(Number(jaar)) ? Number(jaar) : jaren[0] ?? null;

  const [ranglijst, mutaties] = await Promise.all([
    kantoorRanglijst(gekozen ?? undefined),
    wisselingen(gekozen ? { boekjaar: gekozen } : {}),
  ]);

  const totaalControles = ranglijst.reduce((som, rij) => som + rij.aantal_controles, 0);
  const saldi = saldoPerKantoor(mutaties);
  const stijgers = saldi.filter((rij) => rij.saldo > 0).slice(0, 6);
  const dalers = [...saldi].reverse().filter((rij) => rij.saldo < 0).slice(0, 6);
  const periode = gekozen ? `boekjaar ${gekozen}` : "alle boekjaren";

  // De vestigingsplaats bestaat pas na migratie 20260804140000. Zolang die niet
  // is gedraaid is de hele kolom leeg, en een kolom vol streepjes is erger dan
  // geen kolom: hem dan gewoon weglaten.
  const toonPlaats = ranglijst.some((rij) => rij.kantoor.plaats);

  const rijen = ranglijst.map((rij, i) => (
    <tr key={rij.kantoor.id}>
      <td className="rangcel">
        <Rang nummer={i + 1} />
      </td>
      <td>
        <KantoorLink naam={rij.kantoor.naam} naar={kantoorPad(rij.kantoor)} maat="m" />
      </td>
      {toonPlaats ? <td className="zacht klein">{rij.kantoor.plaats ?? "—"}</td> : null}
      <td className="klein">
        {rij.kantoor.oob_vergunning ? (
          <span className="label label-oob">OOB</span>
        ) : (
          <span className="zacht">—</span>
        )}
      </td>
      <td className="klein zacht">
        {rij.perSector.length === 0
          ? "—"
          : rij.perSector
              .slice(0, 2)
              .map(([sector, aantal]) => `${hoofdletter(sector)} ${aantal}`)
              .join(" · ")}
        {rij.perSector.length > 2 ? ` · +${rij.perSector.length - 2}` : ""}
      </td>
      <td className="getal">
        <strong>{rij.aantal_controles}</strong>
      </td>
      <td className="balkcel">
        <Aandeelbalk deel={rij.aantal_controles} geheel={totaalControles} />
      </td>
    </tr>
  ));

  return (
    <>
      <Kruimels paden={[{ naar: "/", tekst: "Start" }, { tekst: "Kantoren" }]} />

      <div className="paginakop">
        <h1>Accountantskantoren</h1>
        <p className="metaregel">
          <span>{aantalKantoren(ranglijst.length)} met controles</span>
          <span>{aantalControles(totaalControles)}</span>
          <span>{periode}</span>
        </p>
        <div className="kerncijfers">
          <Kerncijfer waarde={ranglijst.length} naam="kantoren in de lijst" />
          <Kerncijfer waarde={nl(totaalControles)} naam={`controles in ${periode}`} />
          <Kerncijfer
            waarde={mutaties.length}
            naam="wisselingen in deze periode"
            naar="/wisselingen"
          />
          <Kerncijfer
            waarde={ranglijst.filter((r) => r.kantoor.oob_vergunning).length}
            naam="met OOB-vergunning"
          />
        </div>
      </div>

      <nav className="keuzebalk" aria-label="Kies een boekjaar">
        <Link
          href="/kantoren?jaar=alles"
          className={gekozen === null ? "actief" : undefined}
        >
          Alle jaren
        </Link>
        {jaren.slice(0, JAREN_IN_BALK).map((j) => (
          <Link
            key={j}
            href={`/kantoren?jaar=${j}`}
            className={gekozen === j ? "actief" : undefined}
          >
            {j}
          </Link>
        ))}
      </nav>

      {ranglijst.length >= 3 ? (
        <section className="kaart">
          <h2>De top drie in {periode}</h2>
          <div className="podium">
            {ranglijst.slice(0, 3).map((rij, i) => (
              <Podiumplek
                key={rij.kantoor.id}
                plek={i + 1}
                naar={kantoorPad(rij.kantoor)}
                naam={rij.kantoor.naam}
                onder={`${((rij.aantal_controles / totaalControles) * 100).toFixed(1)}% van de markt`}
                groot={String(rij.aantal_controles)}
              />
            ))}
          </div>
        </section>
      ) : null}

      <section className="kaart">
        <div className="kaartkop">
          <h2>Ranglijst — {periode}</h2>
          <Link href="/wisselingen">Alle wisselingen →</Link>
        </div>
        {ranglijst.length === 0 ? (
          <Leeg tekst="Voor dit boekjaar staan er nog geen controles in de database." />
        ) : (
          <div className="tabel-omhulsel">
            <table>
              <thead>
                <tr>
                  <th>#</th>
                  <th>Kantoor</th>
                  {toonPlaats ? <th>Plaats</th> : null}
                  <th>Vergunning</th>
                  <th>Sectoren</th>
                  <th className="getal">Controles</th>
                  <th>Aandeel</th>
                </tr>
              </thead>
              <tbody>{rijen.slice(0, OPEN)}</tbody>
            </table>
          </div>
        )}
        {rijen.length > OPEN ? (
          <details className="inklapbaar">
            <summary>Nog {rijen.length - OPEN} kantoren met minder controles</summary>
            <div className="tabel-omhulsel">
              <table>
                <tbody>{rijen.slice(OPEN)}</tbody>
              </table>
            </div>
          </details>
        ) : null}
      </section>

      <div className="kolommen">
        <section className="kaart">
          <h2>Stijgers — meeste cliënten gewonnen</h2>
          {stijgers.length === 0 ? (
            <Leeg tekst="Geen wisselingen in deze periode." />
          ) : (
            <table>
              <tbody>
                {stijgers.map((rij) => (
                  <tr key={rij.kantoorId}>
                    <td>
                      <KantoorLink
                        naam={rij.naam}
                        naar={kantoorPad({ afm_nummer: rij.afmNummer, naam: rij.naam })}
                      />
                    </td>
                    <td className="getal zacht klein">
                      +{rij.gewonnen} / −{rij.verloren}
                    </td>
                    <td className="getal">
                      <span className="saldo saldo-plus">+{rij.saldo}</span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </section>

        <section className="kaart">
          <h2>Dalers — meeste cliënten verloren</h2>
          {dalers.length === 0 ? (
            <Leeg tekst="Geen wisselingen in deze periode." />
          ) : (
            <table>
              <tbody>
                {dalers.map((rij) => (
                  <tr key={rij.kantoorId}>
                    <td>
                      <KantoorLink
                        naam={rij.naam}
                        naar={kantoorPad({ afm_nummer: rij.afmNummer, naam: rij.naam })}
                      />
                    </td>
                    <td className="getal zacht klein">
                      +{rij.gewonnen} / −{rij.verloren}
                    </td>
                    <td className="getal">
                      <span className="saldo saldo-min">{rij.saldo}</span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </section>
      </div>

      <Doorklik
        items={[
          ...ranglijst.slice(0, 4).map((rij) => ({
            naar: kantoorPad(rij.kantoor),
            tekst: rij.kantoor.naam,
            toelichting: aantalControles(rij.aantal_controles),
          })),
          ...[...new Set(ranglijst.flatMap((r) => r.perSector.map(([s]) => s)))]
            .slice(0, 3)
            .map((sector) => ({
              naar: sectorPad(sector),
              tekst: `Marktaandelen in de sector ${sector}`,
            })),
          { naar: "/sectoren", tekst: "Alle sectoren" },
          { naar: "/wisselingen", tekst: "Alle accountantswisselingen" },
        ]}
      />
    </>
  );
}
