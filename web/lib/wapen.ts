/**
 * Kantoorwapens: het schildje dat bij een kantoor hoort.
 *
 * Waarom niet het échte logo: de logo's van accountantskantoren zijn
 * beeldmerken van die kantoren. Ze hier hosten en tonen is auteursrechtelijk
 * niet vanzelfsprekend, en ze van hun site trekken maakt de pagina afhankelijk
 * van een server die wij niet beheren. Daarom een eigen beeldmerk: een
 * monogram in een vaste kleur, zoals een clubwapen op een voetbalsite.
 *
 * Voor de kantoren die iedereen kent staat de kleur hieronder met de hand
 * ingesteld op de huiskleur waar het kantoor om bekendstaat — dan herken je
 * Deloitte-groen of KPMG-blauw meteen tussen de rijen. Al het andere krijgt
 * een kleur die uit de naam wordt berekend: dezelfde naam geeft altijd
 * dezelfde kleur, dus een kantoor ziet er overal op de site hetzelfde uit.
 */

export type Wapen = {
  /** Eén tot drie tekens; wat er in het schildje staat. */
  monogram: string;
  /** Achtergrond van het schildje. */
  kleur: string;
  /** Tekstkleur die daarop leesbaar is. */
  inkt: string;
};

/**
 * Handmatig ingesteld voor de bekende namen. De sleutel is een stuk van de
 * genormaliseerde naam; de eerste die past wint, dus zet specifieke namen
 * ("forvis mazars") vóór algemene ("mazars").
 */
const BEKEND: { bevat: string; monogram: string; kleur: string; inkt?: string }[] = [
  { bevat: "deloitte", monogram: "D", kleur: "#0f8b3f" },
  { bevat: "kpmg", monogram: "K", kleur: "#00338d" },
  { bevat: "pricewaterhousecoopers", monogram: "PwC", kleur: "#d04a02" },
  { bevat: "ernst young", monogram: "EY", kleur: "#2e2e38" },
  { bevat: "ey accountants", monogram: "EY", kleur: "#2e2e38" },
  { bevat: "bdo", monogram: "BDO", kleur: "#c8102e" },
  { bevat: "forvis mazars", monogram: "FM", kleur: "#0b3d67" },
  { bevat: "mazars", monogram: "M", kleur: "#0b3d67" },
  { bevat: "grant thornton", monogram: "GT", kleur: "#5c0f8b" },
  { bevat: "baker tilly", monogram: "BT", kleur: "#00857d" },
  { bevat: "flynth", monogram: "F", kleur: "#0a6cb4" },
  { bevat: "alfa accountants", monogram: "A", kleur: "#7a1f3d" },
  { bevat: "jong laan", monogram: "JL", kleur: "#1a5e3a" },
  { bevat: "countus", monogram: "C", kleur: "#b8482a" },
  { bevat: "moore", monogram: "MO", kleur: "#144a8f" },
  { bevat: "with accountants", monogram: "W", kleur: "#116a5e" },
  { bevat: "verstegen", monogram: "V", kleur: "#3b4a6b" },
  { bevat: "dubois", monogram: "DB", kleur: "#4a2f6b" },
  { bevat: "mth", monogram: "MTH", kleur: "#1f6f8b" },
  { bevat: "abab", monogram: "AB", kleur: "#8a5a12" },
  { bevat: "hlb", monogram: "HLB", kleur: "#0c5a7a" },
  { bevat: "crowe", monogram: "CR", kleur: "#243b6b" },
  { bevat: "rsm", monogram: "RSM", kleur: "#1c3f94" },
  { bevat: "mgg", monogram: "MG", kleur: "#5b6b1f" },
];

/**
 * Kleurenwaaier voor alle overige kantoren. Bewust donker en verzadigd, zodat
 * wit erop leesbaar blijft en de rij schildjes een familie vormt in plaats van
 * een zak snoep.
 */
const WAAIER = [
  "#2f4858",
  "#1b5e73",
  "#3d5a3f",
  "#6b3f2a",
  "#4a3b6b",
  "#7a3b52",
  "#2b5f4f",
  "#5c4b1f",
  "#33507a",
  "#6b2f3f",
  "#265c5c",
  "#4f3a2a",
];

function normaliseer(naam: string): string {
  return naam
    .toLowerCase()
    .normalize("NFD")
    .replace(/[̀-ͯ]/g, "")
    .replace(/[^a-z0-9]+/g, " ")
    .trim();
}

/** Woorden die niets zeggen over wélk kantoor het is. */
const RUIS = new Set([
  "accountants",
  "accountant",
  "audit",
  "assurance",
  "registeraccountants",
  "registeraccountant",
  "adviseurs",
  "advies",
  "en",
  "the",
  "van",
  "de",
  "der",
  "het",
  "bv",
  "nv",
  "b",
  "n",
  "v",
  "cv",
  "maatschap",
  "group",
  "groep",
  "holding",
  "nederland",
  "controle",
  "controlepraktijk",
]);

function monogramUit(naam: string): string {
  const woorden = normaliseer(naam)
    .split(" ")
    .filter((w) => w && !RUIS.has(w));
  if (woorden.length === 0) return naam.slice(0, 2).toUpperCase() || "?";
  // Eén woord: de eerste twee letters lezen prettiger dan één losse letter
  // ("Fi" van Finchtree). Meer woorden: de beginletters, hoogstens drie.
  if (woorden.length === 1) return woorden[0].slice(0, 2).toUpperCase();
  return woorden
    .slice(0, 3)
    .map((w) => w[0])
    .join("")
    .toUpperCase();
}

/** Stabiele hash: dezelfde naam geeft altijd dezelfde kleur. */
function hash(tekst: string): number {
  let waarde = 0;
  for (let i = 0; i < tekst.length; i += 1) {
    waarde = (waarde * 31 + tekst.charCodeAt(i)) >>> 0;
  }
  return waarde;
}

export function wapenVoor(naam: string): Wapen {
  const genormaliseerd = normaliseer(naam);
  const bekend = BEKEND.find((k) => genormaliseerd.includes(k.bevat));
  if (bekend) {
    return {
      monogram: bekend.monogram,
      kleur: bekend.kleur,
      inkt: bekend.inkt ?? "#ffffff",
    };
  }
  return {
    monogram: monogramUit(naam),
    kleur: WAAIER[hash(genormaliseerd) % WAAIER.length],
    inkt: "#ffffff",
  };
}
