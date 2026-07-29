import type { Metadata } from "next";
import Link from "next/link";
import { alleOrganisaties, tel } from "@/lib/db";
import { organisatiePad, sectorPad } from "@/lib/paden";
import { Doorklik } from "@/components/onderdelen";

export const metadata: Metadata = {
  title: "Over de data",
  description:
    "Welke openbare bronnen WhoSigns gebruikt, hoe de accountant per boekjaar " +
    "wordt vastgesteld, en wat wij bewust niet vastleggen.",
};

export default async function Bronpagina() {
  const [organisaties, aantalKantoren, aantalOpdrachten] = await Promise.all([
    alleOrganisaties().catch(() => []),
    tel("kantoren").catch(() => 0),
    tel("opdrachten").catch(() => 0),
  ]);

  return (
    <>
      <div className="paginakop">
        <h1>Over de data</h1>
        <p className="metaregel">
          <span className="label label-demo">Demo · gedeeltelijke data</span>
          <span>{organisaties.length} organisaties</span>
          <span>{aantalKantoren} accountantskantoren</span>
          <span>{aantalOpdrachten} opdrachten</span>
        </p>
      </div>

      <section className="kaart">
        <h2>Waar komt het vandaan?</h2>
        <table>
          <thead>
            <tr>
              <th>Bron</th>
              <th>Wat wij eruit halen</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td>
                <a
                  href="https://www.jaarverantwoordingzorg.nl"
                  rel="noreferrer nofollow"
                  target="_blank"
                >
                  Jaarverantwoording Zorg (DigiMV)
                </a>
              </td>
              <td>
                De wettelijk verplichte jaarverantwoording van zorgaanbieders, met de
                gedeponeerde accountantsverklaring. Daaruit lezen wij het
                <strong> kantoor</strong>, het <strong>soort verklaring</strong> en het
                <strong> oordeel</strong>.
              </td>
            </tr>
            <tr>
              <td>
                <a
                  href="https://www.afm.nl/nl-nl/sector/registers/vergunningenregisters/accountantsorganisaties"
                  rel="noreferrer nofollow"
                  target="_blank"
                >
                  AFM-vergunningenregister
                </a>
              </td>
              <td>
                De officiële lijst van accountantsorganisaties met een Wta-vergunning,
                inclusief wie een OOB-vergunning heeft. Een kantoornaam die wij in een
                verklaring lezen moet in deze lijst voorkomen — anders leggen wij hem
                niet vast.
              </td>
            </tr>
          </tbody>
        </table>
      </section>

      <section className="kaart">
        <h2>Hoe stellen wij de accountant vast?</h2>
        <ol>
          <li>
            De organisatie wordt opgezocht op <strong>KvK-nummer</strong>, niet op naam:
            bronnen schrijven namen en plaatsen per boekjaar anders.
          </li>
          <li>
            De gedeponeerde accountantsverklaring wordt als tekst gelezen. Er komt{" "}
            <strong>geen AI aan te pas</strong> — het is een letterlijke tekstvergelijking
            tegen de AFM-lijst.
          </li>
          <li>
            Alleen een <strong>controleverklaring</strong> telt. Samenstellings- en
            beoordelingsverklaringen zijn geen wettelijke controle en worden overgeslagen.
          </li>
          <li>
            Wordt het kantoor niet met zekerheid herkend, dan laten wij het veld leeg en
            gaat de zaak naar een handmatige controlewachtrij. Wij gokken niet.
          </li>
        </ol>
      </section>

      <section className="kaart">
        <h2>Wat wij bewust níét vastleggen</h2>
        <ul>
          <li>
            <strong>Geen namen van personen.</strong> Wij leggen uitsluitend de
            accountants<em>organisatie</em> vast, nooit de tekenend accountant of enige
            andere natuurlijke persoon — ook niet in onze ruwe verwerkingsbestanden.
          </li>
          <li>
            <strong>Geen herpublicatie van hele documenten.</strong> Wij tonen
            geëxtraheerde feiten en verwijzen naar de bron; het gedeponeerde stuk zelf
            haal je bij de bronhouder op.
          </li>
          <li>
            <strong>Geen honoraria, geen voorspellingen.</strong> Nog niet — dit is de
            eerste versie met zes velden: organisatie, accountant, opdrachttype,
            boekjaar, sector en bron.
          </li>
        </ul>
      </section>

      <section className="kaart">
        <h2>Hoe compleet is dit?</h2>
        <p>
          Dit is een <strong>demo met een proefselectie</strong>: {organisaties.length}{" "}
          bekende zorginstellingen over de boekjaren 2019 tot en met 2024. De volledige
          zorgsector volgt. Alle {aantalKantoren} bij de AFM geregistreerde
          accountantsorganisaties staan er wél al in.
        </p>
        <p className="klein zacht" style={{ marginBottom: 0 }}>
          Boekjaar 2018 en ouder is niet meer beschikbaar: het bronarchief bewaart een
          voortschrijdend venster van zeven jaargangen en verwijdert oudere jaren.
        </p>
      </section>

      <Doorklik
        items={[
          ...organisaties.slice(0, 3).map((org) => ({
            naar: organisatiePad(org),
            tekst: org.naam,
            toelichting: org.gemeente ?? undefined,
          })),
          { naar: "/wisselingen", tekst: "Alle accountantswisselingen" },
          { naar: sectorPad("zorg"), tekst: "Marktaandelen in de zorg" },
          { naar: "/", tekst: "Terug naar het overzicht" },
        ]}
      />
    </>
  );
}
