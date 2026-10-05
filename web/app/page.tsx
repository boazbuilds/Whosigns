import Link from "next/link";
import {
  BEVINDING_FILTER,
  controlehonoraria,
  dagvraag,
  dagzaad,
  HONORARIUM_FILTER,
  kantoorRanglijst,
  marktaandeelRijen,
  nieuwsteBoekjaar,
  oordelenPerJaar,
  oordelenVoorafAanWissels,
  opvallendeOordelen,
  oudsteBoekjaar,
  recenteGunningen,
  sectoren,
  tel,
  wisselingen,
  wisselkansPerJaar,
  wisselRijen,
} from "@/lib/db";
import { prijsontwikkelingPerJaar, saldoPerKantoor } from "@/lib/analyse";
import {
  controlesPerJaar,
  dekkingPerSector,
  nieuwsteCompleteBoekjaar,
  sectorleiders,
  transferbalans,
} from "@/lib/voorpagina";
import { DagvraagKaart } from "@/components/dagvraag";
import {
  Dekkingskaart,
  OordelenPerJaar,
  OpvallendeOordelen,
  Prijsontwikkeling,
  RecentGegund,
  Sectorleiders,
  Transfermarkt,
  Wisselkans,
} from "@/components/dashboard";
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
  Doorklik,
  Foutmelding,
  KantoorLink,
  Kerncijfer,
  KortKantoorLink,
  Leeg,
  Tegel,
  Telbalk,
} from "@/components/onderdelen";

/**
 * Zoveel kantoren staan in de lijst op de voorpagina. Tien is genoeg om te zien
 * wie veel controleert; de rest staat op /kantoren.
 */
const KANTOREN_OP_VOORPAGINA = 10;

/** Zoveel regels hebben de lijstjes "zwaarste oordelen" en "recent gegund". */
const LIJSTJE = 8;

/**
 * Een los dashboardblok ophalen. Lukt dat niet, dan verdwijnt alleen dat blok —
 * zonder iets te beweren, ook niet dat er niets is — en de fout gaat naar het
 * log. De kern van de pagina (kerncijfers, ranglijst, sectoren) faalt wél hard:
 * daar is een foutmelding eerlijker dan een halve pagina. Maar een voorpagina
 * met tien blokken hoort niet om te vallen omdat de aanbestedingen even niet
 * laden.
 */
function los<T>(belofte: Promise<T>): Promise<T | null> {
  return belofte.catch((fout) => {
    console.error("[voorpagina] blok overgeslagen:", fout);
    return null;
  });
}

export default async function Startpagina() {
  let inhoud;
  try {
    // Het ranglijstjaar komt uit v_marktaandeel en niet uit max(boekjaar) van
    // de opdrachten: het marktonderzoek levert gebroken boekjaren tot en met
    // 2026 aan, maar die tellen niet als controle — en dan opende de site met
    // "Ranglijst 2026: nog geen opdrachten in dit boekjaar".
    //
    // En niet het nieuwste jaar uit die view, maar het nieuwste dat al compleet
    // is, met dezelfde regel als de sectorleiders verderop (LEIDER_COMPLEET).
    // Op 5-10-2026 stonden er voor 2025 1.321 controles in tegen 2.307 voor
    // 2024: 110 OOB-controles tegen 576 en nog geen enkele woningcorporatie. De
    // ranglijst over 2025 liet vooral zien welke sectoren al binnen waren.
    const marktRijen = await marktaandeelRijen();
    const perJaar = controlesPerJaar(marktRijen);
    const boekjaar =
      nieuwsteCompleteBoekjaar(perJaar) ??
      [...perJaar.keys()].sort((a, b) => b - a)[0] ??
      new Date().getFullYear() - 1;
    // De datum in Nederlandse tijd (sv-SE geeft JJJJ-MM-DD) bepaalt de
    // dagvraag; de pagina ververst per uur, dus om middernacht wisselt hij
    // vanzelf mee.
    const vandaag = new Date().toLocaleDateString("sv-SE", {
      timeZone: "Europe/Amsterdam",
    });
    const [
      organisatieTotaal,
      opdrachtTotaal,
      laatsteWisselingen,
      ranglijst,
      ranglijstAlles,
      sectorlijst,
      vroegste,
      laatste,
      vraag,
      gelezenTotaal,
      bevindingTotaal,
      wisselTotaal,
      tekenaarTotaal,
      honorariumTotaal,
      alleWissels,
      oordelen,
      wisselkans,
      honoraria,
      opvallend,
      gegund,
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
      // Voor de boekjarenreeks in de kerncijfers: die beschrijft de hele
      // dataset, dus mét de al aangeleverde 2026-boekjaren. Vandaar het
      // kopje "boekjaren met opdrachten": aan beide uiteinden (1996–2006 en
      // 2026) staat alleen marktonderzoek, en /sectoren zegt "t/m boekjaar
      // 2025" omdat het daar om controles gaat (5-10-2026).
      nieuwsteBoekjaar(),
      // De dagvraag mag nooit de voorpagina breken: zonder vraag geen kaart.
      dagvraag(vandaag).catch(() => null),
      // Wat er ín het register gevonden is, geteld in de database met dezelfde
      // filters als de pagina's waar de cijfers naartoe linken.
      tel("opdrachten", "oordeel=not.is.null"),
      tel("opdrachten", BEVINDING_FILTER),
      tel("v_wisselingen"),
      tel("v_accountant"),
      tel("opdrachten", HONORARIUM_FILTER),
      // De dashboardblokken. De rijen van v_marktaandeel zijn er al (zie het
      // ranglijstjaar hierboven); kantoorRanglijst() vraagt dezelfde adressen
      // op en Next deelt die verzoeken.
      los(wisselRijen()),
      los(oordelenPerJaar()),
      los(wisselkansPerJaar()),
      los(controlehonoraria()),
      los(opvallendeOordelen(LIJSTJE)),
      los(recenteGunningen(LIJSTJE)),
    ]);
    // Opinion-shopping-label bij de laatste transfers: het oordeel uit het
    // boekjaar vóór de wisseling, zelfde markering als op /wisselingen.
    const vooraf = await oordelenVoorafAanWissels(laatsteWisselingen);

    // De antwoordopties van de dagvraag: het echte kantoor plus drie grote
    // kantoren als afleiders, deterministisch gehusseld op dezelfde datum —
    // iedereen ziet dezelfde volgorde, en de goede staat niet altijd op
    // dezelfde plek. Grote kantoren zijn geloofwaardige afleiders; wie het
    // antwoord wil beredeneren moet dus echt de markt kennen.
    let vraagkaart = null;
    if (vraag) {
      const zaad = dagzaad(vandaag);
      const pool = ranglijstAlles
        .map((rij) => rij.kantoor.naam)
        .filter((naam) => naam !== vraag.kantoor.naam)
        .slice(0, 15);
      const afleiders: string[] = [];
      for (let i = 0; afleiders.length < 3 && pool.length > 0; i++) {
        afleiders.push(...pool.splice((zaad + i * 7919) % pool.length, 1));
      }
      if (afleiders.length >= 2) {
        const juist = zaad % (afleiders.length + 1);
        const opties = [...afleiders];
        opties.splice(juist, 0, vraag.kantoor.naam);
        vraagkaart = (
          <DagvraagKaart
            datum={vandaag}
            organisatieNaam={vraag.organisatie.naam}
            organisatiePad={organisatiePad(vraag.organisatie)}
            boekjaar={vraag.boekjaar}
            opties={opties}
            juist={juist}
          />
        );
      }
    }

    // De lijst van dit boekjaar toont aantallen, geen aandeel. De noemer van
    // zo'n aandeel zou alles zijn wat er voor dit boekjaar in de database
    // staat, over alle sectoren samen — en de database wordt per sector en per
    // boekjaar gevuld: boekjaar 2007 is voor 100% woningcorporaties, 2025 voor
    // 59% zorg (5-10-2026). Wie zulke aandelen vergelijkt ziet vooral de dekking
    // veranderen, niet de markt.
    //
    // Tot 20-8-2026 stond er "% van de markt" onder het podium, daarna "% van
    // wat er in de database staat" met een disclaimer. Het eerste vertelde een
    // onwaar verhaal over een kantoor met naam en toenaam (Deloitte zakte van
    // 43,8% in 2007 naar 12,2% in 2024 puur doordat er sectoren bij kwamen); het
    // tweede bleef een aandeel over sectoren heen, en dat noemt de site sinds
    // 5-10-2026 nergens meer. Per sector en boekjaar klopt het wél: dat staat
    // in "Wie leidt per sector" hieronder en op /sectoren.
    const grootsteDitJaar = ranglijst[0]?.aantal_controles ?? 0;
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

    // Alle kantoren met controles staan al in de eeuwige ranglijst; daaruit
    // komen de namen voor de transferbalans en de sectorleiders, zonder extra
    // verzoek.
    const kantoorPerId = new Map(ranglijstAlles.map((rij) => [rij.kantoor.id, rij.kantoor]));
    const dekking = marktRijen.length ? dekkingPerSector(marktRijen) : null;
    const leiders = sectorleiders(marktRijen);
    const balans = alleWissels ? transferbalans(alleWissels, kantoorPerId) : null;
    const prijzen = honoraria ? prijsontwikkelingPerJaar(honoraria) : [];

    inhoud = (
      <>
        <div className="paginakop">
          <h1>Wie controleert wie?</h1>
          <p className="klein zacht" style={{ marginTop: "0.4rem", maxWidth: "44rem" }}>
            De accountantsmarkt van Nederland als doorklikbaar naslagwerk: welk
            kantoor tekent bij welke organisatie, in welk boekjaar, en wanneer er
            werd gewisseld. Alles uit openbare bronnen, met de vindplaats erbij.
          </p>
          <div className="kerncijfers kerncijfers-raster">
            <Kerncijfer waarde={nl(organisatieTotaal)} naam="organisaties" />
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
              waarde={
                vroegste
                  ? `${vroegste}–${laatste ?? boekjaar}`
                  : `t/m ${laatste ?? boekjaar}`
              }
              naam="boekjaren met opdrachten"
            />
            <Kerncijfer waarde={nl(gelezenTotaal)} naam="verklaringen gelezen" />
            <Kerncijfer
              waarde={nl(bevindingTotaal)}
              naam="bevindingen"
              naar="/bevindingen"
            />
            <Kerncijfer
              waarde={nl(wisselTotaal)}
              naam="wisselingen"
              naar="/wisselingen"
            />
            <Kerncijfer
              waarde={nl(tekenaarTotaal)}
              naam="tekenende accountants"
              naar="/accountants"
            />
            <Kerncijfer
              waarde={nl(honorariumTotaal)}
              naam="honoraria"
              naar="/honoraria"
            />
          </div>
        </div>

        {/* Geen podium en geen rangnummers meer boven deze lijst: hij telt
            alle sectoren op, en een plek geldt op deze site alleen binnen één
            sector en één boekjaar — die staan in "Wie leidt per sector"
            hieronder. Tot 5-10-2026 stond hier "De grootste kantoren in
            boekjaar 2024" als podium (PwC 290, Deloitte 272, BDO 268), met
            daaronder dezelfde kantoren met 1, 2, 3 ervoor. */}
        <div className="kolommen-breed-smal">
          <section className="kaart">
            <div className="kaartkop">
              <h2>Kantoren in boekjaar {boekjaar}</h2>
              <Link href={`/kantoren?jaar=${boekjaar}`}>Alle kantoren →</Link>
            </div>
            {ranglijst.length === 0 ? (
              <Leeg tekst="Nog geen opdrachten in dit boekjaar." />
            ) : (
              <div className="tabel-omhulsel">
                <table>
                  <thead>
                    <tr>
                      <th>Kantoor</th>
                      <th className="getal">Controles</th>
                      <th>
                        <span className="verborgen">Controles als balk</span>
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {ranglijst.slice(0, KANTOREN_OP_VOORPAGINA).map((rij) => (
                      <tr key={rij.kantoor.id}>
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
                          <Telbalk
                            aantal={rij.aantal_controles}
                            grootste={grootsteDitJaar}
                          />
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
            <p className="klein zacht" style={{ marginTop: "0.9rem", marginBottom: 0 }}>
              Aantallen controles over alle sectoren samen, in het nieuwste
              boekjaar dat al vrijwel compleet in de database staat. Een aandeel
              of een plek noemt deze site alleen binnen één sector en één
              boekjaar, want welke sectoren erin zitten verschilt per boekjaar —{" "}
              <Link href="/sectoren">zie de sectoren</Link>.
            </p>
          </section>

          <div className="kolomstapel">
            {vraagkaart}
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
                          {(() => {
                            const stand = vooraf.get(
                              `${w.organisatie_id}-${w.boekjaar_wissel}`,
                            );
                            if (
                              !stand ||
                              ((stand.oordeel === null ||
                                stand.oordeel === "goedkeurend") &&
                                !stand.continuiteitsonzekerheid)
                            ) {
                              return null;
                            }
                            return (
                              <>
                                {" "}
                                <span
                                  className="label label-let-op"
                                  title={`De verklaring over boekjaar ${w.boekjaar_wissel - 1} was niet zonder meer goedkeurend; daarna wisselde de organisatie van kantoor.`}
                                >
                                  na slecht nieuws
                                </span>
                              </>
                            );
                          })()}
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
        </div>

        {wisselkans?.length || balans?.rijen.length ? (
          <div className="kolommen">
            {wisselkans?.length ? <Wisselkans jaren={wisselkans} /> : null}
            {balans ? <Transfermarkt balans={balans} kantoorPerId={kantoorPerId} /> : null}
          </div>
        ) : null}

        <Sectorleiders leiders={leiders} kantoorPerId={kantoorPerId} />

        {dekking ? <Dekkingskaart dekking={dekking} /> : null}

        {oordelen?.length || prijzen.length ? (
          <div className="kolommen">
            {oordelen?.length ? <OordelenPerJaar jaren={oordelen} /> : null}
            <Prijsontwikkeling jaren={prijzen} />
          </div>
        ) : null}

        {opvallend?.length || gegund?.length ? (
          <div className="kolommen">
            {opvallend ? <OpvallendeOordelen rijen={opvallend} /> : null}
            {gegund ? <RecentGegund rijen={gegund} /> : null}
          </div>
        ) : null}

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
              tekst: "Alle kantoren",
              toelichting: `${ranglijstAlles.length} met controles`,
            },
            { naar: "/wisselingen", tekst: "Alle accountantswisselingen" },
            {
              naar: "/bevindingen",
              tekst: "Waar was het oordeel niet goedkeurend?",
              toelichting: `${nl(bevindingTotaal)} bevindingen`,
            },
            {
              naar: "/accountants",
              tekst: "Wie zet de handtekening?",
              toelichting: `${nl(tekenaarTotaal)} tekenende accountants`,
            },
            {
              naar: "/honoraria",
              tekst: "Wat betaalt de organisatie de accountant?",
              toelichting: `${nl(honorariumTotaal)} honoraria`,
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
