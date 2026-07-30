import Link from "next/link";
import {
  actieveKantoren,
  nieuwsteBoekjaar,
  sectoren,
  subsectoren,
  tel,
  wisselingen,
} from "@/lib/db";
import {
  aantalControles,
  aantalOpdrachten,
  aantalOrganisaties,
  kantoorPad,
  organisatiePad,
  sectorPad,
  subsectorPad,
} from "@/lib/paden";
import { Doorklik, Foutmelding, Inklapbaar, Leeg } from "@/components/onderdelen";

/**
 * Zoveel kantoren staan open; de staart zit achter een klik. Tien is genoeg om te
 * zien wie de markt maakt — de kantoren met één of twee controles zijn een
 * naslaglijst, geen voorpagina.
 */
const KANTOREN_OPEN = 10;

export default async function Startpagina() {
  let inhoud;
  try {
    const boekjaar = (await nieuwsteBoekjaar()) ?? new Date().getFullYear() - 1;
    const [
      organisatieTotaal,
      opdrachtTotaal,
      laatsteWisselingen,
      kantoren,
      sectorlijst,
      subsectorlijst,
    ] = await Promise.all([
      // Tellen in de database, niet de rijen ophalen en die tellen: dat laatste
      // gaf "200 organisaties" omdat de lijst op 200 was afgekapt.
      tel("organisaties"),
      tel("opdrachten"),
      wisselingen({ limiet: 8 }),
      actieveKantoren(boekjaar),
      sectoren().catch(() => []),
      subsectoren().catch(() => []),
    ]);

    // Eén keer opbouwen, twee keer gebruiken: de eerste tien open, de rest
    // ingeklapt. De kop is hetzelfde element in beide tabellen.
    const kantoorkop = (
      <thead>
        <tr>
          <th>Kantoor</th>
          <th className="getal">Controles</th>
        </tr>
      </thead>
    );
    const kantoorrijen = kantoren.map((rij) => (
      <tr key={rij.kantoor_id}>
        <td>
          <Link href={kantoorPad(rij.kantoor!)}>{rij.kantoor!.naam}</Link>
          {rij.kantoor!.oob_vergunning ? (
            <> <span className="label label-oob">OOB</span></>
          ) : null}
        </td>
        <td className="getal">{rij.aantal_controles}</td>
      </tr>
    ));

    inhoud = (
      <>
        <div className="paginakop">
          <h1>Wie controleert wie?</h1>
          <p className="metaregel" style={{ marginTop: "0.5rem" }}>
            <span>{aantalOrganisaties(organisatieTotaal)}</span>
            <span>{aantalOpdrachten(opdrachtTotaal)}</span>
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
              <>
                <table>
                  {kantoorkop}
                  <tbody>{kantoorrijen.slice(0, KANTOREN_OPEN)}</tbody>
                </table>
                {kantoorrijen.length > KANTOREN_OPEN ? (
                  <Inklapbaar
                    samenvatting={`Nog ${kantoorrijen.length - KANTOREN_OPEN} kantoren met minder controles`}
                  >
                    <table>
                      {kantoorkop}
                      <tbody>{kantoorrijen.slice(KANTOREN_OPEN)}</tbody>
                    </table>
                  </Inklapbaar>
                ) : null}
              </>
            )}
            <p className="klein" style={{ marginBottom: 0 }}>
              <Link href={sectorPad("zorg")}>Marktaandeel in de zorg →</Link>
            </p>
          </section>
        </div>

        {/* De alfabetische lijst van álle organisaties stond hier eerst helemaal
            uitgeschreven. Dat is een naslagwerk en geen voorpagina; hij heeft nu
            zijn eigen adres. Wat hier blijft staan is de ingang: kies een
            subsector, of ga naar de volledige lijst. */}
        <section className="kaart">
          <h2>Organisaties</h2>
          {subsectorlijst.length === 0 ? (
            <Leeg tekst="De subsectoren worden nog bijgewerkt." />
          ) : (
            <div className="tabel-omhulsel">
              <table>
                <thead>
                  <tr>
                    <th>Subsector</th>
                    <th className="getal">Organisaties</th>
                  </tr>
                </thead>
                <tbody>
                  {subsectorlijst.map((rij) => (
                    <tr key={rij.naam}>
                      <td>
                        <Link href={subsectorPad(rij.naam)}>{rij.naam}</Link>
                      </td>
                      <td className="getal">{rij.aantal}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          <p className="klein" style={{ marginBottom: 0 }}>
            <Link href="/organisaties">
              Alle {organisatieTotaal} organisaties op naam →
            </Link>
          </p>
        </section>

        <Doorklik
          titel="Beginnen met klikken"
          items={[
            { naar: "/wisselingen", tekst: "Alle accountantswisselingen" },
            {
              naar: "/organisaties",
              tekst: "Alle organisaties op naam",
              toelichting: `${organisatieTotaal} in de database`,
            },
            // Alle sectoren die er zijn, niet alleen de zorg: de goede doelen
            // hadden anders geen ingang vanaf de voorpagina.
            ...sectorlijst.map((s) => ({
              naar: sectorPad(s.naam),
              tekst: `Sector ${s.naam}: marktaandelen`,
              toelichting: `${s.aantal} organisaties`,
            })),
            ...kantoren.slice(0, 3).map((rij) => ({
              naar: kantoorPad(rij.kantoor!),
              tekst: rij.kantoor!.naam,
              toelichting: `${aantalControles(rij.aantal_controles)} in ${boekjaar}`,
            })),
          ]}
        />
      </>
    );
  } catch (fout) {
    inhoud = <Foutmelding fout={fout} />;
  }
  return inhoud;
}
