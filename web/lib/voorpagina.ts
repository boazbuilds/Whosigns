/**
 * Afleidingen voor de voorpagina: hoe de database per sector en boekjaar is
 * gevuld, wie per sector de grootste is, en de transferbalans van de kantoren.
 *
 * Pure functies zonder databasetoegang, net als analyse.ts. De getallen op de
 * voorpagina zijn de eerste die iemand citeert, dus ze moeten met de hand na te
 * rekenen zijn — en elke keuze die een getal kleurt (welk boekjaar, welke
 * sectoren samen) staat hier met reden en al.
 */

import type { Kantoor, MarktaandeelRij, Wisseling } from "@/lib/db";
import { saldoPerKantoor, type Saldorij } from "@/lib/analyse";

function som(waarden: Iterable<number>): number {
  let totaal = 0;
  for (const waarde of waarden) totaal += waarde;
  return totaal;
}

// ------------------------------------------------------------------ dekking

/** Wat de kaart "Wat staat er in het register" toont. */
export type Dekking = {
  /** Alle boekjaren van het oudste tot het nieuwste, zonder gaten. */
  jaren: number[];
  rijen: {
    sector: string;
    /** De verzamelregel voor kleine sectoren; die heeft geen eigen pagina. */
    verzameld: boolean;
    perJaar: Map<number, number>;
    totaal: number;
  }[];
  totaalPerJaar: Map<number, number>;
  /** Welke sectoren in de verzamelregel zitten, grootste eerst. */
  verzameldeSectoren: string[];
};

/**
 * Sectoren met over alle boekjaren samen minder controles dan dit gaan op één
 * regel. Vijf sectoren met een tot vier controles per jaar maken de kaart
 * langer zonder dat er iets te zien valt; op /sectoren staan ze gewoon apart.
 */
export const DEKKING_MINIMUM = 100;

/** Controles per sector en boekjaar, uit de kale rijen van v_marktaandeel. */
export function dekkingPerSector(
  rijen: MarktaandeelRij[],
  minimum = DEKKING_MINIMUM,
): Dekking {
  const perSector = new Map<string, Map<number, number>>();
  const totaalPerJaar = new Map<number, number>();
  for (const rij of rijen) {
    const sector = rij.sector ?? "zonder sector";
    const perJaar = perSector.get(sector) ?? new Map<number, number>();
    perJaar.set(rij.boekjaar, (perJaar.get(rij.boekjaar) ?? 0) + rij.aantal_controles);
    perSector.set(sector, perJaar);
    totaalPerJaar.set(
      rij.boekjaar,
      (totaalPerJaar.get(rij.boekjaar) ?? 0) + rij.aantal_controles,
    );
  }

  const bekend = [...totaalPerJaar.keys()];
  const jaren: number[] = [];
  if (bekend.length) {
    for (let jaar = Math.min(...bekend); jaar <= Math.max(...bekend); jaar++) {
      jaren.push(jaar);
    }
  }

  const alle = [...perSector.entries()]
    .map(([sector, perJaar]) => ({ sector, perJaar, totaal: som(perJaar.values()) }))
    .sort((a, b) => b.totaal - a.totaal || a.sector.localeCompare(b.sector, "nl"));
  const groot = alle.filter((r) => r.totaal >= minimum && r.sector !== "zonder sector");
  let klein = alle.filter((r) => !groot.includes(r));
  const uit: Dekking["rijen"] = groot.map((r) => ({ ...r, verzameld: false }));

  // Eén kleine sector blijft gewoon zichzelf: een regel "overige sectoren" met
  // één sector erin verstopt alleen de naam.
  if (klein.length === 1) {
    uit.push({ ...klein[0], verzameld: false });
    klein = [];
  }
  if (klein.length) {
    const perJaar = new Map<number, number>();
    for (const rij of klein) {
      for (const [jaar, aantal] of rij.perJaar) {
        perJaar.set(jaar, (perJaar.get(jaar) ?? 0) + aantal);
      }
    }
    uit.push({
      sector: "overige sectoren",
      verzameld: true,
      perJaar,
      totaal: som(perJaar.values()),
    });
  }

  return {
    jaren,
    rijen: uit,
    totaalPerJaar,
    verzameldeSectoren: klein.map((r) => r.sector),
  };
}

/**
 * De klassen van de dekkingskaart: 1–9, 10–49, 50–199, 200–499 en 500+
 * controles. Ongeveer logaritmisch, omdat de aantallen dat ook zijn: tussen
 * een sector met drie controles en een met achthonderd zit een factor
 * driehonderd, en op een lineaire schaal zou alles onder de honderd even licht
 * zijn.
 */
export const DEKKING_GRENZEN = [10, 50, 200, 500] as const;

/** 0 voor een lege cel, anders 1 tot en met 5. */
export function dekkingsklasse(aantal: number): number {
  if (aantal <= 0) return 0;
  return 1 + DEKKING_GRENZEN.filter((grens) => aantal >= grens).length;
}

// ----------------------------------------------------------- sectorleiders

/** De grootste in één sector, in het nieuwste boekjaar dat al compleet is. */
export type Sectorleider = {
  sector: string;
  boekjaar: number;
  controles: number;
  kantoren: number;
  kantoorId: number;
  aantal: number;
  /** Aandeel van de koploper als fractie (0.18 = 18%). */
  aandeel: number;
  /** Staat er een ander kantoor met precies evenveel controles naast? */
  gedeeld: boolean;
  /** Aandeel van hetzelfde kantoor een boekjaar eerder, of null als de sector
   *  toen nog niet in de database stond. Nul is een echte nul: het kantoor had
   *  toen geen controle in deze sector. */
  aandeelVorigJaar: number | null;
  /** Aandeel van de vier grootste kantoren samen (de CR4). */
  top4: number;
};

/**
 * Onder de twintig controles in een sector-boekjaar zegt "het grootste
 * aandeel" weinig: één opdracht meer of minder verschuift het dan al vijf
 * procentpunt.
 */
export const LEIDER_MINIMUM = 20;

/**
 * Wanneer een boekjaar compleet genoeg is om een koploper te noemen: minstens
 * deze fractie van het aantal controles van het jaar ervoor.
 *
 * Nodig omdat het nieuwste boekjaar vaak nog binnenloopt. In september 2026
 * stonden er voor 2025 110 OOB-controles in de database tegen 576 voor 2024:
 * de beursfondsen die al vroeg publiceerden, en dat zijn vooral de grote. Een
 * marktaandeel over die 110 zou de verschuiving naar de grote kantoren
 * overdrijven, en het verschil met 2024 zou nep zijn.
 */
export const LEIDER_COMPLEET = 0.8;

export function sectorleiders(
  rijen: MarktaandeelRij[],
  minimum = LEIDER_MINIMUM,
  compleet = LEIDER_COMPLEET,
): Sectorleider[] {
  // sector -> boekjaar -> kantoor -> aantal controles
  const boom = new Map<string, Map<number, Map<number, number>>>();
  for (const rij of rijen) {
    if (!rij.sector) continue;
    const perJaar = boom.get(rij.sector) ?? new Map<number, Map<number, number>>();
    const perKantoor = perJaar.get(rij.boekjaar) ?? new Map<number, number>();
    perKantoor.set(rij.kantoor_id, (perKantoor.get(rij.kantoor_id) ?? 0) + rij.aantal_controles);
    perJaar.set(rij.boekjaar, perKantoor);
    boom.set(rij.sector, perJaar);
  }

  const uit: Sectorleider[] = [];
  for (const [sector, perJaar] of boom) {
    const totaal = (jaar: number) => som(perJaar.get(jaar)?.values() ?? []);
    const boekjaar = [...perJaar.keys()]
      .sort((a, b) => b - a)
      .find((jaar) => {
        const aantal = totaal(jaar);
        const vorig = totaal(jaar - 1);
        return aantal >= minimum && (vorig === 0 || aantal >= compleet * vorig);
      });
    if (boekjaar === undefined) continue;

    const controles = totaal(boekjaar);
    const kantoren = [...(perJaar.get(boekjaar) ?? new Map<number, number>())].sort(
      (a, b) => b[1] - a[1] || a[0] - b[0],
    );
    const [kantoorId, aantal] = kantoren[0];
    const vorigTotaal = totaal(boekjaar - 1);
    uit.push({
      sector,
      boekjaar,
      controles,
      kantoren: kantoren.length,
      kantoorId,
      aantal,
      aandeel: aantal / controles,
      gedeeld: kantoren.length > 1 && kantoren[1][1] === aantal,
      aandeelVorigJaar:
        vorigTotaal > 0
          ? (perJaar.get(boekjaar - 1)?.get(kantoorId) ?? 0) / vorigTotaal
          : null,
      top4: som(kantoren.slice(0, 4).map(([, n]) => n)) / controles,
    });
  }
  return uit.sort(
    (a, b) => b.controles - a.controles || a.sector.localeCompare(b.sector, "nl"),
  );
}

// ---------------------------------------------------------- transferbalans

export type Transferbalans = {
  vanaf: number;
  tot: number;
  /** Alle wisselingen in de periode, niet alleen die van de getoonde kantoren. */
  wisselingen: number;
  /** Grootste saldo bovenaan, grootste verliezer onderaan. */
  rijen: Saldorij[];
};

/**
 * Wie won en wie verloor cliënten over de laatste `jaren` boekjaren met
 * wisselingen: de `aantal` kantoren met de meeste beweging (gewonnen plus
 * verloren), gesorteerd op saldo.
 *
 * Op beweging kiezen en niet op saldo, omdat een lijst van alleen de grootste
 * winnaars en verliezers de middenmoot wegpoetst: een groot kantoor dat vijftig
 * cliënten won en vijftig verloor is net zo goed transfermarkt.
 */
export function transferbalans(
  wissels: Wisseling[],
  kantoorPerId: Map<number, Pick<Kantoor, "naam" | "afm_nummer">>,
  jaren = 5,
  aantal = 10,
): Transferbalans | null {
  const venster = [...new Set(wissels.map((w) => w.boekjaar_wissel))]
    .sort((a, b) => b - a)
    .slice(0, jaren);
  if (!venster.length) return null;
  const vanaf = Math.min(...venster);
  const tot = Math.max(...venster);
  const binnen = wissels.filter((w) => w.boekjaar_wissel >= vanaf && w.boekjaar_wissel <= tot);

  const saldi = saldoPerKantoor(
    binnen.map((w) => ({
      van_kantoor_id: w.van_kantoor_id,
      naar_kantoor_id: w.naar_kantoor_id,
      van: kantoorPerId.get(w.van_kantoor_id) ?? null,
      naar: kantoorPerId.get(w.naar_kantoor_id) ?? null,
    })),
  );
  const drukste = [...saldi]
    .sort(
      (a, b) =>
        b.gewonnen + b.verloren - (a.gewonnen + a.verloren) ||
        a.naam.localeCompare(b.naam, "nl"),
    )
    .slice(0, aantal);

  return {
    vanaf,
    tot,
    wisselingen: binnen.length,
    rijen: drukste.sort(
      (a, b) =>
        b.saldo - a.saldo || b.gewonnen - a.gewonnen || a.naam.localeCompare(b.naam, "nl"),
    ),
  };
}

// ------------------------------------------------------------------ assen

/**
 * Ronde rasterlijnen voor een kolomgrafiek: 0, 5, 10, 15 in plaats van
 * 0, 3,9, 7,8. Ongeveer vier stappen, elk 1, 2, 2,5 of 5 keer een macht van
 * tien — de getallen die een lezer zonder rekenen kan plaatsen.
 */
export function rasterstappen(hoogste: number, laagste = 0): number[] {
  const onder = Math.min(0, laagste);
  const ruw = (Math.max(hoogste, 0) - onder) / 4 || 1;
  const macht = 10 ** Math.floor(Math.log10(ruw));
  const stap = [1, 2, 2.5, 5, 10].map((f) => f * macht).find((s) => s >= ruw) ?? 10 * macht;
  const stappen: number[] = [];
  for (let waarde = Math.floor(onder / stap) * stap; waarde <= hoogste + 1e-9; waarde += stap) {
    stappen.push(Number(waarde.toFixed(6)));
  }
  return stappen;
}
