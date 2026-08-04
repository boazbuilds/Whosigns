import Link from "next/link";
import {
  kantoorRanglijst,
  nieuwsteBoekjaar,
  oudsteBoekjaar,
  sectoren,
  tel,
  wisselingen,
} from "@/lib/db";
import { saldoPerKantoor } from "@/lib/analyse";
import {
  aantalControles,
  aantalOpdrachten,
  aantalOrganisaties,
  hoofdletter,
  kantoorPad,
  nl,
  organisatiePad,
  SECTOR_UITLEG,
  sectorPad,
} from "@/lib/paden";
import {
  Aandeelbalk,
  Doorklik,
  Foutmelding,
  KantoorLink,
  Kerncijfer,
  KortKantoorLink,
  Leeg,
  Podiumplek,
  Rang,
  Tegel,
} from "@/components/onderdelen";

/**
 * Zoveel kantoren staan in de ranglijst op de voorpagina. Tien is genoeg om te
 * zien wie de markt maakt; de rest staat op /kantoren.
 */
const KANTOREN_OP_VOORPAGINA = 10;

export default async function Startpagina() {
  let inhoud;
  try {
    const boekjaar = (await nieuwsteBoekjaar()) ?? new Date().getFullYear() - 1;
    const [
      organisatieTotaal,
      opdrachtTotaal,
      laatsteWisselingen,
      ranglijst,
      ranglijstAlles,
      sectorlijst,
      vroegste,
    ] = await Promise.all([
      // Tellen in de database, niet de rijen ophalen en die tellen: dat laatste
      // gaf "200 organisaties" omdat de lijst op 200 was afgekapt.
      tel("organisaties"),
      tel("opdrachten"),
      wisselingen({ limiet: 10 }),
      kantoorRanglijst(boekjaar),
      kantoorRanglijst(),
      // Geen .catch(() => []) meer: een databasestoring werd zo "De sectoren
      // worden nog bijgewerkt" — een storing verkleed als normale toestand. De
      // try om dit hele blok toont dan gewoon de foutmelding.
      sectoren(),
      oudsteBoekjaar(),
    ]);

    const totaalDitJaar = ranglijst.reduce((som, rij) => som + rij.aantal_controles, 0);
    const saldi = saldoPerKantoor(laatsteWisselingen);
    const topWapens = new Map<string, string[]>();
    for (const sector of sectorlijst) {
      topWapens.set(
        sector.naam,
        ranglijstAlles
          .map((rij) => ({
            naam: rij.kantoor.naam,
            aantal: rij.perSector.find(([s]) => s === sector.naam)?.[1] ?? 0,
          }))
          .filter((rij) => rij.aantal > 0)
          .sort((a, b) => b.aantal - a.aantal)
          .slice(0, 5)
          .map((rij) => rij.naam),
      );
    }

    inhoud = (
      <>
        <div className="paginakop">
          <h1>Wie controleert wie?</h1>
          <p className="klein zacht" style={{ marginTop: "0.4rem", maxWidth: "44rem" }}>
            De accountantsmarkt van Nederland als doorklikbaar naslagwerk: welk
            kantoor tekent bij welke organisatie, in welk boekjaar, en wanneer er
            werd gewisseld. Alles uit openbare bronnen, met de vindplaats erbij.
          </p>
          <div className="kerncijfers">
            <Kerncijfer
              waarde={nl(organisatieTotaal)}
              naam="organisaties"
              naar="/organisaties"
            />
            <Kerncijfer waarde={nl(opdrachtTotaal)} naam="opdrachten" />
            <Kerncijfer
              waarde={nl(ranglijstAlles.length)}
              naam="kantoren"
              naar="/kantoren"
            />
            <Kerncijfer
              waarde={sectorlijst.length}
              naam="sectoren"
              naar="/sectoren"
            />
            <Kerncijfer
              waarde={vroegste ? `${vroegste}–${boekjaar}` : `t/m ${boekjaar}`}
              naam="boekjaren"
            />
          </div>
        </div>

        {ranglijst.length >= 3 ? (
          <section className="kaart">
            <div className="kaartkop">
              <h2>De grootste kantoren in boekjaar {boekjaar}</h2>
              <Link href="/kantoren">Hele ranglijst →</Link>
            </div>
            <div className="podium">
              {ranglijst.slice(0, 3).map((rij, i) => (
                <Podiumplek
                  key={rij.kantoor.id}
                  plek={i + 1}
                  naar={kantoorPad(rij.kantoor)}
                  naam={rij.kantoor.naam}
                  onder={`${((rij.aantal_controles / totaalDitJaar) * 100).toFixed(1)}% van de markt`}
                  groot={String(rij.aantal_controles)}
                />
              ))}
            </div>
          </section>
        ) : null}

        <div className="kolommen-breed-smal">
          <section className="kaart">
            <div className="kaartkop">
              <h2>Ranglijst {boekjaar}</h2>
              <Link href={`/kantoren?jaar=${boekjaar}`}>Alle kantoren →</Link>
            </div>
            {ranglijst.length === 0 ? (
              <Leeg tekst="Nog geen opdrachten in dit boekjaar." />
            ) : (
              <div className="tabel-omhulsel">
                <table>
                  <thead>
                    <tr>
                      <th>#</th>
                      <th>Kantoor</th>
                      <th className="getal">Controles</th>
                      <th>Aandeel</th>
                    </tr>
                  </thead>
                  <tbody>
                    {ranglijst.slice(0, KANTOREN_OP_VOORPAGINA).map((rij, i) => (
                      <tr key={rij.kantoor.id}>
                        <td className="rangcel">
                          <Rang nummer={i + 1} />
                        </td>
                        <td>
                          <KantoorLink
                            naam={rij.kantoor.naam}
                            naar={kantoorPad(rij.kantoor)}
                            maat="m"
                          />
                        </td>
                        <td className="getal">
                          <strong>{rij.aantal_controles}</strong>
                        </td>
                        <td className="balkcel">
                          <Aandeelbalk
                            deel={rij.aantal_controles}
                            geheel={totaalDitJaar}
                          />
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>

          <section className="kaart">
            <div className="kaartkop">
              <h2>Laatste transfers</h2>
              <Link href="/wisselingen">Alle →</Link>
            </div>
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
                          <KortKantoorLink kantoor={w.van} /> →{" "}
                          <KortKantoorLink kantoor={w.naar} />
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
            {saldi.length > 0 ? (
              <p className="klein zacht" style={{ marginBottom: 0 }}>
                Beste saldo in deze reeks:{" "}
                <strong>{saldi[0].naam}</strong> ({saldi[0].saldo > 0 ? "+" : ""}
                {saldi[0].saldo}).
              </p>
            ) : null}
          </section>
        </div>

        <section className="kaart">
          <div className="kaartkop">
            <h2>Kies een sector</h2>
            <Link href="/sectoren">Alle sectoren →</Link>
          </div>
          {sectorlijst.length === 0 ? (
            <Leeg tekst="De sectoren worden nog bijgewerkt." />
          ) : (
            <div className="tegels">
              {sectorlijst.map((sector) => (
                <Tegel
                  key={sector.naam}
                  naar={sectorPad(sector.naam)}
                  naam={hoofdletter(sector.naam)}
                  meta={
                    SECTOR_UITLEG[sector.naam] ?? aantalOrganisaties(sector.aantal)
                  }
                  wapens={topWapens.get(sector.naam) ?? []}
                />
              ))}
            </div>
          )}
        </section>

        <Doorklik
          titel="Beginnen met klikken"
          items={[
            {
              naar: "/kantoren",
              tekst: "Ranglijst van alle kantoren",
              toelichting: `${ranglijstAlles.length} met controles`,
            },
            { naar: "/wisselingen", tekst: "Alle accountantswisselingen" },
            {
              naar: "/bevindingen",
              tekst: "Waar was het oordeel niet goedkeurend?",
            },
            {
              naar: "/organisaties",
              tekst: "Alle organisaties op naam",
              toelichting: aantalOrganisaties(organisatieTotaal),
            },
            ...sectorlijst.map((s) => ({
              naar: sectorPad(s.naam),
              tekst: `Sector ${s.naam}: marktaandelen`,
              toelichting: aantalOrganisaties(s.aantal),
            })),
            ...ranglijst.slice(0, 3).map((rij) => ({
              naar: kantoorPad(rij.kantoor),
              tekst: rij.kantoor.naam,
              toelichting: `${aantalControles(rij.aantal_controles)} in ${boekjaar}`,
            })),
            {
              naar: "/sectoren",
              tekst: "Sectoren vergelijken",
              toelichting: aantalOpdrachten(opdrachtTotaal),
            },
          ]}
        />
      </>
    );
  } catch (fout) {
    inhoud = <Foutmelding fout={fout} />;
  }
  return inhoud;
}
