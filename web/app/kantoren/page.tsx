import type { Metadata } from "next";
import Link from "next/link";
import {
  alleKantoren,
  kantoorRanglijst,
  marktaandeelRijen,
  wisselingen,
} from "@/lib/db";
import { saldoPerKantoor } from "@/lib/analyse";
import {
  controlesPerJaar,
  LEIDER_COMPLEET,
  nieuwsteCompleteBoekjaar,
} from "@/lib/voorpagina";
import {
  aantalControles,
  aantalKantoren,
  hoofdletter,
  kantoorPad,
  nl,
  procent,
  sectorPad,
} from "@/lib/paden";
import {
  Doorklik,
  Foutmelding,
  Inklapbaar,
  Kerncijfer,
  Kruimels,
  KantoorLink,
  Leeg,
  Telbalk,
  Vergunning,
} from "@/components/onderdelen";

export const metadata: Metadata = {
  title: "Accountantskantoren",
  description:
    "Hoeveel organisaties elk accountantskantoor in Nederland controleert, per " +
    "boekjaar — met gewonnen en verloren opdrachten. Het marktaandeel per sector " +
    "staat op de sectorpagina's.",
};

/** Zoveel jaren in de keuzebalk; ouder blijft bereikbaar via de sectorpagina's. */
const JAREN_IN_BALK = 8;
/** Zoveel kantoren staan open; de staart zit in dezelfde tabel eronder. */
const OPEN = 30;

type Zoek = { searchParams: Promise<{ jaar?: string }> };

export default async function Kantorenpagina({ searchParams }: Zoek) {
  const { jaar } = await searchParams;

  // De kale rijen van v_marktaandeel: daaruit komen de jaren voor de kiezer,
  // het aantal controles per jaar (voor de compleetheidsregel) en welke
  // kantoren er überhaupt een controle hebben.
  let marktRijen;
  try {
    marktRijen = await marktaandeelRijen();
  } catch (fout) {
    return <Foutmelding fout={fout} />;
  }
  const perJaar = controlesPerJaar(marktRijen);
  const jaren = [...perJaar.keys()].sort((a, b) => b - a);

  // Standaard het nieuwste boekjaar dat al compleet is, met dezelfde regel als
  // de sectorleiders op de voorpagina. Hier stond jaren[0]: boekjaar 2025, met
  // op 5-10-2026 1.321 controles tegen 2.307 voor 2024 — 110 OOB-controles
  // tegen 576 en nog geen enkele woningcorporatie. Die ranglijst liet vooral
  // zien welke sectoren al binnen waren. Nieuwere jaren blijven kiesbaar, met
  // een sterretje.
  const compleetJaar = nieuwsteCompleteBoekjaar(perJaar);
  const onvolledig = new Set(jaren.filter((j) => compleetJaar !== null && j > compleetJaar));

  // "alles" telt alle boekjaren op; een geldig jaartal kiest één jaar. Een
  // onzinnige waarde in de URL valt terug op het standaardjaar in plaats van
  // een lege pagina te geven.
  const standaard = compleetJaar ?? jaren[0] ?? null;
  const gekozen =
    jaar === "alles" ? null : jaren.includes(Number(jaar)) ? Number(jaar) : standaard;

  const [ranglijst, mutaties, kantoren] = await Promise.all([
    kantoorRanglijst(gekozen ?? undefined),
    wisselingen(gekozen ? { boekjaar: gekozen } : {}),
    alleKantoren(),
  ]);

  // Alleen aantallen, geen aandeel. De ranglijst telt alle sectoren op, en
  // welke sectoren er voor een boekjaar in de database staan verschilt sterk
  // per jaar (2007: alleen woningcorporaties; 2024: vijf grote sectoren); bij
  // "alle boekjaren" telt hij die jaren ook nog bij elkaar op. Een percentage
  // daarover zegt vooral iets over de dekking. Tot 5-10-2026 stond hier "18,2%
  // van 25.211 controles" onder Deloitte (alle jaren); per sector en boekjaar
  // staat het aandeel op de sectorpagina's.
  const totaalControles = ranglijst.reduce((som, rij) => som + rij.aantal_controles, 0);
  const grootste = ranglijst[0]?.aantal_controles ?? 0;
  const saldi = saldoPerKantoor(mutaties);
  const stijgers = saldi.filter((rij) => rij.saldo > 0).slice(0, 6);
  const dalers = [...saldi].reverse().filter((rij) => rij.saldo < 0).slice(0, 6);
  const periode = gekozen ? `boekjaar ${gekozen}` : "alle boekjaren";

  // Kantoren zonder één wettelijke of vrijwillige controle in de database: op
  // 5-10-2026 117 van de 288 actieve, waarvan 78 zonder enige opdracht. Ze
  // stonden in geen enkele lijst en waren alleen via de zoekbalk te vinden.
  // Bewust zonder aantallen: wat ze wél hebben is vooral marktonderzoek of een
  // WNT- of productieverantwoording, en dat hoort niet naast een lijst van
  // jaarrekeningcontroles.
  //
  // Alleen actieve kantoren. Een kantoor dat uit het register verdween en hier
  // geen controle heeft, is nergens meer een kantoor om te vinden: zo stond de
  // AFM zelf ("Geen accountantsorganisatie", migratie 20261005120000) hier
  // tussen de accountantskantoren, en VBWA, zonder opvolger. Wie wél een
  // controle heeft staat in de lijst hierboven, met "vervallen" erachter.
  const metControles = new Set(marktRijen.map((rij) => rij.kantoor_id));
  const overige = kantoren.filter((k) => k.actief && !metControles.has(k.id));
  const toonPlaatsOverig = overige.some((k) => k.plaats);

  // De vestigingsplaats bestaat pas na migratie 20260804140000. Zolang die niet
  // is gedraaid is de hele kolom leeg, en een kolom vol streepjes is erger dan
  // geen kolom: hem dan gewoon weglaten.
  const toonPlaats = ranglijst.some((rij) => rij.kantoor.plaats);

  const rijen = ranglijst.map((rij) => (
    <tr key={rij.kantoor.id}>
      <td>
        <KantoorLink naam={rij.kantoor.naam} naar={kantoorPad(rij.kantoor)} maat="m" />
      </td>
      {toonPlaats ? <td className="zacht klein">{rij.kantoor.plaats ?? "—"}</td> : null}
      <td className="klein">
        <Vergunning kantoor={rij.kantoor} className="zacht" />
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
        <Telbalk aantal={rij.aantal_controles} grootste={grootste} />
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
            naar={gekozen ? `/wisselingen?jaar=${gekozen}` : "/wisselingen"}
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
          aria-current={gekozen === null ? "page" : undefined}
        >
          Alle jaren
        </Link>
        {jaren.slice(0, JAREN_IN_BALK).map((j) => (
          <Link
            key={j}
            href={`/kantoren?jaar=${j}`}
            className={gekozen === j ? "actief" : undefined}
            aria-current={gekozen === j ? "page" : undefined}
            title={onvolledig.has(j) ? "Nog niet compleet" : undefined}
          >
            {j}
            {onvolledig.has(j) ? "*" : ""}
          </Link>
        ))}
      </nav>
      {gekozen !== null && onvolledig.has(gekozen) && compleetJaar !== null ? (
        <p className="klein zacht" style={{ marginTop: "-0.4rem", maxWidth: "44rem" }}>
          * Boekjaar {gekozen} is nog niet compleet: er staan{" "}
          {nl(perJaar.get(gekozen) ?? 0)} controles in, tegen{" "}
          {nl(perJaar.get(gekozen - 1) ?? 0)} voor {gekozen - 1}. Welke sectoren
          al binnen zijn bepaalt deze volgorde dus mee.
        </p>
      ) : onvolledig.size ? (
        <p className="klein zacht" style={{ marginTop: "-0.4rem", maxWidth: "44rem" }}>
          * Nog niet compleet: minder dan {procent(100 * LEIDER_COMPLEET, 0)} van
          het aantal controles van het jaar ervoor.
        </p>
      ) : null}

      {/* Geen podium en geen rangnummer: deze lijst telt alle sectoren op, en
          bij "alle jaren" ook alle boekjaren. Een plek geldt op deze site
          alleen binnen één sector en één boekjaar (de sectorpagina's, en "#2 in
          de sector OOB" op een kantoorpagina). Tot 5-10-2026 stond hier "De top
          drie in alle boekjaren" met Deloitte op 1, met 4.598 controles uit
          2007–2025 — een plek die vooral zegt welke sectoren het langst in de
          database staan. Op aantal gesorteerd blijft de lijst wel. */}
      <section className="kaart">
        <div className="kaartkop">
          <h2>Kantoren met controles — {periode}</h2>
          <Link href="/wisselingen">Alle wisselingen →</Link>
        </div>
        <p className="klein zacht" style={{ marginTop: 0, maxWidth: "44rem" }}>
          Aantallen controles over alle sectoren samen, zoals ze voor {periode} in
          de database staan, van veel naar weinig. Een aandeel of een plek noemt
          deze site alleen binnen één sector en één boekjaar, want welke sectoren
          erin zitten verschilt per boekjaar —{" "}
          <Link href="/sectoren">zie de sectoren</Link>.
        </p>
        {ranglijst.length === 0 ? (
          <Leeg tekst="Voor dit boekjaar staan er nog geen controles in de database." />
        ) : (
          <div className="tabel-omhulsel">
            <table>
              <thead>
                <tr>
                  <th>Kantoor</th>
                  {toonPlaats ? <th>Plaats</th> : null}
                  <th>Vergunning</th>
                  <th>Sectoren</th>
                  <th className="getal">Controles</th>
                  <th>
                    <span className="verborgen">Controles als balk</span>
                  </th>
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
                        naar={kantoorPad({
                          id: rij.kantoorId,
                          afm_nummer: rij.afmNummer,
                          naam: rij.naam,
                        })}
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
                        naar={kantoorPad({
                          id: rij.kantoorId,
                          afm_nummer: rij.afmNummer,
                          naam: rij.naam,
                        })}
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

      {overige.length > 0 ? (
        <section className="kaart">
          <div className="kaartkop">
            <h2>Overige kantoren</h2>
            <span className="klein zacht">{nl(overige.length)}</span>
          </div>
          <p className="klein zacht" style={{ marginTop: 0, maxWidth: "44rem" }}>
            Kantoren zonder wettelijke of vrijwillige jaarrekeningcontrole in de
            database, alfabetisch. Wat er wél van ze bekend is — een WNT- of
            productieverantwoording, of een controle waarvan het voorwerp
            onbekend is — staat op hun eigen pagina. Niet elk kantoor hier staat
            in het AFM-register: bij &ldquo;geen Wta-vergunning&rdquo; gaat het om
            een kantoor zonder vergunning voor wettelijke controles.
          </p>
          <Inklapbaar samenvatting={`Toon alle ${nl(overige.length)}`}>
            <div className="tabel-omhulsel">
              <table>
                <thead>
                  <tr>
                    <th>Kantoor</th>
                    {toonPlaatsOverig ? <th>Plaats</th> : null}
                    <th>Vergunning</th>
                  </tr>
                </thead>
                <tbody>
                  {overige.map((kantoor) => (
                    <tr key={kantoor.id}>
                      <td>
                        <KantoorLink naam={kantoor.naam} naar={kantoorPad(kantoor)} voluit />
                      </td>
                      {toonPlaatsOverig ? (
                        <td className="zacht klein">{kantoor.plaats ?? "—"}</td>
                      ) : null}
                      <td className="klein">
                        <Vergunning kantoor={kantoor} />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Inklapbaar>
        </section>
      ) : null}

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
