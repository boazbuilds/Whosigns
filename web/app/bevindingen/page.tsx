import type { Metadata } from "next";
import Link from "next/link";
import { bevindingen } from "@/lib/db";
import {
  kantoorPad,
  organisatiePad,
  OPDRACHT_LABEL,
  sectorPad,
  subsectorPad,
} from "@/lib/paden";
import { Doorklik, Foutmelding, Leeg, Oordeel } from "@/components/onderdelen";

export const metadata: Metadata = {
  title: "Niet-goedkeurende oordelen en continuïteit",
  description:
    "Waar gaf de accountant geen goedkeurend oordeel, en waar stond er een " +
    "paragraaf over continuïteit — per boekjaar, met de grond van de beperking.",
};

export default async function Bevindingenpagina() {
  let rijen;
  try {
    rijen = await bevindingen();
  } catch (fout) {
    return <Foutmelding fout={fout} />;
  }

  const perJaar = new Map<number, typeof rijen>();
  for (const rij of rijen) {
    perJaar.set(rij.boekjaar, [...(perJaar.get(rij.boekjaar) ?? []), rij]);
  }
  for (const lijst of perJaar.values()) {
    lijst.sort((a, b) =>
      (a.organisaties?.naam ?? "").localeCompare(b.organisaties?.naam ?? ""),
    );
  }
  const jaren = [...perJaar.keys()].sort((a, b) => b - a);

  const nietGoedkeurend = rijen.filter(
    (r) => r.oordeel && r.oordeel !== "goedkeurend",
  );
  const wnt = nietGoedkeurend.filter((r) => r.grond_beperking === "wnt");
  const inhoudelijk = nietGoedkeurend.filter(
    (r) => r.grond_beperking === "inhoudelijk",
  );
  const continuiteit = rijen.filter((r) => r.continuiteitsonzekerheid);

  return (
    <>
      <div className="paginakop">
        <h1>Waar was het oordeel niet goedkeurend?</h1>
        <p className="zacht" style={{ margin: "0.4rem 0 0", maxWidth: "44rem" }}>
          Elk oordeel met beperking, elke oordeelonthouding en elk afkeurend oordeel
          dat we in een gedeponeerde verklaring lazen — plus elke verklaring met een
          paragraaf over continuïteit.
        </p>
        <p className="metaregel" style={{ marginTop: "0.7rem" }}>
          <span>{nietGoedkeurend.length} niet-goedkeurende oordelen</span>
          <span>{continuiteit.length} keer continuïteit genoemd</span>
          <span>{jaren.length} boekjaren</span>
        </p>
      </div>

      {/* Zonder deze uitleg leest een bezoeker in "oordeel met beperking" iets wat er
          niet staat. Dat is geen nuance maar het verschil tussen een technische
          informatiebeperking en een probleem met de jaarrekening. */}
      <section className="kaart">
        <h2>Wat een beperking hier meestal betekent</h2>
        <p className="klein" style={{ maxWidth: "46rem" }}>
          Van 26 verklaringen met een beperking die we erbij pakten, gingen er{" "}
          <strong>23 over WNT-aangelegenheden bij intragroepdetachering</strong>: de
          accountant kan de gegevens over topinkomens van binnen een groep
          gedetacheerde functionarissen niet vaststellen. Dat is een beperking in de
          informatie die de accountant kón controleren — geen bevinding over de
          jaarrekening. Twee waren inhoudelijk, één had geen vindbare grond.
        </p>
        <p className="klein" style={{ maxWidth: "46rem" }}>
          Dat verklaart ook de sprong in de cijfers: in boekjaar 2022 was 0,8% van de
          oordelen niet-goedkeurend, in 2023 was dat 10,5%. Dat is geen verslechtering
          van de zorg maar een golf WNT-beperkingen.
        </p>
        {wnt.length + inhoudelijk.length > 0 ? (
          <p className="metaregel">
            <span>{wnt.length} met WNT als grond</span>
            <span>{inhoudelijk.length} inhoudelijk</span>
            <span>
              {nietGoedkeurend.length - wnt.length - inhoudelijk.length} grond nog niet
              vastgesteld
            </span>
          </p>
        ) : (
          <p className="klein zacht" style={{ marginBottom: 0 }}>
            De grond per verklaring wordt bij de volgende volledige extractieronde
            vastgesteld; tot dan staat er een streepje in de kolom.
          </p>
        )}
      </section>

      {rijen.length === 0 ? (
        <section className="kaart">
          <Leeg tekst="Geen niet-goedkeurende oordelen in de database." />
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
                    <th>Accountant</th>
                    <th>Opdracht</th>
                    <th>Oordeel</th>
                    <th>Grond</th>
                    <th>Continuïteit</th>
                  </tr>
                </thead>
                <tbody>
                  {perJaar.get(jaar)!.map((rij) => (
                    <tr
                      key={`${rij.organisaties?.id}-${jaar}-${rij.type_opdracht}`}
                      className={
                        // Eigen klasse: oranje betekent elders "gewisseld" en
                        // dezelfde kleur voor twee betekenissen leest verkeerd.
                        rij.grond_beperking === "inhoudelijk" ? "bevinding" : undefined
                      }
                    >
                      <td>
                        {rij.organisaties ? (
                          <Link href={organisatiePad(rij.organisaties)}>
                            {rij.organisaties.naam}
                          </Link>
                        ) : (
                          "onbekend"
                        )}
                        {rij.organisaties?.gemeente ? (
                          <div className="klein zacht">
                            {rij.organisaties.gemeente}
                          </div>
                        ) : null}
                      </td>
                      <td>
                        {rij.kantoren ? (
                          <Link href={kantoorPad(rij.kantoren)}>
                            {rij.kantoren.naam}
                          </Link>
                        ) : (
                          <span className="zacht">?</span>
                        )}
                      </td>
                      <td className="zacht klein">
                        {OPDRACHT_LABEL[rij.type_opdracht] ?? rij.type_opdracht}
                      </td>
                      <td>
                        <Oordeel waarde={rij.oordeel} />
                      </td>
                      <td className="klein">
                        {rij.grond_beperking === "wnt" ? (
                          <span title="WNT-aangelegenheden; geen bevinding over de jaarrekening">
                            WNT
                          </span>
                        ) : rij.grond_beperking === "inhoudelijk" ? (
                          <strong>jaarrekening</strong>
                        ) : (
                          <span className="zacht">—</span>
                        )}
                      </td>
                      <td className="klein">
                        {rij.continuiteitsonzekerheid ? (
                          <span className="label label-let-op">genoemd</span>
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
          ...inhoudelijk.slice(0, 3).map((rij) => ({
            naar: rij.organisaties ? organisatiePad(rij.organisaties) : "",
            tekst: rij.organisaties?.naam ?? "",
            toelichting: `inhoudelijke beperking in ${rij.boekjaar}`,
          })),
          ...[...new Set(rijen.map((r) => r.organisaties?.subsector).filter(Boolean))]
            .slice(0, 2)
            .map((subsector) => ({
              naar: subsectorPad(subsector as string),
              tekst: `Accountants in de ${(subsector as string).toLowerCase()}`,
            })),
          ...[...new Set(rijen.map((r) => r.organisaties?.sector).filter(Boolean))].map(
            (sector) => ({
              naar: sectorPad(sector as string),
              tekst: `Marktaandelen in de sector ${sector}`,
            }),
          ),
          { naar: "/wisselingen", tekst: "Alle accountantswisselingen" },
          { naar: "/organisaties", tekst: "Alle organisaties op naam" },
        ]}
      />
    </>
  );
}
