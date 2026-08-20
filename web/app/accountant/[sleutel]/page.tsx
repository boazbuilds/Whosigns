import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { accountantOpSlug, opdrachtenVanAccountant } from "@/lib/db";
import {
  aantalOpdrachten,
  aantalOrganisaties,
  hoofdletter,
  jarenReeks,
  kantoorPad,
  nl,
  organisatiePad,
  sectorPad,
  slug,
  veiligGedecodeerd,
} from "@/lib/paden";
import {
  Doorklik,
  Foutmelding,
  KantoorLink,
  Kerncijfer,
  Kruimels,
  Leeg,
  Oordeel,
  Soort,
} from "@/components/onderdelen";

type Params = { params: Promise<{ sleutel: string }> };

export async function generateMetadata({ params }: Params): Promise<Metadata> {
  const { sleutel } = await params;
  const acc = await accountantOpSlug(veiligGedecodeerd(sleutel), slug).catch(() => null);
  if (!acc) return { title: "Accountant niet gevonden" };
  return {
    title: `${acc.naam} — welke jaarrekeningen tekende deze accountant?`,
    description:
      `Alle jaarrekeningen die ${acc.naam} ondertekende: organisatie, boekjaar, ` +
      `kantoor en oordeel, met de vindplaats erbij.`,
  };
}

export default async function Accountantpagina({ params }: Params) {
  const { sleutel } = await params;

  let acc;
  let werk;
  try {
    acc = await accountantOpSlug(veiligGedecodeerd(sleutel), slug);
    werk = acc ? await opdrachtenVanAccountant(acc.sleutel) : null;
  } catch (fout) {
    return <Foutmelding fout={fout} />;
  }
  // Buiten de try, net als op de sectorpagina: notFound() gooit een uitzondering
  // die Next zelf opvangt, en onze catch zou daar een 200 met foutmelding van maken.
  if (!acc || !werk || werk.rijen.length === 0) notFound();

  const { rijen, organisaties, kantoren } = werk;

  // Alle schrijfwijzen waarin deze naam in de stukken staat. Meestal één; staan
  // er meer, dan is het eerlijker om ze te tonen dan om te doen alsof er één is.
  const schrijfwijzen = [...new Set(rijen.map((r) => r.naam_zoals_getekend))];
  const kantoorlijst = [
    ...new Map(
      rijen
        .map((r) => (r.kantoor_id != null ? kantoren.get(r.kantoor_id) : null))
        .filter((k): k is NonNullable<typeof k> => !!k)
        .map((k) => [k.id, k] as const),
    ).values(),
  ];
  const sectorlijst = [
    ...new Set(
      rijen
        .map((r) => organisaties.get(r.organisatie_id)?.sector)
        .filter((s): s is string => !!s),
    ),
  ];

  return (
    <>
      <Kruimels
        paden={[
          { naar: "/", tekst: "Start" },
          { naar: "/accountants", tekst: "Accountants" },
          { tekst: acc.naam },
        ]}
      />

      <div className="paginakop">
        <h1>{acc.naam}</h1>
        <p className="metaregel">
          <span>{aantalOpdrachten(acc.aantal_opdrachten)} getekend</span>
          <span>{aantalOrganisaties(acc.aantal_organisaties)}</span>
          <span>{jarenReeks(rijen.map((r) => r.boekjaar))}</span>
        </p>
        <div className="kerncijfers">
          <Kerncijfer waarde={nl(acc.aantal_opdrachten)} naam="ondertekeningen" />
          <Kerncijfer
            waarde={nl(acc.aantal_organisaties)}
            naam="organisaties"
            naar="/organisaties"
          />
          <Kerncijfer
            waarde={nl(acc.aantal_kantoren)}
            naam={acc.aantal_kantoren === 1 ? "kantoor" : "kantoren"}
            naar="/kantoren"
          />
          <Kerncijfer
            waarde={jarenReeks(rijen.map((r) => r.boekjaar))}
            naam="boekjaren"
          />
        </div>
      </div>

      {/* Twee kantoren onder één naam is óf een overstap óf een naamgenoot, en
          dat onderscheid is uit een verklaring niet te maken. Dus zeggen we het,
          in plaats van te kiezen. */}
      {acc.aantal_kantoren > 1 ? (
        <section className="kaart">
          <p className="klein" style={{ marginBottom: 0 }}>
            <strong>Let op:</strong> deze naam staat onder verklaringen van{" "}
            {acc.aantal_kantoren} verschillende kantoren (
            {kantoorlijst.map((k) => k.naam).join(", ")}). Dat kan één accountant
            zijn die is overgestapt, maar het kunnen ook twee mensen met dezelfde
            initialen en achternaam zijn. Een gedeponeerde verklaring bevat geen
            accountantsnummer, dus dat verschil is hieruit niet te zien.
          </p>
        </section>
      ) : null}

      <section className="kaart">
        <div className="kaartkop">
          <h2>Getekende jaarrekeningen</h2>
          <Link href="/accountants">Alle accountants →</Link>
        </div>
        {rijen.length === 0 ? (
          <Leeg tekst="Nog geen ondertekeningen vastgelegd." />
        ) : (
          <div className="tabel-omhulsel">
            <table>
              <thead>
                <tr>
                  <th>Boekjaar</th>
                  <th>Organisatie</th>
                  <th>Sector</th>
                  <th>Kantoor</th>
                  <th>Soort</th>
                  <th>Oordeel</th>
                </tr>
              </thead>
              <tbody>
                {rijen.map((rij) => {
                  const org = organisaties.get(rij.organisatie_id);
                  const kantoor =
                    rij.kantoor_id != null ? kantoren.get(rij.kantoor_id) : null;
                  return (
                    <tr key={rij.opdracht_id}>
                      <td className="jaar">{rij.boekjaar}</td>
                      <td>
                        {org ? (
                          <Link href={organisatiePad(org)}>{org.naam}</Link>
                        ) : (
                          <span className="zacht">onbekend</span>
                        )}
                      </td>
                      <td className="klein zacht">
                        {org?.sector ? (
                          <Link href={sectorPad(org.sector)}>
                            {hoofdletter(org.sector)}
                          </Link>
                        ) : (
                          "—"
                        )}
                      </td>
                      <td>
                        {kantoor ? (
                          <KantoorLink
                            naam={kantoor.naam}
                            naar={kantoorPad(kantoor)}
                            maat="m"
                          />
                        ) : (
                          <span className="zacht">niet herleid</span>
                        )}
                      </td>
                      <td>
                        <Soort type={rij.type_opdracht} />
                      </td>
                      <td>
                        <Oordeel waarde={rij.oordeel} />
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <section className="kaart">
        <h2>Over dit gegeven</h2>
        <p className="klein">
          De naam komt uit de ondertekening van de gedeponeerde
          controleverklaring zelf — hetzelfde stuk waaruit het oordeel is
          gelezen. Er wordt niets afgeleid: staat er geen leesbare ondertekenaar,
          dan blijft het veld leeg.
        </p>
        {schrijfwijzen.length > 1 ? (
          <p className="klein zacht">
            In de stukken staat deze naam in {schrijfwijzen.length} schrijfwijzen:{" "}
            {schrijfwijzen.join(" · ")}. Ze zijn samengenomen op initialen,
            achternaam en beroepstitel; alleen aanhef en leestekens zijn genegeerd.
          </p>
        ) : null}
        <p className="klein zacht" style={{ marginBottom: 0 }}>
          Klopt er iets niet, of wil je hier niet staan? Zie het colofon onderaan
          deze pagina.
        </p>
      </section>

      <Doorklik
        items={[
          { naar: "/accountants", tekst: "Alle accountants" },
          ...kantoorlijst.slice(0, 3).map((k) => ({
            naar: kantoorPad(k),
            tekst: `Kantoor ${k.naam}`,
          })),
          ...sectorlijst.slice(0, 2).map((s) => ({
            naar: sectorPad(s),
            tekst: `Sector ${hoofdletter(s)}`,
          })),
          ...rijen.slice(0, 3).map((r) => {
            const org = organisaties.get(r.organisatie_id);
            return {
              naar: org ? organisatiePad(org) : "",
              tekst: org ? org.naam : "",
            };
          }),
          { naar: "/wisselingen", tekst: "Alle wisselingen" },
        ]}
      />
    </>
  );
}
