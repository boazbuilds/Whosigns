import type { Metadata } from "next";
import Link from "next/link";
import { accountants } from "@/lib/db";
import { accountantPad, nl } from "@/lib/paden";
import {
  Doorklik,
  Foutmelding,
  Kerncijfer,
  Kruimels,
  Leeg,
  Rang,
} from "@/components/onderdelen";

export const metadata: Metadata = {
  title: "Tekenend accountants",
  description:
    "Wie zet zijn handtekening onder welke jaarrekening? Alle accountants die " +
    "een gedeponeerde controleverklaring ondertekenden, met hun opdrachten.",
};

/** Zoveel accountants staan in de tabel. De rest is via de organisatie- en
 *  kantoorpagina's te bereiken; een lijst van duizenden namen op één pagina is
 *  geen naslagwerk maar een telefoonboek. */
const IN_DE_LIJST = 250;

export default async function Accountantsoverzicht() {
  let lijst;
  try {
    lijst = await accountants();
  } catch (fout) {
    return <Foutmelding fout={fout} />;
  }

  const getoond = lijst.slice(0, IN_DE_LIJST);
  const totaalOpdrachten = lijst.reduce((som, a) => som + a.aantal_opdrachten, 0);
  const meerKantoren = lijst.filter((a) => a.aantal_kantoren > 1).length;

  return (
    <>
      <Kruimels paden={[{ naar: "/", tekst: "Start" }, { tekst: "Accountants" }]} />

      <div className="paginakop">
        <h1>Wie zet de handtekening?</h1>
        <p className="klein zacht" style={{ marginTop: "0.4rem", maxWidth: "44rem" }}>
          Een controleverklaring wordt niet door een kantoor ondertekend maar door
          een mens. Dit zijn de accountants die wij in gedeponeerde verklaringen
          als ondertekenaar aantroffen — klik door voor alle jaarrekeningen die
          iemand tekende.
        </p>
        <div className="kerncijfers">
          <Kerncijfer waarde={nl(lijst.length)} naam="accountants" />
          <Kerncijfer waarde={nl(totaalOpdrachten)} naam="ondertekeningen" />
          <Kerncijfer waarde={nl(meerKantoren)} naam="bij meer dan één kantoor" />
        </div>
      </div>

      <section className="kaart">
        <div className="kaartkop">
          <h2>Meeste ondertekeningen</h2>
          <Link href="/kantoren">Naar de kantoren →</Link>
        </div>
        {getoond.length === 0 ? (
          <Leeg
            tekst={
              "Nog geen ondertekenaars vastgelegd. Dit veld wordt gevuld zodra de " +
              "verklaringen opnieuw zijn gelezen."
            }
          />
        ) : (
          <>
            <div className="tabel-omhulsel">
              <table>
                <thead>
                  <tr>
                    <th>#</th>
                    <th>Accountant</th>
                    <th className="getal">Getekend</th>
                    <th className="getal">Organisaties</th>
                    <th className="getal">Kantoren</th>
                    <th>Boekjaren</th>
                  </tr>
                </thead>
                <tbody>
                  {getoond.map((acc, i) => (
                    <tr key={acc.sleutel}>
                      <td className="rangcel">
                        <Rang nummer={i + 1} />
                      </td>
                      <td>
                        <Link href={accountantPad(acc.sleutel)}>{acc.naam}</Link>
                      </td>
                      <td className="getal">
                        <strong>{acc.aantal_opdrachten}</strong>
                      </td>
                      <td className="getal">{acc.aantal_organisaties}</td>
                      <td className="getal">
                        {acc.aantal_kantoren > 1 ? (
                          <span className="label label-vaag" title={
                            "Overstap of naamgenoot — uit een verklaring niet te zien."
                          }>
                            {acc.aantal_kantoren}
                          </span>
                        ) : (
                          acc.aantal_kantoren
                        )}
                      </td>
                      <td className="klein zacht">
                        {acc.eerste_boekjaar === acc.laatste_boekjaar
                          ? acc.eerste_boekjaar
                          : `${acc.eerste_boekjaar}–${acc.laatste_boekjaar}`}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {lijst.length > getoond.length ? (
              <p className="klein zacht" style={{ marginBottom: 0 }}>
                Getoond: de eerste {nl(getoond.length)} van {nl(lijst.length)}{" "}
                accountants. De rest is te bereiken via de organisatie- of
                kantoorpagina waar zij tekenden.
              </p>
            ) : null}
          </>
        )}
      </section>

      <section className="kaart">
        <h2>Waar komt dit vandaan</h2>
        <p className="klein">
          Uit de ondertekening van de gedeponeerde controleverklaring zelf —
          hetzelfde openbare stuk waaruit het oordeel is gelezen. Er wordt niets
          afgeleid en niets gecombineerd met andere bronnen: staat er geen
          leesbare ondertekenaar, dan blijft het veld leeg.
        </p>
        <p className="klein zacht" style={{ marginBottom: 0 }}>
          Namen die alleen in schrijfwijze verschillen ("J. Jansen RA" en
          "drs. J. Jansen RA") staan onder één noemer. Verschillende beroepstitels
          worden níét samengenomen. Zie het colofon voor wat je kunt doen als er
          iets niet klopt.
        </p>
      </section>

      <Doorklik
        items={[
          ...getoond.slice(0, 4).map((a) => ({
            naar: accountantPad(a.sleutel),
            tekst: a.naam,
          })),
          { naar: "/kantoren", tekst: "Alle kantoren" },
          { naar: "/bevindingen", tekst: "Niet-goedkeurende oordelen" },
        ]}
      />
    </>
  );
}
