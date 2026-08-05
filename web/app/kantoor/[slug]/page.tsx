import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import {
  gunningenVanKantoor,
  kantoorOpAfm,
  kantoorOpId,
  kantoorRanglijst,
  nieuwsteBoekjaar,
  opdrachtenVanKantoor,
  wisselingen,
  type Kantoor,
  type WisselingVolledig,
} from "@/lib/db";
import { clientenVanKantoor } from "@/lib/analyse";
import {
  OPDRACHT_LABEL,
  aantalControles,
  aantalJaren,
  aantalOpdrachten,
  datumNL,
  hoofdletter,
  jarenReeks,
  kantoorPad,
  nl,
  organisatiePad,
  sectorPad,
  sleutelUitSlug,
} from "@/lib/paden";
import { Aandeelbalk, Doorklik, Foutmelding, Inklapbaar, KantoorLink, Kerncijfer, KortKantoorLink, Kruimels, Leeg, Oordeel, Soort, Wapen } from "@/components/onderdelen";

type Params = { params: Promise<{ slug: string }> };

/**
 * Zoveel cliënten staan open; de staart zit achter een klik. Een groot kantoor
 * heeft er honderden, en die stonden allemaal uitgeschreven onder de pagina.
 * De lijst is op laatste boekjaar gesorteerd, dus wat openstaat is het meest
 * actuele deel.
 */
const CLIENTEN_OPEN = 25;

/**
 * Zoveel mutaties staan open per kolom. Zonder grens werd de pagina van PwC
 * 19.000 pixels lang: 57 gewonnen en 115 verloren opdrachten, allemaal
 * uitgeschreven, met de cliëntenlijst dáár nog onder.
 */
const MUTATIES_OPEN = 12;

/**
 * Kolom met gewonnen of verloren opdrachten: de nieuwste open, de rest achter
 * één klik. Eén onderdeel voor beide richtingen, want ze verschillen alleen in
 * de kop en in welk kantoor er aan de andere kant stond.
 */
function Mutatiekaart({
  titel,
  leegtekst,
  richting,
  mutaties,
}: {
  titel: string;
  leegtekst: string;
  richting: string;
  mutaties: WisselingVolledig[];
}) {
  const regel = (m: WisselingVolledig, sleutel: string) => (
    <tr key={sleutel}>
      <td className="jaar">{m.boekjaar_wissel}</td>
      <td>
        {m.organisatie ? (
          <Link href={organisatiePad(m.organisatie)}>{m.organisatie.naam}</Link>
        ) : (
          "onbekend"
        )}
        <div className="klein zacht">
          {richting} <KortKantoorLink kantoor={richting === "gegaan naar" ? m.naar : m.van} />
        </div>
      </td>
    </tr>
  );

  return (
    <section className="kaart">
      <div className="kaartkop">
        <h2>{titel}</h2>
        {mutaties.length > 0 ? (
          <span className="klein zacht">{mutaties.length}</span>
        ) : null}
      </div>
      {mutaties.length === 0 ? (
        <Leeg tekst={leegtekst} />
      ) : (
        <>
          <table>
            <tbody>
              {mutaties
                .slice(0, MUTATIES_OPEN)
                .map((m) => regel(m, `${m.organisatie_id}-${m.boekjaar_wissel}`))}
            </tbody>
          </table>
          {mutaties.length > MUTATIES_OPEN ? (
            <Inklapbaar
              samenvatting={`Nog ${mutaties.length - MUTATIES_OPEN} uit eerdere boekjaren`}
            >
              <table>
                <tbody>
                  {mutaties
                    .slice(MUTATIES_OPEN)
                    .map((m) => regel(m, `r${m.organisatie_id}-${m.boekjaar_wissel}`))}
                </tbody>
              </table>
            </Inklapbaar>
          ) : null}
        </>
      )}
    </section>
  );
}

/** Kantoor bij een slug: op AFM-nummer, of op id wanneer het `k<id>` draagt. */
async function vindKantoor(slug: string): Promise<Kantoor | null> {
  const { nummer, id } = sleutelUitSlug(slug);
  if (id !== null) return kantoorOpId(id);
  return nummer ? kantoorOpAfm(nummer) : null;
}

export async function generateMetadata({ params }: Params): Promise<Metadata> {
  const { slug } = await params;
  const kantoor = await vindKantoor(slug).catch(() => null);
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

  let kantoor;
  try {
    kantoor = await vindKantoor(slug);
  } catch (fout) {
    return <Foutmelding fout={fout} />;
  }
  if (!kantoor) notFound();

  const [opdrachten, mutaties, boekjaar, ranglijst, aanbestedingen] = await Promise.all([
    opdrachtenVanKantoor(kantoor.id),
    // Zonder limiet: hieruit komen "gewonnen" en "verloren" in de kop. Met een
    // grens van 50 stond er bij Verstegen "34 gewonnen en 16 verloren" — samen
    // precies 50, dus het was de grens die dat getal bepaalde en niet de data.
    wisselingen({ kantoorId: kantoor.id }),
    nieuwsteBoekjaar(),
    kantoorRanglijst().catch(() => []),
    gunningenVanKantoor(kantoor.id),
  ]);

  const clienten = clientenVanKantoor(opdrachten);

  // Tellen per soort opdracht, aflopend. Alleen tonen als er meer dan één
  // soort is — bij een kantoor dat uitsluitend wettelijke controles doet
  // voegt de regel niets toe.
  const perSoort = new Map<string, number>();
  for (const opdracht of opdrachten) {
    perSoort.set(opdracht.type_opdracht, (perSoort.get(opdracht.type_opdracht) ?? 0) + 1);
  }
  const soorten = [...perSoort.entries()].sort((a, b) => b[1] - a[1]);
  const gewonnen = mutaties.filter((m) => m.naar_kantoor_id === kantoor.id);
  const verloren = mutaties.filter((m) => m.van_kantoor_id === kantoor.id);
  const alleJaren = opdrachten.map((o) => o.boekjaar);

  // Plaats in de eeuwige ranglijst, en wie er direct om dit kantoor heen staan.
  const positie = ranglijst.findIndex((r) => r.kantoor.id === kantoor.id);
  const eigenRij = positie >= 0 ? ranglijst[positie] : null;
  const buren =
    positie >= 0
      ? ranglijst.slice(Math.max(0, positie - 1), positie + 3).filter((r) => r.kantoor.id !== kantoor.id)
      : ranglijst.slice(0, 3);
  const marktTotaal = ranglijst.reduce((som, rij) => som + rij.aantal_controles, 0);

  // In welke sectoren dit kantoor werkt, grootste eerst. Uit de eigen cliënten
  // en niet uit de ranglijst: zo klopt het ook als de view nog niet is bijgewerkt.
  const perSector = new Map<string, number>();
  for (const client of clienten) {
    if (client.sector) perSector.set(client.sector, (perSector.get(client.sector) ?? 0) + 1);
  }
  const sectorrijen = [...perSector.entries()].sort((a, b) => b[1] - a[1]);
  const eigenSectoren = sectorrijen.map(([sector]) => sector);

  const clientkop = (
    <thead>
      <tr>
        <th>Organisatie</th>
        <th>Plaats</th>
        <th>Opdracht</th>
        <th>Boekjaren</th>
        <th className="getal">Duur</th>
        <th>Laatste oordeel</th>
      </tr>
    </thead>
  );
  const clientrijen = clienten.map((client) => (
    <tr key={client.organisatieId}>
      <td>
        <Link
          href={organisatiePad({
            kvk_nummer: client.kvkNummer,
            naam: client.naam,
            id: client.organisatieId,
          })}
        >
          {client.naam}
        </Link>
      </td>
      <td className="zacht klein">{client.gemeente ?? "—"}</td>
      <td className="zacht klein">
        <Soort type={client.typeLaatste} />
      </td>
      <td className="jaar">{jarenReeks(client.jaren)}</td>
      <td className="getal zacht">{aantalJaren(client.jaren.length)}</td>
      <td>
        <Oordeel waarde={client.oordeelLaatste} />
      </td>
    </tr>
  ));

  return (
    <>
      <Kruimels
        paden={[
          { naar: "/", tekst: "Start" },
          { naar: "/kantoren", tekst: "Kantoren" },
          { tekst: kantoor.naam },
        ]}
      />

      <div className="paginakop">
        <div className="paginakop-met-wapen">
          <Wapen naam={kantoor.naam} maat="xl" />
          <div>
            <h1>{kantoor.naam}</h1>
            <p className="metaregel">
              {positie >= 0 ? (
                <span>
                  <strong>#{positie + 1}</strong> in de ranglijst
                </span>
              ) : null}
              <span>
                {kantoor.oob_vergunning ? (
                  <span className="label label-oob">OOB-vergunning</span>
                ) : kantoor.afm_nummer ? (
                  "reguliere Wta-vergunning"
                ) : (
                  "geen Wta-vergunning"
                )}
              </span>
              {kantoor.plaats ? <span>{kantoor.plaats}</span> : null}
              <span>{jarenReeks(alleJaren)}</span>
            </p>
          </div>
        </div>

        <div className="kerncijfers">
          <Kerncijfer waarde={clienten.length} naam="cliënten" />
          <Kerncijfer waarde={opdrachten.length} naam="opdrachten" />
          <Kerncijfer waarde={gewonnen.length} naam="gewonnen" />
          <Kerncijfer waarde={verloren.length} naam="verloren" />
          <Kerncijfer
            waarde={gewonnen.length - verloren.length > 0 ? `+${gewonnen.length - verloren.length}` : gewonnen.length - verloren.length}
            naam="saldo"
          />
        </div>

        {/* Waaruit die opdrachten bestaan. Zonder deze regel zegt "1.242
            opdrachten" niets over wát er gecontroleerd is: negen van de tien
            zijn jaarrekeningcontroles, maar een verklaring bij een WNT-opgave
            of een productieverantwoording telde er net zo hard in mee. */}
        {soorten.length > 1 ? (
          <p className="soortverdeling">
            {soorten.map(([type, aantal]) => (
              <span key={type}>
                <span className="telling">{nl(aantal)}</span>{" "}
                <Soort type={type} />
              </span>
            ))}
          </p>
        ) : null}
      </div>

      <div className="kolommen-breed-smal">
        <section className="kaart">
          <h2>Waar dit kantoor werkt</h2>
          {sectorrijen.length === 0 ? (
            <Leeg tekst="Nog geen cliënten in de database." />
          ) : (
            <table>
              <thead>
                <tr>
                  <th>Sector</th>
                  <th className="getal">Cliënten</th>
                  <th>Aandeel in eigen portefeuille</th>
                </tr>
              </thead>
              <tbody>
                {sectorrijen.map(([sector, aantal]) => (
                  <tr key={sector}>
                    <td>
                      <Link href={sectorPad(sector)}>{hoofdletter(sector)}</Link>
                    </td>
                    <td className="getal">{aantal}</td>
                    <td className="balkcel">
                      <Aandeelbalk deel={aantal} geheel={clienten.length} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
          {eigenRij && marktTotaal > 0 ? (
            <p className="klein zacht" style={{ marginBottom: 0 }}>
              Samen {aantalControles(eigenRij.aantal_controles)} over alle boekjaren
              — {((eigenRij.aantal_controles / marktTotaal) * 100).toFixed(1)}% van
              alles wat in deze database staat.
            </p>
          ) : null}
        </section>

        <section className="kaart">
          <h2>Over dit kantoor</h2>
          <dl className="feiten">
            <div>
              <dt>AFM-nummer</dt>
              <dd>{kantoor.afm_nummer ?? "geen (geen Wta-vergunning)"}</dd>
            </div>
            <div>
              <dt>Rechtsvorm</dt>
              <dd>{kantoor.rechtsvorm ?? "—"}</dd>
            </div>
            <div>
              <dt>Vestigingsplaats</dt>
              <dd>{kantoor.plaats ?? "—"}</dd>
            </div>
            <div>
              <dt>Vergunning sinds</dt>
              <dd>{datumNL(kantoor.vergunning_sinds)}</dd>
            </div>
            <div>
              <dt>OOB-vergunning</dt>
              <dd>{kantoor.oob_vergunning ? "ja" : "nee"}</dd>
            </div>
            <div>
              <dt>Website</dt>
              <dd>
                {kantoor.website ? (
                  <a href={kantoor.website} rel="noreferrer nofollow" target="_blank">
                    {kantoor.website.replace(/^https?:\/\//, "").replace(/\/$/, "")}
                  </a>
                ) : (
                  "—"
                )}
              </dd>
            </div>
          </dl>
          <p className="klein zacht" style={{ marginBottom: 0, marginTop: "0.85rem" }}>
            Gegevens uit het AFM-vergunningenregister. &ldquo;Vergunning sinds&rdquo;
            is de datum waarop de AFM de vergunning verleende, niet de
            oprichtingsdatum van het kantoor.
          </p>
        </section>
      </div>

      <div className="kolommen">
        <Mutatiekaart
          titel="Gewonnen opdrachten"
          leegtekst="Geen gewonnen opdrachten in deze periode."
          richting="overgenomen van"
          mutaties={gewonnen}
        />
        <Mutatiekaart
          titel="Verloren opdrachten"
          leegtekst="Geen verloren opdrachten in deze periode."
          richting="gegaan naar"
          mutaties={verloren}
        />
      </div>

      <section className="kaart">
        <div className="kaartkop">
          <h2>Cliënten</h2>
          {boekjaar ? (
            <Link href={`/kantoren?jaar=${boekjaar}`}>Ranglijst {boekjaar} →</Link>
          ) : null}
        </div>
        {clienten.length === 0 ? (
          <Leeg tekst="Nog geen cliënten van dit kantoor in de database." />
        ) : (
          <>
            <div className="tabel-omhulsel">
              <table>
                {clientkop}
                <tbody>{clientrijen.slice(0, CLIENTEN_OPEN)}</tbody>
              </table>
            </div>
            {clientrijen.length > CLIENTEN_OPEN ? (
              <Inklapbaar
                samenvatting={`Nog ${clientrijen.length - CLIENTEN_OPEN} cliënten uit eerdere boekjaren`}
              >
                <div className="tabel-omhulsel">
                  <table>
                    {clientkop}
                    <tbody>{clientrijen.slice(CLIENTEN_OPEN)}</tbody>
                  </table>
                </div>
              </Inklapbaar>
            ) : null}
          </>
        )}
      </section>

      {buren.length > 0 ? (
        <section className="kaart">
          <h2>Om dit kantoor heen in de ranglijst</h2>
          <table>
            <tbody>
              {buren.map((rij) => (
                <tr key={rij.kantoor.id}>
                  <td>
                    <KantoorLink
                      naam={rij.kantoor.naam}
                      naar={kantoorPad(rij.kantoor)}
                      maat="m"
                    />
                  </td>
                  <td className="zacht klein">
                    {rij.kantoor.plaats ?? <span className="zacht">—</span>}
                  </td>
                  <td className="getal">{rij.aantal_controles}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      ) : null}

      {aanbestedingen.length > 0 ? (
        <section className="kaart">
          <div className="kaartkop">
            <h2>Gewonnen aanbestedingen</h2>
            <span className="klein zacht">{aanbestedingen.length} · bron: TED</span>
          </div>
          <p className="klein zacht" style={{ marginTop: 0 }}>
            Europees aanbestede opdrachten die dit kantoor won. Een gunning zegt
            wie er benoemd is en wanneer — niet of de controle er kwam.
          </p>
          <div className="tabel-omhulsel">
            <table>
              <thead>
                <tr>
                  <th>Gegund</th>
                  <th>Opdrachtgever</th>
                  <th>Bericht</th>
                </tr>
              </thead>
              <tbody>
                {aanbestedingen.map((gunning) => (
                  <tr key={gunning.publicatienummer + (gunning.organisaties?.id ?? "")}>
                    <td className="jaar">{datumNL(gunning.gunningsdatum)}</td>
                    <td>
                      {gunning.organisaties ? (
                        <Link href={organisatiePad(gunning.organisaties)}>
                          {gunning.organisaties.naam}
                        </Link>
                      ) : (
                        <span className="zacht">onbekend</span>
                      )}
                    </td>
                    <td className="klein">
                      <a
                        href={`https://ted.europa.eu/nl/notice/-/detail/${gunning.publicatienummer}`}
                        rel="noreferrer nofollow"
                        target="_blank"
                      >
                        {gunning.publicatienummer}
                      </a>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      ) : null}

      <Doorklik
        items={[
          ...clienten.slice(0, 3).map((client) => ({
            naar: organisatiePad({
              kvk_nummer: client.kvkNummer,
              naam: client.naam,
              id: client.organisatieId,
            }),
            tekst: client.naam,
            toelichting: `cliënt ${jarenReeks(client.jaren)}`,
          })),
          ...buren.slice(0, 3).map((rij) => ({
            naar: kantoorPad(rij.kantoor),
            tekst: rij.kantoor.naam,
            toelichting: `concurrent, ${aantalControles(rij.aantal_controles)}`,
          })),
          // De sectoren waarin dít kantoor werkt, uit zijn eigen cliënten. Hier
          // stond "Marktaandelen in de zorg" vast, ook voor een kantoor dat
          // hoofdzakelijk goede doelen controleert.
          ...eigenSectoren.map((sector) => ({
            naar: sectorPad(sector),
            tekst: `Marktaandelen in de sector ${sector}`,
          })),
          { naar: "/kantoren", tekst: "Ranglijst van alle kantoren" },
          { naar: "/wisselingen", tekst: "Alle accountantswisselingen" },
          {
            naar: "/organisaties",
            tekst: "Alle organisaties op naam",
            toelichting: aantalOpdrachten(opdrachten.length) + " bij dit kantoor",
          },
        ]}
      />
    </>
  );
}
