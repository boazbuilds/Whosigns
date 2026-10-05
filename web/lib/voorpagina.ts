/**
 * Afleidingen voor de voorpagina: hoe de database per sector en boekjaar is
 * gevuld, wie per sector de grootste is, en de transferbalans van de kantoren.
 *
 * Pure functies zonder databasetoegang, net als analyse.ts. De getallen op de
 * voorpagina zijn de eerste die iemand citeert, dus ze moeten met de hand na te
 * rekenen zijn — en elke keuze die een getal kleurt (welk boekjaar, welke
 * sectoren samen) staat hier met reden en al.
 *
 * De regel welk boekjaar compleet genoeg is (`nieuwsteCompleteBoekjaar`) staat
 * hier ook, en geldt niet alleen voor de voorpagina: /kantoren, de sector-,
 * subsector- en kantoorpagina's kiezen er hun boekjaar mee. Eén regel op één
 * plek, zodat de voorpagina en een sectorpagina nooit een ander "nieuwste
 * jaar" noemen.
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

/** Controles per boekjaar, opgeteld over de meegegeven rijen. */
export function controlesPerJaar(
  rijen: Pick<MarktaandeelRij, "boekjaar" | "aantal_controles">[],
): Map<number, number> {
  const perJaar = new Map<number, number>();
  for (const rij of rijen) {
    perJaar.set(rij.boekjaar, (perJaar.get(rij.boekjaar) ?? 0) + rij.aantal_controles);
  }
  return perJaar;
}

/**
 * Het nieuwste boekjaar met minstens `minimum` controles en minstens
 * `compleet` keer het aantal van het jaar ervoor; null als geen enkel jaar
 * aan de ondergrens komt.
 *
 * Dezelfde regel voor één sector (de sectorleiders, de sectorpagina) als voor
 * de hele database (het ranglijstjaar van de voorpagina en /kantoren). Op
 * 5-10-2026 kiest hij voor de hele database 2024: voor 2025 stonden er 1.321
 * controles in tegen 2.307 voor 2024 (57%), met 110 OOB-controles tegen 576 en
 * nog geen enkele woningcorporatie. Een ranglijst over 2025 liet vooral zien
 * welke sectoren al binnen waren. Voor de zorg is 2025 wél compleet (776 tegen
 * 816), dus daar noemt de sectorpagina 2025.
 */
export function nieuwsteCompleteBoekjaar(
  perJaar: Map<number, number>,
  minimum = LEIDER_MINIMUM,
  compleet = LEIDER_COMPLEET,
): number | null {
  const jaar = [...perJaar.keys()]
    .sort((a, b) => b - a)
    .find((jaar) => jaarCompleet(perJaar, jaar, minimum, compleet));
  return jaar ?? null;
}

/**
 * Of één boekjaar compleet genoeg is voor een aandeel: minstens `minimum`
 * controles, en minstens `compleet` keer het jaar ervoor. De regel van
 * nieuwsteCompleteBoekjaar, maar dan voor elk jaar los — de kantoorpagina zet
 * een aandeel per sector en boekjaar alleen bij de jaren die hier doorheen
 * komen, en bij de rest alleen het aantal.
 */
export function jaarCompleet(
  perJaar: Map<number, number>,
  jaar: number,
  minimum = LEIDER_MINIMUM,
  compleet = LEIDER_COMPLEET,
): boolean {
  const aantal = perJaar.get(jaar) ?? 0;
  const vorig = perJaar.get(jaar - 1) ?? 0;
  return aantal >= minimum && (vorig === 0 || aantal >= compleet * vorig);
}

/** sector -> boekjaar -> kantoor -> aantal controles; rijen zonder sector vallen weg. */
function sectorboom(rijen: MarktaandeelRij[]) {
  const boom = new Map<string, Map<number, Map<number, number>>>();
  for (const rij of rijen) {
    if (!rij.sector) continue;
    const perJaar = boom.get(rij.sector) ?? new Map<number, Map<number, number>>();
    const perKantoor = perJaar.get(rij.boekjaar) ?? new Map<number, number>();
    perKantoor.set(rij.kantoor_id, (perKantoor.get(rij.kantoor_id) ?? 0) + rij.aantal_controles);
    perJaar.set(rij.boekjaar, perKantoor);
    boom.set(rij.sector, perJaar);
  }
  return boom;
}

export function sectorleiders(
  rijen: MarktaandeelRij[],
  minimum = LEIDER_MINIMUM,
  compleet = LEIDER_COMPLEET,
): Sectorleider[] {
  const boom = sectorboom(rijen);
  const uit: Sectorleider[] = [];
  for (const [sector, perJaar] of boom) {
    const totaal = (jaar: number) => som(perJaar.get(jaar)?.values() ?? []);
    const boekjaar = nieuwsteCompleteBoekjaar(
      new Map([...perJaar.keys()].map((jaar) => [jaar, totaal(jaar)])),
      minimum,
      compleet,
    );
    if (boekjaar === null) continue;

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

// ------------------------------------------------------- plek per sector

/** Waar één kantoor staat in één sector, in het nieuwste complete boekjaar daarvan. */
export type Sectorpositie = {
  sector: string;
  boekjaar: number;
  /** 1 is de grootste; kantoren met evenveel controles delen een plek. */
  plek: number;
  aantal: number;
  /** Alle controles in deze sector in dit boekjaar: de noemer van het aandeel. */
  controles: number;
  /** De hele ranglijst van dit sector-boekjaar, grootste eerst. */
  ranglijst: { kantoorId: number; aantal: number }[];
};

/**
 * De plek van een kantoor in elke sector waar het in het nieuwste complete
 * boekjaar van die sector controles had; de sector met de meeste eigen
 * controles eerst.
 *
 * Dit vervangt "#1 in de ranglijst" en "18,2% van alles wat in deze database
 * staat" op de kantoorpagina. Die plek en dat aandeel gingen over alle sectoren
 * en alle boekjaren samen, en daarin weegt vooral mee welke sectoren er per
 * jaar in de database staan. Per sector en boekjaar is Deloitte op 5-10-2026
 * #2 in de OOB (2024, 116 van 576), #4 in de zorg (2025) en #1 bij de overheid
 * (2024) — een ander verhaal dan één plek bovenaan.
 */
export function sectorposities(
  rijen: MarktaandeelRij[],
  kantoorId: number,
  minimum = LEIDER_MINIMUM,
  compleet = LEIDER_COMPLEET,
): Sectorpositie[] {
  const uit: Sectorpositie[] = [];
  for (const [sector, perJaar] of sectorboom(rijen)) {
    const boekjaar = nieuwsteCompleteBoekjaar(
      new Map([...perJaar].map(([jaar, perKantoor]) => [jaar, som(perKantoor.values())])),
      minimum,
      compleet,
    );
    if (boekjaar === null) continue;
    const perKantoor = perJaar.get(boekjaar) ?? new Map<number, number>();
    const aantal = perKantoor.get(kantoorId) ?? 0;
    if (aantal === 0) continue;
    const ranglijst = [...perKantoor]
      .map(([id, n]) => ({ kantoorId: id, aantal: n }))
      .sort((a, b) => b.aantal - a.aantal || a.kantoorId - b.kantoorId);
    uit.push({
      sector,
      boekjaar,
      plek: 1 + ranglijst.filter((rij) => rij.aantal > aantal).length,
      aantal,
      controles: som(perKantoor.values()),
      ranglijst,
    });
  }
  return uit.sort(
    (a, b) =>
      b.aantal - a.aantal || b.controles - a.controles || a.sector.localeCompare(b.sector, "nl"),
  );
}

// ------------------------------------------------------ reeks per sector

/** Eén kantoor in één sector, boekjaar voor boekjaar. */
export type Sectorreeks = {
  sector: string;
  /** Controles van dit kantoor in deze sector, over alle boekjaren samen. */
  eigen: number;
  jaren: {
    boekjaar: number;
    /** Controles van dit kantoor; nul is een echte nul als de sector dat jaar
     *  wél in de database staat. */
    aantal: number;
    /** Alle controles in deze sector in dit boekjaar: de noemer. */
    controles: number;
    /** Door jaarCompleet heen: alleen dan hoort er een aandeel bij. */
    compleet: boolean;
  }[];
};

/**
 * Per sector waarin een kantoor controles had: elk boekjaar vanaf zijn eerste
 * controle in die sector tot het nieuwste boekjaar van de sector, met het eigen
 * aantal en het sectortotaal ernaast. De sector met de meeste eigen controles
 * eerst.
 *
 * Het aandeel dat een pagina hieruit rekent, geldt dus altijd binnen één sector
 * én één boekjaar. Alleen bij een compleet jaar: onder de twintig controles
 * schommelt een aandeel van 50 naar 100% op één opdracht (de financiële
 * dienstverlening had op 5-10-2026 in geen enkel jaar meer dan twee), en een
 * jaar dat nog binnenloopt overdrijft de grote kantoren (OOB 2025: 110
 * controles tegen 576 een jaar eerder).
 */
export function sectorreeksen(
  rijen: MarktaandeelRij[],
  kantoorId: number,
  minimum = LEIDER_MINIMUM,
  compleet = LEIDER_COMPLEET,
): Sectorreeks[] {
  const uit: Sectorreeks[] = [];
  for (const [sector, perJaar] of sectorboom(rijen)) {
    const eigenJaren = [...perJaar]
      .filter(([, perKantoor]) => (perKantoor.get(kantoorId) ?? 0) > 0)
      .map(([jaar]) => jaar);
    if (!eigenJaren.length) continue;
    const totalen = new Map(
      [...perJaar].map(([jaar, perKantoor]) => [jaar, som(perKantoor.values())]),
    );
    const eerste = Math.min(...eigenJaren);
    const jaren = [...perJaar.keys()]
      .filter((jaar) => jaar >= eerste)
      .sort((a, b) => a - b)
      .map((boekjaar) => ({
        boekjaar,
        aantal: perJaar.get(boekjaar)?.get(kantoorId) ?? 0,
        controles: totalen.get(boekjaar) ?? 0,
        compleet: jaarCompleet(totalen, boekjaar, minimum, compleet),
      }));
    uit.push({ sector, eigen: som(jaren.map((j) => j.aantal)), jaren });
  }
  return uit.sort((a, b) => b.eigen - a.eigen || a.sector.localeCompare(b.sector, "nl"));
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
