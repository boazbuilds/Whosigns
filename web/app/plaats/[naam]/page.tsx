import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import {
  opdrachtenVanOrganisaties,
  organisatiesInPlaats,
  plaatsRijen,
  tel,
  type Kantoor,
} from "@/lib/db";
import {
  aantalOrganisaties,
  CONTROLE_TYPES,
  hoofdletter,
  kantoorPad,
  nl,
  organisatiePad,
  PLAATS_MINIMUM,
  plaatsgroepen,
  plaatsPad,
  procent,
  sectorPad,
  veiligGedecodeerd,
  type Plaatsgroep,
} from "@/lib/paden";
import {
  Doorklik,
  Foutmelding,
  Inklapbaar,
  KantoorLink,
  Kerncijfer,
  Kruimels,
  Leeg,
  Soort,
} from "@/components/onderdelen";

type Params = { params: Promise<{ naam: string }> };

/** Zoveel organisaties staan open; de rest zit achter een klik. Amsterdam had
 *  er op 5-10-2026 184. */
const OPEN = 30;

/**
 * De plaats bij een slug, met al zijn schrijfwijzen. Net als bij de sector-
 * en subsectorpagina is de slug niet terug te vertalen, dus we zoeken hem op
 * in de lijst die de database kent. Onder PLAATS_MINIMUM organisaties geen
 * pagina: daar linkt ook niets heen.
 */
async function vindPlaats(naamSlug: string): Promise<{
  plaats: Plaatsgroep | null;
  groepen: Plaatsgroep[];
  rijen: Awaited<ReturnType<typeof plaatsRijen>>;
}> {
  const rijen = await plaatsRijen();
  const groepen = plaatsgroepen(rijen.map((r) => r.gemeente));
  const plaats = groepen.find((g) => g.sleutel === naamSlug) ?? null;
  return {
    plaats: plaats && plaats.aantal >= PLAATS_MINIMUM ? plaats : null,
    groepen,
    rijen,
  };
}

export async function generateMetadata({ params }: Params): Promise<Metadata> {
  const { naam } = await params;
  const { plaats } = await vindPlaats(veiligGedecodeerd(naam)).catch(() => ({
    plaats: null,
  }));
  if (!plaats) return { title: "Plaats niet gevonden" };
  return {
    title: `Organisaties in ${plaats.naam} en hun accountant`,
    description:
      `Organisaties uit ${plaats.naam} in het register, met het kantoor van hun ` +
      `laatste jaarrekeningcontrole — uit openbare bronnen.`,
  };
}

/** De nieuwste jaarrekeningcontrole van één organisatie. */
type LaatsteControle = { boekjaar: number; type: string; kantoor: Kantoor };

export default async function Plaatspagina({ params }: Params) {
  const { naam } = await params;

  let gevonden;
  let organisaties: Awaited<ReturnType<typeof organisatiesInPlaats>> = [];
  let opdrachten: Awaited<ReturnType<typeof opdrachtenVanOrganisaties>> = [];
  let totaal = 0;
  try {
    gevonden = await vindPlaats(veiligGedecodeerd(naam));
    if (gevonden.plaats) {
      organisaties = await organisatiesInPlaats(gevonden.plaats.schrijfwijzen);
      [opdrachten, totaal] = await Promise.all([
        opdrachtenVanOrganisaties(organisaties.map((o) => o.id)),
        tel("organisaties"),
      ]);
    }
  } catch (fout) {
    return <Foutmelding fout={fout} />;
  }
  // Buiten de try, zoals op de sectorpagina: notFound() werkt met een
  // uitzondering die onze eigen catch anders zou opslokken.
  const plaats = gevonden.plaats;
  if (!plaats || organisaties.length === 0) notFound();

  // Per organisatie de nieuwste wettelijke of vrijwillige controle — dezelfde
  // typen als de marktaandelen. Een verklaring bij een WNT-opgave of "voorwerp
  // onbekend" uit het marktonderzoek is geen jaarrekeningcontrole; zo'n
  // organisatie krijgt hier een streepje en houdt de rest op haar eigen pagina.
  // Binnen één boekjaar gaat de wettelijke voor de vrijwillige.
  const laatste = new Map<number, LaatsteControle>();
  for (const opdracht of opdrachten) {
    if (!opdracht.kantoren || !CONTROLE_TYPES.includes(opdracht.type_opdracht)) continue;
    const bestaand = laatste.get(opdracht.organisatie_id);
    const beter =
      !bestaand ||
      opdracht.boekjaar > bestaand.boekjaar ||
      (opdracht.boekjaar === bestaand.boekjaar &&
        CONTROLE_TYPES.indexOf(opdracht.type_opdracht) < CONTROLE_TYPES.indexOf(bestaand.type));
    if (beter) {
      laatste.set(opdracht.organisatie_id, {
        boekjaar: opdracht.boekjaar,
        type: opdracht.type_opdracht,
        kantoor: opdracht.kantoren,
      });
    }
  }

  const perSector = new Map<string, number>();
  for (const org of organisaties) {
    if (org.sector) perSector.set(org.sector, (perSector.get(org.sector) ?? 0) + 1);
  }
  const sectorlijst = [...perSector.entries()].sort(
    (a, b) => b[1] - a[1] || a[0].localeCompare(b[0], "nl"),
  );
  // De kantoren die hier een laatste controle hebben, alfabetisch en zonder
  // aantal erbij: een plaats is geen sector, en een telling per kantoor over
  // zorg, overheid en goede doelen samen zou een ranglijst zijn die nergens
  // over gaat.
  const kantoren = [
    ...new Map([...laatste.values()].map((c) => [c.kantoor.id, c.kantoor])).values(),
  ].sort((a, b) => a.naam.localeCompare(b.naam, "nl"));

  // Hoe volledig het plaatsveld is, gemeten op het moment van tonen. Op
  // 5-10-2026 had 19,5% van de organisaties een plaats (3.439 van 17.653),
  // bijna allemaal zorg, overheid, woningcorporaties en goede doelen; in het
  // bedrijfsleven uit het marktonderzoek staat er geen. Zonder deze zin leest
  // de lijst als "alle organisaties in deze plaats".
  const metPlaats = gevonden.rijen.length;
  const metPlaatsPerSector = new Map<string, number>();
  for (const rij of gevonden.rijen) {
    if (rij.sector) {
      metPlaatsPerSector.set(rij.sector, (metPlaatsPerSector.get(rij.sector) ?? 0) + 1);
    }
  }
  const vooral = [...metPlaatsPerSector.entries()]
    .sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0], "nl"))
    .slice(0, 4)
    .map(([sector]) => sector);

  const anderePlaatsen = gevonden.groepen
    .filter((g) => g.sleutel !== plaats.sleutel && g.aantal >= PLAATS_MINIMUM)
    .slice(0, 3);

  const kop = (
    <thead>
      <tr>
        <th>Organisatie</th>
        <th>Sector</th>
        <th>Laatste jaarrekeningcontrole</th>
        <th>Boekjaar</th>
      </tr>
    </thead>
  );
  const regels = organisaties.map((org) => {
    const controle = laatste.get(org.id);
    return (
      <tr key={org.id}>
        <td>
          <Link href={organisatiePad(org)}>{org.naam}</Link>
        </td>
        <td className="klein">
          {org.sector ? (
            <Link href={sectorPad(org.sector)}>{hoofdletter(org.sector)}</Link>
          ) : (
            <span className="zacht">—</span>
          )}
        </td>
        <td>
          {controle ? (
            <>
              <KantoorLink naam={controle.kantoor.naam} naar={kantoorPad(controle.kantoor)} />
              {controle.type !== "wettelijke_controle" ? (
                <>
                  {" "}
                  <Soort type={controle.type} />
                </>
              ) : null}
            </>
          ) : (
            <span className="zacht klein">geen gelezen controle</span>
          )}
        </td>
        <td className="jaar">{controle?.boekjaar ?? ""}</td>
      </tr>
    );
  });

  return (
    <>
      <Kruimels
        paden={[{ naar: "/", tekst: "Start" }, { tekst: "Plaatsen" }, { tekst: plaats.naam }]}
      />

      <div className="paginakop">
        <h1>{plaats.naam}</h1>
        <p className="zacht klein" style={{ margin: "0.4rem 0 0", maxWidth: "46rem" }}>
          Organisaties uit {plaats.naam} in het register, met het kantoor van hun
          nieuwste jaarrekeningcontrole.
        </p>
        <div className="kerncijfers">
          <Kerncijfer waarde={nl(organisaties.length)} naam="organisaties" />
          <Kerncijfer waarde={nl(laatste.size)} naam="met een gelezen controle" />
          <Kerncijfer waarde={nl(sectorlijst.length)} naam="sectoren" />
          <Kerncijfer waarde={nl(kantoren.length)} naam="kantoren" />
        </div>
      </div>

      {/* Het plaatsveld is maar bij een klein deel gevuld. Dat staat bovenaan,
          niet in een voetnoot: anders leest de lijst als een volledige
          opsomming van wat er in deze plaats gecontroleerd wordt. */}
      <div className="kanttekening">
        <strong>Niet volledig.</strong>{" "}
        <span className="klein">
          Van de {nl(totaal)} organisaties in het register staat maar bij{" "}
          {nl(metPlaats)} een plaats ({procent((100 * metPlaats) / Math.max(totaal, 1))}),
          vooral bij{" "}
          {vooral.length > 1
            ? `${vooral.slice(0, -1).join(", ")} en ${vooral[vooral.length - 1]}`
            : vooral.join("")}
          . Organisaties uit {plaats.naam} zonder
          plaats in de bron staan hier dus niet. En geen aandelen of plekken: een
          plaats is geen sector, en deze organisaties komen uit verschillende
          sectoren en boekjaren.
        </span>
      </div>

      <section className="kaart">
        <div className="kaartkop">
          <h2>Organisaties ({organisaties.length})</h2>
        </div>
        {organisaties.length === 0 ? (
          <Leeg tekst="Geen organisaties in deze plaats." />
        ) : (
          <>
            <div className="tabel-omhulsel">
              <table>
                {kop}
                <tbody>{regels.slice(0, OPEN)}</tbody>
              </table>
            </div>
            {regels.length > OPEN ? (
              <Inklapbaar samenvatting={`Nog ${regels.length - OPEN} organisaties`}>
                <div className="tabel-omhulsel">
                  <table>
                    {kop}
                    <tbody>{regels.slice(OPEN)}</tbody>
                  </table>
                </div>
              </Inklapbaar>
            ) : null}
          </>
        )}
        <p className="klein zacht" style={{ marginBottom: 0 }}>
          Een jaarrekeningcontrole is hier een wettelijke of vrijwillige controle,
          net als in de marktaandelen. Bij een organisatie met alleen een
          verklaring bij een WNT-opgave, een gunning of een kantoor uit het
          marktonderzoek staat hier &ldquo;geen gelezen controle&rdquo;; wat er
          wel is, staat op haar eigen pagina.
          {plaats.schrijfwijzen.length > 1
            ? ` Samengenomen schrijfwijzen: ${plaats.schrijfwijzen.join(", ")}.`
            : ""}{" "}
          Een andere naam voor dezelfde gemeente (Den Haag en
          &rsquo;s-Gravenhage) blijft een eigen plaats: zo staat het in de bron.
        </p>
      </section>

      {sectorlijst.length > 0 ? (
        <section className="kaart">
          <h2>Sectoren in {plaats.naam}</h2>
          <div className="tabel-omhulsel">
            <table>
              <thead>
                <tr>
                  <th>Sector</th>
                  <th className="getal">Organisaties</th>
                </tr>
              </thead>
              <tbody>
                {sectorlijst.map(([sector, aantal]) => (
                  <tr key={sector}>
                    <td>
                      <Link href={sectorPad(sector)}>{hoofdletter(sector)}</Link>
                    </td>
                    <td className="getal">{nl(aantal)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      ) : null}

      <Doorklik
        items={[
          ...organisaties.slice(0, 3).map((org) => ({
            naar: organisatiePad(org),
            tekst: org.naam,
            toelichting: org.sector ?? undefined,
          })),
          ...kantoren.slice(0, 3).map((kantoor) => ({
            naar: kantoorPad(kantoor),
            tekst: kantoor.naam,
          })),
          ...sectorlijst.slice(0, 3).map(([sector]) => ({
            naar: sectorPad(sector),
            tekst: `Sector ${sector}: wie controleert er`,
          })),
          ...anderePlaatsen.map((ander) => ({
            naar: plaatsPad(ander.naam),
            tekst: `Organisaties in ${ander.naam}`,
            toelichting: aantalOrganisaties(ander.aantal),
          })),
          { naar: "/sectoren", tekst: "Sectoren vergelijken" },
          { naar: "/kantoren", tekst: "Alle kantoren" },
        ]}
      />
    </>
  );
}
