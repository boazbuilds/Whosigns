/**
 * URL's en presentatie-hulpjes.
 *
 * URL-vorm: `/organisatie/27268552-stichting-hagaziekenhuis`. Het nummer vooraan
 * is de echte sleutel (KvK voor organisaties, AFM-nummer voor kantoren); de naam
 * erachter is er alleen voor de lezer en voor Google. Zo blijft een link werken
 * als de bron de naam volgend boekjaar anders spelt — precies het probleem dat
 * we in de pipeline al op KvK hebben opgelost (zie adapters/digimv.py).
 */

import type { Kantoor, Organisatie } from "./db";

export function slug(naam: string): string {
  return naam
    .toLowerCase()
    .normalize("NFD")
    .replace(/[̀-ͯ]/g, "") // accenten weg
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 60);
}

/** decodeURIComponent, maar zonder te crashen op een adres als `/sector/50%`.
 *  Next levert params al gedecodeerd aan; een kapot percentteken hoort een
 *  404 op te leveren, geen 500. */
export function veiligGedecodeerd(waarde: string): string {
  try {
    return decodeURIComponent(waarde);
  } catch {
    return waarde;
  }
}

/** Het nummer terug uit de URL halen: alles vóór het eerste koppelteken. */
export function nummerUitSlug(waarde: string): string {
  return veiligGedecodeerd(waarde).split("-")[0];
}

/** Organisaties uit een transparantieverslag hebben geen KvK-nummer (het
 *  verslag noemt alleen namen); die krijgen `o<id>` als sleutel — zelfde
 *  oplossing als `k<id>` voor kantoren zonder AFM-nummer hieronder. */
export function organisatiePad(
  org: Pick<Organisatie, "kvk_nummer" | "naam"> & { id?: number },
): string {
  const sleutel = org.kvk_nummer ?? (org.id != null ? `o${org.id}` : "");
  return `/organisatie/${sleutel}-${slug(org.naam)}`;
}

/** Kantoren zónder AFM-nummer (geen Wta-vergunning, zoals WITh Accountants)
 *  krijgen `k<id>` als sleutel in de URL. Met alleen het AFM-nummer was hun
 *  adres `/kantoor/-with-accountants-b-v` en liep élke link naar zo'n kantoor
 *  dood op een 404 — terwijl juist zij in de goededoelensector de meeste
 *  verklaringen tekenen.
 *
 *  Het id is verplicht, niet optioneel. Zolang het optioneel was gaven drie
 *  aanroepen het niet mee (stijgers en dalers op /kantoren, de
 *  prijsontwikkeling op /honoraria), en daar liep de link alsnog op een 404:
 *  gemeten op 5-10-2026 bij Astrium, Hofsteenge, Ipa-Acon, Kroese Wevers en
 *  DRV, vijf van de 55 kantoren zonder AFM-nummer. Verplicht maakt de
 *  typecontrole er een fout van in plaats van een dode link. */
export function kantoorPad(
  kantoor: Pick<Kantoor, "afm_nummer" | "naam"> & { id: number },
): string {
  const sleutel = kantoor.afm_nummer ?? `k${kantoor.id}`;
  return `/kantoor/${sleutel}-${slug(kantoor.naam)}`;
}

/** Wat een kantoor nu mag, voor het label achter zijn naam. */
export type Vergunningsoort = "oob" | "wta" | "vervallen" | "geen";

/**
 * Eén regel voor het vergunningslabel, voor /zoeken, /kantoren en de
 * kantoorpagina. Op 5-10-2026 had elk van die drie een eigen regel — op AFM-
 * nummer, op wta_vergunning en op actief — en heetten dezelfde kantoren er
 * "geen", "geen Wta-vergunning" en "—".
 *
 * Verdwenen uit het register gaat vóór de vlaggen. De lader haalt die vlaggen
 * weg zodra een nummer verdwijnt, maar tot 5-10-2026 deed hij dat niet: de AFM
 * zelf stond toen vijf weken na haar verdwijning nog met OOB-vlag in de
 * database (migratie 20261005120000). Een achtergebleven vlag mag een
 * vervallen kantoor geen vergunninghouder meer maken.
 *
 * Zonder AFM-nummer is het altijd "geen": dat zijn de kantoren van buiten het
 * register (seed/kantoren_overig.csv), op 5-10-2026 55 van de 291.
 */
export function vergunningSoort(
  kantoor: Pick<Kantoor, "afm_nummer" | "oob_vergunning" | "wta_vergunning" | "actief">,
): Vergunningsoort {
  if (!kantoor.afm_nummer) return "geen";
  if (!kantoor.actief) return "vervallen";
  if (kantoor.oob_vergunning) return "oob";
  if (kantoor.wta_vergunning) return "wta";
  return "geen";
}

export function sectorPad(sector: string): string {
  return `/sector/${slug(sector)}`;
}

/** Het adres van een tekenend accountant. De sleutel komt uit `v_accountant`
 *  en is al genormaliseerd (kleine letters, geen punten, titels vooraan eraf);
 *  `slug()` maakt er alleen nog koppeltekens van. Niet omkeerbaar bij accenten
 *  of een dubbele achternaam, dus de pagina zoekt de echte sleutel op —
 *  `accountantOpSlug()` doet eerst de goedkope gok en valt daarna pas terug. */
export function accountantPad(sleutel: string): string {
  return `/accountant/${slug(sleutel)}`;
}

/** Subsectoren hebben spaties en koppeltekens, dus de slug is niet omkeerbaar;
 *  de pagina zoekt de echte waarde op via de lijst uit de database. */
export function subsectorPad(subsector: string): string {
  return `/subsector/${slug(subsector)}`;
}

/**
 * De plaats van een organisatie zoals de bron hem noemt — meestal de
 * vestigingsplaats, soms de gemeente ("Hoofddorp" naast "Haarlemmermeer").
 * De slug is ook de sleutel waarop schrijfwijzen samengaan: "AMSTERDAM" en
 * "Amsterdam", en "'s-Gravenhage" met en zonder apostrof, krijgen hetzelfde adres.
 */
export function plaatsPad(plaats: string): string {
  return `/plaats/${slug(plaats)}`;
}

/**
 * Onder zoveel organisaties krijgt een plaats geen eigen pagina, en linkt de
 * plaatsnaam op een organisatiepagina nergens heen. Op 5-10-2026 hadden 366
 * van de 732 plaatsen één organisatie en 134 er twee — een pagina met alleen
 * de organisatie waar je vandaan kwam is een doodlopende klik. Van drie en
 * meer waren er 232.
 */
export const PLAATS_MINIMUM = 3;

/** Alle schrijfwijzen van één plaats, met de naam die de pagina toont. */
export type Plaatsgroep = {
  sleutel: string;
  naam: string;
  schrijfwijzen: string[];
  aantal: number;
};

/**
 * Plaatsnamen samennemen die alleen in hoofdletters, accenten of leestekens
 * verschillen — precies wat `slug()` gelijkmaakt, en niets meer. Op 5-10-2026
 * stonden er 846 schrijfwijzen in voor 732 plaatsen: "AMSTERDAM" naast
 * "Amsterdam", vier vormen van "'s-Gravenhage". Een andere naam voor dezelfde
 * gemeente ("Den Haag") blijft apart: dat samennemen zou een gok zijn over wat
 * de bron bedoelde.
 *
 * Als naam de schrijfwijze die niet in kapitalen staat, en daarbinnen de
 * meest voorkomende; bij gelijke stand alfabetisch, zodat de naam niet
 * verspringt met de volgorde van de rijen.
 */
export function plaatsgroepen(plaatsen: string[]): Plaatsgroep[] {
  const perSleutel = new Map<string, Map<string, number>>();
  for (const plaats of plaatsen) {
    const sleutel = slug(plaats);
    if (!sleutel) continue;
    const telling = perSleutel.get(sleutel) ?? new Map<string, number>();
    telling.set(plaats, (telling.get(plaats) ?? 0) + 1);
    perSleutel.set(sleutel, telling);
  }
  const kapitalen = (tekst: string) => tekst === tekst.toUpperCase() ? 1 : 0;
  return [...perSleutel.entries()]
    .map(([sleutel, telling]) => {
      const schrijfwijzen = [...telling.entries()].sort(
        (a, b) =>
          kapitalen(a[0]) - kapitalen(b[0]) || b[1] - a[1] || a[0].localeCompare(b[0], "nl"),
      );
      return {
        sleutel,
        naam: schrijfwijzen[0][0].trim(),
        schrijfwijzen: schrijfwijzen.map(([tekst]) => tekst),
        aantal: schrijfwijzen.reduce((som, [, n]) => som + n, 0),
      };
    })
    .sort((a, b) => b.aantal - a.aantal || a.naam.localeCompare(b.naam, "nl"));
}

// ---------------------------------------------------------------- weergave

/** Kort label voor het oordeel; `null` bij een leeg oordeel. */
export const OORDEEL_LABEL: Record<string, string> = {
  goedkeurend: "goedkeurend",
  beperking: "oordeel met beperking",
  oordeelonthouding: "oordeelonthouding",
  afkeurend: "afkeurend",
};

/** Alles behalve goedkeurend verdient nadruk — dat is de interessante uitzondering. */
export function oordeelOpvallend(oordeel: string | null): boolean {
  return oordeel !== null && oordeel !== "goedkeurend";
}

export const OPDRACHT_LABEL: Record<string, string> = {
  wettelijke_controle: "wettelijke controle",
  vrijwillige_controle: "vrijwillige controle",
  // Vastgesteld uit de verklaring: een controleverklaring bij een WNT- of
  // productieverantwoording is een andere opdracht dan de jaarrekeningcontrole.
  wnt_verantwoording: "controle WNT-verantwoording",
  productieverantwoording: "controle productieverantwoording",
  subsidieverklaring: "subsidieverklaring",
  controle_onbepaald: "controle, voorwerp onbekend",
  beoordeling: "beoordelingsopdracht",
  samenstelling: "samenstellingsopdracht",
  subsidie: "subsidieverklaring",
  isae: "ISAE-opdracht",
};

/** Alleen dit type is een wettelijke controle van de jaarrekening. */
/**
 * In welke groep een opdracht valt, voor de weergave.
 *
 * Dit onderscheid is de kern van wat WhoSigns laat zien, en het was op de
 * pagina's niet te zien: het type stond er als grijze tekst, waardoor een
 * controleverklaring bij een WNT-verantwoording er precies zo uitzag als een
 * jaarrekeningcontrole. Dat zijn heel verschillende dingen.
 *
 *   wettelijk   De controle die de wet voorschrijft. Negen van de tien
 *               opdrachten in de database. Dit is de norm, dus rustig gezet.
 *   vrijwillig  Een volledige controle, maar de organisatie was er niet toe
 *               verplicht. Telt mee in marktaandelen (zie CONTROLE_TYPES).
 *   anders      GEEN jaarrekeningcontrole. Een verklaring bij een WNT-opgave,
 *               een productieverantwoording of een subsidieafrekening gaat
 *               over één onderwerp, niet over de jaarrekening. Die mag je
 *               nooit lezen als "de accountant heeft de jaarrekening
 *               gecontroleerd" — daarom springt deze groep eruit.
 *   onbekend    Er stond een controleverklaring, maar waarover precies was
 *               niet vast te stellen.
 */
export type Soortgroep = "wettelijk" | "vrijwillig" | "anders" | "onbekend";

export const SOORTGROEP: Record<string, Soortgroep> = {
  wettelijke_controle: "wettelijk",
  vrijwillige_controle: "vrijwillig",
  wnt_verantwoording: "anders",
  productieverantwoording: "anders",
  subsidieverklaring: "anders",
  subsidie: "anders",
  beoordeling: "anders",
  samenstelling: "anders",
  isae: "anders",
  controle_onbepaald: "onbekend",
};

/** Korte uitleg per soort, voor de titel-tekst bij het label. */
export const SOORT_UITLEG: Record<string, string> = {
  wettelijke_controle:
    "Controle van de jaarrekening die de wet voorschrijft.",
  vrijwillige_controle:
    "Volledige controle van de jaarrekening, terwijl de organisatie daartoe niet verplicht was.",
  wnt_verantwoording:
    "Verklaring bij de opgave van topinkomens (WNT) — niet bij de jaarrekening.",
  productieverantwoording:
    "Verklaring bij de productie- of omzetopgave aan een zorgverzekeraar of gemeente — niet bij de jaarrekening.",
  subsidieverklaring:
    "Verklaring bij de afrekening van een subsidie — niet bij de jaarrekening.",
  controle_onbepaald:
    "Er is een controleverklaring aangetroffen, maar waarover die precies gaat was niet vast te stellen.",
};

export const WETTELIJKE_CONTROLE = "wettelijke_controle";

/** De typen die de SQL-views meetellen in marktaandelen en wisselingen
 *  (migratie 20260730000000: wettelijk én vrijwillig). Elke pagina die zelf
 *  controles telt, hoort op déze set te filteren — de subsectorpagina telde
 *  alleen wettelijke en sprak daarmee de sectorpagina tegen, een verschil van
 *  ruim duizend vrijwillige controles. */
export const CONTROLE_TYPES: readonly string[] = [
  "wettelijke_controle",
  "vrijwillige_controle",
];

/** Nederlandse notatie voor aantallen: 1.142 in plaats van 1142. */
export function nl(n: number): string {
  return n.toLocaleString("nl-NL");
}

/**
 * Een percentage in Nederlandse notatie: "18,3%". Tot september 2026 stond er
 * op de meeste pagina's "18.3%" — een Engelse punt midden in een Nederlandse
 * zin, terwijl de honorariapagina er al een komma zette.
 */
export function procent(waarde: number, decimalen = 1): string {
  return `${waarde.toLocaleString("nl-NL", {
    minimumFractionDigits: decimalen,
    maximumFractionDigits: decimalen,
  })}%`;
}

/**
 * Een bedrag in hele euro's, Nederlands genoteerd. `null` blijft null, zodat de
 * pagina zelf beslist wat "niet opgegeven" eruitziet — een honorarium van nul is
 * iets anders dan een honorarium dat niet is verantwoord, en €0 tonen waar de
 * bron niets zegt zou een bewering zijn.
 */
export function euro(bedrag: number | null | undefined): string | null {
  if (bedrag === null || bedrag === undefined) return null;
  return `€ ${Math.round(bedrag).toLocaleString("nl-NL")}`;
}

export function jarenReeks(jaren: number[]): string {
  if (!jaren.length) return "—";
  const min = Math.min(...jaren);
  const max = Math.max(...jaren);
  return min === max ? `${min}` : `${min}–${max}`;
}

/** "6 boekjaren" / "1 boekjaar" — voorkomt "1 boekjaren". */
export function aantalJaren(n: number): string {
  return `${n} ${n === 1 ? "boekjaar" : "boekjaren"}`;
}

export function aantalControles(n: number): string {
  return `${n} ${n === 1 ? "controle" : "controles"}`;
}

// Meervoud voor de aantallen in de kopregels. Zonder dit stond er "1 organisaties"
// op elke zoekopdracht met één treffer, en dat is precies waar iemand het eerst
// naar kijkt. Alles in Nederlandse notatie: "5.146 opdrachten", niet "5146".
export function aantalOrganisaties(n: number): string {
  return `${nl(n)} ${n === 1 ? "organisatie" : "organisaties"}`;
}

export function aantalKantoren(n: number): string {
  return `${nl(n)} ${n === 1 ? "accountantskantoor" : "accountantskantoren"}`;
}

export function aantalWisselingen(n: number): string {
  return `${nl(n)} ${n === 1 ? "wisseling" : "wisselingen"}`;
}

export function aantalOpdrachten(n: number): string {
  return `${nl(n)} ${n === 1 ? "opdracht" : "opdrachten"}`;
}

export function aantalPlaatsen(n: number): string {
  return `${nl(n)} ${n === 1 ? "plaats" : "plaatsen"}`;
}

export function aantalClienten(n: number): string {
  return `${nl(n)} ${n === 1 ? "cliënt" : "cliënten"}`;
}

export function aantalGunningen(n: number): string {
  return `${nl(n)} ${n === 1 ? "gunning" : "gunningen"}`;
}

/**
 * Eerste letter groot, maar afkortingen met rust laten.
 *
 * "zorg" wordt "Zorg"; "OOB" blijft "OOB". Zonder die uitzondering stond er
 * "OOB" in de database en "Oob" in het menu.
 */
export function hoofdletter(tekst: string): string {
  if (!tekst) return tekst;
  if (tekst === tekst.toUpperCase()) return tekst;
  return tekst.charAt(0).toUpperCase() + tekst.slice(1);
}

/**
 * Wat een sector inhoudt, in één zin — voor de tegels en de sectorpagina.
 *
 * Sectornamen komen uit de pipeline (`sector` op de organisatie), dus dit is
 * bewust een opzoeklijst met een terugval: een nieuwe sector verschijnt gewoon
 * zonder zin, in plaats van de pagina te breken.
 */
export const SECTOR_UITLEG: Record<string, string> = {
  zorg:
    "Ziekenhuizen, ouderenzorg, ggz en gehandicaptenzorg — uit de jaarverantwoording " +
    "die elke zorgaanbieder moet publiceren.",
  OOB:
    "Organisaties van openbaar belang: beursfondsen, banken en verzekeraars. " +
    "Uit de transparantieverslagen van de OOB-kantoren en het AFM-register.",
  woningcorporaties:
    "Woningcorporaties, uit de verantwoordingsinformatie (dVi) die zij jaarlijks " +
    "bij de Autoriteit woningcorporaties indienen.",
  "goede doelen":
    "Goede doelen met een CBF-erkenning, uit hun gepubliceerde jaarverslagen.",
  overheid:
    "Gemeenten, provincies, waterschappen en veiligheidsregio's, uit Europees " +
    "aanbestede accountantsdiensten (TED). Hier staat wie er benoemd is en " +
    "wanneer — het oordeel bij de jaarrekening zit in deze bron niet.",
  // De grove bedrijfsleven-indeling op SBI-hoofdgroep, gevuld vanuit
  // aangeleverd marktonderzoek (zie pipeline/laad_marktonderzoek.py).
  "landbouw en visserij": "Agrarische bedrijven en visserij, ingedeeld op SBI-code.",
  "industrie en bouw":
    "Productie-, energie- en bouwbedrijven, ingedeeld op SBI-code.",
  handel: "Groothandel, detailhandel en autohandel, ingedeeld op SBI-code.",
  "transport en logistiek":
    "Vervoer, opslag, post en logistiek, ingedeeld op SBI-code.",
  "ict en media": "Software, IT-diensten, uitgevers en media, ingedeeld op SBI-code.",
  "financiële dienstverlening":
    "Holdings, financierings- en verzekeringsbedrijven, ingedeeld op SBI-code.",
  vastgoed: "Verhuur en handel in onroerend goed, ingedeeld op SBI-code.",
  "zakelijke dienstverlening":
    "Advies, advocatuur, uitzenders en overige zakelijke diensten, ingedeeld op SBI-code.",
  "overig bedrijfsleven":
    "Bedrijven buiten de andere hokjes: horeca, cultuur, sport en overige diensten.",
};

/** Datum uit de database als "13 augustus 2007"; null blijft een streepje. */
export function datumNL(waarde: string | null | undefined): string {
  if (!waarde) return "—";
  const datum = new Date(waarde);
  if (Number.isNaN(datum.getTime())) return waarde;
  return datum.toLocaleDateString("nl-NL", {
    day: "numeric",
    month: "long",
    year: "numeric",
  });
}

/**
 * De sleutel uit een slug uit elkaar halen: is het een registernummer of een
 * intern id? `k12` en `o12` betekenen "rij 12 in de tabel"; al het andere is
 * een AFM- of KvK-nummer.
 */
export function sleutelUitSlug(waarde: string): { nummer: string; id: number | null } {
  const nummer = nummerUitSlug(waarde);
  const intern = /^[ko](\d+)$/.exec(nummer);
  return { nummer, id: intern ? Number(intern[1]) : null };
}

/**
 * Korte weergavenaam van een kantoor: "PricewaterhouseCoopers Accountants N.V."
 * wordt "PricewaterhouseCoopers".
 *
 * Waarom: in een ranglijst staan tientallen namen onder elkaar, en de helft
 * daarvan bestaat uit rechtsvorm en beroepsaanduiding. Voluit brak "Pricewater-
 * houseCoopers" midden in het woord af over drie regels; kort past het op één.
 * De volledige naam blijft in het `title`-attribuut en op de kantoorpagina zelf
 * staan, dus er gaat niets verloren.
 *
 * Bewust van achteren strippen en alleen bekende sluitwoorden: zo blijft
 * "Accountants voor de Gezondheidszorg" heel, want daar is "Accountants" de
 * naam en niet het aanhangsel.
 */
const SLUITWOORDEN = new Set([
  "bv", "b.v.", "nv", "n.v.", "llp", "ua", "u.a.", "ba", "b.a.", "se",
  "accountants", "accountant", "registeraccountants", "registeraccountant",
  "audit", "auditors", "assurance", "accountancy", "controle", "controlepraktijk",
  "adviseurs", "adviseur", "advies", "belastingadviseurs", "fiscalisten",
  "en", "&", "group", "groep", "nederland", "netherlands",
]);

export function kortKantoor(naam: string): string {
  const opgeschoond = naam
    .replace(/\s*\((?:netherlands|nederland)\)/gi, "")
    .replace(/\s+/g, " ")
    .trim();
  const woorden = opgeschoond.split(" ");
  while (woorden.length > 1) {
    const laatste = woorden[woorden.length - 1].toLowerCase().replace(/[,.]$/, "");
    if (!SLUITWOORDEN.has(laatste) && !SLUITWOORDEN.has(`${laatste}.`)) break;
    woorden.pop();
  }
  const kort = woorden.join(" ").replace(/[\s&,]+$/, "");
  return kort || opgeschoond || naam;
}
