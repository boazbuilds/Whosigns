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
 *  verklaringen tekenen. */
export function kantoorPad(
  kantoor: Pick<Kantoor, "afm_nummer" | "naam"> & { id?: number },
): string {
  const sleutel = kantoor.afm_nummer ?? (kantoor.id != null ? `k${kantoor.id}` : "");
  return `/kantoor/${sleutel}-${slug(kantoor.naam)}`;
}

export function sectorPad(sector: string): string {
  return `/sector/${slug(sector)}`;
}

/** Subsectoren hebben spaties en koppeltekens, dus de slug is niet omkeerbaar;
 *  de pagina zoekt de echte waarde op via de lijst uit de database. */
export function subsectorPad(subsector: string): string {
  return `/subsector/${slug(subsector)}`;
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
