import type { Metadata } from "next";
import Link from "next/link";
import { sectoren } from "@/lib/db";
import { hoofdletter, sectorPad } from "@/lib/paden";
import "./globals.css";

export const metadata: Metadata = {
  title: {
    default: "WhoSigns — wie controleert wie?",
    template: "%s — WhoSigns",
  },
  description:
    "Openbare database van assurance-relaties in Nederland: welke accountant " +
    "controleert welke organisatie, in welk boekjaar, en wanneer werd er gewisseld.",
  // Nog niet vindbaar in zoekmachines. Beslissing #2 (publiek gaan) staat open;
  // zodra die valt, mag dit blok weg — zie docs/beslissingen.md.
  robots: { index: false, follow: false },
};

function Zoekbalk() {
  return (
    <form className="zoekbalk" action="/zoeken" method="get" role="search">
      <input
        type="search"
        name="q"
        placeholder="Zoek een organisatie of kantoor"
        aria-label="Zoek een organisatie of accountantskantoor"
      />
      <button type="submit">Zoek</button>
    </form>
  );
}

export default async function RootLayout({ children }: { children: React.ReactNode }) {
  // Het menu noemt de sectoren die er écht zijn. Hier stond "Zorg" hardgecodeerd,
  // waardoor de goede doelen nergens in de navigatie voorkwamen. Faalt de database,
  // dan vervalt alleen de inhoud van de uitklapper — de rest van het menu blijft
  // staan, want een stukgelopen menu maakt élke pagina onbruikbaar.
  const sectorlijst = await sectoren().catch(() => []);

  return (
    <html lang="nl">
      <body>
        <header className="kop">
          <div className="omhulsel kop-binnen">
            <Link href="/" className="merk">
              <span className="merk-teken" aria-hidden="true">
                S
              </span>
              <span className="merk-woord">
                Who<em>Signs</em>
              </span>
            </Link>

            <nav className="hoofdmenu-balk" aria-label="Hoofdmenu">
              <ul className="hoofdmenu">
                {/* De knop is zélf een link naar het overzicht: op een telefoon
                    gaat een uitklapper niet open door erboven te zweven, en dan
                    moet je er nog steeds komen. */}
                <li className="heeft-uitklap">
                  <Link href="/sectoren">Sectoren</Link>
                  {sectorlijst.length > 0 ? (
                    <ul className="uitklap">
                      {sectorlijst.map((sector) => (
                        <li key={sector.naam}>
                          <Link href={sectorPad(sector.naam)}>
                            <span>{hoofdletter(sector.naam)}</span>
                            <span className="telling">{sector.aantal}</span>
                          </Link>
                        </li>
                      ))}
                      <li>
                        <hr />
                      </li>
                      <li>
                        <Link href="/sectoren">
                          <span>Alle sectoren vergelijken</span>
                        </Link>
                      </li>
                    </ul>
                  ) : null}
                </li>
                <li>
                  <Link href="/kantoren">Kantoren</Link>
                </li>
                <li>
                  <Link href="/wisselingen">Wisselingen</Link>
                </li>
                <li>
                  <Link href="/bevindingen">Oordelen</Link>
                </li>
                <li>
                  <Link href="/organisaties">Organisaties</Link>
                </li>
              </ul>
            </nav>

            <Zoekbalk />
          </div>
        </header>

        <main className="omhulsel">{children}</main>

        <footer className="voet">
          <div className="omhulsel voet-binnen">
            <span>
              WhoSigns — wie controleert wie. Alles uit openbare bronnen, met de
              vindplaats erbij.
            </span>
            <nav aria-label="Voettekst">
              <Link href="/sectoren">Sectoren</Link>
              <Link href="/kantoren">Kantoren</Link>
              <Link href="/wisselingen">Wisselingen</Link>
              <Link href="/bevindingen">Oordelen</Link>
            </nav>
          </div>
        </footer>
      </body>
    </html>
  );
}
