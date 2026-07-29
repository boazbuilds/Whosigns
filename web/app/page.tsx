import Link from "next/link";
import {
  actieveKantoren,
  alleOrganisaties,
  nieuwsteBoekjaar,
  tel,
  wisselingen,
} from "@/lib/db";
import { aantalControles, kantoorPad, organisatiePad, sectorPad } from "@/lib/paden";
import { Doorklik, Foutmelding, Leeg } from "@/components/onderdelen";

export default async function Startpagina() {
  let inhoud;
  try {
    const boekjaar = (await nieuwsteBoekjaar()) ?? new Date().getFullYear() - 1;
    const [organisaties, laatsteWisselingen, kantoren, aantalOpdrachten] =
      await Promise.all([
        alleOrganisaties(),
        wisselingen({ limiet: 8 }),
        actieveKantoren(boekjaar),
        tel("opdrachten"),
      ]);

    inhoud = (
      <>
        <div className="paginakop">
          <h1>Wie controleert wie?</h1>
          <p className="zacht" style={{ margin: "0.4rem 0 0", maxWidth: "44rem" }}>
            WhoSigns legt de assurance-markt vast als relatiegraaf: welke accountant
            controleert welke organisatie, in welk boekjaar, en wanneer er is
            gewisseld. Alles uit openbare bronnen, met de bron erbij.
          </p>
          <p className="metaregel" style={{ marginTop: "0.7rem" }}>
            <span className="label label-demo">Demo · gedeeltelijke data</span>
            <span>{organisaties.length} organisaties</span>
            <span>{aantalOpdrachten} opdrachten</span>
            <span>boekjaren 2019–{boekjaar}</span>
          </p>
        </div>

        <div className="kolommen">
          <section className="kaart">
            <h2>Recente accountantswisselingen</h2>
            {laatsteWisselingen.length === 0 ? (
              <Leeg tekst="Nog geen wisselingen in de database." />
            ) : (
              <table>
                <tbody>
                  {laatsteWisselingen.map((w) => (
                    <tr key={`${w.organisatie_id}-${w.boekjaar_wissel}`}>
                      <td className="jaar">{w.boekjaar_wissel}</td>
                      <td>
                        {w.organisatie ? (
                          <Link href={organisatiePad(w.organisatie)}>
                            {w.organisatie.naam}
                          </Link>
                        ) : (
                          "onbekend"
                        )}
                        <div className="klein zacht">
                          {w.van ? (
                            <Link href={kantoorPad(w.van)}>{w.van.naam}</Link>
                          ) : (
                            "?"
                          )}{" "}
                          →{" "}
                          {w.naar ? (
                            <Link href={kantoorPad(w.naar)}>{w.naar.naam}</Link>
                          ) : (
                            "?"
                          )}
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
            <p className="klein" style={{ marginBottom: 0 }}>
              <Link href="/wisselingen">Alle wisselingen →</Link>
            </p>
          </section>

          <section className="kaart">
            <h2>Accountantskantoren in {boekjaar}</h2>
            {kantoren.length === 0 ? (
              <Leeg tekst="Nog geen opdrachten in dit boekjaar." />
            ) : (
              <table>
                <thead>
                  <tr>
                    <th>Kantoor</th>
                    <th className="getal">Controles</th>
                  </tr>
                </thead>
                <tbody>
                  {kantoren.map((rij) => (
                    <tr key={rij.kantoor_id}>
                      <td>
                        <Link href={kantoorPad(rij.kantoor!)}>{rij.kantoor!.naam}</Link>
                        {rij.kantoor!.oob_vergunning ? (
                          <> <span className="label label-oob">OOB</span></>
                        ) : null}
                      </td>
                      <td className="getal">{rij.aantal_controles}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
            <p className="klein" style={{ marginBottom: 0 }}>
              <Link href={sectorPad("zorg")}>Marktaandeel in de zorg →</Link>
            </p>
          </section>
        </div>

        <section className="kaart">
          <h2>Alle organisaties</h2>
          <div className="tabel-omhulsel">
            <table>
              <thead>
                <tr>
                  <th>Organisatie</th>
                  <th>Plaats</th>
                  <th>Sector</th>
                </tr>
              </thead>
              <tbody>
                {organisaties.map((org) => (
                  <tr key={org.id}>
                    <td>
                      <Link href={organisatiePad(org)}>{org.naam}</Link>
                    </td>
                    <td className="zacht">{org.gemeente ?? "—"}</td>
                    <td>
                      {org.sector ? (
                        <Link href={sectorPad(org.sector)}>{org.sector}</Link>
                      ) : (
                        "—"
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>

        <Doorklik
          titel="Beginnen met klikken"
          items={[
            { naar: "/wisselingen", tekst: "Alle accountantswisselingen" },
            { naar: sectorPad("zorg"), tekst: "Sector zorg: marktaandelen" },
            ...kantoren.slice(0, 3).map((rij) => ({
              naar: kantoorPad(rij.kantoor!),
              tekst: rij.kantoor!.naam,
              toelichting: `${aantalControles(rij.aantal_controles)} in ${boekjaar}`,
            })),
            { naar: "/bron", tekst: "Waar komt deze data vandaan?" },
          ]}
        />
      </>
    );
  } catch (fout) {
    inhoud = <Foutmelding fout={fout} />;
  }
  return inhoud;
}
