/**
 * Wegschrijven wat er in de zoekbalk is getypt.
 *
 * Eén ding, en niet meer: het woord en het aantal treffers. Geen IP, geen
 * browser, geen sessie — zie de toelichting in
 * `supabase/migrations/20260805120000_zoeklog.sql` voor waarom dat de
 * belangrijkste ontwerpkeuze is.
 *
 * Waarom niet gewoon in de Supabase-logboeken kijken? Die zijn er wel, maar ze
 * kunnen deze vraag niet beantwoorden. De zoekpagina hergebruikt haar antwoord
 * een uur lang (`revalidate` in db.ts), dus dezelfde zoekterm bereikt Supabase
 * hooguit één keer per uur — het logboek zou stelselmatig te laag tellen. En
 * het bewaart maar kort. Een eigen regel per zoekopdracht heeft geen van beide
 * problemen.
 */

const BASIS = process.env.NEXT_PUBLIC_SUPABASE_URL;
const SLEUTEL = process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY;

/** Zelfde grens als de check-constraint in de migratie. */
const MAX_LENGTE = 120;

/**
 * Legt één zoekopdracht vast. Faalt nooit hoorbaar: een zoekpagina die stukgaat
 * omdat het meeschrijven niet lukte zou de bezoeker straffen voor iets waar hij
 * niets aan heeft. Mislukt het, dan verdwijnt die ene regel en verder niets.
 */
export async function legZoekopdrachtVast(term: string, resultaten: number): Promise<void> {
  const schoon = term.trim().slice(0, MAX_LENGTE);
  if (!schoon || !BASIS || !SLEUTEL) return;

  try {
    await fetch(`${BASIS}/rest/v1/zoekopdrachten`, {
      method: "POST",
      headers: {
        apikey: SLEUTEL,
        Authorization: `Bearer ${SLEUTEL}`,
        "Content-Type": "application/json",
        // Zonder dit stuurt PostgREST de nieuwe rij terug; die willen we niet.
        Prefer: "return=minimal",
      },
      body: JSON.stringify({ term: schoon, resultaten }),
      // Dit verzoek mag nooit uit een cache komen: elke zoekopdracht telt apart.
      cache: "no-store",
    });
  } catch {
    // Bewust stil. Zie de toelichting hierboven.
  }
}
