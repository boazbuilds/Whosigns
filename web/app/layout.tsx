import type { Metadata } from "next";
import Link from "next/link";
import { IBM_Plex_Sans, Instrument_Serif } from "next/font/google";
import { Analytics } from "@vercel/analytics/next";
import { laatstBijgewerkt, sectoren, tel } from "@/lib/db";
import { datumNL, hoofdletter, nl, sectorPad } from "@/lib/paden";
import "./globals.css";

/**
 * Twee letters, en dat is een keuze.
 *
 * Instrument Serif voor de kop van het blad en voor grote getallen: hoog
 * contrast, smal, redactioneel — de letter van een jaarboek, niet die van een
 * dashboard. IBM Plex Sans voor alle tekst en tabellen: technisch van karakter,
 * met echte tabelcijfers, en herkenbaar géén standaard systeemletter.
 *
 * `next/font` haalt ze bij de build op en serveert ze vanaf ons eigen domein:
 * geen verzoek naar Google vanaf de pagina van een bezoeker, en geen extra
 * afhankelijkheid in package.json.
 */
const serif = Instrument_Serif({
  subsets: ["latin"],
  weight: "400",
  style: ["normal", "italic"],
  display: "swap",
  variable: "--letter-serif",
});

const schreefloos = IBM_Plex_Sans({
  subsets: ["latin"],
  weight: ["400", "500", "600"],
  display: "swap",
  variable: "--letter-tekst",
});

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
  // staan, want een stukgelopen menu maakt élke pagina onbruikbaar. Hetzelfde
  // geldt voor de datumregel: liever geen datum dan geen site.
  const [sectorlijst, bijgewerkt, organisatieTotaal] = await Promise.all([
    sectoren().catch(() => []),
    laatstBijgewerkt().catch(() => null),
    tel("organisaties").catch(() => 0),
  ]);

  return (
    <html lang="nl" className={`${serif.variable} ${schreefloos.variable}`}>
      <body>
        {/* Titelkop van het blad: naam, ondertitel en een datumregel — zoals de
            kop van een jaarboek. Hij scrollt gewoon weg; alleen de rubriekenbalk
            eronder blijft plakken, want dáár navigeer je mee. */}
        <header className="titelkop">
          <div className="omhulsel titelkop-binnen">
            <Link href="/" className="merk">
              Who<em>Signs</em>
            </Link>
            <p className="ondertitel">
              Register van accountantscontroles in Nederland
            </p>
            <p className="datumregel">
              {bijgewerkt ? <span>Stand per {datumNL(bijgewerkt)}</span> : null}
              {organisatieTotaal ? (
                <span>{nl(organisatieTotaal)} organisaties</span>
              ) : null}
              <span>uit openbare bronnen</span>
            </p>
          </div>
        </header>

        <div className="rubrieken">
          <div className="omhulsel rubrieken-binnen">
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
                            <span className="telling">{nl(sector.aantal)}</span>
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
        </div>

        <main className="omhulsel">{children}</main>

        {/* Colofon, geen voettekst-met-linkjes: waar het vandaan komt en wat het
            wel en niet is. */}
        <footer className="colofon">
          <div className="omhulsel colofon-binnen">
            <div>
              <p className="colofon-titel">WhoSigns</p>
              <p>
                Samengesteld uit openbare bronnen — jaarverantwoordingen,
                transparantieverslagen, het AFM-register en het CBF. Bij elke
                opdracht staat de vindplaats vermeld.
              </p>
              <p className="klein">
                Geen advies, geen oordeel over kantoren. Een wisseling is
                afgeleid uit de historie, niet uit een aankondiging.
              </p>
            </div>
            <nav aria-label="Voettekst">
              <Link href="/sectoren">Sectoren</Link>
              <Link href="/kantoren">Kantoren</Link>
              <Link href="/wisselingen">Wisselingen</Link>
              <Link href="/bevindingen">Oordelen</Link>
              <Link href="/organisaties">Organisaties</Link>
            </nav>
          </div>
        </footer>

        {/* Bezoekersstatistiek van Vercel, de partij die de site toch al host.
            Telt paginaweergaven, land en van welke pagina iemand kwam — zonder
            cookies en zonder de bezoeker over sites heen te volgen, dus er
            hoeft geen cookiemelding bij. Werkt pas als Web Analytics in het
            Vercel-project aan staat; staat het uit, dan doet dit niets.
            Weg willen? Deze regel en de import eruit. */}
        <Analytics />
      </body>
    </html>
  );
}
