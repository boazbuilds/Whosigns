import type { Metadata } from "next";
import Link from "next/link";
import { kantoorRanglijst, wisselingen } from "@/lib/db";
import { saldoPerKantoor } from "@/lib/analyse";
import {
  aantalJaren,
  aantalWisselingen,
  hoofdletter,
  kantoorPad,
  organisatiePad,
  sectorPad,
} from "@/lib/paden";
import {
  Doorklik,
  Foutmelding,
  KantoorLink,
  Kerncijfer,
  Kruimels,
  Leeg,
} from "@/components/onderdelen";

export const metadata: Metadata = {
  title: "Accountantswisselingen",
  description:
    "Welke organisaties wisselden van accountantskantoor, in welk boekjaar, " +
    "en van welk kantoor naar welk kantoor.",
};

export default async function Wisselingenpagina() {
  let rijen;
  let ranglijst;
  try {
    [rijen, ranglijst] = await Promise.all([
      // Zonder limiet: deze pagina heet "alle wisselingen" en de kop noemt het
      // aantal. Met een vaste grens van 200 stond daar "200" zodra er meer waren.
      wisselingen(),
      kantoorRanglijst().catch(() => []),
    ]);
  } catch (fout) {
    return <Foutmelding fout={fout} />;
  }

  const perJaar = new Map<number, typeof rijen>();
  for (const rij of rijen) {
    perJaar.set(rij.boekjaar_wissel, [...(perJaar.get(rij.boekjaar_wissel) ?? []), rij]);
  }
  const jaren = [...perJaar.keys()].sort((a, b) => b - a);
  const drukste = jaren.length
    ? jaren.reduce((a, b) => (perJaar.get(b)!.length > perJaar.get(a)!.length ? b : a))
    : null;
  const saldi = saldoPerKantoor(rijen);
  const winnaar = saldi[0];
  const verliezer = saldi[saldi.length - 1];

  return (
    <>
      <Kruimels paden={[{ naar: "/", tekst: "Start" }, { tekst: "Wisselingen" }]} />

      <div className="paginakop">
        <h1>Accountantswisselingen</h1>
        <p className="zacht klein" style={{ margin: "0.4rem 0 0", maxWidth: "44rem" }}>
          Een wisseling is een boekjaar waarin een organisatie de controle door een
          ánder kantoor liet uitvoeren dan het boekjaar ervoor. Afgeleid uit de
          historie — niet uit een aankondiging.
        </p>
        <div className="kerncijfers">
          <Kerncijfer waarde={rijen.length} naam="wisselingen" />
          <Kerncijfer waarde={jaren.length} naam="boekjaren" />
          {drukste ? (
            <Kerncijfer
              waarde={drukste}
              naam={`drukste jaar (${perJaar.get(drukste)!.length})`}
            />
          ) : null}
          {winnaar && winnaar.saldo > 0 ? (
            <Kerncijfer waarde={`+${winnaar.saldo}`} naam={`beste saldo: ${winnaar.naam}`} />
          ) : null}
          {verliezer && verliezer.saldo < 0 ? (
            <Kerncijfer
              waarde={String(verliezer.saldo)}
              naam={`slechtste saldo: ${verliezer.naam}`}
            />
          ) : null}
        </div>
      </div>

      {jaren.length > 1 ? (
        <nav className="keuzebalk" aria-label="Spring naar een boekjaar">
          {jaren.map((jaar) => (
            <Link key={jaar} href={`#jaar-${jaar}`}>
              {jaar} <span className="zacht">({perJaar.get(jaar)!.length})</span>
            </Link>
          ))}
        </nav>
      ) : null}

      {rijen.length === 0 ? (
        <section className="kaart">
          <Leeg tekst="Nog geen wisselingen in de database." />
        </section>
      ) : (
        jaren.map((jaar) => (
          <section className="kaart" key={jaar} id={`jaar-${jaar}`}>
            <div className="kaartkop">
              <h2>Boekjaar {jaar}</h2>
              <span className="klein zacht">
                {aantalWisselingen(perJaar.get(jaar)!.length)}
              </span>
            </div>
            <div className="tabel-omhulsel">
              <table>
                <thead>
                  <tr>
                    <th>Organisatie</th>
                    <th>Van</th>
                    <th>Naar</th>
                    <th>Sector</th>
                  </tr>
                </thead>
                <tbody>
                  {perJaar.get(jaar)!.map((w) => (
                    <tr key={`${w.organisatie_id}-${jaar}`}>
                      <td>
                        {w.organisatie ? (
                          <Link href={organisatiePad(w.organisatie)}>
                            {w.organisatie.naam}
                          </Link>
                        ) : (
                          "onbekend"
                        )}
                        {w.organisatie?.gemeente ? (
                          <div className="klein zacht">{w.organisatie.gemeente}</div>
                        ) : null}
                      </td>
                      <td>
                        {w.van ? (
                          <KantoorLink naam={w.van.naam} naar={kantoorPad(w.van)} />
                        ) : (
                          <span className="zacht">?</span>
                        )}
                      </td>
                      <td>
                        {w.naar ? (
                          <KantoorLink naam={w.naar.naam} naar={kantoorPad(w.naar)} />
                        ) : (
                          <span className="zacht">?</span>
                        )}
                      </td>
                      <td className="klein">
                        {w.organisatie?.sector ? (
                          <Link href={sectorPad(w.organisatie.sector)}>
                            {hoofdletter(w.organisatie.sector)}
                          </Link>
                        ) : (
                          <span className="zacht">—</span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        ))
      )}

      <Doorklik
        items={[
          ...rijen.slice(0, 3).map((w) => ({
            naar: w.organisatie ? organisatiePad(w.organisatie) : "",
            tekst: w.organisatie?.naam ?? "",
            toelichting: `wisselde in ${w.boekjaar_wissel}`,
          })),
          ...ranglijst.slice(0, 2).map((rij) => ({
            naar: kantoorPad(rij.kantoor),
            tekst: rij.kantoor.naam,
            toelichting: "gewonnen en verloren opdrachten",
          })),
          // De sectoren waarin er daadwerkelijk gewisseld is; niet "zorg" vast.
          ...[...new Set(rijen.map((w) => w.organisatie?.sector).filter(Boolean))].map(
            (sector) => ({
              naar: sectorPad(sector as string),
              tekst: `Marktaandelen in de sector ${sector}`,
            }),
          ),
          {
            naar: "/kantoren",
            tekst: "Ranglijst van kantoren met stijgers en dalers",
            toelichting: aantalJaren(jaren.length),
          },
          { naar: "/organisaties", tekst: "Alle organisaties op naam" },
        ]}
      />
    </>
  );
}
