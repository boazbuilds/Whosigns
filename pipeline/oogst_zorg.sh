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

# Hoe vaak de tussenstand naar de repo gaat terwijl een blok nog loopt. Drie
# minuten is een afweging tussen verlies bij een herstart en het aantal commits:
# de oogst duurt uren, dus elke minuut zou honderden commits opleveren.
BEWAARKLOK="${BEWAARKLOK:-180}"

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
# De eerste versie hiervan vergeleek de kopregel met die van de repo-kopie. Dat
# dekt een boekjaar dat al eens geoogst is, maar voor een boekjaar dat nog niet
# in de repo staat viel de functie meteen terug op "niets te herstellen" en bleef
# het oude bestand in .cache liggen. Op 17-8-2026 begon de oogst van 2023 zo
# bovenop een resultaat_2023.csv van 29 juli: 22 rijen met zeven kolommen, waar
# de oogst er elf achteraan schreef. Voor 2024 en 2025 lag hetzelfde klaar.
#
# Daarom is de kopregel van de schrijver nu de maatstaf, niet die van de
# repo-kopie: RAPPORT_KOLOMMEN in laad_zorg.py zegt welke kolommen het hóren te
# zijn, ook als er van dit boekjaar nog nooit iets geoogst is.
KOLOMMEN="$(python3 -c 'import sys
sys.path.insert(0, sys.argv[1])
from laad_zorg import RAPPORT_KOLOMMEN
print(",".join(RAPPORT_KOLOMMEN))' "$WORTEL/pipeline" 2>/dev/null)"
[ -n "$KOLOMMEN" ] ||
  echo "  let op: kolommen van laad_zorg niet op te vragen; oud rapport in .cache wordt niet herkend"

opzij() {
  echo "  $1"
  mv "$RAPPORT" "${RAPPORT}.oud"
  # Het rapport en de lijst met bekeken organisaties horen bij elkaar. Gaat het
  # rapport opzij, dan moet die lijst mee: "bekeken" betekent hier "nooit meer",
  # dus een lijst die hoort bij rijen die we net weglegden zou organisaties
  # stilzwijgend overslaan. Precies de schade die we hier proberen te vermijden.
  [ -e "$VERWERKT" ] && mv "$VERWERKT" "${VERWERKT}.oud"
  return 0
}

herstel_rapport() {
  local bewaard="$OOGST/zorg_${BOEKJAAR}.csv"
  if [ -s "$RAPPORT" ] && [ -n "$KOLOMMEN" ] &&
     [ "$(head -1 "$RAPPORT")" != "$KOLOMMEN" ]; then
    opzij "rapport in .cache heeft niet de kolommen die laad_zorg schrijft; opzij als ${RAPPORT}.oud"
  fi
  [ -s "$bewaard" ] || return 0
  # De repo-kopie moet dezelfde toets doorstaan. Die kan zelf uit een oude oogst
  # komen: op 17-8-2026 committeerde de oogst twee keer een rapport in het oude
  # formaat voordat iemand het doorhad. Zonder deze regel zet elke herstart die
  # fout keurig terug.
  if [ -n "$KOLOMMEN" ] && [ "$(head -1 "$bewaard")" != "$KOLOMMEN" ]; then
    echo "  repo-kopie van dit boekjaar heeft oude kolommen; niet teruggezet"
    return 0
  fi
  if [ -s "$RAPPORT" ]; then
    if [ "$(head -1 "$RAPPORT")" != "$(head -1 "$bewaard")" ]; then
      opzij "rapport in .cache wijkt af van de repo-kopie; opzij als ${RAPPORT}.oud"
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

# De gelezen OCR-tekst hoort ook in de repo, en niet alleen in .cache.
#
# Waarom: .cache overleeft een herstart van het proces, maar niet een herstart
# van de omgeving — die zet de hele map terug op een oudere momentopname. Op
# 7-8-2026 gebeurde dat om 12:10: de pdf's stonden er nog (1.784), de gelezen
# tekst was weg. En juist die tekst is het dure deel: een gescande verklaring
# kost een minuut OCR, een pdf mét tekstlaag milliseconden.
#
# Gemeten: ongeveer een kwart van de organisaties heeft een scan, en de oogst
# doet er 75 per uur. Elke rollback kostte dus zo'n twintig minuten leeswerk
# opnieuw, en die komen ongeveer elk uur. Over de resterende 25 uur is dat een
# derde van de tijd.
#
# De bestanden zijn klein (9 tot 18 kB tekst) en comprimeren goed, dus ze mogen
# gewoon mee. Ze zijn bovendien meer dan een cache: met de tekst bewaard kan een
# organisatie die nu geen kantoor oplevert later opnieuw worden nagekeken zonder
# de pdf opnieuw op te halen en te lezen. Zie de aantekening over "bekeken"
# betekent ook "nooit meer" in adapters/digimv.md.
OCR_BEWAAR="$OOGST/ocr"
mkdir -p "$OCR_BEWAAR"
herstel_ocr() {
  local aantal=0
  for bewaard in "$OCR_BEWAAR"/*.ocr.txt; do
    [ -e "$bewaard" ] || break
    local doel="$CACHE/$(basename "$bewaard")"
    [ -e "$doel" ] || { cp "$bewaard" "$doel" && aantal=$((aantal + 1)); }
  done
  [ "$aantal" -eq 0 ] || echo "  $aantal eerder gelezen documenten teruggezet in .cache"
}
herstel_ocr

bewaar() {
  [ -s "$RAPPORT" ] || return 0
  # Alleen bewaren als het rapport op een hele regel eindigt.
  #
  # Sinds deze functie ook tijdens een blok draait (zie de bewaarklok hieronder)
  # kan er tegelijk in geschreven worden. De lader flusht na elke regel, maar de
  # buffer van python is 8 kB en een rapportregel is er zo'n 200 groot, dus eens
  # in de veertig regels valt er eentje over een buffergrens. Precies dan zou een
  # kopie een halve regel kunnen meenemen, en dat rapport gaat regelrecht de
  # database in. Eindigt het bestand niet op een nieuwe regel, dan is het midden
  # in een schrijfactie; volgende ronde dan maar.
  [ -z "$(tail -c 1 "$RAPPORT")" ] || return 0
  cp "$RAPPORT" "$OOGST/zorg_${BOEKJAAR}.csv" 2>/dev/null || return 0
  cp "$VERWERKT" "$OOGST/verwerkt_${BOEKJAAR}.txt" 2>/dev/null || true
  # Nieuw gelezen tekst meenemen; -n overschrijft niets wat er al staat.
  for gelezen in "$CACHE"/*.ocr.txt; do
    [ -e "$gelezen" ] || break
    cp -n "$gelezen" "$OCR_BEWAAR/" 2>/dev/null || true
  done
  cd "$WORTEL" || return 0
  git add "pipeline/oogst/zorg_${BOEKJAAR}.csv" "pipeline/oogst/verwerkt_${BOEKJAAR}.txt" \
          "pipeline/oogst/ocr" 2>/dev/null
  git diff --cached --quiet 2>/dev/null && return 0
  local rijen bekeken
  rijen=$(($(wc -l < "$RAPPORT") - 1))
  bekeken=$(wc -l < "$VERWERKT")
  # [skip ci] staat er met opzet in. Dit script commit na elk blok, dus elke paar
  # minuten, en zolang er een pull request openstaat startte elk van die commits
  # een volledige ronde: de extractietests én een npm-installatie met
  # typecontrole. Op één ochtend zijn dat tientallen runs terwijl er geen regel
  # code verandert — deze commits raken alleen pipeline/oogst/, en dat zijn
  # meetresultaten. Actions-minuten zijn hier schaars.
  #
  # Waarom niet met paths-ignore in de workflow: dat werkt hier niet. Bij een
  # pull_request-event kijkt paths-ignore naar álle bestanden die de pull request
  # ten opzichte van de basisbranch wijzigt, niet naar de bestanden in deze ene
  # push. Zodra er ook maar één codebestand in de pull request zit — en dat is
  # altijd zo — slaat het filter nooit meer aan. Gemeten: met paths-ignore
  # erin draaide CI gewoon door op een commit die alleen verwerkt_2019.txt
  # aanraakte.
  #
  # [skip ci] werkt wél, want dat kijkt naar het bericht van de commit zelf. Het
  # geldt alleen voor deze tussenstanden; elke commit met code erin draait
  # gewoon door de tests heen.
  git commit -q -m "Zorgoogst ${BOEKJAAR}: ${rijen} opdrachten, ${bekeken} organisaties bekeken [skip ci]

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

# Elk blok pakt de eerste $BLOK organisaties die nog niet bekeken zijn.
#
# `--vanaf` telt sinds 13-8-2026 in de lijst van nog-te-doen organisaties en niet
# meer in de volle populatie (waarom: zie de uitleg bij `onbekeken` in
# laad_zorg.py). Die lijst krimpt na elk blok, dus staat hier geen oplopende
# teller meer maar steeds `--vanaf 0`: de vorige ronde heeft de vorige kop er al
# afgehaald. Juist een oplopende teller zou nu overslaan.
#
# Dat repareert twee dingen tegelijk. Het scheelt de lege aanroepen — met 2.081
# van 2.678 bekeken liep de oude lus nog 299 blokken af waarvan de meeste niets te
# doen hadden, elk met een volledige inleesbeurt van de populatie van zo'n tien
# seconden. En belangrijker: een organisatie kan niet meer buiten beeld raken
# doordat de populatie groeide nadat de oogst begon.
#
# Stoppen doet de lus als een blok niets nieuws oplevert. Dat kan twee dingen
# betekenen: klaar, of de bron was even onbereikbaar. Van buitenaf is dat verschil
# niet te zien, dus krijgt hij drie kansen met een half minuutje ertussen. Klaar
# zijn kost dan hooguit anderhalve minuut extra; een hik in het netwerk kost geen
# halve oogst.
LEEG=0
while :; do
  BEKEKEN=$(regels "$VERWERKT")
  echo "=== $BEKEKEN/$TOTAAL bekeken ==="
  # De bewaarklok loopt mee zolang het blok bezig is.
  #
  # Waarom niet alleen na afloop: .cache overleeft geen herstart van de omgeving,
  # en die komt hier elk half uur. Wat een blok tot dan toe gelezen had stond
  # alleen in .cache, dus een herstart midden in een blok gooide dat hele blok
  # weg. Erger nog: sinds elk blok met `--vanaf 0` dezelfde kop van de wachtrij
  # pakt, begon de volgende omgeving aan precies hetzelfde blok. Op 13-8-2026 om
  # 14:37 leverde een hele container zo nul organisaties op — één uur voor niets.
  #
  # Een document mag ruim twintig minuten duren (OCR_TIJDBUDGET is 600 seconden
  # voor het renderen en nog eens 600 voor het lezen), dus een blok kan langer
  # duren dan de omgeving leeft. Daar valt niet omheen te plannen; wel omheen te
  # bewaren. Elke drie minuten wegschrijven maakt het verlies hooguit drie
  # minuten, ongeacht hoe lang het blok doet.
  #
  # Dit mag alleen omdat de lader zijn aantekening "bekeken" pas maakt als de
  # uitkomst geflusht is (zie noteer_bekeken in laad_zorg.py). Andersom zou een
  # tussentijdse kopie een organisatie als afgehandeld kunnen vastleggen zonder
  # zijn opdracht, en die komt dan nooit meer langs.
  # De klok stopt zichzelf op een vlaggetje; hij wordt niet doodgeschoten.
  #
  # Doodschieten lag voor de hand en is precies verkeerd. `kill` op de subshell
  # laat zijn `sleep` als wees achter (die hangt eronder, niet ernaast), en veel
  # erger: het signaal kan aankomen terwijl de klok middenin `git commit` zit.
  # Een halverwege afgebroken commit laat .git/index.lock staan, en dan mislukt
  # elke volgende commit van de oogst — hij blijft dan uren doorlezen zonder ook
  # maar iets te bewaren, precies het tegenovergestelde van wat deze klok moet
  # bereiken.
  #
  # Met een vlaggetje stopt de klok uit zichzelf, altijd tussen twee bewaarbeurten
  # in. Het wachten gaat in stappen van tien seconden zodat hij kort na het blok
  # weg is en niet nog drie minuten blijft hangen.
  BLOKBEZIG="$CACHE/.blok_bezig"
  : > "$BLOKBEZIG"
  (
    while [ -e "$BLOKBEZIG" ]; do
      for _ in $(seq $(( (BEWAARKLOK + 9) / 10 ))); do
        [ -e "$BLOKBEZIG" ] || break
        sleep 10
      done
      [ -e "$BLOKBEZIG" ] && bewaar
    done
  ) &
  KLOK=$!
  python3 "$WORTEL/pipeline/laad_zorg.py" \
    --boekjaar "$BOEKJAAR" --uit-archief --droogloop --hervat \
    --vanaf 0 --aantal "$BLOK" --werkers "$WERKERS" 2>&1 |
    grep -E '^---|opdrachten,|^[0-9]+ organisaties'
  # Eerst de klok laten uitlopen, dan pas zelf bewaren: twee git-commits tegelijk
  # vechten om index.lock en dan mislukt er eentje.
  rm -f "$BLOKBEZIG"
  wait "$KLOK" 2>/dev/null
  bewaar
  if [ "$(regels "$VERWERKT")" -le "$BEKEKEN" ]; then
    LEEG=$((LEEG + 1))
    [ "$LEEG" -ge 3 ] && break
    echo "  blok leverde niets op ($LEEG van 3); nog een keer over 30 seconden"
    sleep 30
  else
    LEEG=0
  fi
done

echo "=== boekjaar $BOEKJAAR klaar ==="
bewaar
