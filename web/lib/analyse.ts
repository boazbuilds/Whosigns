/**
 * Kleine afleidingen die alleen voor de weergave nodig zijn.
 *
 * Let op de taakverdeling: wat een *feit* is (wanneer heet iets een wisseling,
 * hoe lang loopt een relatie, wat is marktaandeel) staat als view in SQL —
 * `supabase/migrations/`. Hier staat alleen het groeperen en tellen dat je nodig
 * hebt om een tabel te tekenen. Zo kan de database nooit iets anders beweren dan
 * de website.
 */

import type { OpdrachtMetKantoor, OpdrachtMetOrganisatie } from "./db";

/** De reeks boekjaren die aaneengesloten bij hetzelfde kantoor horen. */
export type Periode = {
  kantoorId: number;
  kantoorNaam: string;
  afmNummer: string | null;
  jaren: number[];
};

/**
 * Splitst een (op boekjaar aflopend gesorteerde) opdrachtenlijst in periodes per
 * kantoor. Nieuwste periode eerst; twee losse periodes bij hetzelfde kantoor
 * blijven gescheiden als er een ander kantoor tussen zat.
 */
export function periodes(opdrachten: OpdrachtMetKantoor[]): Periode[] {
  const uit: Periode[] = [];
  for (const opdracht of opdrachten) {
    const kantoor = opdracht.kantoren;
    if (!kantoor) continue;
    const laatste = uit[uit.length - 1];
    if (laatste && laatste.kantoorId === kantoor.id) {
      laatste.jaren.push(opdracht.boekjaar);
    } else {
      uit.push({
        kantoorId: kantoor.id,
        kantoorNaam: kantoor.naam,
        afmNummer: kantoor.afm_nummer,
        jaren: [opdracht.boekjaar],
      });
    }
  }
  return uit;
}

/** Boekjaren waarin het kantoor anders was dan het boekjaar ervoor. */
export function wisseljaren(opdrachten: OpdrachtMetKantoor[]): Set<number> {
  const oplopend = [...opdrachten].sort((a, b) => a.boekjaar - b.boekjaar);
  const jaren = new Set<number>();
  for (let i = 1; i < oplopend.length; i++) {
    const vorige = oplopend[i - 1];
    const huidige = oplopend[i];
    if (
      vorige.kantoren &&
      huidige.kantoren &&
      huidige.boekjaar === vorige.boekjaar + 1 &&
      huidige.kantoren.id !== vorige.kantoren.id
    ) {
      jaren.add(huidige.boekjaar);
    }
  }
  return jaren;
}

export type Clientregel = {
  organisatieId: number;
  naam: string;
  kvkNummer: string | null;
  gemeente: string | null;
  sector: string | null;
  jaren: number[];
  laatsteBoekjaar: number;
  oordeelLaatste: string | null;
};

/** Eén regel per cliënt in plaats van één regel per cliëntjaar. */
export function clientenVanKantoor(
  opdrachten: OpdrachtMetOrganisatie[],
): Clientregel[] {
  const perOrganisatie = new Map<number, Clientregel>();
  for (const opdracht of opdrachten) {
    const org = opdracht.organisaties;
    if (!org) continue;
    const bestaand = perOrganisatie.get(org.id);
    if (bestaand) {
      bestaand.jaren.push(opdracht.boekjaar);
      if (opdracht.boekjaar > bestaand.laatsteBoekjaar) {
        bestaand.laatsteBoekjaar = opdracht.boekjaar;
        bestaand.oordeelLaatste = opdracht.oordeel;
      }
    } else {
      perOrganisatie.set(org.id, {
        organisatieId: org.id,
        naam: org.naam,
        kvkNummer: org.kvk_nummer,
        gemeente: org.gemeente,
        sector: org.sector,
        jaren: [opdracht.boekjaar],
        laatsteBoekjaar: opdracht.boekjaar,
        oordeelLaatste: opdracht.oordeel,
      });
    }
  }
  return [...perOrganisatie.values()].sort(
    (a, b) => b.laatsteBoekjaar - a.laatsteBoekjaar || a.naam.localeCompare(b.naam),
  );
}
