import type { Metadata } from "next";
import Link from "next/link";
import { sectoren } from "@/lib/db";
import { sectorPad } from "@/lib/paden";
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
        placeholder="Zoek een organisatie of accountantskantoor"
        aria-label="Zoek een organisatie of accountantskantoor"
      />
      <button type="submit">Zoek</button>
    </form>
  );
}

export default async function RootLayout({ children }: { children: React.ReactNode }) {
  // Het menu noemt de sectoren die er écht zijn. Hier stond "Zorg" hardgecodeerd,
  // waardoor de goede doelen nergens in de navigatie voorkwamen. Faalt de database,
  // dan vervallen alleen deze links — de rest van het menu blijft staan, want een
  // stukgelopen menu maakt élke pagina onbruikbaar.
  const sectorlijst = await sectoren().catch(() => []);

  return (
    <html lang="nl">
      <body>
        <header className="kop">
          <div className="omhulsel kop-binnen">
            <Link href="/" className="merk">
              WhoSigns
            </Link>
            <Zoekbalk />
            <nav className="kop-menu" aria-label="Hoofdmenu">
              <Link href="/organisaties">Organisaties</Link>
              <Link href="/wisselingen">Wisselingen</Link>
              {sectorlijst.map((sector) => (
                <Link key={sector.naam} href={sectorPad(sector.naam)}>
                  {sector.naam.charAt(0).toUpperCase() + sector.naam.slice(1)}
                </Link>
              ))}
            </nav>
          </div>
        </header>

        <main className="omhulsel">{children}</main>
      </body>
    </html>
  );
}
