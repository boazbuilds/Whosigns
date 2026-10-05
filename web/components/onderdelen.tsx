/** Gedeelde bouwstenen voor de pagina's. */

import Link from "next/link";
import type { Bronlabel, Kantoor } from "@/lib/db";
import {
  kantoorPad,
  kortKantoor,
  OORDEEL_LABEL,
  oordeelOpvallend,
  OPDRACHT_LABEL,
  procent,
  SOORT_UITLEG,
  SOORTGROEP,
  vergunningSoort,
  type Vergunningsoort,
} from "@/lib/paden";
import { wapenVoor } from "@/lib/wapen";

/**
 * Wat voor opdracht het was, als label.
 *
 * Drie tinten, omdat er drie soorten verschil te maken zijn. De wettelijke
 * controle is negen van de tien opdrachten en dus de norm: die staat rustig.
 * De vrijwillige controle is ook een volledige jaarrekeningcontrole, maar er
 * was geen plicht — dat verschil is klein en het label dus bijna hetzelfde.
 *
 * De derde groep is de reden dat dit onderdeel bestaat: een verklaring bij een
 * WNT-opgave, een productieverantwoording of een subsidieafrekening gaat NIET
 * over de jaarrekening. Stond die als grijze tekst tussen de rest, dan las een
 * bezoeker hem als "de accountant heeft de jaarrekening gecontroleerd". Die
 * springt er nu uit.
 */
export function Soort({ type }: { type: string }) {
  const groep = SOORTGROEP[type] ?? "onbekend";
  const klasse =
    groep === "anders" ? "label label-anders"
    : groep === "onbekend" ? "label label-vaag"
    : "label";
  return (
    <span className={klasse} title={SOORT_UITLEG[type] ?? undefined}>
      {OPDRACHT_LABEL[type] ?? type}
    </span>
  );
}

/**
 * Het oordeel als label; niet-goedkeurend krijgt nadruk.
 *
 * `waarde` komt uit de gedeponeerde verklaring zelf en gaat voor. `gerapporteerd`
 * is wat de organisatie in de jaardataset heeft opgegeven en dient als vangnet:
 * bij een ingescande pdf zonder tekstlaag is dat het enige dat er is. Zo'n
 * oordeel wordt gemarkeerd als opgave, want het is niet uit het ondertekende
 * stuk gelezen.
 */
export function Oordeel({
  waarde,
  gerapporteerd = null,
}: {
  waarde: string | null;
  gerapporteerd?: string | null;
}) {
  const oordeel = waarde ?? gerapporteerd;
  if (!oordeel) return <span className="zacht">—</span>;
  const tekst = OORDEEL_LABEL[oordeel] ?? oordeel;
  return (
    <>
      <span className={oordeelOpvallend(oordeel) ? "label label-let-op" : "label"}>
        {tekst}
      </span>
      {waarde === null ? (
        <>
          {" "}
          <span className="zacht klein" title="Opgave van de organisatie zelf; de verklaring was niet machinaal leesbaar">
            (opgave)
          </span>
        </>
      ) : null}
    </>
  );
}

/**
 * Het wapen van een kantoor: een monogram in de huiskleur.
 *
 * Geen echt bedrijfslogo — zie lib/wapen.ts voor waarom niet. Het schildje is
 * puur decoratief naast een naam die er altijd bij staat, dus voor een
 * schermlezer is het lucht: `aria-hidden`.
 */
export function Wapen({
  naam,
  maat = "m",
}: {
  naam: string;
  maat?: "s" | "m" | "l" | "xl";
}) {
  const wapen = wapenVoor(naam);
  return (
    <span
      className={`wapen wapen-${maat}`}
      style={{ background: wapen.kleur, color: wapen.inkt }}
      aria-hidden="true"
    >
      {wapen.monogram}
    </span>
  );
}

/**
 * Kantoornaam met wapen ervoor, als link.
 *
 * De naam staat kort ("PricewaterhouseCoopers") omdat hij in ranglijsten
 * anders over drie regels breekt; voluit staat hij in het `title`-attribuut en
 * op de kantoorpagina zelf. Zet `voluit` waar de ruimte er wél is.
 */
export function KantoorLink({
  naam,
  naar,
  maat = "s",
  voluit = false,
}: {
  naam: string;
  naar: string;
  maat?: "s" | "m" | "l";
  voluit?: boolean;
}) {
  const tonen = voluit ? naam : kortKantoor(naam);
  return (
    <span className="naamcel">
      <Wapen naam={naam} maat={maat} />
      <Link href={naar} title={tonen === naam ? undefined : naam}>
        {tonen}
      </Link>
    </span>
  );
}

/**
 * Kantoornaam als losse link, kort weergegeven.
 *
 * Voor transferregels ("BDO → Stolwijk Kelderman"), waar twee kantoornamen op
 * één regel moeten passen. `null` wordt een vraagteken: dat komt voor als een
 * wisseling naar een kantoor verwijst dat niet meer in de database staat.
 */
export function KortKantoorLink({
  kantoor,
}: {
  kantoor: { afm_nummer: string | null; naam: string; id: number } | null;
}) {
  if (!kantoor) return <span className="zacht">?</span>;
  const kort = kortKantoor(kantoor.naam);
  return (
    <Link
      href={kantoorPad(kantoor)}
      title={kort === kantoor.naam ? undefined : kantoor.naam}
    >
      {kort}
    </Link>
  );
}

const VERGUNNING_KORT: Record<Vergunningsoort, string> = {
  oob: "OOB",
  wta: "Wta",
  vervallen: "vervallen",
  geen: "geen Wta-vergunning",
};

const VERGUNNING_VOLUIT: Record<Vergunningsoort, string> = {
  oob: "OOB-vergunning",
  wta: "reguliere Wta-vergunning",
  vervallen: "niet meer in het AFM-register",
  geen: "geen Wta-vergunning",
};

/**
 * Het vergunningslabel achter een kantoornaam, kort in een tabel en voluit op
 * de kantoorpagina — met de regel van vergunningSoort(). OOB als gekleurd
 * label; de rest als tekst in de klasse van de plek waar het staat.
 */
export function Vergunning({
  kantoor,
  voluit = false,
  className,
}: {
  kantoor: Pick<Kantoor, "afm_nummer" | "oob_vergunning" | "wta_vergunning" | "actief">;
  voluit?: boolean;
  className?: string;
}) {
  const soort = vergunningSoort(kantoor);
  const tekst = (voluit ? VERGUNNING_VOLUIT : VERGUNNING_KORT)[soort];
  if (soort === "oob") return <span className="label label-oob">{tekst}</span>;
  return (
    <span
      className={className}
      title={
        soort === "vervallen"
          ? "Staat niet meer in het AFM-register van accountantsorganisaties"
          : undefined
      }
    >
      {tekst}
    </span>
  );
}

/** Positienummer in een ranglijst; de top drie krijgt kleur. */
export function Rang({ nummer }: { nummer: number }) {
  const klasse = nummer <= 3 ? `rang rang-${nummer}` : "rang";
  return <span className={klasse}>{nummer}</span>;
}

/**
 * Marktaandeel als balk plus percentage.
 *
 * `deel` en `geheel` in plaats van een kant-en-klaar percentage: zo staat de
 * berekening op één plek en kan er geen pagina zijn die 100% anders afrondt.
 */
export function Aandeelbalk({ deel, geheel }: { deel: number; geheel: number }) {
  const pct = geheel > 0 ? (deel / geheel) * 100 : 0;
  return (
    <span className="balkregel">
      <span className="balk" role="img" aria-label={procent(pct)}>
        <span style={{ width: `${Math.max(pct, 1.5)}%` }} />
      </span>
      <span className="pct">{procent(pct)}</span>
    </span>
  );
}

/**
 * Een aantal als balk, geschaald op de grootste in dezelfde lijst — zonder
 * percentage.
 *
 * Voor de lijsten over alle sectoren heen (voorpagina, /kantoren). Daar stond
 * een Aandeelbalk met "12,9%", maar de noemer was alles wat er voor dat
 * boekjaar in de database stond, en welke sectoren dat zijn verschilt per jaar.
 * Een aandeel of plek noemt de site alleen binnen één sector en één boekjaar;
 * hier blijft alleen de verhouding tussen de aantallen over, en die is waar.
 */
export function Telbalk({ aantal, grootste }: { aantal: number; grootste: number }) {
  const breedte = grootste > 0 ? (aantal / grootste) * 100 : 0;
  return (
    <span className="balkregel" aria-hidden="true">
      <span className="balk">
        <span style={{ width: `${Math.max(breedte, 1.5)}%` }} />
      </span>
    </span>
  );
}

/**
 * Het bronlabel bij een gegeven dat iemand zelf heeft aangeleverd, zoals het
 * marktonderzoek; bij een openbare bron niets.
 *
 * De labelplicht uit docs/concept.md: bij elk gegeven hoort zichtbaar te zijn
 * of het uit een openbare bron komt. Het colofon belooft dat opdrachten uit
 * marktonderzoek dat label dragen, maar tot 5-10-2026 stond het alleen naast
 * een bron met een url — en het marktonderzoek heeft er geen. Zo stonden
 * 35.582 opdrachten bij 12.726 organisaties zonder label, waarvan 11.646
 * organisaties met niets anders dan marktonderzoek. Alleen het soort bron, nooit
 * de leverancier of een bestandsnaam.
 */
export function Aangeleverd({
  bron,
  jaren,
  van,
}: {
  bron: Bronlabel | null | undefined;
  /** Bij een periode: de boekjaren die op deze bron rusten. */
  jaren?: number[];
  /** En alle boekjaren van die periode. Rust maar een deel op de aangeleverde
   *  bron, dan staan die jaren in het label zelf: "marktonderzoek 2018" naast
   *  een periode 2018–2025 zegt iets anders dan alleen "marktonderzoek". */
  van?: number[];
}) {
  if (!bron || bron.betrouwbaarheid !== "zelf_aangeleverd") return null;
  const uitleg = `${bron.bron_type}, niet uit een openbaar document en niet per opdracht na te slaan.`;
  const deel = jaren?.length ? jarenKort(jaren) : "";
  const titel = deel
    ? `${jaren!.length === 1 ? "Boekjaar" : "Boekjaren"} ${deel}: aangeleverd ${uitleg}`
    : `Aangeleverd ${uitleg}`;
  const gedeeltelijk = deel && van && jaren!.length < new Set(van).size;
  return (
    <span className="label label-vaag" title={titel}>
      {gedeeltelijk ? `${bron.bron_type} ${deel}` : bron.bron_type}
    </span>
  );
}

/** "2017–2018, 2021": aaneengesloten jaren als reeks, de rest los. */
function jarenKort(jaren: number[]): string {
  const gesorteerd = [...new Set(jaren)].sort((a, b) => a - b);
  const stukken: string[] = [];
  let begin = gesorteerd[0];
  for (let i = 1; i <= gesorteerd.length; i++) {
    if (gesorteerd[i] === gesorteerd[i - 1] + 1) continue;
    const eind = gesorteerd[i - 1];
    stukken.push(begin === eind ? `${begin}` : `${begin}–${eind}`);
    begin = gesorteerd[i];
  }
  return stukken.join(", ");
}

/** Waar je heen kunt: een grote knop met naam, toelichting en wapens. */
export function Tegel({
  naar,
  naam,
  meta,
  wapens = [],
}: {
  naar: string;
  naam: string;
  meta?: string;
  wapens?: string[];
}) {
  return (
    <Link href={naar} className="tegel">
      <span className="tegelnaam">{naam}</span>
      {meta ? <span className="tegelmeta">{meta}</span> : null}
      {wapens.length ? (
        <span className="tegelwapens">
          {wapens.map((kantoornaam) => (
            <Wapen key={kantoornaam} naam={kantoornaam} maat="s" />
          ))}
        </span>
      ) : null}
    </Link>
  );
}

/** Eén van de top drie, groot uitgelicht. */
export function Podiumplek({
  plek,
  naar,
  naam,
  onder,
  groot,
}: {
  plek: number;
  naar: string;
  naam: string;
  onder: string;
  groot: string;
}) {
  return (
    <Link href={naar} className={`podiumplek plek-${plek}`} title={naam}>
      <Wapen naam={naam} maat="l" />
      <span style={{ minWidth: 0 }}>
        <span className="naam">{kortKantoor(naam)}</span>
        <br />
        <span className="onder">{onder}</span>
      </span>
      <span className="groot">{groot}</span>
    </Link>
  );
}

/** Eén groot getal met een naam eronder; als `naar` is gegeven, aanklikbaar. */
export function Kerncijfer({
  waarde,
  naam,
  naar,
}: {
  waarde: string | number;
  naam: string;
  naar?: string;
}) {
  const binnen = (
    <>
      <span className="waarde">{waarde}</span>
      <span className="naam">{naam}</span>
    </>
  );
  return naar ? (
    <Link href={naar} className="kerncijfer">
      {binnen}
    </Link>
  ) : (
    <div className="kerncijfer">{binnen}</div>
  );
}

/** Het spoor terug naar boven: Start › Sectoren › Zorg. */
export function Kruimels({
  paden,
}: {
  paden: { naar?: string; tekst: string }[];
}) {
  return (
    <nav className="kruimels" aria-label="Kruimelpad">
      {paden.map((kruimel, i) => {
        const laatste = i === paden.length - 1;
        return (
          <span key={kruimel.tekst + i}>
            {kruimel.naar && !laatste ? (
              <Link href={kruimel.naar}>{kruimel.tekst}</Link>
            ) : (
              kruimel.tekst
            )}
          </span>
        );
      })}
    </nav>
  );
}

export type Doorklikje = {
  naar: string;
  tekst: string;
  toelichting?: string;
};

/**
 * Het blok onderaan elke pagina.
 *
 * Harde UI-regel uit docs/visie.md: **minimaal 5 interessante vervolgklikken per
 * pagina, nooit een doodlopende pagina.** Tijdens ontwikkelen waarschuwt dit
 * onderdeel in de console als een pagina onder de vijf zakt, zodat de regel niet
 * stilletjes sneuvelt als er een link wegvalt bij weinig data.
 */
export function Doorklik({
  titel = "Verder klikken",
  items,
}: {
  titel?: string;
  items: Doorklikje[];
}) {
  // Dubbelen eruit (zelfde link én tekst): de relatiegeschiedenis A→B→A leverde
  // hetzelfde kantoor twee keer aan, en dat gaf twee identieke regels met
  // botsende React-sleutels.
  const zichtbaar = [
    ...new Map(
      items
        .filter((item) => item.naar)
        .map((item) => [`${item.naar}|${item.tekst}`, item] as const),
    ).values(),
  ];
  if (process.env.NODE_ENV !== "production" && zichtbaar.length < 5) {
    console.warn(
      `[visie] Deze pagina heeft ${zichtbaar.length} vervolgklikken; de regel is minimaal 5.`,
    );
  }
  if (!zichtbaar.length) return null;
  return (
    <nav className="doorklik" aria-label={titel}>
      <h2>{titel}</h2>
      <ul>
        {zichtbaar.map((item) => (
          <li key={item.naar + item.tekst}>
            <Link href={item.naar}>{item.tekst}</Link>
            {item.toelichting ? (
              <span className="zacht klein"> — {item.toelichting}</span>
            ) : null}
          </li>
        ))}
      </ul>
    </nav>
  );
}

/**
 * De staart van een lange lijst, achter één klik.
 *
 * Een tabel van honderden regels is op een telefoon geen lijst meer maar een muur:
 * je scrolt eindeloos langs iets waar je niet om vroeg, en de rest van de pagina
 * raakt onbereikbaar. De eerste regels staan open, de staart zit hierin.
 *
 * Bewust `<details>` en geen uitklap-knop in JavaScript: het werkt zonder, het is
 * met toetsenbord te openen, en de links blijven in de HTML staan — zoekmachines
 * en Ctrl-F vinden ze dus alsnog. Dat laatste is precies waarom we de staart
 * inklappen en niet weglaten.
 */
export function Inklapbaar({
  samenvatting,
  children,
}: {
  samenvatting: string;
  children: React.ReactNode;
}) {
  return (
    <details className="inklapbaar">
      <summary>{samenvatting}</summary>
      {children}
    </details>
  );
}

/** Nette melding als de database niet bereikbaar is of leeg blijkt. */
export function Foutmelding({ fout }: { fout: unknown }) {
  const tekst = fout instanceof Error ? fout.message : String(fout);
  return (
    <div className="foutvlak">
      <strong>De gegevens konden niet worden opgehaald.</strong>
      <p className="klein">
        <code>{tekst}</code>
      </p>
    </div>
  );
}

export function Leeg({ tekst }: { tekst: string }) {
  return <p className="leeg">{tekst}</p>;
}
