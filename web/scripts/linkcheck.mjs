/**
 * Linkcontrole voor CI: volgt de interne links van een draaiende productiebuild
 * en faalt bij elke kapotte.
 *
 * Waarom: tot 5-10-2026 bouwde CI de site niet eens. Een kapotte link of een
 * pagina die omvalt zag je pas na de merge, op de echte site. Een lokale
 * kruipronde vond toen twee 404's en vijf kantoorlinks zonder sleutel
 * ("/kantoor/-..."), en een organisatiebeschrijving met "KvK null" erin.
 *
 * Wat het doet: begint bij de rubriekpagina's, haalt elke gevonden interne
 * link op en faalt op
 *   - een status anders dan 200;
 *   - een link die met /kantoor/- of /organisatie/- begint: een kantoor of
 *     organisatie zonder sleutel, die altijd een 404 geeft;
 *   - "null" of "undefined" in de <title> of de beschrijving.
 *
 * Bewust begrensd: per soort pagina (alles na /kantoor/ is één soort, enz.)
 * hooguit PER_SOORT stuks, en nooit meer dan MAX_PAGINAS in totaal. Het gaat
 * om de klasse fouten, niet om alle 17.653 organisaties. /zoeken wordt nooit
 * opgevraagd: die pagina schrijft elke zoekopdracht in de zoeklog van de
 * productiedatabase.
 *
 * Gebruik: node scripts/linkcheck.mjs [basis-url]   (standaard 127.0.0.1:3000)
 */

const BASIS = (process.argv[2] ?? process.env.LINKCHECK_BASIS ?? "http://127.0.0.1:3000").replace(
  /\/$/,
  "",
);
const BEGIN = ["/", "/kantoren", "/sectoren", "/wisselingen", "/honoraria", "/bevindingen"];
const PER_SOORT = 20;
const MAX_PAGINAS = 220;
const TEGELIJK = 4;
/** Na zoveel seconden geen nieuwe pagina's meer: CI hoort niet te slepen. */
const TIJDSLIMIET_S = 150;

const start = Date.now();
const gezien = new Set();
const perSoort = new Map();
const wachtrij = [];
const fouten = [];
let opgehaald = 0;

/** /kantoor/13000311-bdo → "kantoor"; /kantoren?jaar=2024 → "kantoren". */
function soort(pad) {
  return pad.split("?")[0].split("/")[1] || "start";
}

function overslaan(pad) {
  return (
    pad.startsWith("/zoeken") ||
    pad.includes("?q=") ||
    pad.includes("&q=") ||
    pad.startsWith("/_next/") ||
    /\.[a-z0-9]+(\?|$)/i.test(pad.split("?")[0])
  );
}

function ontsnap(tekst) {
  return tekst
    .replace(/&amp;/g, "&")
    .replace(/&quot;/g, '"')
    .replace(/&#x27;|&#39;/g, "'")
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">");
}

function voegToe(pad, vanaf) {
  if (gezien.has(pad) || overslaan(pad)) return;
  const s = soort(pad);
  const aantal = perSoort.get(s) ?? 0;
  if (!BEGIN.includes(pad) && aantal >= PER_SOORT) return;
  if (gezien.size >= MAX_PAGINAS) return;
  gezien.add(pad);
  perSoort.set(s, aantal + 1);
  wachtrij.push({ pad, vanaf });
}

async function controleer({ pad, vanaf }) {
  let antwoord;
  try {
    antwoord = await fetch(BASIS + pad, { redirect: "manual" });
  } catch (fout) {
    fouten.push(`${pad} (gevonden op ${vanaf}): niet bereikbaar: ${fout.message}`);
    return;
  }
  opgehaald += 1;
  if (antwoord.status !== 200) {
    fouten.push(`${pad} (gevonden op ${vanaf}): status ${antwoord.status}`);
    return;
  }
  const html = await antwoord.text();

  const titel = /<title>([^<]*)<\/title>/.exec(html)?.[1] ?? "";
  const beschrijving = /<meta name="description" content="([^"]*)"/.exec(html)?.[1] ?? "";
  for (const [wat, tekst] of [
    ["titel", titel],
    ["beschrijving", beschrijving],
  ]) {
    if (/\b(null|undefined)\b/.test(ontsnap(tekst))) {
      fouten.push(`${pad}: ${wat} bevat null/undefined: "${ontsnap(tekst)}"`);
    }
  }

  for (const [, ruw] of html.matchAll(/<a\b[^>]*\bhref="([^"]+)"/g)) {
    const href = ontsnap(ruw).split("#")[0];
    if (!href.startsWith("/") || href.startsWith("//")) continue;
    if (href.startsWith("/kantoor/-") || href.startsWith("/organisatie/-")) {
      fouten.push(`${pad}: link zonder sleutel: ${href}`);
      continue;
    }
    voegToe(href, pad);
  }
}

async function werker() {
  while (wachtrij.length) {
    if ((Date.now() - start) / 1000 > TIJDSLIMIET_S) return;
    await controleer(wachtrij.shift());
  }
}

for (const pad of BEGIN) voegToe(pad, "(begin)");
// Werkers tot de wachtrij leeg blijft: een werker die stopt omdat de rij even
// leeg is, terwijl een andere nog links aan het verzamelen is, mag opnieuw.
while (wachtrij.length && (Date.now() - start) / 1000 <= TIJDSLIMIET_S) {
  await Promise.all(Array.from({ length: TEGELIJK }, werker));
}

const duur = ((Date.now() - start) / 1000).toFixed(0);
const soorten = [...perSoort.entries()].map(([s, n]) => `${s} ${n}`).join(", ");
console.log(`${opgehaald} pagina's opgehaald in ${duur} s (${soorten}).`);
if (wachtrij.length) {
  console.log(`Tijdslimiet bereikt; ${wachtrij.length} pagina's niet meer bekeken.`);
}
if (fouten.length) {
  console.log(`\n${fouten.length} fout(en):`);
  for (const fout of fouten) console.log(`  ${fout}`);
  process.exit(1);
}
console.log("Geen kapotte links.");
