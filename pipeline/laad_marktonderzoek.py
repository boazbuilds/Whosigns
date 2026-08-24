"""Aangeleverd marktonderzoek -> opdrachten in de database.

De eigenaar levert exportbestanden aan met per rij een organisatie
(KvK-nummer), boekjaar en accountantsnaam. De bestanden zelf blijven buiten
de repository — die is openbaar — en bereiken de lader als omgevingsvariabele
(gzip+base64, zie workflow marktonderzoek.yml) of als los csv-pad.

Draaien:
    python3 pipeline/laad_marktonderzoek.py --bestand pad/naar/export.csv
    python3 pipeline/laad_marktonderzoek.py --bestand ... --droogloop

    # of met de data in een omgevingsvariabele (workflow-route):
    MARKTONDERZOEK_DATA="$(gzip -c export.csv | base64 -w0)" \
        python3 pipeline/laad_marktonderzoek.py

Csv-kolommen: kvk,naam,boekjaar,accountant en optioneel sbi,plaats.

Spelregels:

- **`controle_onbepaald`, geen wettelijke controle.** De aanlevering bewijst
  de accountantsrelatie, niet het soort opdracht. Daardoor telt dit ook niet
  mee in v_marktaandeel (die filtert op wettelijke_controle) en vervuilt een
  aanlevering per kantoor de marktaandelen niet.
- **Nooit gokken.** De accountantsnaam wordt herleid tot een kantoor uit de
  AFM-lijst via een expliciete verkorte-namenlijst plus de bestaande matcher;
  onherleidbaar of meerdere kantoren in één veld -> review-queue.
- **Bestaande rijen winnen.** Heeft een organisatie voor dat boekjaar al een
  wettelijke controle (uit een document-bron), dan slaan we de rij over.
- Bronregistratie: bron_type "marktonderzoek", betrouwbaarheid
  "zelf_aangeleverd", zonder url. Het colofon van de site benoemt deze
  categorie.
- Organisaties worden op KvK-nummer herkend of aangemaakt. Een aangeleverde
  SBI-code en plaats vullen sbi_code, gemeente en (via SBI_SECTOR, een klein
  aantal grove hokjes) de sector — maar alléén velden die nog leeg zijn: wat
  een documentbron of een mens al invulde blijft staan.
"""

import argparse
import base64
import csv
import gzip
import io
import os
import re
import sys
import urllib.parse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent / "adapters"))
sys.path.insert(0, str(Path(__file__).resolve().parent / "extractie"))

from kantoor_match import bouw_index, laad_kantoren, normaliseer, zoek_kantoor  # noqa: E402
from supabase_client import Supabase, SupabaseFout  # noqa: E402

CACHE = Path(__file__).resolve().parent / ".cache"

# Verkorte namen zoals aanleveringen ze schrijven -> AFM-nummer. Alleen namen
# die ondubbelzinnig één Wta-vergunninghouder aanduiden; al het andere loopt
# via de gewone matcher of de review-queue.
VERKORT: dict[str, str] = {
    "kpmg": "13000121",
    "pwc": "13000291",
    "deloitte": "13000015",
    "ey": "13020186",
    "e y": "13020186",
    "bdo": "13000311",
    "mazars": "13000408",
    "forvis mazars": "13000408",
    "confinant": "13020070",
    "confinant audit": "13020070",
    "confinant audit assurance": "13020070",
    "q concepts": "13000773",
    "flynth": "13000519",
    "dubois": "13000044",
    "dubois co": "13000044",
    "crowe foederer": "13000413",
    "crowe peak": "13000097",
    "crowe peak audit": "13000097",
    # De merknaam tot 2019; Foederer en Peak waren toen al aparte kantoren.
    "crowe horwath foederer": "13000413",
    "crowe horwath peak": "13000097",
    "baker tilly": "13000741",
    "baker tilly netherlands": "13000741",
    "baker tilly berk": "13000741",
    # Veelvoorkomende tikfouten met hoofdletter-i's in plaats van l'en.
    "baker tiiiy": "13000741",
    "baker tiily": "13000741",
    "baker tiiiy netherlands": "13000741",
    "baker tiily netherlands": "13000741",
    "eshuis": "13000144",
    "eshuis registeraccountants": "13000144",
    "verstegen": "13000147",
    "visser visser": "13000491",
    "visser and visser": "13000491",
    "share impact": "13020072",
    "share impact audit": "13020072",
    "grant thornton": "13000524",
    # Veelvoorkomende scan-tikfout: rn leest als m.
    "grant thomton": "13000524",
    # De groep heeft twee actieve Wta-vergunningen (13000090 Accountants N.V.
    # en 13000252 Audit B.V., zelfde adres en site). Kaal "RSM" wijst naar de
    # N.V. op grond van de ondertekenpraktijk in de eigen database: alle 46
    # uit documenten gelezen RSM-verklaringen staan op de N.V., nul op de
    # Audit B.V. (gemeten 24-8-2026).
    "rsm": "13000090",
    "rsm netherlands": "13000090",
    "rsm nederland": "13000090",
    # Tikfout met kapitaal-i voor de l.
    "rsm netheriands": "13000090",
    "newtone": "13000027",
    "newtone audit": "13000027",
    "van oers": "13000154",
    "van oers audit": "13000154",
    "aaff": "13000259",
    "aaff ra": "13000259",
    # ETL heeft in Nederland één vergunninghouder; Dales is een lidkantoor
    # van dezelfde groep.
    "etl": "13000643",
    "etl dales": "13000643",
    "etl accountants": "13000643",
    # De naam tot de rebranding van 2016.
    "mazars paardekooper hoffman": "13000408",
    # Bewust NIET: kaal "visser" of initialen als "t visser" — dat kan een
    # persoon of een ander kantoor zijn; een mens kiest.
    # WITh heeft geen Wta-vergunning maar tekent vrijwillige controles bij
    # goede doelen; staat als overig kantoor in de database.
    "with": "overig_with_accountants",
    "with accountants": "overig_with_accountants",
    # Bewust NIET: "crowe" alleen (Foederer of Peak? een mens kiest) en
    # "crowe contour" (staat niet in het register).
}


AANLEVER = Path(__file__).resolve().parent / "aanlever"

# SBI-hoofdgroep (eerste twee cijfers) -> sector. Bewust weinig hokjes: de
# sectorpagina's moeten leesbaar blijven, dus het bedrijfsleven krijgt acht
# grove sectoren in plaats van de honderden SBI-groepen. Drie hoofdgroepen
# wijzen naar sectoren die al bestaan (zorg, onderwijs, pensioenfondsen),
# zodat een organisatie uit een aanlevering op dezelfde pagina belandt als
# een organisatie uit een documentbron. Hernoemen is later één migratie —
# de SBI-code zelf blijft op de organisatie staan.
SBI_SECTOR: list[tuple[range, str]] = [
    (range(1, 4), "landbouw en visserij"),
    (range(5, 44), "industrie en bouw"),  # incl. delfstoffen, energie, water
    (range(45, 48), "handel"),
    (range(49, 54), "transport en logistiek"),
    (range(58, 64), "ict en media"),
    (range(64, 67), "financiële dienstverlening"),
    (range(68, 69), "vastgoed"),
    (range(69, 83), "zakelijke dienstverlening"),
    (range(85, 86), "onderwijs"),
    (range(86, 89), "zorg"),
]


def sector_uit_sbi(sbi: str) -> str | None:
    """Grove sector bij een SBI-code; None zonder code.

    65.30 is de SBI-groep voor pensioenfondsen en gaat vóór de hoofdgroep
    64-66 (financiële dienstverlening): die sector bestaat al met eigen
    lader en eigen pagina.
    """
    if len(sbi) < 2:
        return None
    if sbi.startswith("6530"):
        return "pensioenfondsen"
    groep = int(sbi[:2])
    for bereik, sector in SBI_SECTOR:
        if groep in bereik:
            return sector
    # Horeca, overheid, cultuur, sport, overige diensten: te weinig
    # controlecliënten voor een eigen hokje.
    return "overig bedrijfsleven"


def lees_map(map_pad: Path = AANLEVER) -> list[dict]:
    """Alle marktonderzoek_*.csv uit de aanlevermap, op bestandsnaam gesorteerd."""
    rijen: list[dict] = []
    for pad in sorted(map_pad.glob("marktonderzoek_*.csv")):
        with pad.open(encoding="utf-8") as f:
            rijen.extend(csv.DictReader(f))
    return rijen


def lees_rijen(argumenten) -> list[dict]:
    """De aangeleverde rijen: --bestand wint, dan MARKTONDERZOEK_DATA, dan de map."""
    if argumenten.bestand:
        tekst = Path(argumenten.bestand).read_text(encoding="utf-8")
        return list(csv.DictReader(io.StringIO(tekst)))
    blob = os.environ.get("MARKTONDERZOEK_DATA", "").strip()
    if blob:
        tekst = gzip.decompress(base64.b64decode(blob)).decode("utf-8")
        return list(csv.DictReader(io.StringIO(tekst)))
    return lees_map()


def herleid_kantoren(veld: str, index: dict) -> tuple[list[str], list[str]]:
    """Accountantsveld -> (AFM-nummers, onherleidbare delen).

    Een veld kan meerdere namen bevatten ("A; B", "a/b"); elk deel wordt los
    herleid. Dubbele treffers vouwen samen.
    """
    delen = [d for d in re.split(r"[;/]", veld) if d.strip()]
    gevonden: list[str] = []
    onbekend: list[str] = []
    for deel in delen:
        sleutel = normaliseer(deel)
        afm = VERKORT.get(sleutel)
        if afm is None:
            # Zelfde kunstgreep als laad_corporaties: de naam op een
            # ondertekeningsplek aanbieden zodat de positiescontrole van de
            # matcher niet in de weg zit.
            treffer = zoek_kantoor(f"Rotterdam, 1 juni 2026 {deel.strip()}", index)
            if treffer and not treffer["zwak"]:
                afm = treffer["kantoor"].get("sleutel")
        if afm:
            if afm not in gevonden:
                gevonden.append(afm)
        else:
            onbekend.append(deel.strip())
    return gevonden, onbekend


def geldige_rij(rij: dict) -> dict | None:
    kvk = re.sub(r"\D", "", rij.get("kvk") or "")
    naam = (rij.get("naam") or "").strip()
    boekjaar = (rij.get("boekjaar") or "").strip()
    accountant = (rij.get("accountant") or "").strip()
    if len(kvk) != 8 or not naam or not boekjaar.isdigit() or not accountant:
        return None
    return {
        "kvk": kvk,
        "naam": naam,
        "boekjaar": int(boekjaar),
        "accountant": accountant,
        # Optioneel, sinds formaat v2; oudere aanleverbestanden missen de
        # kolommen en leveren hier gewoon een lege tekst.
        "sbi": re.sub(r"\D", "", rij.get("sbi") or ""),
        "plaats": (rij.get("plaats") or "").strip(),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--bestand",
        help="csv met kolommen kvk,naam,boekjaar,accountant (en optioneel sbi,plaats)",
    )
    parser.add_argument("--droogloop", action="store_true")
    argumenten = parser.parse_args()

    rijen = [g for r in lees_rijen(argumenten) if (g := geldige_rij(r))]
    print(f"{len(rijen)} geldige rijen aangeleverd", flush=True)
    if not rijen:
        return 0

    index = bouw_index(laad_kantoren())

    db = None
    kantoor_id_per_sleutel: dict[str, int] = {}
    org_per_kvk: dict[str, dict] = {}
    if not argumenten.droogloop:
        try:
            db = Supabase()
        except SupabaseFout as fout:
            print(fout)
            return 1
        kantoor_id_per_sleutel = {
            rij["sleutel"]: rij["id"]
            for rij in db.selecteer_alles("kantoren", "select=id,sleutel")
            if rij.get("sleutel")
        }
        # Ook sector, sbi_code en gemeente voorladen: de verrijking hieronder
        # vult alleen velden die nog leeg zijn, dus die moet kunnen zien wat
        # er al staat.
        for rij in db.selecteer_alles(
            "organisaties", "select=id,kvk_nummer,sector,sbi_code,gemeente"
        ):
            if rij.get("kvk_nummer"):
                org_per_kvk[rij["kvk_nummer"]] = rij

    CACHE.mkdir(exist_ok=True)
    rapport_pad = CACHE / "resultaat_marktonderzoek.csv"
    rapport = rapport_pad.open("w", newline="", encoding="utf-8")
    schrijver = csv.writer(rapport)
    schrijver.writerow(["kvk", "naam", "boekjaar", "kantoor", "status"])

    # Eén bron-rij voor alle marktonderzoek: bestaat er al een, dan die
    # hergebruiken — anders laat elke herstart een extra rij achter.
    bron_id = None
    bezet: set[tuple[int, int]] = set()
    al_in_review: set[tuple] = set()
    review_rijen: list[dict] = []
    if db is not None:
        bestaande_bron = db.selecteer_alles(
            "bronnen", "select=id&bron_type=eq.marktonderzoek&limit=1"
        )
        if bestaande_bron:
            bron_id = bestaande_bron[0]["id"]
        # Alle organisatie-boekjaren die al een controle hebben, in één keer
        # voorgeladen: per rij naar de database vragen kost drie verzoeken per
        # rij en dat past bij duizenden rijen in geen enkele timeout.
        for r in db.selecteer_alles(
            "opdrachten",
            "select=organisatie_id,boekjaar"
            "&type_opdracht=in.(wettelijke_controle,controle_onbepaald)",
        ):
            bezet.add((r["organisatie_id"], r["boekjaar"]))
        for r in db.selecteer_alles(
            "review_queue", "select=payload&soort=eq.naam_match&status=eq.open"
        ):
            p = r.get("payload") or {}
            al_in_review.add((p.get("organisatie"), p.get("boekjaar")))

    # Eerste doorloop: herleiden, rapporteren, reviewgevallen wegschrijven.
    schoon: list[dict] = []
    geschreven = overgeslagen = review = 0
    for rij in rijen:
        kantoren, onbekend = herleid_kantoren(rij["accountant"], index)
        if len(kantoren) != 1 or onbekend:
            # Meerdere kantoren of een onherleidbaar deel: een mens kiest.
            review += 1
            schrijver.writerow(
                [rij["kvk"], rij["naam"], rij["boekjaar"], rij["accountant"], "review"]
            )
            if (rij["naam"], rij["boekjaar"]) not in al_in_review:
                al_in_review.add((rij["naam"], rij["boekjaar"]))
                review_rijen.append(
                    {
                        "soort": "naam_match",
                        "payload": {
                            "bron": "marktonderzoek",
                            "organisatie": rij["naam"],
                            "kvk": rij["kvk"],
                            "boekjaar": rij["boekjaar"],
                            "opgegeven": rij["accountant"],
                            "herleid": kantoren,
                            "onherleidbaar": onbekend,
                        },
                    }
                )
            continue
        schoon.append({**rij, "afm": kantoren[0]})
        schrijver.writerow(
            [rij["kvk"], rij["naam"], rij["boekjaar"], kantoren[0],
             "droogloop" if db is None else "ok"]
        )

    if db is not None:
        db.invoegen_bulk("review_queue", review_rijen)

    verrijkt = 0
    if db is not None and schoon:
        # Beste aangeleverde SBI en plaats per KvK, over alle bestanden heen:
        # een oudere aanlevering zonder die kolommen mag een nieuwere met
        # kolommen niet in de weg zitten.
        aangeleverd_per_kvk: dict[str, dict] = {}
        for rij in schoon:
            info = aangeleverd_per_kvk.setdefault(rij["kvk"], {"sbi": "", "plaats": ""})
            info["sbi"] = info["sbi"] or rij["sbi"]
            info["plaats"] = info["plaats"] or rij["plaats"]

        # Verrijking van bestaande organisaties: sbi_code, gemeente en (uit de
        # SBI) de sector, alléén op velden die nog leeg zijn. Geen upsert met
        # een teruggestuurde momentopname: tussen het voorladen en het
        # schrijven zit de hele herleidingsdoorloop, en na een merge draaien
        # meerdere laders tegelijk — een upsert zou een intussen gevulde
        # sector stil terugdraaien naar de oude waarde. Daarom een update per
        # doelwaarde met `is.null` in het filter: de database zelf bewaakt dat
        # alleen lege velden gevuld worden, wat er intussen ook gebeurd is.
        vul: dict[str, dict[int, str]] = {"sector": {}, "sbi_code": {}, "gemeente": {}}
        for kvk, info in aangeleverd_per_kvk.items():
            org = org_per_kvk.get(kvk)
            if org is None:
                continue
            if not org.get("sector"):
                sector = sector_uit_sbi(info["sbi"])
                if sector:
                    vul["sector"][org["id"]] = sector
            if not org.get("sbi_code") and info["sbi"]:
                vul["sbi_code"][org["id"]] = info["sbi"]
            if not org.get("gemeente") and info["plaats"]:
                vul["gemeente"][org["id"]] = info["plaats"]
        verrijkt = len(vul["sector"].keys() | vul["sbi_code"].keys() | vul["gemeente"].keys())
        for veld, waarde_per_id in vul.items():
            per_waarde: dict[str, list[int]] = {}
            for org_id, waarde in waarde_per_id.items():
                per_waarde.setdefault(waarde, []).append(org_id)
            for waarde, ids in per_waarde.items():
                # Blokken houden de URL onder de lengtegrens van de server.
                for begin in range(0, len(ids), 200):
                    blok = ",".join(str(i) for i in sorted(ids[begin : begin + 200]))
                    db.bijwerken(
                        "organisaties",
                        f"id=in.({blok})&{veld}=is.null",
                        {veld: waarde},
                    )

        # Nieuwe organisaties in bulk, zonder bestaande te overschrijven: een
        # naam uit een documentbron is beter dan die uit een aanlevering.
        nieuw_per_kvk: dict[str, dict] = {}
        for rij in schoon:
            if rij["kvk"] not in org_per_kvk:
                info = aangeleverd_per_kvk[rij["kvk"]]
                nieuw_per_kvk.setdefault(
                    rij["kvk"],
                    {
                        "naam": rij["naam"],
                        "kvk_nummer": rij["kvk"],
                        "sector": sector_uit_sbi(info["sbi"]),
                        "sbi_code": info["sbi"] or None,
                        "gemeente": info["plaats"] or None,
                    },
                )
        if nieuw_per_kvk:
            db.invoegen_zonder_overschrijven(
                "organisaties", list(nieuw_per_kvk.values()), "kvk_nummer"
            )
            org_per_kvk = {
                r["kvk_nummer"]: r
                for r in db.selecteer_alles("organisaties", "select=id,kvk_nummer")
                if r.get("kvk_nummer")
            }

        if bron_id is None:
            bron = db.invoegen(
                "bronnen",
                {
                    "bron_type": "marktonderzoek",
                    "url": None,
                    "betrouwbaarheid": "zelf_aangeleverd",
                },
            )
            bron_id = bron["id"]

        # Opdrachten in bulk; wat al een controle heeft (of dubbel in de batch
        # zit) blijft staan — een documentbron wint altijd van een aanlevering.
        nieuwe_opdrachten: list[dict] = []
        for rij in schoon:
            org = org_per_kvk.get(rij["kvk"])
            kantoor_id = kantoor_id_per_sleutel.get(rij["afm"])
            if org is None or kantoor_id is None:
                overgeslagen += 1
                continue
            sleutel = (org["id"], rij["boekjaar"])
            if sleutel in bezet:
                overgeslagen += 1
                continue
            bezet.add(sleutel)
            nieuwe_opdrachten.append(
                {
                    "organisatie_id": org["id"],
                    "kantoor_id": kantoor_id,
                    "boekjaar": rij["boekjaar"],
                    "type_opdracht": "controle_onbepaald",
                    "bron_id": bron_id,
                }
            )
        geschreven = db.upsert(
            "opdrachten", nieuwe_opdrachten, "organisatie_id,boekjaar,type_opdracht"
        )

    rapport.close()
    print(
        f"\n{geschreven} opdrachten geschreven, {overgeslagen} al bekend, "
        f"{review} naar review, {verrijkt} organisaties verrijkt; "
        f"rapport: {rapport_pad}",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
