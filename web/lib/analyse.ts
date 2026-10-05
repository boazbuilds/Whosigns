/**
 * Kleine afleidingen die alleen voor de weergave nodig zijn.
 *
 * Let op de taakverdeling: wat een *feit* is (wanneer heet iets een wisseling,
 * hoe lang loopt een relatie, wat is marktaandeel) staat als view in SQL —
 * `supabase/migrations/`. Hier staat alleen het groeperen en tellen dat je nodig
 * hebt om een tabel te tekenen. Zo kan de database nooit iets anders beweren dan
 * de website.
 */

import type {
  Bronlabel,
  Kantoor,
  OpdrachtMetKantoor,
  OpdrachtMetOrganisatie,
} from "./db";
import { CONTROLE_TYPES } from "./paden";

/**
 * Welke opdrachttypen tellen als "de accountant van de organisatie", en wie
 * wint als een boekjaar er meerdere heeft. WNT- en productieverantwoordingen
 * doen bewust níét mee: die lopen soms bij een ander kantoor dan de
 * jaarrekening, en zonder dit filter kreeg een organisatie een "wisseling"
 * aangesmeerd omdat de productieverantwoording bij kantoor B lag terwijl de
 * jaarrekening gewoon bij A bleef — of ging de kop "Huidige accountant" over
 * de WNT-controleur.
 *
 * `controle_onbepaald` telt hier mee voor de kop "Huidige accountant" en de
 * relatiegeschiedenis, maar níét voor een wisseling (zie `wisseljaren`). Het
 * is precies wat we niet weten: laad_zorg.py geeft dit type aan een verklaring
 * waarvan het voorwerp níét viel vast te stellen, en het marktonderzoek levert
 * niets anders aan. Toch weglaten zou de pagina leeg maken van 11.646
 * organisaties die alleen uit marktonderzoek bekend zijn (gemeten 5-10-2026);
 * daar staat nu het label "controle, voorwerp onbekend" naast, en het
 * bronlabel "marktonderzoek".
 *
 * In de SQL-views telt het niet mee, want daar zou het ongemerkt als
 * jaarrekeningcontrole in een marktaandeel belanden. Op 20-8-2026 ging het nog
 * om 49 opdrachten bij 41 organisaties; sinds het marktonderzoek om 35.637,
 * waarvan 35.582 uit het marktonderzoek zelf.
 */
const TYPE_VOORRANG: Record<string, number> = {
  wettelijke_controle: 0,
  vrijwillige_controle: 1,
  controle_onbepaald: 2,
};

/**
 * Dezelfde voorrang, maar alleen de typen die v_wisselingen meetelt: de
 * wettelijke en de vrijwillige controle (CONTROLE_TYPES, migratie
 * 20260730000000). Hierop rust `wisseljaren`, zodat de organisatiepagina
 * dezelfde wisselingen aanwijst als /wisselingen.
 */
const WISSEL_VOORRANG: Record<string, number> = Object.fromEntries(
  CONTROLE_TYPES.map((type) => [type, TYPE_VOORRANG[type]]),
);

/** Het kantoor van één boekjaar, met de bron van de opdracht die won. */
type Jaarkantoor = { kantoor: Kantoor; bron: Bronlabel | null };

/**
 * 1 voor een aangeleverde bron, 0 voor een openbare. Bij verder gelijke
 * opdrachten (zelfde type, zelfde kantoor) wint zo de openbare, en staat het
 * label "marktonderzoek" alleen waar er voor dat jaar niets openbaars is — niet
 * afhankelijk van welke rij de database het eerst teruggeeft.
 */
function aangeleverd(bron: Bronlabel | null | undefined): number {
  return bron?.betrouwbaarheid === "zelf_aangeleverd" ? 1 : 0;
}

/** Per boekjaar het kantoor van de jaarrekeningcontrole (voorrang: wettelijk
 *  boven vrijwillig boven onbepaald; daarbinnen het laagste kantoor-id, zodat
 *  de uitkomst niet afhangt van de rijvolgorde uit de database). */
function controleKantoorPerJaar(
  opdrachten: OpdrachtMetKantoor[],
  voorrangPerType: Record<string, number> = TYPE_VOORRANG,
): Map<number, Jaarkantoor> {
  const perJaar = new Map<number, Jaarkantoor & { voorrang: number }>();
  for (const opdracht of opdrachten) {
    const voorrang = voorrangPerType[opdracht.type_opdracht];
    if (voorrang === undefined || !opdracht.kantoren) continue;
    const bestaand = perJaar.get(opdracht.boekjaar);
    if (
      !bestaand ||
      voorrang < bestaand.voorrang ||
      (voorrang === bestaand.voorrang && opdracht.kantoren.id < bestaand.kantoor.id) ||
      (voorrang === bestaand.voorrang &&
        opdracht.kantoren.id === bestaand.kantoor.id &&
        aangeleverd(opdracht.bronnen) < aangeleverd(bestaand.bron))
    ) {
      perJaar.set(opdracht.boekjaar, {
        kantoor: opdracht.kantoren,
        bron: opdracht.bronnen,
        voorrang,
      });
    }
  }
  return new Map(
    [...perJaar.entries()].map(([jaar, { voorrang: _v, ...rest }]) => [jaar, rest]),
  );
}

/** De reeks boekjaren die aaneengesloten bij hetzelfde kantoor horen. */
export type Periode = {
  kantoorId: number;
  kantoorNaam: string;
  afmNummer: string | null;
  jaren: number[];
  /** Boekjaren in deze periode waarvan het kantoor alleen uit een
   *  aangeleverde bron komt (het marktonderzoek), met die bron erbij; leeg en
   *  null als elk jaar uit een openbare bron komt. */
  aangeleverdeJaren: number[];
  aangeleverd: Bronlabel | null;
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
    const { kantoor, bron } = perJaar.get(jaar)!;
    const laatste = uit[uit.length - 1];
    const vorigJaar = laatste?.jaren[laatste.jaren.length - 1];
    let periode: Periode;
    if (laatste && laatste.kantoorId === kantoor.id && vorigJaar === jaar + 1) {
      periode = laatste;
      periode.jaren.push(jaar);
    } else {
      periode = {
        kantoorId: kantoor.id,
        kantoorNaam: kantoor.naam,
        afmNummer: kantoor.afm_nummer,
        jaren: [jaar],
        aangeleverdeJaren: [],
        aangeleverd: null,
      };
      uit.push(periode);
    }
    if (bron?.betrouwbaarheid === "zelf_aangeleverd") {
      periode.aangeleverdeJaren.push(jaar);
      periode.aangeleverd ??= bron;
    }
  }
  return uit;
}

/** Opeenvolgende boekjaren met een ander kantoor, volgens deze voorrang. */
function overgangen(perJaar: Map<number, Jaarkantoor>): Set<number> {
  const jaren = new Set<number>();
  for (const [jaar, { kantoor }] of perJaar) {
    const vorige = perJaar.get(jaar - 1);
    if (vorige && vorige.kantoor.id !== kantoor.id) jaren.add(jaar);
  }
  return jaren;
}

/**
 * Boekjaren waarin het controlerende kantoor anders was dan het boekjaar ervoor:
 * opeenvolgende jaren, ander kantoor — alleen op wettelijke en vrijwillige
 * controles, precies zoals v_wisselingen.
 *
 * Tot 5-10-2026 telde `controle_onbepaald` hier mee. Toen dat 49 gelezen
 * zorgverklaringen waren was het verschil met /wisselingen twee wisselingen;
 * met het marktonderzoek erbij werden het er 517, bij 495 organisaties (2.226
 * tegen 1.709 in v_wisselingen). Een regel uit het marktonderzoek bij kantoor
 * B na een gelezen verklaring van kantoor A kreeg zo het label "wisseling",
 * met "gewisseld in boekjaar X" in de kop en een doorklik naar /wisselingen
 * waar hij niet stond. Met deze set wijzen pagina en view exact dezelfde
 * 1.709 wisselingen aan.
 */
export function wisseljaren(opdrachten: OpdrachtMetKantoor[]): Set<number> {
  return overgangen(controleKantoorPerJaar(opdrachten, WISSEL_VOORRANG));
}

/**
 * Boekjaren met een ander kantoor dan het jaar ervoor die géén wisseling zijn,
 * omdat aan één kant alleen een controle staat waarvan het voorwerp onbekend
 * is. De organisatiepagina zet daar een neutraal label bij in plaats van
 * "wisseling": het kantoor is anders, maar dat de jaarrekeningcontrole
 * verhuisde is niet vastgesteld.
 */
export function onbevestigdeWisseljaren(opdrachten: OpdrachtMetKantoor[]): Set<number> {
  const bevestigd = wisseljaren(opdrachten);
  return new Set(
    [...overgangen(controleKantoorPerJaar(opdrachten))].filter((jaar) => !bevestigd.has(jaar)),
  );
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
  /** De bron van die opdracht. Een cliënt die er alleen staat dankzij het
   *  aangeleverde marktonderzoek draagt in de lijst dat label. */
  bronLaatste: Bronlabel | null;
};

/** De stand van één boekjaar binnen één cliëntrelatie. */
type Jaarstand = {
  oordeel: string | null;
  oordeelOpgave: string | null;
  type: string;
  bron: Bronlabel | null;
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
        bronLaatste: opdracht.bronnen,
        voorrangLaatste: voorrang,
        perJaar: new Map(),
      };
      perOrganisatie.set(org.id, regel);
    }
    regel.jaarSet.add(opdracht.boekjaar);
    if (
      opdracht.boekjaar > regel.laatsteBoekjaar ||
      (opdracht.boekjaar === regel.laatsteBoekjaar &&
        (voorrang < regel.voorrangLaatste ||
          (voorrang === regel.voorrangLaatste &&
            aangeleverd(opdracht.bronnen) < aangeleverd(regel.bronLaatste))))
    ) {
      regel.laatsteBoekjaar = opdracht.boekjaar;
      regel.oordeelLaatste = opdracht.oordeel;
      regel.oordeelOpgaveLaatste = opdracht.oordeel_gerapporteerd;
      regel.typeLaatste = opdracht.type_opdracht;
      regel.bronLaatste = opdracht.bronnen;
      regel.voorrangLaatste = voorrang;
    }
    const jaarstand = regel.perJaar.get(opdracht.boekjaar);
    if (
      !jaarstand ||
      voorrang < jaarstand.voorrang ||
      (voorrang === jaarstand.voorrang &&
        aangeleverd(opdracht.bronnen) < aangeleverd(jaarstand.bron))
    ) {
      regel.perJaar.set(opdracht.boekjaar, {
        oordeel: opdracht.oordeel,
        oordeelOpgave: opdracht.oordeel_gerapporteerd,
        type: opdracht.type_opdracht,
        bron: opdracht.bronnen,
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
        bronLaatste: stand.bron,
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

/**
 * Het saldo van één kantoor in de meegegeven wisselingen: hoeveel cliënten het
 * won en verloor. Dezelfde telling als de kop van de kantoorpagina.
 *
 * Voor /wisselingen?kantoor=, waar alle rijen over dit ene kantoor gaan. De
 * saldi van de andere kantoren in die rijen zeggen alleen wat zij van dít
 * kantoor wonnen of eraan verloren, niet hoe ze er in de markt voor staan.
 */
export function saldoVanKantoor(
  wisselingen: { van_kantoor_id: number; naar_kantoor_id: number }[],
  kantoorId: number,
): { gewonnen: number; verloren: number; saldo: number } {
  const gewonnen = wisselingen.filter((w) => w.naar_kantoor_id === kantoorId).length;
  const verloren = wisselingen.filter((w) => w.van_kantoor_id === kantoorId).length;
  return { gewonnen, verloren, saldo: gewonnen - verloren };
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

/**
 * Per boekjaar (nieuwste eerst) de sectoren (meeste regels eerst, bij gelijke
 * stand op naam) met hun regels, in de volgorde waarin ze binnenkwamen; op
 * /honoraria is dat het hoogste controlehonorarium eerst. Zo vergelijkt elke
 * tabel daar alleen binnen één sector en één boekjaar. Hier en niet in de
 * pagina, zodat pipeline/test_site_snel.py het kan narekenen.
 */
export function perBoekjaarEnSector<
  T extends { boekjaar: number; organisaties: { sector: string | null } | null },
>(rijen: T[]): { boekjaar: number; aantal: number; sectoren: [string | null, T[]][] }[] {
  const jaren = new Map<number, Map<string | null, T[]>>();
  for (const rij of rijen) {
    const sectoren = jaren.get(rij.boekjaar) ?? new Map<string | null, T[]>();
    const sector = rij.organisaties?.sector ?? null;
    const lijst = sectoren.get(sector) ?? [];
    lijst.push(rij);
    sectoren.set(sector, lijst);
    jaren.set(rij.boekjaar, sectoren);
  }
  return [...jaren.entries()]
    .sort((a, b) => b[0] - a[0])
    .map(([boekjaar, sectoren]) => ({
      boekjaar,
      aantal: [...sectoren.values()].reduce((som, lijst) => som + lijst.length, 0),
      sectoren: [...sectoren.entries()].sort(
        (a, b) => b[1].length - a[1].length || (a[0] ?? "").localeCompare(b[0] ?? "", "nl"),
      ),
    }));
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
  // hetzelfde jaar wint het hoogste bedrag; de bron levert er zelden meer dan
  // één. Uitdrukkelijk het hoogste en niet "de eerste": dan hangt de uitkomst
  // niet af van de volgorde waarin de rijen binnenkomen, en rekent de
  // voorpagina (prijsontwikkelingPerJaar) met precies dezelfde paren.
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
    bewaarHoogste(reeks.perJaar, rij.boekjaar, bedrag);
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

/** Zet `bedrag` bij `jaar`, tenzij daar al een hoger bedrag staat. */
function bewaarHoogste(perJaar: Map<number, number>, jaar: number, bedrag: number) {
  const bestaand = perJaar.get(jaar);
  if (bestaand === undefined || bedrag > bestaand) perJaar.set(jaar, bedrag);
}

/** De prijsontwikkeling van één boekjaar op het vorige, over alle kantoren samen. */
export type PrijsJaar = {
  /** Het tweede jaar van elk paar: 2022 staat voor 2021 → 2022. */
  boekjaar: number;
  paren: number;
  /** Mediane jaar-op-jaar-verandering als fractie (0.062 = +6,2%). */
  mediaanVerandering: number;
};

/**
 * Hoeveel duurder een controle werd, per boekjaar: de mediane verandering van
 * het controlehonorarium op gematchte paren — dezelfde organisatie bij
 * hetzelfde kantoor in twee opeenvolgende boekjaren. Dezelfde paren als
 * `prijsontwikkelingPerKantoor`, alleen per jaar gegroepeerd in plaats van per
 * kantoor.
 *
 * Het gemiddelde honorarium per jaar zou vooral meten wélke organisaties dat
 * jaar in de database staan: voor 2020 en 2021 honderden zorginstellingen, in
 * de jaren erna enkele tientallen organisaties uit andere bronnen. Binnen een
 * paar staat de organisatie vast, dus meet de verandering de prijs. Jaren met
 * minder dan `minimumParen` paren vallen weg: een mediaan van een handvol is
 * een anekdote.
 */
export function prijsontwikkelingPerJaar(
  rijen: {
    boekjaar: number;
    organisatie_id: number;
    kantoor_id: number | null;
    honorarium_controle_eur: number | null;
  }[],
  minimumParen = 20,
): PrijsJaar[] {
  const reeksen = new Map<string, Map<number, number>>();
  for (const rij of rijen) {
    const bedrag = rij.honorarium_controle_eur;
    if (bedrag == null || rij.kantoor_id == null) continue;
    const sleutel = `${rij.organisatie_id}-${rij.kantoor_id}`;
    const perJaar = reeksen.get(sleutel) ?? new Map<number, number>();
    bewaarHoogste(perJaar, rij.boekjaar, bedrag);
    reeksen.set(sleutel, perJaar);
  }

  const veranderingen = new Map<number, number[]>();
  for (const reeks of reeksen.values()) {
    for (const [jaar, bedrag] of reeks) {
      const vorig = reeks.get(jaar - 1);
      if (vorig === undefined || vorig <= 0) continue;
      veranderingen.set(jaar, [...(veranderingen.get(jaar) ?? []), (bedrag - vorig) / vorig]);
    }
  }

  return [...veranderingen.entries()]
    .filter(([, lijst]) => lijst.length >= minimumParen)
    .map(([boekjaar, lijst]) => {
      const gesorteerd = [...lijst].sort((a, b) => a - b);
      return {
        boekjaar,
        paren: gesorteerd.length,
        mediaanVerandering: gesorteerd[Math.floor(gesorteerd.length / 2)],
      };
    })
    .sort((a, b) => a.boekjaar - b.boekjaar);
}
