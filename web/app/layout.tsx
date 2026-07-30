import type { Metadata } from "next";
import Link from "next/link";
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

export default function RootLayout({ children }: { children: React.ReactNode }) {
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
              <Link href="/sector/zorg">Zorg</Link>
            </nav>
          </div>
        </header>

        <main className="omhulsel">{children}</main>
      </body>
    </html>
  );
}
