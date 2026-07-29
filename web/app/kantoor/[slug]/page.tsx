import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import {
  actieveKantoren,
  kantoorOpAfm,
  nieuwsteBoekjaar,
  opdrachtenVanKantoor,
  wisselingen,
} from "@/lib/db";
import { clientenVanKantoor } from "@/lib/analyse";
import {
  aantalControles,
  aantalJaren,
  jarenReeks,
  kantoorPad,
  nummerUitSlug,
  organisatiePad,
  sectorPad,
} from "@/lib/paden";
import { Doorklik, Foutmelding, Leeg, Oordeel } from "@/components/onderdelen";

type Params = { params: Promise<{ slug: string }> };

export async function generateMetadata({ params }: Params): Promise<Metadata> {
  const { slug } = await params;
  const kantoor = await kantoorOpAfm(nummerUitSlug(slug)).catch(() => null);
  if (!kantoor) return { title: "Kantoor niet gevonden" };
  return {
    title: `${kantoor.naam}: welke organisaties controleert dit kantoor?`,
    description:
      `Cliënten van ${kantoor.naam} per boekjaar, gewonnen en verloren opdrachten ` +
      `en marktaandeel — uit openbare bronnen.`,
  };
}

export default async function Kantoorpagina({ params }: Params) {
  const { slug } = await params;
  const afm = nummerUitSlug(slug);

  let kantoor;
  try {
    kantoor = await kantoorOpAfm(afm);
  } catch (fout) {
    return <Foutmelding fout={fout} />;
  }
  if (!kantoor) notFound();

  const [opdrachten, mutaties, boekjaar] = await Promise.all([
    opdrachtenVanKantoor(kantoor.id),
    wisselingen({ kantoorId: kantoor.id, limiet: 50 }),
    nieuwsteBoekjaar(),
  ]);

  const clienten = clientenVanKantoor(opdrachten);
  const gewonnen = mutaties.filter((m) => m.naar_kantoor_id === kantoor.id);
  const verloren = mutaties.filter((m) => m.van_kantoor_id === kantoor.id);
  const alleJaren = opdrachten.map((o) => o.boekjaar);
  const concurrenten = boekjaar
    ? (await actieveKantoren(boekjaar)).filter((r) => r.kantoor_id !== kantoor.id)
    : [];

  return (
    <>
      <div className="paginakop">
        <h1>{kantoor.naam}</h1>
        <p className="metaregel">
          <span>AFM-nummer {kantoor.afm_nummer ?? "onbekend"}</span>
          <span>
            {kantoor.oob_vergunning ? (
              <span className="label label-oob">OOB-vergunning</span>
            ) : (
              "reguliere Wta-vergunning"
            )}
          </span>
          {kantoor.website ? (
            <span>
              <a href={kantoor.website} rel="noreferrer nofollow" target="_blank">
                website
              </a>
            </span>
          ) : null}
        </p>
        <p className="samenvatting">
          <strong>{clienten.length}</strong> cliënten in de database
          <span className="zacht">
            {" "}
            — {opdrachten.length} opdrachten over {jarenReeks(alleJaren)}
            {gewonnen.length || verloren.length
              ? `, ${gewonnen.length} gewonnen en ${verloren.length} verloren`
              : ""}
          </span>
        </p>
      </div>

      <div className="kolommen">
        <section className="kaart">
          <h2>Gewonnen opdrachten</h2>
          {gewonnen.length === 0 ? (
            <Leeg tekst="Geen gewonnen opdrachten in deze periode." />
          ) : (
            <table>
              <tbody>
                {gewonnen.map((m) => (
                  <tr key={`w${m.organisatie_id}-${m.boekjaar_wissel}`}>
                    <td className="jaar">{m.boekjaar_wissel}</td>
                    <td>
                      {m.organisatie ? (
                        <Link href={organisatiePad(m.organisatie)}>
                          {m.organisatie.naam}
                        </Link>
                      ) : (
                        "onbekend"
                      )}
                      <div className="klein zacht">
                        overgenomen van{" "}
                        {m.van ? (
                          <Link href={kantoorPad(m.van)}>{m.van.naam}</Link>
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
        </section>

        <section className="kaart">
          <h2>Verloren opdrachten</h2>
          {verloren.length === 0 ? (
            <Leeg tekst="Geen verloren opdrachten in deze periode." />
          ) : (
            <table>
              <tbody>
                {verloren.map((m) => (
                  <tr key={`v${m.organisatie_id}-${m.boekjaar_wissel}`}>
                    <td className="jaar">{m.boekjaar_wissel}</td>
                    <td>
                      {m.organisatie ? (
                        <Link href={organisatiePad(m.organisatie)}>
                          {m.organisatie.naam}
                        </Link>
                      ) : (
                        "onbekend"
                      )}
                      <div className="klein zacht">
                        gegaan naar{" "}
                        {m.naar ? (
                          <Link href={kantoorPad(m.naar)}>{m.naar.naam}</Link>
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
        </section>
      </div>

      <section className="kaart">
        <h2>Cliënten</h2>
        {clienten.length === 0 ? (
          <Leeg tekst="Nog geen cliënten van dit kantoor in de database." />
        ) : (
          <div className="tabel-omhulsel">
            <table>
              <thead>
                <tr>
                  <th>Organisatie</th>
                  <th>Plaats</th>
                  <th>Boekjaren</th>
                  <th className="getal">Duur</th>
                  <th>Laatste oordeel</th>
                </tr>
              </thead>
              <tbody>
                {clienten.map((client) => (
                  <tr key={client.organisatieId}>
                    <td>
                      <Link
                        href={organisatiePad({
                          kvk_nummer: client.kvkNummer,
                          naam: client.naam,
                        })}
                      >
                        {client.naam}
                      </Link>
                    </td>
                    <td className="zacht">{client.gemeente ?? "—"}</td>
                    <td className="jaar">{jarenReeks(client.jaren)}</td>
                    <td className="getal zacht">{aantalJaren(client.jaren.length)}</td>
                    <td>
                      <Oordeel waarde={client.oordeelLaatste} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <Doorklik
        items={[
          ...clienten.slice(0, 3).map((client) => ({
            naar: organisatiePad({ kvk_nummer: client.kvkNummer, naam: client.naam }),
            tekst: client.naam,
            toelichting: `cliënt ${jarenReeks(client.jaren)}`,
          })),
          ...concurrenten.slice(0, 3).map((rij) => ({
            naar: kantoorPad(rij.kantoor!),
            tekst: rij.kantoor!.naam,
            toelichting: `concurrent, ${aantalControles(rij.aantal_controles)}`,
          })),
          { naar: sectorPad("zorg"), tekst: "Marktaandelen in de zorg" },
          { naar: "/wisselingen", tekst: "Alle accountantswisselingen" },
        ]}
      />
    </>
  );
}
