"""Ontbrekende sector aanvullen uit de KvK Open Dataset Basis Bedrijfsgegevens.

    organisaties zonder sector, mét KvK-nummer
        ->  opendata.kvk.nl/api/v1/hvds/basisbedrijfsgegevens/kvknummer/<kvk>
        ->  SBI-code van de hoofdactiviteit
        ->  sbi_code en sector, alléén waar die nog leeg zijn

Waarom
------
Op 5-10-2026 hadden 423 organisaties geen sector, allemaal uit het
marktonderzoek: de aanlevering gaf er geen SBI-code bij. Ze staan daardoor op
geen enkele sectorpagina. Hun 764 opdrachten zijn allemaal
"controle_onbepaald", dus aan de marktaandelen verandert dit niets; het gaat om
vindbaarheid per sector.

De bron
-------
De KvK stelt deze dataset beschikbaar onder CC BY 4.0 (High Value Dataset,
zonder sleutel). Hij bevat alleen BV's en NV's en geen persoonsgegevens: per
KvK-nummer de rechtsvorm, de startdatum, actief ja/nee en de SBI-codes. Een
stichting of vereniging geeft 404. Een inactieve inschrijving geeft nog steeds
een SBI-code, en die is voor de sector net zo goed. Een steekproef van tien op
5-10-2026: vijf met een hoofdactiviteit, vier keer 404, één zonder SBI.

De bulkdownload van dezelfde dataset heeft geen KvK-nummers (bewust
geanonimiseerd), dus de API is de enige weg. Die staat één verzoek per minuut
per IP-adres toe, plus 200 per vijf minuten voor alle gebruikers samen; sneller
geeft HTTP 429.

Hervatten
---------
423 verzoeken van een minuut is ruim zeven uur, en een Actions-job mag er zes.
Daarom stopt dit script bij een tijdbudget (standaard 320 minuten) en houdt het
bij wat het al vroeg in pipeline/werkvoorraad/sector_kvk.json. De workflow
"Sector aanvullen" commit dat bestand na elke run; de volgende run slaat over
wat er al in staat. Wat gevuld is valt vanzelf af (de sector is dan niet meer
leeg); het bestand is er voor de 404's en de antwoorden zonder SBI-code, die
pas na een half jaar opnieuw gevraagd worden.

Het bestand is op organisatie-id, niet op KvK-nummer. Ook van een eenmanszaak
is het KvK-nummer een persoonsgegeven, en wat hier 404 geeft is precies wat
geen BV of NV is; dat hoort niet in een openbare repository.

Volgorde: namen die op B.V. of N.V. eindigen eerst (310 van de 423), want
alleen die staan in de dataset; de rest daarna.

De sector komt uit laad_marktonderzoek.sector_voor: dezelfde grove hokjes als
bij het laden van een aanlevering, en een schoolbestuur uit de DUO-lijsten
wordt onderwijs. Holdings (SBI 64.20) komen in financiële dienstverlening;
zo staat het ook in de uitleg bij die sector op de site.

Draaien:
    python3 pipeline/vul_sector.py --droogloop --maximum 3
    python3 pipeline/vul_sector.py --tijdbudget 320
"""

import argparse
import http.client
import json
import re
import sys
import time
import urllib.error
import urllib.request
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent / "adapters"))
sys.path.insert(0, str(Path(__file__).resolve().parent / "extractie"))

import duo_besturen  # noqa: E402
from laad_marktonderzoek import sector_voor  # noqa: E402
from supabase_client import Supabase, SupabaseFout  # noqa: E402

API = "https://opendata.kvk.nl/api/v1/hvds/basisbedrijfsgegevens/kvknummer/{kvk}"
BRON = "KvK Open Dataset Basis Bedrijfsgegevens (CC BY 4.0)"
VOORTGANG = Path(__file__).resolve().parent / "werkvoorraad" / "sector_kvk.json"

# Eén verzoek per minuut per IP; een paar seconden marge, want de klok van de
# KvK en die van de runner lopen niet gelijk.
INTERVAL = 62
# Een 404 of een antwoord zonder SBI-code verandert zelden; na een half jaar
# opnieuw vragen vangt een BV die later is opgericht of omgezet.
OPNIEUW_NA = timedelta(days=180)
# Zoveel keer achter elkaar 429 of een netwerkfout, en het heeft geen zin meer:
# dan stopt de run en bewaart wat hij heeft.
MAX_FOUTEN_OP_RIJ = 3

# "Testbedrijf B.V.", "Testbedrijf BV", maar ook "… N.V. in liquidatie" en
# "B.V. Testbedrijf": zeven van de 423 droegen de rechtsvorm niet achteraan.
_BV_NV = re.compile(r"\b[bn]\.\s?v\.?(?:\s|$)|\b[bn]v\s*$", re.I)


def is_bv_nv(naam: str) -> bool:
    return bool(_BV_NV.search(naam or ""))


def lees_voortgang(pad: Path = VOORTGANG) -> dict:
    if not pad.exists():
        return {"bron": BRON, "uitkomsten": {}}
    return json.loads(pad.read_text(encoding="utf-8"))


def schrijf_voortgang(voortgang: dict, pad: Path = VOORTGANG) -> None:
    pad.parent.mkdir(parents=True, exist_ok=True)
    pad.write_text(
        json.dumps(voortgang, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def te_doen(organisaties: list[dict], voortgang: dict, vandaag: date) -> list[dict]:
    """Wie er gevraagd moet worden, BV's en NV's eerst."""
    uitkomsten = voortgang.get("uitkomsten", {})
    lijst = []
    for org in organisaties:
        if org.get("sector") or not re.fullmatch(r"\d{8}", org.get("kvk_nummer") or ""):
            continue
        eerder = uitkomsten.get(str(org["id"]))
        if eerder and eerder["uitkomst"] in ("niet_in_dataset", "geen_sbi"):
            if vandaag - date.fromisoformat(eerder["op"]) < OPNIEUW_NA:
                continue
        lijst.append(org)
    lijst.sort(key=lambda o: (not is_bv_nv(o["naam"]), o["id"]))
    return lijst


def hoofdactiviteit(antwoord: dict) -> str | None:
    """De SBI-code van de hoofdactiviteit, of None (ook bij een vreemde vorm)."""
    activiteiten = antwoord.get("activiteiten")
    for activiteit in activiteiten if isinstance(activiteiten, list) else []:
        if isinstance(activiteit, dict) and activiteit.get("soortActiviteit") == "Hoofdactiviteit":
            code = re.sub(r"\D", "", str(activiteit.get("sbiCode") or ""))
            if code:
                return code
    return None


def haal(kvk: str, timeout: int = 30) -> tuple[int, object]:
    """(HTTP-status, antwoord) voor één KvK-nummer; status 0 bij een netwerkfout.

    Het antwoord is wat de JSON gaf; of dat een object is, controleert draai().
    """
    verzoek = urllib.request.Request(
        API.format(kvk=kvk),
        headers={"Accept": "application/json", "User-Agent": "WhoSigns-pipeline"},
    )
    try:
        with urllib.request.urlopen(verzoek, timeout=timeout) as antwoord:
            return antwoord.status, json.loads(antwoord.read().decode("utf-8"))
    except urllib.error.HTTPError as fout:
        return fout.code, None
    # Een verbinding die na het verzoek wegvalt, komt niet als URLError maar
    # als RemoteDisconnected, IncompleteRead of ConnectionResetError (urllib
    # pakt alleen fouten tijdens het versturen in). Ook dat is "geen
    # verbinding": tellen en doorgaan, niet de hele run laten omvallen.
    except (urllib.error.URLError, http.client.HTTPException, OSError, ValueError):
        return 0, None


def draai(
    organisaties: list[dict],
    voortgang: dict,
    db,
    *,
    haal=haal,
    klok=time.monotonic,
    slaap=time.sleep,
    tijdbudget_s: float = 320 * 60,
    maximum: int | None = None,
    vandaag: date | None = None,
    schoolbesturen: set[str] | None = None,
    bewaar=lambda voortgang: None,
) -> dict:
    """Vraag de KvK, vul wat leeg is, en houd bij wat er gebeurde.

    `db` mag None zijn (droogloop). `bewaar` wordt na elk antwoord aangeroepen,
    zodat een afgebroken run zijn voortgang niet kwijt is.
    """
    vandaag = vandaag or date.today()
    if schoolbesturen is None:
        schoolbesturen = duo_besturen.kvk_nummers()
    uitkomsten = voortgang.setdefault("uitkomsten", {})
    voortgang["bron"] = BRON
    telling = {"gevraagd": 0, "gevuld": 0, "niet_in_dataset": 0, "geen_sbi": 0, "fout": 0}
    begin = klok()
    vorige = None
    fouten_op_rij = 0
    # Een 404 zegt pas "geen BV of NV" als dezelfde run ook een 200 zag: een
    # verhuisd endpoint geeft óók 404 op alles, en dan zou elke organisatie
    # 180 dagen lang "niet in de dataset" heten. Tot de eerste 200 blijven de
    # 404's hier staan; komt die 200 nooit, dan tellen ze als fout.
    gezien_200 = False
    wacht_404: list[str] = []
    reden = "alles gevraagd"
    for org in te_doen(organisaties, voortgang, vandaag):
        if maximum is not None and telling["gevraagd"] >= maximum:
            reden = f"maximum van {maximum} bereikt"
            break
        # Niet aan een verzoek beginnen dat het budget niet meer haalt.
        wacht = 0.0 if vorige is None else max(0.0, INTERVAL - (klok() - vorige))
        if klok() - begin + wacht + INTERVAL > tijdbudget_s:
            reden = "tijdbudget op"
            break
        if wacht:
            slaap(wacht)
        vorige = klok()
        status, antwoord = haal(org["kvk_nummer"])
        telling["gevraagd"] += 1

        if status == 404:
            uitkomst = {"uitkomst": "niet_in_dataset", "op": vandaag.isoformat()}
        elif status == 200 and isinstance(antwoord, dict):
            # Een 200 met iets anders dan een JSON-object (een lijst, een
            # tekst) valt hieronder bij de fouten, niet om in hoofdactiviteit.
            gezien_200 = True
            sbi = hoofdactiviteit(antwoord)
            if sbi is None:
                uitkomst = {"uitkomst": "geen_sbi", "op": vandaag.isoformat()}
            else:
                sector = sector_voor(org["kvk_nummer"], sbi, schoolbesturen)
                uitkomst = {
                    "uitkomst": "gevuld",
                    "op": vandaag.isoformat(),
                    "sbi": sbi,
                    "sector": sector,
                }
                if db is not None:
                    # Alleen lege velden: `is.null` in het filter laat de
                    # database bewaken dat niets wordt overschreven, ook niet
                    # wat een andere lader intussen heeft gezet.
                    if sector:
                        db.bijwerken(
                            "organisaties",
                            f"id=eq.{org['id']}&sector=is.null",
                            {"sector": sector},
                        )
                    db.bijwerken(
                        "organisaties",
                        f"id=eq.{org['id']}&sbi_code=is.null",
                        {"sbi_code": sbi},
                    )
        else:
            # 429, een serverfout of geen verbinding: niets vastleggen, de
            # volgende run vraagt het opnieuw. Bij 429 extra lang wachten.
            telling["fout"] += 1
            fouten_op_rij += 1
            if fouten_op_rij >= MAX_FOUTEN_OP_RIJ:
                reden = f"{fouten_op_rij} fouten op rij (laatste HTTP {status})"
                break
            if status == 429:
                slaap(INTERVAL)
            continue

        fouten_op_rij = 0
        if uitkomst["uitkomst"] == "niet_in_dataset" and not gezien_200:
            wacht_404.append(str(org["id"]))
            continue
        for org_id in wacht_404:
            telling["niet_in_dataset"] += 1
            uitkomsten[org_id] = {"uitkomst": "niet_in_dataset", "op": vandaag.isoformat()}
        wacht_404 = []
        telling[uitkomst["uitkomst"]] += 1
        uitkomsten[str(org["id"])] = uitkomst
        bewaar(voortgang)
    if wacht_404:
        # Geen enkele 200 in deze run: die 404's zijn niet te vertrouwen.
        telling["fout"] += len(wacht_404)
        reden += f"; {len(wacht_404)} keer 404 zonder één 200, niet vastgelegd"
    telling["reden"] = reden
    return telling


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--droogloop", action="store_true", help="niets naar de database")
    parser.add_argument("--maximum", type=int, help="hoogstens zoveel verzoeken")
    parser.add_argument(
        "--tijdbudget", type=float, default=320, help="minuten; daarna netjes stoppen"
    )
    argumenten = parser.parse_args()

    try:
        db = Supabase()
    except SupabaseFout as fout:
        print(fout)
        return 1
    organisaties = db.selecteer_alles(
        "organisaties", "select=id,naam,kvk_nummer,sector&sector=is.null&kvk_nummer=not.is.null"
    )
    voortgang = lees_voortgang()
    open_nu = len(te_doen(organisaties, voortgang, date.today()))
    print(f"{len(organisaties)} organisaties zonder sector; {open_nu} nog te vragen", flush=True)

    telling = draai(
        organisaties,
        voortgang,
        None if argumenten.droogloop else db,
        tijdbudget_s=argumenten.tijdbudget * 60,
        maximum=argumenten.maximum,
        bewaar=schrijf_voortgang,
    )
    schrijf_voortgang(voortgang)
    print(
        f"{telling['gevraagd']} gevraagd: {telling['gevuld']} gevuld, "
        f"{telling['niet_in_dataset']} niet in de dataset (geen BV/NV), "
        f"{telling['geen_sbi']} zonder SBI-code, {telling['fout']} fout. "
        f"Gestopt: {telling['reden']}.",
        flush=True,
    )
    # Rood alleen als er niets lukte terwijl er wel iets te doen was: een
    # reeks 429's of een onbereikbare API. De voortgang is dan al bewaard.
    if telling["gevraagd"] and telling["fout"] == telling["gevraagd"]:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
