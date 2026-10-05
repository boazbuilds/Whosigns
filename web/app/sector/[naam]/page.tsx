import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import {
  marktaandeel,
  marktonderzoekPerSector,
  organisatiesInSector,
  sectoren,
  wisselingen,
  type MarktonderzoekJaar,
} from "@/lib/db";
import { saldoPerKantoor } from "@/lib/analyse";
import {
  controlesPerJaar,
  LEIDER_COMPLEET,
  LEIDER_MINIMUM,
  nieuwsteCompleteBoekjaar,
} from "@/lib/voorpagina";
import {
  aantalKantoren,
  aantalOrganisaties,
  aantalWisselingen,
  hoofdletter,
  kantoorPad,
  kortKantoor,
  nl,
  organisatiePad,
  procent,
  SECTOR_UITLEG,
  sectorOrganisatiesPad,
  sectorPad,
  slug,
  subsectorPad,
  veiligGedecodeerd,
  wisselingenPad,
} from "@/lib/paden";
import {
  Aandeelbalk,
  Aangeleverd,
  Doorklik,
  KantoorLink,
  Kerncijfer,
  KortKantoorLink,
  Kruimels,
  Leeg,
  Podiumplek,
  Rang,
} from "@/components/onderdelen";

type Params = { params: Promise<{ naam: string }> };

/** ISR: bij het eerste bezoek opbouwen en dan een uur uit de cache, zoals de
 *  organisatiepagina; zie de uitleg daar. Deze pagina hangt in het menu van
 *  élke pagina, dus juist hier telt het. */
export const revalidate = 3600;

export function generateStaticParams(): { naam: string }[] {
  return [];
}

/**
 * Zoveel organisaties staan op deze pagina; de hele lijst staat op een eigen,
 * gepagineerde pagina. Hier stonden ze tot 5-10-2026 állemaal in de HTML, de
 * staart ingeklapt: bij de zorg 2.448 regels en 1,6 MB, bij de financiële
 * dienstverlening 4.165 regels en 1,8 MB — ook voor wie alleen het podium
 * kwam bekijken.
 */
const ORGANISATIES_OPEN = 15;

/** Zoveel boekjaren marktonderzoek staan open; de oudste, met een handvol
 *  organisaties per jaar, zitten achter een klik. */
const MARKTONDERZOEK_OPEN = 8;

/**
 * Wat het aangeleverde marktonderzoek over deze sector zegt — apart van de
 * controles, en alleen als telling van organisaties per boekjaar.
 *
 * Het onderzoek noemt per organisatie en boekjaar een kantoor, maar niet
 * waarover de opdracht ging (opdrachttype "controle, voorwerp onbekend").
 * Daarom telt het nergens mee in de controles, aandelen en wisselingen
 * hierboven. Hier staat het toch, omdat de pagina anders "nog geen opdrachten"
 * zei bij een sector met duizenden: op 5-10-2026 had de handel 0 controles en
 * 4.095 opdrachten uit het marktonderzoek, de financiële dienstverlening 11
 * tegen 12.053.
 *
 * Geen verdeling per kantoor, ook niet binnen één jaar: het onderzoek dekt 22
 * kantoren en twee van de vier grootste niet, dus zo'n verdeling zou laten zien
 * wie er in de aanlevering zit en niet wie de sector controleert.
 */
function Marktonderzoek({ jaren }: { jaren: MarktonderzoekJaar[] }) {
  const regel = (rij: MarktonderzoekJaar) => (
    <tr key={rij.boekjaar}>
      <td className="jaar">{rij.boekjaar}</td>
      <td className="getal">{nl(rij.aantal_organisaties)}</td>
      <td className="getal">{nl(rij.zonder_controle)}</td>
    </tr>
  );
  const kop = (
    <thead>
      <tr>
        <th>Boekjaar</th>
        <th className="getal">Organisaties met een kantoor</th>
        <th className="getal">waarvan zonder gelezen controle</th>
      </tr>
    </thead>
  );
  return (
    <section className="kaart">
      <div className="kaartkop">
        <h2>Volgens marktonderzoek</h2>
        <span>
          <Aangeleverd bron={{ bron_type: "marktonderzoek", betrouwbaarheid: "zelf_aangeleverd" }} />{" "}
          <span className="klein zacht">(zelf aangeleverd)</span>
        </span>
      </div>
      <p className="klein zacht" style={{ marginTop: 0, maxWidth: "46rem" }}>
        Aangeleverd marktonderzoek noemt voor deze organisaties per boekjaar
        een accountantskantoor, maar niet waarover de opdracht ging: een
        wettelijke of vrijwillige controle van de jaarrekening, of iets anders.
        Het staat daarom los van de controles hierboven en telt niet mee in een
        aandeel of een wisseling. Welk kantoor het is, staat op de pagina van
        de organisatie.
      </p>
      <div className="tabel-omhulsel">
        <table>
          {kop}
          <tbody>{jaren.slice(0, MARKTONDERZOEK_OPEN).map(regel)}</tbody>
        </table>
      </div>
      {jaren.length > MARKTONDERZOEK_OPEN ? (
        <Inklapbaar samenvatting={`Nog ${jaren.length - MARKTONDERZOEK_OPEN} eerdere boekjaren`}>
          <div className="tabel-omhulsel">
            <table>
              {kop}
              <tbody>{jaren.slice(MARKTONDERZOEK_OPEN).map(regel)}</tbody>
            </table>
          </div>
        </Inklapbaar>
      ) : null}
      <p className="klein zacht" style={{ marginBottom: 0 }}>
        Geen verdeling over kantoren: het onderzoek dekt niet alle kantoren, dus
        zo&rsquo;n verdeling zou laten zien wie er in het onderzoek zit, niet wie
        deze sector controleert. Niet per document na te slaan.
      </p>
    </section>
  );
}

/**
 * De echte sectorwaarde bij een slug.
 *
 * Dit stond hier eerst als `slug.toLowerCase()`, met de aantekening dat het zou
 * breken zodra er een sector met een spatie bij kwam. Dat gebeurde: "goede doelen"
 * werd `goede-doelen` en die pagina gaf een 404, terwijl elke organisatiepagina van
 * een goed doel er wél naar linkte. Nu zoeken we de waarde op in de lijst die de
 * database kent — dezelfde aanpak als op de subsectorpagina.
 */
async function vindSector(naamSlug: string): Promise<string | null> {
  const lijst = await sectoren();
  return lijst.find((s) => slug(s.naam) === naamSlug)?.naam ?? null;
}

export async function generateMetadata({ params }: Params): Promise<Metadata> {
  const { naam } = await params;
  const sector = await vindSector(veiligGedecodeerd(naam)).catch(() => null);
  if (!sector) return { title: "Sector niet gevonden" };
  return {
    title: `Accountants in de sector ${sector}`,
    description:
      `Welke accountantskantoren controleren organisaties in de sector ${sector}: ` +
      `controles per boekjaar, het marktaandeel in het nieuwste complete boekjaar ` +
      `en recente wisselingen.`,
  };
}

export default async function Sectorpagina({ params }: Params) {
  const { naam } = await params;

  // Geen try met <Foutmelding> meer: deze pagina staat een uur in de cache, en
  // een gerenderde foutmelding ging daar bij een mislukte verversing in mee.
  // Een geworpen fout laat de vorige versie staan; zie error.tsx.
  const sector = await vindSector(veiligGedecodeerd(naam));
  const [organisaties, aandelen, sectorWisselingen, marktonderzoek] = sector
    ? await Promise.all([
        organisatiesInSector(sector),
        marktaandeel(sector),
        // Alleen de wisselingen van deze sector, zonder limiet: met een limiet
        // vooraf vielen ze buiten beeld zodra een andere sector de nieuwste
        // regels vulde.
        wisselingen({ sector }),
        // Het marktonderzoek is een los blok onderaan. Zolang de view er niet
        // is, geeft marktonderzoekPerSector() null en blijft het blok weg; elke
        // andere fout gooit door, zoals de rest van deze pagina, zodat de
        // vorige versie in de cache blijft staan.
        marktonderzoekPerSector(sector),
      ])
    : [[], [], [], null];
  // notFound() werkt met een uitzondering die Next zelf opvangt; in een try
  // met eigen catch werd dat een foutmelding met http-status 200.
  if (!sector || organisaties.length === 0) notFound();

  const marktonderzoekJaren = (marktonderzoek ?? []).filter((j) => j.aantal_organisaties > 0);

  // Subsectoren uit de organisaties van déze sector. Hier stond de landelijke
  // lijst, dus de zorgpagina toonde ook de subsectoren van de goede doelen.
  const perSubsector = new Map<string, number>();
  for (const org of organisaties) {
    if (org.subsector) {
      perSubsector.set(org.subsector, (perSubsector.get(org.subsector) ?? 0) + 1);
    }
  }
  const subsectorlijst = [...perSubsector.entries()].sort((a, b) => b[1] - a[1]);

  // Kruistabel: kantoren als rijen, boekjaren als kolommen. Zo zie je in één
  // oogopslag wie er over de jaren wint en wie krimpt.
  const boekjaren = [...new Set(aandelen.map((a) => a.boekjaar))].sort((a, b) => b - a);
  const perKantoor = new Map<
    number,
    { naam: string; afm: string | null; cellen: Map<number, number>; totaal: number }
  >();
  for (const rij of aandelen) {
    if (!rij.kantoor) continue;
    const bestaand = perKantoor.get(rij.kantoor_id) ?? {
      naam: rij.kantoor.naam,
      afm: rij.kantoor.afm_nummer,
      cellen: new Map<number, number>(),
      totaal: 0,
    };
    bestaand.cellen.set(rij.boekjaar, rij.aantal_controles);
    bestaand.totaal += rij.aantal_controles;
    perKantoor.set(rij.kantoor_id, bestaand);
  }
  const totaalControles = [...perKantoor.values()].reduce((som, rij) => som + rij.totaal, 0);

  // Het aandeel geldt binnen één sector én één boekjaar: het nieuwste boekjaar
  // dat voor deze sector al compleet is, met dezelfde regel als de
  // sectorleiders op de voorpagina. Hier stond het aandeel over alle boekjaren
  // samen. Bij de woningcorporaties gaf dat Deloitte 27,3% (1.666 van 6.093
  // over 2007–2024), terwijl het per jaar tussen 11 en 16% lag in 2019–2024;
  // bij de financiële dienstverlening stond Eshuis op 54,5% — 6 van 11
  // controles verspreid over dertien jaar (5-10-2026).
  const perJaar = controlesPerJaar(aandelen);
  const leiderJaar = nieuwsteCompleteBoekjaar(perJaar);
  const inLeiderJaar = (rij: { cellen: Map<number, number> }) =>
    leiderJaar === null ? 0 : (rij.cellen.get(leiderJaar) ?? 0);
  const controlesLeiderJaar = leiderJaar === null ? 0 : (perJaar.get(leiderJaar) ?? 0);

  // Gesorteerd op dat boekjaar, en pas daarna op het totaal: het rangnummer
  // hoort bij hetzelfde jaar als het aandeel ernaast.
  const kantoorrijen = [...perKantoor.entries()].sort(
    (a, b) =>
      inLeiderJaar(b[1]) - inLeiderJaar(a[1]) ||
      b[1].totaal - a[1].totaal ||
      a[1].naam.localeCompare(b[1].naam, "nl"),
  );
  // De plek in dat boekjaar: bij gelijke aantallen dezelfde plek, in de tabel,
  // op het podium en op de kantoorpagina (sectorposities) dezelfde regel. Het
  // podium deelde eerst i + 1 uit in sorteervolgorde: bij de overheid in 2024
  // (46, 30, 26, 26 controles) stond één van de twee met 26 op het podium en de
  // ander niet, en in overig bedrijfsleven stonden BDO en Eshuis (8 en 8) op
  // plek 2 en 3, terwijl de tabel ze allebei 2 gaf (5-10-2026).
  const plekIn = (rij: { cellen: Map<number, number> }) =>
    1 + kantoorrijen.filter(([, ander]) => inLeiderJaar(ander) > inLeiderJaar(rij)).length;
  const kandidaten = kantoorrijen.filter(
    ([, rij]) => inLeiderJaar(rij) > 0 && plekIn(rij) <= 3,
  );
  // Meer dan drie betekent een gelijke stand op de laagste plek. Dan gaat die
  // hele groep van het podium, met een zin erbij, in plaats van er één uit te
  // kiezen op naam. Hooguit één groep: wie erboven staat, telt er samen nooit
  // meer dan twee.
  const grensplek = kandidaten.length > 3 ? Math.max(...kandidaten.map(([, rij]) => plekIn(rij))) : null;
  const podium = kandidaten.filter(([, rij]) => grensplek === null || plekIn(rij) < grensplek);
  const gedeeld = kandidaten.filter(([, rij]) => grensplek !== null && plekIn(rij) === grensplek);
  const saldi = saldoPerKantoor(sectorWisselingen).filter((rij) => rij.saldo !== 0);

  const organisatierijen = organisaties.slice(0, ORGANISATIES_OPEN).map((org) => (
    <tr key={org.id}>
      <td>
        <Link href={organisatiePad(org)}>{org.naam}</Link>
      </td>
      <td className="zacht klein">{org.gemeente ?? "—"}</td>
    </tr>
  ));

  return (
    <>
      <Kruimels
        paden={[
          { naar: "/", tekst: "Start" },
          { naar: "/sectoren", tekst: "Sectoren" },
          { tekst: hoofdletter(sector) },
        ]}
      />

      <div className="paginakop">
        <h1>{hoofdletter(sector)}</h1>
        {SECTOR_UITLEG[sector] ? (
          <p className="klein zacht" style={{ marginTop: "0.35rem" }}>
            {SECTOR_UITLEG[sector]}
          </p>
        ) : null}
        <div className="kerncijfers">
          <Kerncijfer waarde={organisaties.length} naam="organisaties" />
          <Kerncijfer waarde={kantoorrijen.length} naam="kantoren actief" />
          <Kerncijfer waarde={totaalControles} naam="controles" />
          <Kerncijfer
            waarde={sectorWisselingen.length}
            naam="wisselingen"
            naar={wisselingenPad({ sector })}
          />
          <Kerncijfer
            waarde={boekjaren.length ? `${Math.min(...boekjaren)}–${Math.max(...boekjaren)}` : "—"}
            naam="boekjaren"
          />
        </div>
      </div>

      {leiderJaar !== null && kandidaten.length > 0 ? (
        <section className="kaart">
          <h2>Wie is hier de baas in boekjaar {leiderJaar}?</h2>
          <div className="podium">
            {podium.map(([id, rij]) => (
              <Podiumplek
                key={id}
                plek={plekIn(rij)}
                naar={kantoorPad({ afm_nummer: rij.afm, naam: rij.naam, id })}
                naam={rij.naam}
                onder={`${procent((inLeiderJaar(rij) / controlesLeiderJaar) * 100)} van ${nl(controlesLeiderJaar)} controles in ${leiderJaar}`}
                groot={String(inLeiderJaar(rij))}
              />
            ))}
          </div>
          {gedeeld.length > 0 ? (
            <p className="klein" style={{ marginTop: "0.9rem", marginBottom: 0 }}>
              {gedeeld.map(([id, rij], i) => (
                <span key={id}>
                  {i === 0 ? null : i === gedeeld.length - 1 ? " en " : ", "}
                  <Link href={kantoorPad({ afm_nummer: rij.afm, naam: rij.naam, id })}>
                    {kortKantoor(rij.naam)}
                  </Link>
                </span>
              ))}{" "}
              delen plek {grensplek}, met elk {inLeiderJaar(gedeeld[0][1])} controles
              in {leiderJaar}.
            </p>
          ) : null}
          <p className="klein zacht" style={{ marginTop: "0.9rem", marginBottom: 0 }}>
            Het nieuwste boekjaar dat al vrijwel compleet in de database staat:
            minstens {procent(100 * LEIDER_COMPLEET, 0)} van het aantal controles
            van het jaar ervoor, en minstens {LEIDER_MINIMUM}. De andere jaren
            staan hieronder als aantallen.
          </p>
        </section>
      ) : kantoorrijen.length > 0 ? (
        <section className="kaart">
          <h2>Wie is hier de baas?</h2>
          <Leeg
            tekst={`Te weinig controles voor een aandeel: in geen enkel boekjaar staan er in deze sector minstens ${LEIDER_MINIMUM} in de database. De aantallen per boekjaar staan hieronder.`}
          />
        </section>
      ) : null}

      <section className="kaart">
        <div className="kaartkop">
          <h2>Controles per kantoor per boekjaar</h2>
          <Link href="/kantoren">Alle kantoren →</Link>
        </div>
        {kantoorrijen.length === 0 ? (
          // Hier stond "Nog geen opdrachten in deze sector", ook bij de handel
          // met 4.095 opdrachten uit het marktonderzoek (5-10-2026). Wat er
          // ontbreekt zijn gelezen controles; het marktonderzoek staat apart.
          <Leeg
            tekst={
              marktonderzoekJaren.length
                ? "Nog geen gelezen wettelijke of vrijwillige controles in deze sector. Wel noemt aangeleverd marktonderzoek een kantoor bij een deel van de organisaties; zie hieronder."
                : "Nog geen gelezen wettelijke of vrijwillige controles in deze sector."
            }
          />
        ) : (
          <div className="tabel-omhulsel">
            <table>
              <thead>
                <tr>
                  <th>#</th>
                  <th>Kantoor</th>
                  {boekjaren.map((jaar) => (
                    <th key={jaar} className="getal">
                      {jaar}
                    </th>
                  ))}
                  <th className="getal">Totaal</th>
                  {leiderJaar !== null ? <th>Aandeel {leiderJaar}</th> : null}
                </tr>
              </thead>
              <tbody>
                {kantoorrijen.map(([id, rij]) => (
                  <tr key={id}>
                    <td className="rangcel">
                      {/* Een plek alleen in het boekjaar van het aandeel; wie
                          dat jaar niets controleerde, krijgt geen nummer. Bij
                          gelijke aantallen dezelfde plek, zoals op de
                          kantoorpagina (sectorposities). */}
                      {inLeiderJaar(rij) > 0 ? <Rang nummer={plekIn(rij)} /> : null}
                    </td>
                    <td>
                      <KantoorLink
                        naam={rij.naam}
                        naar={kantoorPad({ afm_nummer: rij.afm, naam: rij.naam, id })}
                      />
                    </td>
                    {boekjaren.map((jaar) => (
                      <td key={jaar} className="getal">
                        {rij.cellen.get(jaar) ?? <span className="zacht">·</span>}
                      </td>
                    ))}
                    <td className="getal">
                      <strong>{rij.totaal}</strong>
                    </td>
                    {leiderJaar !== null ? (
                      <td className="balkcel">
                        {inLeiderJaar(rij) > 0 ? (
                          <Aandeelbalk deel={inLeiderJaar(rij)} geheel={controlesLeiderJaar} />
                        ) : (
                          <span className="zacht">·</span>
                        )}
                      </td>
                    ) : null}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        {kantoorrijen.length > 0 ? (
          <p className="klein zacht" style={{ marginBottom: 0 }}>
            Het totaal is een optelsom van aantallen over de boekjaren, geen
            aandeel: welke organisaties er per boekjaar in de database staan
            verschilt.
            {leiderJaar !== null
              ? ` Rangnummer en aandeel gelden voor boekjaar ${leiderJaar}.`
              : ""}
          </p>
        ) : null}
      </section>

      {marktonderzoekJaren.length > 0 ? <Marktonderzoek jaren={marktonderzoekJaren} /> : null}

      {subsectorlijst.length > 0 ? (
        <section className="kaart">
          <h2>Subsectoren binnen {hoofdletter(sector)}</h2>
          <div className="tabel-omhulsel">
            <table>
              <thead>
                <tr>
                  <th>Subsector</th>
                  <th className="getal">Organisaties</th>
                  <th>Aandeel in de sector</th>
                </tr>
              </thead>
              <tbody>
                {subsectorlijst.map(([subsector, aantal]) => (
                  <tr key={subsector}>
                    <td>
                      <Link href={subsectorPad(subsector)}>{subsector}</Link>
                    </td>
                    <td className="getal">{aantal}</td>
                    <td className="balkcel">
                      <Aandeelbalk deel={aantal} geheel={organisaties.length} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      ) : null}

      <div className="kolommen">
        <section className="kaart">
          <div className="kaartkop">
            <h2>Wisselingen in deze sector</h2>
            <Link href={wisselingenPad({ sector })}>Alle →</Link>
          </div>
          {sectorWisselingen.length === 0 ? (
            <Leeg tekst="Geen wisselingen gevonden." />
          ) : (
            <table>
              <tbody>
                {sectorWisselingen.slice(0, 12).map((w) => (
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
        </section>

        <section className="kaart">
          <h2>Stijgers en dalers in deze sector</h2>
          {saldi.length === 0 ? (
            <Leeg tekst="Nog geen wisselingen om een saldo uit te rekenen." />
          ) : (
            <table>
              <tbody>
                {[...saldi.slice(0, 5), ...saldi.slice(-5).filter((r) => r.saldo < 0)]
                  // Bij weinig wisselingen kunnen kop en staart elkaar overlappen;
                  // dezelfde regel twee keer tonen is verwarrend.
                  .filter(
                    (rij, i, lijst) =>
                      lijst.findIndex((a) => a.kantoorId === rij.kantoorId) === i,
                  )
                  .map((rij) => (
                    <tr key={rij.kantoorId}>
                      <td>
                        <KantoorLink
                          naam={rij.naam}
                          naar={kantoorPad({
                            afm_nummer: rij.afmNummer,
                            naam: rij.naam,
                            id: rij.kantoorId,
                          })}
                        />
                      </td>
                      <td className="getal zacht klein">
                        +{rij.gewonnen} / −{rij.verloren}
                      </td>
                      <td className="getal">
                        <span
                          className={rij.saldo > 0 ? "saldo saldo-plus" : "saldo saldo-min"}
                        >
                          {rij.saldo > 0 ? `+${rij.saldo}` : rij.saldo}
                        </span>
                      </td>
                    </tr>
                  ))}
              </tbody>
            </table>
          )}
        </section>
      </div>

      <section className="kaart">
        <div className="kaartkop">
          <h2>Organisaties in deze sector</h2>
          {organisaties.length > ORGANISATIES_OPEN ? (
            <Link href={sectorOrganisatiesPad(sector)}>
              Alle {nl(organisaties.length)} →
            </Link>
          ) : null}
        </div>
        <div className="tabel-omhulsel">
          <table>
            <tbody>{organisatierijen}</tbody>
          </table>
        </div>
      </section>

      <Doorklik
        items={[
          ...subsectorlijst.slice(0, 3).map(([subsector, aantal]) => ({
            naar: subsectorPad(subsector),
            tekst: subsector,
            toelichting: aantalOrganisaties(aantal),
          })),
          ...kantoorrijen.slice(0, 3).map(([id, rij]) => ({
            naar: kantoorPad({ afm_nummer: rij.afm, naam: rij.naam, id }),
            tekst: rij.naam,
            toelichting: `${rij.totaal} controles in deze sector`,
          })),
          ...organisaties.slice(0, 2).map((org) => ({
            naar: organisatiePad(org),
            tekst: org.naam,
            toelichting: org.gemeente ?? undefined,
          })),
          {
            naar: sectorOrganisatiesPad(sector),
            tekst: "Alle organisaties in deze sector, alfabetisch",
            toelichting: aantalOrganisaties(organisaties.length),
          },
          { naar: "/sectoren", tekst: "Alle sectoren vergelijken" },
          {
            naar: "/kantoren",
            tekst: "Alle kantoren, over alle sectoren",
            toelichting: `${aantalKantoren(kantoorrijen.length)} actief in deze sector`,
          },
          {
            naar: wisselingenPad({ sector }),
            tekst: `Accountantswisselingen in de sector ${sector}`,
            toelichting: aantalWisselingen(sectorWisselingen.length),
          },
          { naar: "/bevindingen", tekst: "Waar was het oordeel niet goedkeurend?" },
        ]}
      />
    </>
  );
}
