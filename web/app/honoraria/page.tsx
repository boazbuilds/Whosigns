import type { Metadata } from "next";
import Link from "next/link";
import { opdrachtenMetHonoraria } from "@/lib/db";
import {
  controleHonorariumPerJaar,
  perBoekjaarEnSector,
  prijsontwikkelingPerKantoor,
} from "@/lib/analyse";
import {
  euro,
  hoofdletter,
  jarenReeks,
  kantoorPad,
  nl,
  organisatiePad,
  sectorPad,
} from "@/lib/paden";
import {
  Aandeelbalk,
  Aangeleverd,
  Doorklik,
  KantoorLink,
  Kerncijfer,
  Kruimels,
  Leeg,
  Soort,
} from "@/components/onderdelen";

export const metadata: Metadata = {
  title: "Honoraria van de accountant",
  description:
    "Wat betalen organisaties hun accountant? De verantwoorde honoraria per " +
    "organisatie en boekjaar, in de vier categorieën van art. 2:382a BW.",
};

/**
 * Zoveel bedragen per sector en boekjaar staan in de tabel, de hoogste eerst.
 *
 * Hier stonden tot 5-10-2026 álle bedragen in één tabel: 2.505 regels en
 * 4,3 MB HTML, over alle sectoren en boekjaren door elkaar gesorteerd —
 * terwijl de pagina zelf zegt dat je alleen binnen een sector en boekjaar mag
 * vergelijken. Nu per boekjaar en per sector de hoogste; elk bedrag blijft
 * staan op de pagina van de organisatie zelf.
 */
const PER_GROEP = 25;

export default async function Honorariapagina() {
  // Geen try met <Foutmelding>: deze pagina staat een uur in de cache, en een
  // gerenderde foutmelding ging daar bij een mislukte verversing in mee. Een
  // geworpen fout laat de vorige versie staan (zie error.tsx).
  const rijen = await opdrachtenMetHonoraria();

  const bedragen = rijen
    .map((r) => r.honorarium_controle_eur)
    .filter((b): b is number => b != null)
    .sort((a, b) => a - b);
  const totaalControle = bedragen.reduce((som, b) => som + b, 0);
  const mediaan = bedragen.length
    ? bedragen[Math.floor(bedragen.length / 2)]
    : null;
  const boekjaren = [...new Set(rijen.map((r) => r.boekjaar))].sort();
  const sectoren = [
    ...new Set(rijen.map((r) => r.organisaties?.sector).filter((s): s is string => !!s)),
  ];
  const perJaar = controleHonorariumPerJaar(rijen);
  const maxGemiddelde = Math.max(...perJaar.map((j) => j.gemiddelde), 1);
  const ontwikkeling = prijsontwikkelingPerKantoor(rijen);
  // +6,2% / −3,1%; de echte minus, niet het koppelteken.
  const procent = (fractie: number) =>
    `${fractie >= 0 ? "+" : "−"}${Math.abs(fractie * 100).toFixed(1).replace(".", ",")}%`;

  return (
    <>
      <Kruimels paden={[{ naar: "/", tekst: "Start" }, { tekst: "Honoraria" }]} />

      <div className="paginakop">
        <h1>Wat betaalt de organisatie de accountant?</h1>
        <p className="klein zacht" style={{ marginTop: "0.4rem", maxWidth: "44rem" }}>
          Sinds boekjaar 2008 moet de jaarrekening vermelden wat er aan de
          accountant is betaald, uitgesplitst in vier categorieën
          (art. 2:382a BW). Dit zijn die bedragen, zoals de organisaties ze
          zélf hebben verantwoord — per boekjaar, doorgaans voor het hele
          accountantsnetwerk, en dus niet de prijs van één losse opdracht.
          De bedragen over boekjaar 2019, en een enkel bedrag in een later jaar
          dat de organisatie zelf niet opgaf, zijn de vergelijkende cijfers uit
          de jaarverantwoording van het jaar erna.
        </p>
        <div className="kerncijfers">
          <Kerncijfer waarde={nl(rijen.length)} naam="opdrachten met een bedrag" />
          <Kerncijfer
            waarde={euro(totaalControle) ?? "—"}
            naam="aan controle verantwoord"
          />
          <Kerncijfer waarde={euro(mediaan) ?? "—"} naam="mediaan controlehonorarium" />
          <Kerncijfer
            waarde={jarenReeks(boekjaren)}
            naam={boekjaren.length === 1 ? "boekjaar" : "boekjaren"}
          />
        </div>
      </div>

      {perJaar.length > 0 ? (
        <section className="kaart">
          <div className="kaartkop">
            <h2>Gemiddeld controlehonorarium per boekjaar</h2>
          </div>
          <div className="tabel-omhulsel">
            <table>
              <thead>
                <tr>
                  <th>Boekjaar</th>
                  <th className="getal">Opdrachten</th>
                  <th className="getal">Gemiddeld</th>
                  <th className="getal">Mediaan</th>
                  <th>Verhouding</th>
                </tr>
              </thead>
              <tbody>
                {perJaar.map((jaar) => (
                  <tr key={jaar.boekjaar}>
                    <td className="jaar">{jaar.boekjaar}</td>
                    <td className="getal zacht">{jaar.aantal}</td>
                    <td className="getal">
                      <strong>{euro(Math.round(jaar.gemiddelde))}</strong>
                    </td>
                    <td className="getal">{euro(jaar.mediaan)}</td>
                    <td className="balkcel">
                      <Aandeelbalk deel={jaar.gemiddelde} geheel={maxGemiddelde} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="klein zacht" style={{ marginBottom: 0 }}>
            Alleen de categorie controle van de jaarrekening. Let op: welke
            organisaties er per boekjaar in zitten verschilt — een jaar met veel
            beursfondsen ligt vanzelf hoger dan een jaar met veel
            zorginstellingen. Jaren onderling vergelijken zegt dus vooral iets
            over de samenstelling; de prijsontwikkeling hieronder werkt dat
            effect weg.
          </p>
        </section>
      ) : null}

      {ontwikkeling.length > 0 ? (
        <section className="kaart">
          <div className="kaartkop">
            <h2>Prijsontwikkeling per kantoor</h2>
            <span className="klein zacht">jaar-op-jaar, zelfde cliënt</span>
          </div>
          <div className="tabel-omhulsel">
            <table>
              <thead>
                <tr>
                  <th>Kantoor</th>
                  <th>Periode</th>
                  <th className="getal">Metingen</th>
                  <th className="getal">Mediane verandering per jaar</th>
                </tr>
              </thead>
              <tbody>
                {ontwikkeling.map((rij) => (
                  <tr key={rij.kantoorId}>
                    <td>
                      <KantoorLink
                        naam={rij.naam}
                        naar={kantoorPad({ id: rij.kantoorId, afm_nummer: rij.afmNummer, naam: rij.naam })}
                        maat="m"
                      />
                    </td>
                    <td className="jaar">
                      {rij.vanJaar}–{rij.totJaar}
                    </td>
                    <td className="getal zacht">{rij.paren}</td>
                    <td className="getal">
                      <strong>{procent(rij.mediaanVerandering)}</strong>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="klein zacht" style={{ marginBottom: 0 }}>
            Gemeten op gematchte paren: dezelfde organisatie, bij hetzelfde
            kantoor, in twee opeenvolgende boekjaren — zo meet je de prijs en
            niet de klantenmix. Per kantoor staat de mediaan van die
            veranderingen; kantoren met minder dan drie metingen blijven weg,
            want twee waarnemingen zijn geen ontwikkeling maar een anekdote.
          </p>
        </section>
      ) : null}

      {rijen.length === 0 ? (
        <section className="kaart">
          <h2>Verantwoorde honoraria</h2>
          <Leeg tekst="Nog geen honoraria in de database." />
        </section>
      ) : (
        perBoekjaarEnSector(rijen).map(({ boekjaar, aantal, sectoren: groepen }) => (
          <section className="kaart" key={boekjaar}>
            <div className="kaartkop">
              <h2>Boekjaar {boekjaar}</h2>
              <span className="klein zacht">{nl(aantal)} met een bedrag</span>
            </div>
            {groepen.map(([sector, lijst]) => (
              <div key={sector ?? "onbekend"}>
                <h3 style={{ margin: "0.8rem 0 0.3rem" }}>
                  {sector ? (
                    <Link href={sectorPad(sector)}>{hoofdletter(sector)}</Link>
                  ) : (
                    "Sector onbekend"
                  )}{" "}
                  <span className="klein zacht" style={{ fontWeight: 400 }}>
                    {lijst.length > PER_GROEP
                      ? `de ${PER_GROEP} hoogste van ${nl(lijst.length)}`
                      : lijst.length === 1
                        ? "één bedrag"
                        : `${nl(lijst.length)} bedragen`}
                  </span>
                </h3>
                <div className="tabel-omhulsel">
                  <table>
                    <thead>
                      <tr>
                        <th>Organisatie</th>
                        <th>Kantoor</th>
                        <th className="getal">Controle</th>
                        <th className="getal">Overige controle</th>
                        <th className="getal">Fiscaal</th>
                        <th className="getal">Niet-controle</th>
                      </tr>
                    </thead>
                    <tbody>
                      {lijst.slice(0, PER_GROEP).map((rij, i) => (
                        <tr key={i}>
                          <td>
                            {rij.organisaties ? (
                              <Link href={organisatiePad(rij.organisaties)}>
                                {rij.organisaties.naam}
                              </Link>
                            ) : (
                              <span className="zacht">onbekend</span>
                            )}
                          </td>
                          <td>
                            {rij.kantoren ? (
                              <KantoorLink
                                naam={rij.kantoren.naam}
                                naar={kantoorPad(rij.kantoren)}
                                maat="m"
                              />
                            ) : (
                              <span className="zacht">niet herleid</span>
                            )}
                            {/* Het bedrag is openbaar, maar welk kantoor erbij
                                hoort komt bij 54 van de 1.872 regels uit
                                aangeleverd marktonderzoek (5-10-2026); dan zegt de
                                regel dat. */}
                            <Aangeleverd bron={rij.bronnen} />
                          </td>
                          {/* Een streepje is "niet verantwoord", geen nul: €0 tonen
                              waar niets is opgegeven zou een bewering zijn. */}
                          <td className="getal">
                            {euro(rij.honorarium_controle_eur) ?? <span className="zacht">—</span>}
                          </td>
                          <td className="getal">
                            {euro(rij.honorarium_overig_eur) ?? <span className="zacht">—</span>}
                          </td>
                          <td className="getal">
                            {euro(rij.honorarium_fiscaal_eur) ?? <span className="zacht">—</span>}
                          </td>
                          <td className="getal">
                            {euro(rij.honorarium_nietcontrole_eur) ?? <span className="zacht">—</span>}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            ))}
          </section>
        ))
      )}

      {rijen.length > 0 ? (
        <p className="klein zacht" style={{ maxWidth: "44rem" }}>
          Per boekjaar en per sector de {PER_GROEP} hoogste controlehonoraria;
          elk bedrag staat ook op de pagina van de organisatie zelf. Dekking:
          dit zijn alleen de organisaties waarvan de bron de bedragen
          gestructureerd meelevert
          {sectoren.length ? ` (nu: ${sectoren.map(hoofdletter).join(", ")})` : ""}.
          De meeste jaarrekeningen vermelden de honoraria wel, maar als tekst in
          een pdf; die worden per bron ontsloten. Geen bedrag hier betekent dus
          niet dat er niets is betaald.
        </p>
      ) : null}

      <section className="kaart">
        <h2>Hoe deze bedragen te lezen</h2>
        <p className="klein">
          <strong>Controle van de jaarrekening</strong> is het honorarium voor de
          wettelijke of vrijwillige controle zelf. <strong>Overige
          controlewerkzaamheden</strong> omvat onder meer de WNT-controle.
          <strong> Fiscaal</strong> en <strong>niet-controlediensten</strong> zijn
          advieswerk — bij OOB's grotendeels verboden, daarbuiten een klassiek
          discussiepunt over onafhankelijkheid: hoe meer advies naast de
          controle, hoe scherper de vraag wie hier wiens klant is.
        </p>
        <p className="klein zacht" style={{ marginBottom: 0 }}>
          Een streepje betekent dat de bron dat bedrag niet noemt — niet dat het
          nul is. De bedragen zijn zelfopgave van de organisatie en niet door ons
          herrekend. Vergelijk binnen een sector en boekjaar; een ziekenhuis en
          een thuiszorg-bv verschillen te veel voor één ranglijst.
        </p>
      </section>

      <Doorklik
        items={[
          ...rijen.slice(0, 3).map((r) => ({
            naar: r.organisaties ? organisatiePad(r.organisaties) : "",
            tekst: r.organisaties?.naam ?? "",
          })),
          ...sectoren.slice(0, 2).map((s) => ({
            naar: sectorPad(s),
            tekst: `Sector ${hoofdletter(s)}`,
          })),
          { naar: "/kantoren", tekst: "Alle kantoren" },
          { naar: "/bevindingen", tekst: "Niet-goedkeurende oordelen" },
        ]}
      />
    </>
  );
}
