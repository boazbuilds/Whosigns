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
# Eén blok is één golf werkers, en dat is geen willekeurige keuze.
#
# De lader verdeelt een blok over de werkers en schrijft het rapport pas als het
# hele blok klaar is. Eén document mag in het slechtste geval ruim twintig minuten
# duren (zie OCR_TIJDBUDGET in extractie/verklaring.py: het renderen en het lezen
# hebben elk hun eigen budget). Een blok van tien op vier werkers is dus drie
# golven van elk maximaal twintig minuten, en dat haalt het uur dat deze omgeving
# aan één stuk overeind blijft niet. Zo liep blok 110-120 van boekjaar 2019 tien
# keer op rij vast: niet stuk, gewoon te groot voor de tijd die het kreeg.
# Blokgrootte gelijk aan het aantal werkers maakt er één golf van, en dan staat de
# tussenstand na hooguit één traag document in de repo.
WERKERS="${3:-4}"
BLOK="${2:-$WERKERS}"

WORTEL="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CACHE="$WORTEL/pipeline/.cache"
OOGST="$WORTEL/pipeline/oogst"
RAPPORT="$CACHE/resultaat_${BOEKJAAR}.csv"
VERWERKT="$CACHE/verwerkt_${BOEKJAAR}.txt"
mkdir -p "$CACHE" "$OOGST"

# Terugzetten wat een vorige run al had: zo kost een herstart niets.
#
# De repo-kopie is daarbij de baas, niet .cache. Een omgeving die opnieuw begint
# zet .cache terug op een oudere momentopname, en die kan een rapport bevatten
# uit een tijd dat het nog andere kolommen had. Zo'n bestand is niet leeg, dus
# een simpele "alleen terugzetten als er niets staat" liet het staan — waarna de
# lader er nieuwe rijen met een ándere kolomindeling achteraan schreef. Dat is
# precies het soort stille schade dat dit project niet wil: het rapport gaat
# regelrecht de database in.
#
# Vandaar twee controles. Wijkt de kopregel af, dan gaat het bestand opzij.
# Heeft de repo-kopie meer rijen, dan heeft die de herstart overleefd en wint hij.
herstel_rapport() {
  local bewaard="$OOGST/zorg_${BOEKJAAR}.csv"
  [ -s "$bewaard" ] || return 0
  if [ -s "$RAPPORT" ]; then
    if [ "$(head -1 "$RAPPORT")" != "$(head -1 "$bewaard")" ]; then
      echo "  rapport in .cache heeft andere kolommen; opzij als ${RAPPORT}.oud"
      mv "$RAPPORT" "${RAPPORT}.oud"
    elif [ "$(wc -l < "$RAPPORT")" -ge "$(wc -l < "$bewaard")" ]; then
      return 0
    fi
  fi
  cp "$bewaard" "$RAPPORT"
}
herstel_rapport

# Idem voor de lijst met bekeken organisaties: de langste wint. `wc -l` krijgt
# hier bewust een bestaand bestand — een omleiding uit een bestand dat er niet is
# faalt in bash vóór het commando draait, en dan helpt 2>/dev/null niet.
regels() { [ -s "$1" ] && wc -l < "$1" || echo 0; }
if [ -s "$OOGST/verwerkt_${BOEKJAAR}.txt" ] &&
   [ "$(regels "$OOGST/verwerkt_${BOEKJAAR}.txt")" -gt "$(regels "$VERWERKT")" ]; then
  cp "$OOGST/verwerkt_${BOEKJAAR}.txt" "$VERWERKT"
fi

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

# Beginnen waar de vorige run gebleven was, in plaats van elke keer vanaf nul.
#
# `--hervat` slaat bekeken organisaties over, dus de blokken die al gedaan zijn
# leveren niets op — maar ze kosten wel elk een volledige aanroep van de lader,
# die daarvoor eerst de hele populatie van 2.211 inleest. Bij blokken van vier en
# 110 bekeken zijn dat 28 lege aanroepen vóór het eerste echte werk, en dat loopt
# op naarmate de oogst vordert.
#
# Naar bodenen afronden, nooit naar boven: dan kan er geen organisatie tussenuit
# vallen. Staat er iets in de lijst dat níét in de eerste blokken zat, dan wordt
# er hooguit een stuk overgedaan dat `--hervat` alsnog overslaat. Overslaan zou
# betekenen dat een organisatie stilletjes nooit gelezen wordt, en dat is precies
# wat hier niet mag gebeuren.
BEGIN=$(( ($(regels "$VERWERKT") / BLOK) * BLOK ))
[ "$BEGIN" -gt 0 ] && echo "$(regels "$VERWERKT") al bekeken; begin bij blok $BEGIN"

for (( VANAF = BEGIN; VANAF < TOTAAL; VANAF += BLOK )); do
  echo "=== blok vanaf $VANAF/$TOTAAL ==="
  python3 "$WORTEL/pipeline/laad_zorg.py" \
    --boekjaar "$BOEKJAAR" --uit-archief --droogloop --hervat \
    --vanaf "$VANAF" --aantal "$BLOK" --werkers "$WERKERS" 2>&1 |
    grep -E '^---|opdrachten,|^[0-9]+ organisaties'
  bewaar
done

echo "=== boekjaar $BOEKJAAR klaar ==="
bewaar
