/**
 * Kleine afleidingen die alleen voor de weergave nodig zijn.
 *
 * Let op de taakverdeling: wat een *feit* is (wanneer heet iets een wisseling,
 * hoe lang loopt een relatie, wat is marktaandeel) staat als view in SQL —
 * `supabase/migrations/`. Hier staat alleen het groeperen en tellen dat je nodig
 * hebt om een tabel te tekenen. Zo kan de database nooit iets anders beweren dan
 * de website.
 */

import type { Kantoor, OpdrachtMetKantoor, OpdrachtMetOrganisatie } from "./db";

/**
 * Welke opdrachttypen tellen als "de accountant van de organisatie", en wie
 * wint als een boekjaar er meerdere heeft. WNT- en productieverantwoordingen
 * doen bewust níét mee: die lopen soms bij een ander kantoor dan de
 * jaarrekening, en zonder dit filter kreeg een organisatie een "wisseling"
 * aangesmeerd omdat de productieverantwoording bij kantoor B lag terwijl de
 * jaarrekening gewoon bij A bleef — of ging de kop "Huidige accountant" over
 * de WNT-controleur.
 *
 * `controle_onbepaald` telt hier wél mee en in de SQL-views níét. Dat verschil
 * is met opzet, maar het stond hier verkeerd opgeschreven: er stond dat het
 * "ís de jaarrekeningcontrole". Dat is precies wat we niet weten. laad_zorg.py
 * geeft dit type juist aan een verklaring waarvan het voorwerp níét viel vast
 * te stellen, in plaats van het zwaarste type te gokken — het kan dus net zo
 * goed een WNT-verantwoording zijn.
 *
 * Waarom het hier tóch meetelt: op de organisatiepagina staat naast dit jaar
 * het label "controle, voorwerp onbekend" (SOORTGROEP zet het op `onbekend`,
 * met uitleg in de titel). De lezer ziet de onzekerheid dus in dezelfde regel
 * als de bewering. Weglaten zou 49 organisatie-boekjaren leeg maken, waarvan er
 * 22 organisaties zijn die verder geen enkele kantoorrelatie hebben — een
 * gelezen, ondertekende verklaring die nergens meer te zien is.
 *
 * In de views telt het niet mee, want daar zou het ongemerkt als
 * jaarrekeningcontrole in een marktaandeel belanden. Gemeten op 20-8-2026 gaat
 * het om 49 opdrachten bij 41 organisaties, verdeeld over 2019-2025. Zouden de
 * views ze meenemen, dan groeit v_wisselingen van 1.689 naar 1.691 rijen en
 * v_relatieduur van 8.108 naar 8.127.
 */
const TYPE_VOORRANG: Record<string, number> = {
  wettelijke_controle: 0,
  vrijwillige_controle: 1,
  controle_onbepaald: 2,
};

/** Per boekjaar het kantoor van de jaarrekeningcontrole (voorrang: wettelijk
 *  boven vrijwillig boven onbepaald; daarbinnen het laagste kantoor-id, zodat
 *  de uitkomst niet afhangt van de rijvolgorde uit de database). */
function controleKantoorPerJaar(
  opdrachten: OpdrachtMetKantoor[],
): Map<number, Kantoor> {
  const perJaar = new Map<number, { kantoor: Kantoor; voorrang: number }>();
  for (const opdracht of opdrachten) {
    const voorrang = TYPE_VOORRANG[opdracht.type_opdracht];
    if (voorrang === undefined || !opdracht.kantoren) continue;
    const bestaand = perJaar.get(opdracht.boekjaar);
    if (
      !bestaand ||
      voorrang < bestaand.voorrang ||
      (voorrang === bestaand.voorrang && opdracht.kantoren.id < bestaand.kantoor.id)
    ) {
      perJaar.set(opdracht.boekjaar, { kantoor: opdracht.kantoren, voorrang });
    }
  }
  return new Map([...perJaar.entries()].map(([jaar, r]) => [jaar, r.kantoor]));
}

/** De reeks boekjaren die aaneengesloten bij hetzelfde kantoor horen. */
export type Periode = {
  kantoorId: number;
  kantoorNaam: string;
  afmNummer: string | null;
  jaren: number[];
};

/**
 * Periodes per kantoor, nieuwste eerst. Unieke boekjaren, geen opdrachtrijen:
 * een organisatie met controle + WNT + productieverantwoording in elk van drie
 * jaren kreeg hier eerst "9 boekjaren" voor een relatie van drie jaar. Een gat
 * (2019 wel, 2020 niets, 2021 weer) splitst de periode, net als v_relatieduur
 * in SQL dat doet.
 */
export function periodes(opdrachten: OpdrachtMetKantoor[]): Periode[] {
  const perJaar = controleKantoorPerJaar(opdrachten);
  const jaren = [...perJaar.keys()].sort((a, b) => b - a);
  const uit: Periode[] = [];
  for (const jaar of jaren) {
    const kantoor = perJaar.get(jaar)!;
    const laatste = uit[uit.length - 1];
    const vorigJaar = laatste?.jaren[laatste.jaren.length - 1];
    if (laatste && laatste.kantoorId === kantoor.id && vorigJaar === jaar + 1) {
      laatste.jaren.push(jaar);
    } else {
      uit.push({
        kantoorId: kantoor.id,
        kantoorNaam: kantoor.naam,
        afmNummer: kantoor.afm_nummer,
        jaren: [jaar],
      });
    }
  }
  return uit;
}

/**
 * Boekjaren waarin het controlerende kantoor anders was dan het boekjaar ervoor:
 * opeenvolgende jaren, ander kantoor.
 *
 * Bijna dezelfde definitie als v_wisselingen, maar niet helemaal, en hier stond
 * eerst dat het er wél dezelfde was. Het verschil zit in `controle_onbepaald`
 * (zie TYPE_VOORRANG hierboven): twee wisselingen die deze functie aanwijst
 * staan daardoor niet op /wisselingen. Op de organisatiepagina staan ze naast
 * het label "controle, voorwerp onbekend"; /wisselingen laat ze weg omdat een
 * verklaring waarvan het voorwerp onbekend is geen bewijs is dat de
 * jaarrekeningcontrole verhuisde.
 */
export function wisseljaren(opdrachten: OpdrachtMetKantoor[]): Set<number> {
  const perJaar = controleKantoorPerJaar(opdrachten);
  const jaren = new Set<number>();
  for (const [jaar, kantoor] of perJaar) {
    const vorige = perJaar.get(jaar - 1);
    if (vorige && vorige.id !== kantoor.id) jaren.add(jaar);
  }
  return jaren;
}

export type Clientregel = {
  organisatieId: number;
  naam: string;
  kvkNummer: string | null;
  gemeente: string | null;
  sector: string | null;
  /** Unieke boekjaren, oplopend. */
  jaren: number[];
  laatsteBoekjaar: number;
  /** Oordeel uit de gedeponeerde verklaring van het laatste boekjaar. */
  oordeelLaatste: string | null;
  /** Opgave van de organisatie zelf, apart gehouden: het verschil moet op de
   *  pagina zichtbaar blijven als "(opgave)" — samengevouwen ging dat label
   *  verloren en stond een eigen opgave er als gelezen feit. */
  oordeelOpgaveLaatste: string | null;
  /** Opdrachttype van het laatste boekjaar. Nodig omdat een kantoor naast
   *  jaarrekeningcontroles ook WNT- of productieverantwoordingen kan doen; die
   *  ongemerkt als cliënt tonen suggereert meer dan er staat. */
  typeLaatste: string;
};

/** Eén regel per cliënt in plaats van één regel per cliëntjaar. */
export function clientenVanKantoor(
  opdrachten: OpdrachtMetOrganisatie[],
): Clientregel[] {
  const perOrganisatie = new Map<
    number,
    Clientregel & { jaarSet: Set<number>; voorrangLaatste: number }
  >();
  for (const opdracht of opdrachten) {
    const org = opdracht.organisaties;
    if (!org) continue;
    // Binnen één boekjaar wint de jaarrekeningcontrole van een WNT- of
    // productieverantwoording, zodat het getoonde "laatste oordeel" over de
    // jaarrekening gaat en niet van de rijvolgorde afhangt.
    const voorrang = TYPE_VOORRANG[opdracht.type_opdracht] ?? 9;
    const bestaand = perOrganisatie.get(org.id);
    if (bestaand) {
      bestaand.jaarSet.add(opdracht.boekjaar);
      if (
        opdracht.boekjaar > bestaand.laatsteBoekjaar ||
        (opdracht.boekjaar === bestaand.laatsteBoekjaar &&
          voorrang < bestaand.voorrangLaatste)
      ) {
        bestaand.laatsteBoekjaar = opdracht.boekjaar;
        bestaand.oordeelLaatste = opdracht.oordeel;
        bestaand.oordeelOpgaveLaatste = opdracht.oordeel_gerapporteerd;
        bestaand.typeLaatste = opdracht.type_opdracht;
        bestaand.voorrangLaatste = voorrang;
      }
    } else {
      perOrganisatie.set(org.id, {
        organisatieId: org.id,
        naam: org.naam,
        kvkNummer: org.kvk_nummer,
        gemeente: org.gemeente,
        sector: org.sector,
        jaren: [],
        jaarSet: new Set([opdracht.boekjaar]),
        laatsteBoekjaar: opdracht.boekjaar,
        oordeelLaatste: opdracht.oordeel,
        oordeelOpgaveLaatste: opdracht.oordeel_gerapporteerd,
        typeLaatste: opdracht.type_opdracht,
        voorrangLaatste: voorrang,
      });
    }
  }
  return [...perOrganisatie.values()]
    .map(({ jaarSet, voorrangLaatste: _v, ...regel }) => ({
      ...regel,
      jaren: [...jaarSet].sort((a, b) => a - b),
    }))
    .sort(
      (a, b) => b.laatsteBoekjaar - a.laatsteBoekjaar || a.naam.localeCompare(b.naam),
    );
}

/** Wat een kantoor won en verloor in een periode; het saldo is de transfermarkt. */
export type Saldorij = {
  kantoorId: number;
  naam: string;
  afmNummer: string | null;
  gewonnen: number;
  verloren: number;
  saldo: number;
};

/**
 * Stijgers en dalers: per kantoor het aantal gewonnen min het aantal verloren
 * cliënten, grootste saldo eerst.
 *
 * Alleen tellen wat er in de meegegeven wisselingen staat — filter die vooraf
 * op boekjaar of sector. Kantoren zonder naam (uit de database gevallen) laten
 * we weg in plaats van ze als "onbekend" op te tellen: een ranglijst met een
 * naamloze koploper is erger dan een ranglijst met één regel minder.
 */
export function saldoPerKantoor(
  wisselingen: {
    van_kantoor_id: number;
    naar_kantoor_id: number;
    van: { naam: string; afm_nummer: string | null } | null;
    naar: { naam: string; afm_nummer: string | null } | null;
  }[],
): Saldorij[] {
  const perKantoor = new Map<number, Saldorij>();
  const zorg = (
    id: number,
    kantoor: { naam: string; afm_nummer: string | null } | null,
  ) => {
    if (!kantoor) return null;
    const bestaand = perKantoor.get(id);
    if (bestaand) return bestaand;
    const nieuw: Saldorij = {
      kantoorId: id,
      naam: kantoor.naam,
      afmNummer: kantoor.afm_nummer,
      gewonnen: 0,
      verloren: 0,
      saldo: 0,
    };
    perKantoor.set(id, nieuw);
    return nieuw;
  };

  for (const wisseling of wisselingen) {
    const naar = zorg(wisseling.naar_kantoor_id, wisseling.naar);
    if (naar) naar.gewonnen += 1;
    const van = zorg(wisseling.van_kantoor_id, wisseling.van);
    if (van) van.verloren += 1;
  }
  for (const rij of perKantoor.values()) rij.saldo = rij.gewonnen - rij.verloren;

  return [...perKantoor.values()].sort(
    (a, b) => b.saldo - a.saldo || b.gewonnen - a.gewonnen || a.naam.localeCompare(b.naam, "nl"),
  );
}
