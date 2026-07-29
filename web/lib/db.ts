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
  continuiteitsonzekerheid: boolean | null;
  kantoren: Kantoor | null;
  bronnen: Bron | null;
};

export type OpdrachtMetOrganisatie = {
  boekjaar: number;
  type_opdracht: string;
  oordeel: string | null;
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

const ORG_VELDEN = "id,kvk_nummer,naam,sector,gemeente";
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
      `&select=boekjaar,type_opdracht,oordeel,continuiteitsonzekerheid,` +
      `kantoren(${KANTOOR_VELDEN}),bronnen(url,bron_type,opgehaald_op)` +
      `&order=boekjaar.desc`,
  );
}

/** Alle cliëntjaren van één kantoor, nieuwste eerst. */
export function opdrachtenVanKantoor(kantoorId: number) {
  return haal<OpdrachtMetOrganisatie>(
    `opdrachten?kantoor_id=eq.${kantoorId}` +
      `&select=boekjaar,type_opdracht,oordeel,continuiteitsonzekerheid,` +
      `organisaties(${ORG_VELDEN})` +
      `&order=boekjaar.desc`,
  );
}

// ---------------------------------------------------------------- lijsten

export function organisatiesInSector(sector: string, limiet = 200) {
  return haal<Organisatie>(
    `organisaties?sector=eq.${encodeURIComponent(sector)}` +
      `&select=${ORG_VELDEN}&order=naam.asc&limit=${limiet}`,
  );
}

export function organisatiesInGemeente(gemeente: string, limiet = 20) {
  return haal<Organisatie>(
    `organisaties?gemeente=eq.${encodeURIComponent(gemeente)}` +
      `&select=${ORG_VELDEN}&order=naam.asc&limit=${limiet}`,
  );
}

export function alleOrganisaties(limiet = 200) {
  return haal<Organisatie>(
    `organisaties?select=${ORG_VELDEN}&order=naam.asc&limit=${limiet}`,
  );
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
  filters.push(`limit=${opties.limiet ?? 100}`);

  const rijen = await haal<Wisseling>(`v_wisselingen?${filters.join("&")}`);
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

/** Kantoren die daadwerkelijk opdrachten hebben, met hun aantal in één boekjaar. */
export async function actieveKantoren(boekjaar: number) {
  const rijen = await haal<{ kantoor_id: number; aantal_controles: number }>(
    `v_marktaandeel?select=kantoor_id,aantal_controles&boekjaar=eq.${boekjaar}` +
      `&order=aantal_controles.desc`,
  );
  const kantoren = await kantorenOpId(rijen.map((r) => r.kantoor_id));
  const kantoorPerId = new Map(kantoren.map((k) => [k.id, k]));
  return rijen
    .map((r) => ({ ...r, kantoor: kantoorPerId.get(r.kantoor_id) ?? null }))
    .filter((r) => r.kantoor !== null);
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
