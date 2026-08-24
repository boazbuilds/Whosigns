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
  /** Oordeel uit de gedeponeerde verklaring van het getoonde boekjaar: zonder
   *  jaarfilter het laatste, met jaarfilter dat jaar. */
  oordeelLaatste: string | null;
  /** Opgave van de organisatie zelf, apart gehouden: het verschil moet op de
   *  pagina zichtbaar blijven als "(opgave)" — samengevouwen ging dat label
   *  verloren en stond een eigen opgave er als gelezen feit. */
  oordeelOpgaveLaatste: string | null;
  /** Opdrachttype van het getoonde boekjaar. Nodig omdat een kantoor naast
   *  jaarrekeningcontroles ook WNT- of productieverantwoordingen kan doen; die
   *  ongemerkt als cliënt tonen suggereert meer dan er staat. */
  typeLaatste: string;
};

/** De stand van één boekjaar binnen één cliëntrelatie. */
type Jaarstand = {
  oordeel: string | null;
  oordeelOpgave: string | null;
  type: string;
  voorrang: number;
};

/**
 * Eén regel per cliënt in plaats van één regel per cliëntjaar.
 *
 * Zonder `boekjaar` de volledige lijst, nieuwste relatie eerst, met type en
 * oordeel uit ieders laatste boekjaar. Mét `boekjaar` alleen de cliënten van
 * dat jaar (de "selectie van het seizoen"), alfabetisch, met type en oordeel
 * uit dát jaar — de kolom `jaren` blijft de hele relatie beslaan, zodat de
 * duur van de relatie zichtbaar blijft.
 */
export function clientenVanKantoor(
  opdrachten: OpdrachtMetOrganisatie[],
  boekjaar?: number,
): Clientregel[] {
  const perOrganisatie = new Map<
    number,
    Clientregel & {
      jaarSet: Set<number>;
      voorrangLaatste: number;
      perJaar: Map<number, Jaarstand>;
    }
  >();
  for (const opdracht of opdrachten) {
    const org = opdracht.organisaties;
    if (!org) continue;
    // Binnen één boekjaar wint de jaarrekeningcontrole van een WNT- of
    // productieverantwoording, zodat het getoonde oordeel over de
    // jaarrekening gaat en niet van de rijvolgorde afhangt.
    const voorrang = TYPE_VOORRANG[opdracht.type_opdracht] ?? 9;
    let regel = perOrganisatie.get(org.id);
    if (!regel) {
      regel = {
        organisatieId: org.id,
        naam: org.naam,
        kvkNummer: org.kvk_nummer,
        gemeente: org.gemeente,
        sector: org.sector,
        jaren: [],
        jaarSet: new Set(),
        laatsteBoekjaar: opdracht.boekjaar,
        oordeelLaatste: opdracht.oordeel,
        oordeelOpgaveLaatste: opdracht.oordeel_gerapporteerd,
        typeLaatste: opdracht.type_opdracht,
        voorrangLaatste: voorrang,
        perJaar: new Map(),
      };
      perOrganisatie.set(org.id, regel);
    }
    regel.jaarSet.add(opdracht.boekjaar);
    if (
      opdracht.boekjaar > regel.laatsteBoekjaar ||
      (opdracht.boekjaar === regel.laatsteBoekjaar &&
        voorrang < regel.voorrangLaatste)
    ) {
      regel.laatsteBoekjaar = opdracht.boekjaar;
      regel.oordeelLaatste = opdracht.oordeel;
      regel.oordeelOpgaveLaatste = opdracht.oordeel_gerapporteerd;
      regel.typeLaatste = opdracht.type_opdracht;
      regel.voorrangLaatste = voorrang;
    }
    const jaarstand = regel.perJaar.get(opdracht.boekjaar);
    if (!jaarstand || voorrang < jaarstand.voorrang) {
      regel.perJaar.set(opdracht.boekjaar, {
        oordeel: opdracht.oordeel,
        oordeelOpgave: opdracht.oordeel_gerapporteerd,
        type: opdracht.type_opdracht,
        voorrang,
      });
    }
  }

  if (boekjaar === undefined) {
    return [...perOrganisatie.values()]
      .map(({ jaarSet, voorrangLaatste: _v, perJaar: _p, ...regel }) => ({
        ...regel,
        jaren: [...jaarSet].sort((a, b) => a - b),
      }))
      .sort(
        (a, b) => b.laatsteBoekjaar - a.laatsteBoekjaar || a.naam.localeCompare(b.naam),
      );
  }

  return [...perOrganisatie.values()]
    .filter((regel) => regel.perJaar.has(boekjaar))
    .map(({ jaarSet, voorrangLaatste: _v, perJaar, ...regel }) => {
      const stand = perJaar.get(boekjaar)!;
      return {
        ...regel,
        jaren: [...jaarSet].sort((a, b) => a - b),
        oordeelLaatste: stand.oordeel,
        oordeelOpgaveLaatste: stand.oordeelOpgave,
        typeLaatste: stand.type,
      };
    })
    .sort((a, b) => a.naam.localeCompare(b.naam, "nl"));
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

/** Controlehonoraria samengevat per boekjaar. */
export type HonorariumJaar = {
  boekjaar: number;
  aantal: number;
  gemiddelde: number;
  mediaan: number;
};

/** De vorm die de honorarium-afleidingen nodig hebben; een subset van
 *  HonorariumRij uit db.ts, structureel getypt zodat een test geen echte
 *  databaserij hoeft na te bouwen. */
type HonorariumBron = {
  boekjaar: number;
  honorarium_controle_eur: number | null;
  organisaties: { id: number } | null;
  kantoren: { id: number; naam: string; afm_nummer: string | null } | null;
};

/**
 * Gemiddelde en mediaan van het controlehonorarium per boekjaar, nieuwste
 * eerst. Alleen de controlecategorie: de vier categorieën van art. 2:382a
 * BW blijven uit elkaar, en de andere drie ontbreken te vaak om een
 * jaargemiddelde te dragen.
 */
export function controleHonorariumPerJaar(rijen: HonorariumBron[]): HonorariumJaar[] {
  const perJaar = new Map<number, number[]>();
  for (const rij of rijen) {
    const bedrag = rij.honorarium_controle_eur;
    if (bedrag == null) continue;
    perJaar.set(rij.boekjaar, [...(perJaar.get(rij.boekjaar) ?? []), bedrag]);
  }
  return [...perJaar.entries()]
    .map(([boekjaar, bedragen]) => {
      bedragen.sort((a, b) => a - b);
      return {
        boekjaar,
        aantal: bedragen.length,
        gemiddelde: bedragen.reduce((som, bedrag) => som + bedrag, 0) / bedragen.length,
        mediaan: bedragen[Math.floor(bedragen.length / 2)],
      };
    })
    .sort((a, b) => b.boekjaar - a.boekjaar);
}

/** De prijsontwikkeling van één kantoor, gemeten op gematchte paren. */
export type Prijsontwikkeling = {
  kantoorId: number;
  naam: string;
  afmNummer: string | null;
  /** Aantal jaar-op-jaar-paren waarop de mediaan rust. */
  paren: number;
  /** Mediane jaar-op-jaar-verandering als fractie (0.062 = +6,2%). */
  mediaanVerandering: number;
  vanJaar: number;
  totJaar: number;
};

/**
 * Prijsontwikkeling per kantoor: de mediane jaar-op-jaar-verandering van het
 * controlehonorarium, gemeten op gematchte paren — dezelfde organisatie, bij
 * hetzelfde kantoor, in twee opeenvolgende boekjaren.
 *
 * Waarom zo omslachtig: het gemiddelde per kantoor per jaar vergelijkt vooral
 * de klantenmix (een kantoor dat een ziekenhuis wint "stijgt" dan zonder één
 * tarief te verhogen). Binnen een gematcht paar is de organisatie constant,
 * dus meet de verandering de prijs. De mediaan in plaats van het gemiddelde,
 * omdat één uitschieter bij kleine aantallen anders het hele kantoor kleurt;
 * en een minimum aantal paren, omdat een mediaan van twee waarnemingen geen
 * ontwikkeling is maar een anekdote.
 */
export function prijsontwikkelingPerKantoor(
  rijen: HonorariumBron[],
  minimumParen = 3,
): Prijsontwikkeling[] {
  // (organisatie, kantoor) -> boekjaar -> bedrag. Bij een dubbele rij voor
  // hetzelfde jaar wint de eerste; de bron levert er zelden meer dan één.
  const reeksen = new Map<
    string,
    {
      kantoor: { id: number; naam: string; afm_nummer: string | null };
      perJaar: Map<number, number>;
    }
  >();
  for (const rij of rijen) {
    const bedrag = rij.honorarium_controle_eur;
    if (bedrag == null || !rij.kantoren || !rij.organisaties) continue;
    const sleutel = `${rij.organisaties.id}-${rij.kantoren.id}`;
    const reeks = reeksen.get(sleutel) ?? { kantoor: rij.kantoren, perJaar: new Map() };
    if (!reeks.perJaar.has(rij.boekjaar)) reeks.perJaar.set(rij.boekjaar, bedrag);
    reeksen.set(sleutel, reeks);
  }

  const perKantoor = new Map<
    number,
    {
      kantoor: { id: number; naam: string; afm_nummer: string | null };
      veranderingen: number[];
      jaren: number[];
    }
  >();
  for (const reeks of reeksen.values()) {
    for (const [jaar, bedrag] of reeks.perJaar) {
      const vorig = reeks.perJaar.get(jaar - 1);
      if (vorig === undefined || vorig <= 0) continue;
      const stand = perKantoor.get(reeks.kantoor.id) ?? {
        kantoor: reeks.kantoor,
        veranderingen: [],
        jaren: [],
      };
      stand.veranderingen.push((bedrag - vorig) / vorig);
      stand.jaren.push(jaar - 1, jaar);
      perKantoor.set(reeks.kantoor.id, stand);
    }
  }

  return [...perKantoor.values()]
    .filter((stand) => stand.veranderingen.length >= minimumParen)
    .map((stand) => {
      const gesorteerd = [...stand.veranderingen].sort((a, b) => a - b);
      return {
        kantoorId: stand.kantoor.id,
        naam: stand.kantoor.naam,
        afmNummer: stand.kantoor.afm_nummer,
        paren: gesorteerd.length,
        mediaanVerandering: gesorteerd[Math.floor(gesorteerd.length / 2)],
        vanJaar: Math.min(...stand.jaren),
        totJaar: Math.max(...stand.jaren),
      };
    })
    .sort(
      (a, b) =>
        b.mediaanVerandering - a.mediaanVerandering || a.naam.localeCompare(b.naam, "nl"),
    );
}
