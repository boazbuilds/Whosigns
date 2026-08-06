#!/usr/bin/env bash
# Oogst een zorgboekjaar buiten GitHub Actions om, in blokken, en bewaart de
# voortgang na elk blok in de repo.
#
#     bash pipeline/oogst_zorg.sh 2019 [blokgrootte]
#
# Waarom een script en geen losse aanroep: het lezen van één boekjaar duurt uren
# (±37 seconden per organisatie, ruim 2.200 organisaties) en de omgeving waarin
# dit draait kan tussendoor opnieuw beginnen. Na elk blok gaan het rapport én de
# lijst met bekeken organisaties naar pipeline/oogst/ en worden ze gecommit, dus
# er kan nooit meer dan één blok werk verloren gaan. Bij een herstart zet dit
# script ze terug in .cache en pikt de lader op waar hij gebleven was.
#
# Het rapport dat hieruit komt gaat via de workflow "Zorgoogst inladen" in een
# paar minuten de database in. Zie docs/draaiboek-acties.md.
set -uo pipefail

BOEKJAAR="${1:-2019}"
BLOK="${2:-100}"
WERKERS="${3:-4}"

WORTEL="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CACHE="$WORTEL/pipeline/.cache"
OOGST="$WORTEL/pipeline/oogst"
RAPPORT="$CACHE/resultaat_${BOEKJAAR}.csv"
VERWERKT="$CACHE/verwerkt_${BOEKJAAR}.txt"
mkdir -p "$CACHE" "$OOGST"

# Terugzetten wat een vorige run al had: zo kost een herstart niets.
[ -s "$OOGST/zorg_${BOEKJAAR}.csv" ] && [ ! -s "$RAPPORT" ] &&
  cp "$OOGST/zorg_${BOEKJAAR}.csv" "$RAPPORT"
[ -s "$OOGST/verwerkt_${BOEKJAAR}.txt" ] && [ ! -s "$VERWERKT" ] &&
  cp "$OOGST/verwerkt_${BOEKJAAR}.txt" "$VERWERKT"

bewaar() {
  cp "$RAPPORT" "$OOGST/zorg_${BOEKJAAR}.csv" 2>/dev/null || return 0
  cp "$VERWERKT" "$OOGST/verwerkt_${BOEKJAAR}.txt" 2>/dev/null || true
  cd "$WORTEL" || return 0
  git add "pipeline/oogst/zorg_${BOEKJAAR}.csv" "pipeline/oogst/verwerkt_${BOEKJAAR}.txt" 2>/dev/null
  git diff --cached --quiet 2>/dev/null && return 0
  local rijen bekeken
  rijen=$(($(wc -l < "$RAPPORT") - 1))
  bekeken=$(wc -l < "$VERWERKT")
  git commit -q -m "Zorgoogst ${BOEKJAAR}: ${rijen} opdrachten, ${bekeken} organisaties bekeken

Tussenstand van pipeline/oogst_zorg.sh. Het lezen van de verklaring-pdf's draait
buiten GitHub Actions om; dit bestand gaat er via 'Zorgoogst inladen' in een paar
minuten in. Zie docs/draaiboek-acties.md.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01Rb6HsTuXQ7L6FFCgPSwN1y" || return 0
  # Duwen mag mislukken (netwerk, gelijktijdige push); de volgende ronde probeert
  # het opnieuw en de commit staat er dan al.
  git push -q origin HEAD 2>/dev/null || echo "  (push mislukt, volgende blok opnieuw)"
}

# Hoeveel organisaties heeft dit boekjaar? De lader meldt het op zijn eerste
# regel; met --vanaf 999999 doet hij verder niets. Bewust zonder `head` in de
# pijp: dat sluit de pijp vroeg, python krijgt SIGPIPE en met `pipefail` telt dat
# als een mislukte pipeline — waarna de terugval een tweede regel toevoegde en
# de test hieronder op "2211\n0" struikelde.
PROBE=$(python3 "$WORTEL/pipeline/laad_zorg.py" --boekjaar "$BOEKJAAR" \
  --uit-archief --droogloop --aantal 0 --vanaf 999999 2>/dev/null)
TOTAAL=$(printf '%s\n' "$PROBE" | sed -n '1s/^\([0-9]\{1,\}\).*/\1/p')
[ "${TOTAAL:-0}" -gt 0 ] || { echo "kon de omvang van boekjaar $BOEKJAAR niet bepalen"; exit 1; }
echo "boekjaar $BOEKJAAR: $TOTAAL organisaties, blokken van $BLOK"

for (( VANAF = 0; VANAF < TOTAAL; VANAF += BLOK )); do
  echo "=== blok vanaf $VANAF/$TOTAAL ==="
  python3 "$WORTEL/pipeline/laad_zorg.py" \
    --boekjaar "$BOEKJAAR" --uit-archief --droogloop --hervat \
    --vanaf "$VANAF" --aantal "$BLOK" --werkers "$WERKERS" 2>&1 |
    grep -E '^---|opdrachten,|^[0-9]+ organisaties'
  bewaar
done

echo "=== boekjaar $BOEKJAAR klaar ==="
bewaar
