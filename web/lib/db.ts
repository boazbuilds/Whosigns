/**
 * Leesroute naar Supabase.
 *
 * Bewust zonder bibliotheek: PostgREST (de API van Supabase) is gewoon HTTP, en
 * `fetch` zit al in Next.js. Dat scheelt een afhankelijkheid en spiegelt
 * `pipeline/supabase_client.py`, dat aan de schrijfkant hetzelfde doet.
 *
 * De sleutel hier is de **publishable key**: die mag openbaar zijn en kan
 * uitsluitend lezen — Row Level Security in `supabase/migrations/` geeft
 * `select` aan iedereen en kent bewust géén insert/update/delete-policy.
 * De secret key hoort alleen in GitHub Secrets, nooit in deze map.
 */

const BASIS = process.env.NEXT_PUBLIC_SUPABASE_URL;
const SLEUTEL = process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY;

/** Hoe lang een antwoord hergebruikt mag worden. De pipeline draait wekelijks,
 *  dus een uur is ruim genoeg en houdt het aantal database-verzoeken laag. */
const VERVERS_SECONDEN = 3600;

export class DatabaseFout extends Error {}

async function haal<T>(pad: string): Promise<T[]> {
  if (!BASIS || !SLEUTEL) {
    throw new DatabaseFout(
      "NEXT_PUBLIC_SUPABASE_URL of NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY ontbreekt. " +
        "Zet ze in web/.env.local (lokaal) of in de Vercel-projectinstellingen.",
    );
  }
  const antwoord = await fetch(`${BASIS}/rest/v1/${pad}`, {
    headers: { apikey: SLEUTEL, Authorization: `Bearer ${SLEUTEL}` },
    next: { revalidate: VERVERS_SECONDEN },
  });
  if (!antwoord.ok) {
    throw new DatabaseFout(
      `Supabase gaf ${antwoord.status} op /${pad}: ${await antwoord.text()}`,
    );
  }
  return antwoord.json();
}

async function haalEen<T>(pad: string): Promise<T | null> {
  const rijen = await haal<T>(pad);
  return rijen[0] ?? null;
}

/**
 * PostgREST levert er nooit meer dan duizend per verzoek, ook niet met
 * `limit=10000` erin. Dat faalt stíl: je krijgt de eerste duizend en niets wijst
 * erop dat er meer was. Deze functie haalt ze allemaal, in pagina's.
 *
 * Gebruik dit overal waar het antwoord kan doorgroeien met de dataset. Een
 * afgekapte lijst geeft geen foutmelding maar een verkeerd getal, en dat is erger.
 */
const PAGINA = 1000;

async function haalAlles<T>(pad: string): Promise<T[]> {
  const alles: T[] = [];
  for (;;) {
    const pagina = await haal<T>(`${pad}&limit=${PAGINA}&offset=${alles.length}`);
    alles.push(...pagina);
    if (pagina.length < PAGINA) return alles;
  }
}

/**
 * Alleen tellen, zonder de rijen op te halen. PostgREST zet het totaal in de
 * `content-range`-header (`0-0/74`) als je om `count=exact` vraagt.
 */
export async function tel(tabel: string, filter = ""): Promise<number> {
  if (!BASIS || !SLEUTEL) return 0;
  const antwoord = await fetch(
    `${BASIS}/rest/v1/${tabel}?select=id&limit=1${filter ? `&${filter}` : ""}`,
    {
      headers: {
        apikey: SLEUTEL,
        Authorization: `Bearer ${SLEUTEL}`,
        Prefer: "count=exact",
      },
      next: { revalidate: VERVERS_SECONDEN },
    },
  );
  if (!antwoord.ok) return 0;
  return Number(antwoord.headers.get("content-range")?.split("/")[1] ?? 0);
}

/** PostgREST-lijstfilter: `id=in.(1,2,3)`. Lege lijst = geen verzoek doen. */
function inLijst(waarden: (number | string)[]): string {
  return `(${[...new Set(waarden)].join(",")})`;
}

// ---------------------------------------------------------------- types

export type Organisatie = {
  id: number;
  kvk_nummer: string | null;
  naam: string;
  sector: string | null;
  subsector: string | null;
  gemeente: string | null;
};

export type Kantoor = {
  id: number;
  afm_nummer: string | null;
  naam: string;
  oob_vergunning: boolean;
  website: string | null;
};

export type Bron = {
  url: string | null;
  bron_type: string;
  opgehaald_op: string;
};

/** Eén opdracht met het kantoor en de bron er direct aan vast (PostgREST-embed). */
export type OpdrachtMetKantoor = {
  boekjaar: number;
  type_opdracht: string;
  oordeel: string | null;
  /** Het oordeel zoals de bron het meldt. `oordeel` komt uit de gedeponeerde
   *  verklaring zelf en gaat voor; dit veld vult het gat wanneer de pdf een scan
   *  zonder tekstlaag was. */
  oordeel_gerapporteerd: string | null;
  continuiteitsonzekerheid: boolean | null;
  kantoren: Kantoor | null;
  bronnen: Bron | null;
};

export type OpdrachtMetOrganisatie = {
  boekjaar: number;
  type_opdracht: string;
  oordeel: string | null;
  oordeel_gerapporteerd: string | null;
  continuiteitsonzekerheid: boolean | null;
  organisaties: Organisatie | null;
};

export type Wisseling = {
  organisatie_id: number;
  van_kantoor_id: number;
  naar_kantoor_id: number;
  boekjaar_wissel: number;
};

/** Een wisseling met de namen erbij gezocht — klaar om te tonen. */
export type WisselingVolledig = Wisseling & {
  organisatie: Organisatie | null;
  van: Kantoor | null;
  naar: Kantoor | null;
};

export type Marktaandeel = {
  boekjaar: number;
  sector: string | null;
  kantoor_id: number;
  aantal_controles: number;
  marktaandeel_pct: number;
};

// Honoraria, omzet en de zelfgerapporteerde wisselvlag staan wél in de database
// maar worden hier bewust niet opgevraagd: het MVP toont de zes velden uit
// docs/visie.md. Wie ze wil gebruiken, voegt ze hier toe — niet eerder.
const ORG_VELDEN = "id,kvk_nummer,naam,sector,subsector,gemeente";
const KANTOOR_VELDEN = "id,afm_nummer,naam,oob_vergunning,website";

// ---------------------------------------------------------------- opzoeken

export function organisatieOpKvk(kvk: string) {
  return haalEen<Organisatie>(
    `organisaties?kvk_nummer=eq.${encodeURIComponent(kvk)}&select=${ORG_VELDEN}`,
  );
}

export function kantoorOpAfm(afm: string) {
  return haalEen<Kantoor>(
    `kantoren?afm_nummer=eq.${encodeURIComponent(afm)}&select=${KANTOOR_VELDEN}`,
  );
}

export function organisatiesOpId(ids: number[]) {
  if (!ids.length) return Promise.resolve([]);
  return haal<Organisatie>(`organisaties?id=in.${inLijst(ids)}&select=${ORG_VELDEN}`);
}

export function kantorenOpId(ids: number[]) {
  if (!ids.length) return Promise.resolve([]);
  return haal<Kantoor>(`kantoren?id=in.${inLijst(ids)}&select=${KANTOOR_VELDEN}`);
}

// ---------------------------------------------------------------- opdrachten

/** Alle boekjaren van één organisatie, nieuwste eerst. */
export function opdrachtenVanOrganisatie(organisatieId: number) {
  return haal<OpdrachtMetKantoor>(
    `opdrachten?organisatie_id=eq.${organisatieId}` +
      `&select=boekjaar,type_opdracht,oordeel,oordeel_gerapporteerd,` +
      `continuiteitsonzekerheid,` +
      `kantoren(${KANTOOR_VELDEN}),bronnen(url,bron_type,opgehaald_op)` +
      `&order=boekjaar.desc`,
  );
}

/** Alle cliëntjaren van één kantoor, nieuwste eerst. */
export function opdrachtenVanKantoor(kantoorId: number) {
  return haalAlles<OpdrachtMetOrganisatie>(
    `opdrachten?kantoor_id=eq.${kantoorId}` +
      `&select=boekjaar,type_opdracht,oordeel,oordeel_gerapporteerd,` +
      `continuiteitsonzekerheid,organisaties(${ORG_VELDEN})` +
      `&order=boekjaar.desc`,
  );
}

// ---------------------------------------------------------------- lijsten

/**
 * Organisaties in een sector. Zonder `limiet` komen ze állemaal.
 *
 * Dat moet ook: de sectorpagina toont het aantal, filtert de wisselingen op deze
 * lijst en berekent er marktaandeel over. Met de oude vaste grens van 200 stond er
 * "200 organisaties" zodra er meer waren, en verdwenen de wisselingen van
 * organisatie 201 en verder uit het overzicht — zonder enig teken dat er iets
 * miste. Dezelfde stille afkapping als de duizend-rijen-grens hierboven.
 */
export function organisatiesInSector(sector: string, limiet?: number) {
  const basis =
    `organisaties?sector=eq.${encodeURIComponent(sector)}` +
    `&select=${ORG_VELDEN}&order=naam.asc`;
  return limiet
    ? haal<Organisatie>(`${basis}&limit=${limiet}`)
    : haalAlles<Organisatie>(basis);
}

/**
 * Organisaties in een subsector. Zonder `limiet` komen ze állemaal — nodig voor de
 * subsectorpagina, die er marktaandeel over berekent en dus niet mag afkappen.
 * Met `limiet` blijft het één verzoek; genoeg voor een handvol doorklikken.
 */
export function organisatiesInSubsector(subsector: string, limiet?: number) {
  const basis =
    `organisaties?subsector=eq.${encodeURIComponent(subsector)}` +
    `&select=${ORG_VELDEN}&order=naam.asc`;
  return limiet
    ? haal<Organisatie>(`${basis}&limit=${limiet}`)
    : haalAlles<Organisatie>(basis);
}

/**
 * Sectoren met hun aantal organisaties, grootste eerst.
 *
 * Nodig omdat een sectornaam niet meer uit zijn URL te herleiden is: "goede doelen"
 * wordt `goede-doelen`, en terugvertalen naar een spatie is gokwerk. De sectorpagina
 * zoekt de echte waarde hier op, net als de subsectorpagina doet.
 */
export async function sectoren(): Promise<{ naam: string; aantal: number }[]> {
  const rijen = await haalAlles<{ sector: string | null }>(
    "organisaties?select=sector&sector=not.is.null",
  );
  const perSector = new Map<string, number>();
  for (const rij of rijen) {
    if (!rij.sector) continue;
    perSector.set(rij.sector, (perSector.get(rij.sector) ?? 0) + 1);
  }
  return [...perSector.entries()]
    .map(([naam, aantal]) => ({ naam, aantal }))
    .sort((a, b) => b.aantal - a.aantal);
}

/**
 * Subsectoren met hun aantal organisaties, grootste eerst.
 *
 * PostgREST kan niet groeperen zonder view, dus we halen alleen de kolom op en
 * tellen hier. Bij enkele duizenden organisaties is dat één klein verzoek; wordt
 * het meer, dan hoort hier een view tegenover te staan.
 */
export async function subsectoren(): Promise<{ naam: string; aantal: number }[]> {
  const rijen = await haalAlles<{ subsector: string | null }>(
    "organisaties?select=subsector&subsector=not.is.null",
  );
  const perSubsector = new Map<string, number>();
  for (const rij of rijen) {
    if (!rij.subsector) continue;
    perSubsector.set(rij.subsector, (perSubsector.get(rij.subsector) ?? 0) + 1);
  }
  return [...perSubsector.entries()]
    .map(([naam, aantal]) => ({ naam, aantal }))
    .sort((a, b) => b.aantal - a.aantal);
}

export function organisatiesInGemeente(gemeente: string, limiet = 20) {
  return haal<Organisatie>(
    `organisaties?gemeente=eq.${encodeURIComponent(gemeente)}` +
      `&select=${ORG_VELDEN}&order=naam.asc&limit=${limiet}`,
  );
}

/**
 * Alle organisaties, alfabetisch. Zonder `limiet` komen ze állemaal — dat is wat
 * /organisaties nodig heeft. Geef wél een limiet mee waar een handvol genoeg is
 * (een paar doorklikken); dat blijft één klein verzoek.
 */
export function alleOrganisaties(limiet?: number) {
  const basis = `organisaties?select=${ORG_VELDEN}&order=naam.asc`;
  return limiet
    ? haal<Organisatie>(`${basis}&limit=${limiet}`)
    : haalAlles<Organisatie>(basis);
}

export function zoekOrganisaties(term: string, limiet = 40) {
  const patroon = `*${term.replace(/[*,()]/g, " ").trim()}*`;
  return haal<Organisatie>(
    `organisaties?naam=ilike.${encodeURIComponent(patroon)}` +
      `&select=${ORG_VELDEN}&order=naam.asc&limit=${limiet}`,
  );
}

export function zoekKantoren(term: string, limiet = 40) {
  const patroon = `*${term.replace(/[*,()]/g, " ").trim()}*`;
  return haal<Kantoor>(
    `kantoren?naam=ilike.${encodeURIComponent(patroon)}` +
      `&select=${KANTOOR_VELDEN}&order=naam.asc&limit=${limiet}`,
  );
}

// ---------------------------------------------------------------- afgeleiden

/**
 * Wisselingen uit de view `v_wisselingen` (de definitie van "wisseling" staat in
 * SQL, niet hier — zo geven database en website altijd hetzelfde antwoord).
 *
 * De view heeft geen foreign keys, dus PostgREST kan de namen er niet zelf bij
 * halen; die zoeken we in twee extra verzoeken op en plakken we hier vast.
 */
export async function wisselingen(opties: {
  boekjaar?: number;
  organisatieId?: number;
  /** Wisselingen naar én van dit kantoor: gewonnen en verloren cliënten. */
  kantoorId?: number;
  /** Zonder limiet komen ze állemaal. Geef er alleen een mee waar een kort
   *  lijstje bedoeld is, zoals de acht op de voorpagina — een limiet die als
   *  "alle" wordt gepresenteerd geeft een verkeerd getal zodra de database groeit. */
  limiet?: number;
} = {}): Promise<WisselingVolledig[]> {
  const filters = ["select=*", "order=boekjaar_wissel.desc"];
  if (opties.boekjaar) filters.push(`boekjaar_wissel=eq.${opties.boekjaar}`);
  if (opties.organisatieId) filters.push(`organisatie_id=eq.${opties.organisatieId}`);
  if (opties.kantoorId) {
    filters.push(
      `or=(van_kantoor_id.eq.${opties.kantoorId},naar_kantoor_id.eq.${opties.kantoorId})`,
    );
  }

  const pad = `v_wisselingen?${filters.join("&")}`;
  const rijen = opties.limiet
    ? await haal<Wisseling>(`${pad}&limit=${opties.limiet}`)
    : await haalAlles<Wisseling>(pad);
  if (!rijen.length) return [];

  const [organisaties, kantoren] = await Promise.all([
    organisatiesOpId(rijen.map((r) => r.organisatie_id)),
    kantorenOpId(rijen.flatMap((r) => [r.van_kantoor_id, r.naar_kantoor_id])),
  ]);
  const orgPerId = new Map(organisaties.map((o) => [o.id, o]));
  const kantoorPerId = new Map(kantoren.map((k) => [k.id, k]));

  return rijen.map((r) => ({
    ...r,
    organisatie: orgPerId.get(r.organisatie_id) ?? null,
    van: kantoorPerId.get(r.van_kantoor_id) ?? null,
    naar: kantoorPerId.get(r.naar_kantoor_id) ?? null,
  }));
}

/** Het hoogste boekjaar waarvoor überhaupt een opdracht in de database staat. */
export async function nieuwsteBoekjaar(): Promise<number | null> {
  const rij = await haalEen<{ boekjaar: number }>(
    "opdrachten?select=boekjaar&order=boekjaar.desc&limit=1",
  );
  return rij?.boekjaar ?? null;
}

/**
 * Kantoren die daadwerkelijk opdrachten hebben, met hun aantal in één boekjaar —
 * over alle sectoren samen.
 *
 * Dat optellen moet hier gebeuren: `v_marktaandeel` groepeert óók op sector, dus
 * een kantoor dat zowel zorginstellingen als goede doelen controleert staat er
 * twee keer in, elk met een deel van het aantal. Ongeteld gaf dat op de
 * voorpagina twee regels "BDO Audit & Assurance" met 61 en 8 controles.
 */
export async function actieveKantoren(boekjaar: number) {
  const rijen = await haalAlles<{ kantoor_id: number; aantal_controles: number }>(
    `v_marktaandeel?select=kantoor_id,aantal_controles&boekjaar=eq.${boekjaar}`,
  );
  const perKantoor = new Map<number, number>();
  for (const rij of rijen) {
    perKantoor.set(
      rij.kantoor_id,
      (perKantoor.get(rij.kantoor_id) ?? 0) + rij.aantal_controles,
    );
  }
  const kantoren = await kantorenOpId([...perKantoor.keys()]);
  const kantoorPerId = new Map(kantoren.map((k) => [k.id, k]));
  return [...perKantoor.entries()]
    .map(([kantoor_id, aantal_controles]) => ({
      kantoor_id,
      aantal_controles,
      kantoor: kantoorPerId.get(kantoor_id) ?? null,
    }))
    .filter((r) => r.kantoor !== null)
    .sort((a, b) => b.aantal_controles - a.aantal_controles);
}

/** Marktaandeel per kantoor, met de kantoornamen erbij. */
export async function marktaandeel(sector: string, boekjaar?: number) {
  const filters = [
    "select=*",
    `sector=eq.${encodeURIComponent(sector)}`,
    "order=boekjaar.desc,aantal_controles.desc",
  ];
  if (boekjaar) filters.push(`boekjaar=eq.${boekjaar}`);

  const rijen = await haal<Marktaandeel>(`v_marktaandeel?${filters.join("&")}`);
  const kantoren = await kantorenOpId(rijen.map((r) => r.kantoor_id));
  const kantoorPerId = new Map(kantoren.map((k) => [k.id, k]));
  return rijen.map((r) => ({ ...r, kantoor: kantoorPerId.get(r.kantoor_id) ?? null }));
}
