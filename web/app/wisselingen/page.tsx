import type { Metadata } from "next";
import Link from "next/link";
import { actieveKantoren, nieuwsteBoekjaar, wisselingen } from "@/lib/db";
import { kantoorPad, organisatiePad, sectorPad } from "@/lib/paden";
import { Doorklik, Foutmelding, Leeg } from "@/components/onderdelen";

export const metadata: Metadata = {
  title: "Accountantswisselingen",
  description:
    "Welke organisaties wisselden van accountantskantoor, in welk boekjaar, " +
    "en van welk kantoor naar welk kantoor.",
};

export default async function Wisselingenpagina() {
  let rijen;
  let kantoren;
  try {
    const boekjaar = await nieuwsteBoekjaar();
    [rijen, kantoren] = await Promise.all([
      wisselingen({ limiet: 200 }),
      boekjaar ? actieveKantoren(boekjaar) : Promise.resolve([]),
    ]);
  } catch (fout) {
    return <Foutmelding fout={fout} />;
  }

  const perJaar = new Map<number, typeof rijen>();
  for (const rij of rijen) {
    perJaar.set(rij.boekjaar_wissel, [...(perJaar.get(rij.boekjaar_wissel) ?? []), rij]);
  }
  const jaren = [...perJaar.keys()].sort((a, b) => b - a);

  return (
    <>
      <div className="paginakop">
        <h1>Accountantswisselingen</h1>
        <p className="zacht" style={{ margin: "0.4rem 0 0", maxWidth: "44rem" }}>
          Een wisseling is een boekjaar waarin een organisatie de controle door een
          ánder kantoor liet uitvoeren dan het boekjaar ervoor. Afgeleid uit de
          historie — niet uit een aankondiging.
        </p>
        <p className="metaregel" style={{ marginTop: "0.7rem" }}>
          <span className="label label-demo">Demo · gedeeltelijke data</span>
          <span>{rijen.length} wisselingen</span>
          <span>{jaren.length} boekjaren</span>
        </p>
      </div>

      {rijen.length === 0 ? (
        <section className="kaart">
          <Leeg tekst="Nog geen wisselingen in de database." />
        </section>
      ) : (
        jaren.map((jaar) => (
          <section className="kaart" key={jaar}>
            <h2>Boekjaar {jaar}</h2>
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
                          <Link href={kantoorPad(w.van)}>{w.van.naam}</Link>
                        ) : (
                          <span className="zacht">?</span>
                        )}
                      </td>
                      <td>
                        {w.naar ? (
                          <Link href={kantoorPad(w.naar)}>{w.naar.naam}</Link>
                        ) : (
                          <span className="zacht">?</span>
                        )}
                      </td>
                      <td>
                        {w.organisatie?.sector ? (
                          <Link href={sectorPad(w.organisatie.sector)}>
                            {w.organisatie.sector}
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
          ...kantoren.slice(0, 2).map((rij) => ({
            naar: kantoorPad(rij.kantoor!),
            tekst: rij.kantoor!.naam,
            toelichting: "gewonnen en verloren opdrachten",
          })),
          { naar: sectorPad("zorg"), tekst: "Marktaandelen in de zorg" },
          { naar: "/", tekst: "Alle organisaties" },
        ]}
      />
    </>
  );
}
