"""DUO-besturenlijsten -> is dit een schoolbestuur, en met welk KvK-nummer?

Bron: DUO Open Onderwijsdata (onderwijsdata.duo.nl), licentie CC BY 4.0.

- de vijf lijsten "besturen" bij de adresbestanden van bo, so, vo, mbo en ho:
  per bevoegd gezag het nummer, de naam en het KvK-nummer;
- het RIO-bestand onderwijsbesturen.csv: per onderwijsbestuur alle namen die
  het in de loop der jaren droeg, met het KvK-nummer.

Waarom dit bestaat
------------------
Een openbaar schoolbestuur legt zijn jaarrekening voor aan de gemeenteraad,
en laad_raadsinformatie.py vindt die controleverklaring daar. Die lader maakt
elke nieuwe organisatie aan als "overheid", zonder KvK-nummer — dus ook
"Stichting Openbaar Primair Onderwijs …" en "Stichting ROC …". Gemeten op
5-10-2026: 96 organisaties in sector overheid wijzen op naam naar precies één
schoolbestuur uit deze lijsten. Hun controles telden mee in het marktaandeel
van overheid, en onderwijs miste ze.

Twee keuzes
-----------
1. **Wát een schoolbestuur is, komt alleen uit de besturenlijsten.** RIO kent
   ook gemeenten en bedrijven die onderwijs aanbieden; die tellen hier niet. RIO
   levert alleen extra (oudere) namen bij een KvK-nummer dat in de
   besturenlijsten staat. Zonder die namen vonden we er 69, met 96: de lijsten
   korten namen fors af ("Stg. Openb. Prim. Onderw."), en de raadsstukken gaan
   tot 2010 terug, toen veel besturen nog anders heetten.

   Vier besturen zijn een gemeente (bevoegd gezag van de eigen openbare
   scholen). Die blijven buiten de lijst: een gemeente is geen schoolbestuur
   in de zin van een sector.

2. **Precies één KvK-nummer, anders niets.** Een naam die bij twee
   KvK-nummers hoort — twee besturen met dezelfde naam, of een oude naam die
   later door een ánder bestuur werd gedragen — levert geen treffer op. Ook
   een naam die in RIO bij een KvK-nummer búiten de besturenlijsten hoort, telt
   als dubbelzinnig. Die namen zelf staan niet in de seed (RIO kent ook
   niet-bekostigde aanbieders, en daar kan een eenmanszaak tussen zitten: een
   persoon); alleen de vlag `ook_elders` bij de naam van het bestuur.

   De rechtsvorm telt mee als beide namen er een hebben: "Vereniging X" is niet
   "Stichting X". Heeft één kant er geen, dan beslist de rest van de naam.

   Een plaatsstaart ("…, gevestigd te Testdam") gaat er bij het zoeken af,
   maar dan telt ook elke naam uit de lijsten zonder zíjn staart mee. Veel
   verenigingen heten "Vereniging voor Protestants Christelijk Onderwijs te
   <plaats>", en zonder staart is dat de naam van een vereniging in een heel
   ander dorp. Gemeten op 6-10-2026: 31 namen in de seed hadden zonder hun
   plaatsstaart de kern van een ánder bestuur. Van de 96 treffers in migratie
   20261006110000 veranderde er door deze regel geen; hij is er voor wat de
   laders voortaan op naam aanmaken. `ook_elders` is dan "kort": alleen de
   naam zonder staart is dubbelzinnig.

3. **Een lader kent op naam alleen de sector toe, nooit het KvK-nummer.**
   Een naam is geen harde sleutel. Gemeten op 6-10-2026: van de 161
   productierijen mét KvK-nummer waarvan de naam hier op precies één bestuur
   wijst, draagt die rij bij 4 een ánder nummer (drie zorginstellingen die de
   naam van een vroeger schoolbestuur voeren). Het nummer gaat daarom als
   kandidaat naar de review-queue (`bij_aanmaak`, `review_kandidaat`), en een
   mens kent het toe. De 71 nummers in migratie 20261006110000 zijn stuk voor
   stuk met de hand nagelopen tegen de besturenlijsten en RIO; die regel geldt
   niet voor wat een lader onbekeken aanmaakt.

De seed
-------
pipeline/seed/duo_besturen.csv, ververst met:

    python3 pipeline/adapters/duo_besturen.py

Alleen organisatiegegevens (nummer, naam, KvK), geen adressen of
telefoonnummers. De lader hoeft zo niet bij DUO aan te kloppen tijdens een run.
"""

import csv
import io
import re
import sys
import unicodedata
import urllib.request
from pathlib import Path

SEED_PAD = Path(__file__).resolve().parents[1] / "seed" / "duo_besturen.csv"

BESTUREN_URLS = {
    "bo": "https://onderwijsdata.duo.nl/dataset/786f12ea-6224-42fd-ab72-de4d7d879535/"
    "resource/d06cc759-ec8c-4430-91ad-14631b6c7bed/download/besturenbo.csv",
    "so": "https://onderwijsdata.duo.nl/dataset/033ab279-8e6f-44a2-8455-6ad42147762f/"
    "resource/cb92b932-6b7f-4948-b405-4dd97e561aba/download/besturenso.csv",
    "vo": "https://onderwijsdata.duo.nl/dataset/c8e6ffdd-cc2b-44ee-880f-0ff03f72e868/"
    "resource/bfc13171-de6b-4a3b-a095-e05d312107c4/download/besturenvo.csv",
    "mbo": "https://onderwijsdata.duo.nl/dataset/1bafae09-10e4-47b5-a54e-1c01f5776a60/"
    "resource/9aedc028-b38b-48d7-a158-7fd360d5fc30/download/besturenmbo.csv",
    "ho": "https://onderwijsdata.duo.nl/dataset/37051cda-b681-43eb-a385-efa18e99cdd2/"
    "resource/a521ddc2-b8d9-43d5-97df-1e700ee9f8c5/download/besturenho.csv",
}
RIO_URL = (
    "https://onderwijsdata.duo.nl/dataset/c416acd1-e083-4ec6-9203-3b20f98fe143/"
    "resource/918b5325-5f63-42ad-977a-63e4f0cc983e/download/onderwijsbesturen.csv"
)

# Onder deze lengte zegt een kernnaam te weinig ("Spirit", "Iris"): liever geen
# treffer dan een toevallige.
MIN_KERN = 8

# Afkortingen zoals de besturenlijsten ze schrijven, gemeten over de vijf
# lijsten van 2-10-2026 (de top-80 van woorden met een punt). Alleen wat
# eenduidig is; "st." staat er niet in, want dat is vooraan "stichting" en
# verderop "sint" (zie _woorden).
AFKORTINGEN = {
    "stg": "stichting",
    "stg.": "stichting",
    "sticht.": "stichting",
    "stiching": "stichting",
    "ver.": "vereniging",
    "verenig.": "vereniging",
    "veren.": "vereniging",
    "onderw.": "onderwijs",
    "onderw": "onderwijs",
    "ond.": "onderwijs",
    "chr.": "christelijk",
    "christ.": "christelijk",
    "christel.": "christelijk",
    "prot.": "protestants",
    "protest.": "protestants",
    "kath.": "katholiek",
    "kathol.": "katholiek",
    "openb.": "openbaar",
    "prim.": "primair",
    "voortg.": "voortgezet",
    "voortgez.": "voortgezet",
    "geref.": "gereformeerd",
    "gereform.": "gereformeerd",
    "alg.": "algemeen",
    "bijz.": "bijzonder",
    "spec.": "speciaal",
    "basisonderw.": "basisonderwijs",
    "basisond.": "basisonderwijs",
    "grondsl.": "grondslag",
    "v.": "voor",
}
RECHTSVORMEN = {"stichting", "vereniging"}

_PLAATSSTAART = re.compile(
    r"[,.\s)]+(?:statutair\s+)?(?:gevestigd\s+)?te\s+[\w'\-. ]+$", re.I
)
_GEMEENTE = re.compile(r"^\W*gemeente\b", re.I)


def is_gemeente(naam: str) -> bool:
    return bool(_GEMEENTE.match(naam or ""))


def _woorden(naam: str) -> list[str]:
    tekst = unicodedata.normalize("NFKD", naam or "")
    tekst = "".join(teken for teken in tekst if not unicodedata.combining(teken))
    tekst = tekst.lower().replace("&", " en ")
    woorden = []
    for i, woord in enumerate(re.findall(r"[a-z0-9]+\.?", tekst)):
        if woord in ("st.", "st"):
            woorden.append("stichting" if i == 0 else "sint")
        else:
            woorden.append(AFKORTINGEN.get(woord, woord.rstrip(".")))
    return woorden


def kern(naam: str) -> tuple[str, str | None]:
    """'Stg. Openb. Prim. Onderw. Testdorp' -> ('openbaarprimaironderwijstestdorp', 'stichting').

    De rechtsvorm gaat er vooraan en achteraan af en komt apart terug, zodat
    'Stichting X' en 'X, stichting' dezelfde kern hebben maar 'Vereniging X'
    er wel van te onderscheiden blijft.
    """
    woorden = _woorden(naam)
    rechtsvorm = None
    while woorden and woorden[0] in RECHTSVORMEN:
        rechtsvorm = rechtsvorm or woorden[0]
        woorden = woorden[1:]
    while woorden and woorden[-1] in RECHTSVORMEN:
        rechtsvorm = rechtsvorm or woorden[-1]
        woorden = woorden[:-1]
    return "".join(woorden), rechtsvorm


def zonder_plaatsstaart(naam: str) -> str:
    """'…, gevestigd te Testdam' -> '…' (zoals de raadsstukken de naam schrijven)."""
    return _PLAATSSTAART.sub("", naam or "")


def _kvk(waarde: str) -> str | None:
    cijfers = re.sub(r"\D", "", waarde or "")
    if not cijfers or len(cijfers) > 8:
        return None
    return cijfers.zfill(8)


def lees_besturen(tekst: str, soort: str) -> list[dict]:
    """Eén DUO-besturenlijst -> [{bevoegd_gezag, naam, kvk, soort}]."""
    uit = []
    for rij in csv.DictReader(io.StringIO(tekst.lstrip("\ufeff"))):
        naam = (rij.get("BEVOEGD GEZAG NAAM") or "").strip()
        kvk = _kvk(rij.get("KVK-NUMMER") or "")
        if not naam or not kvk:
            continue
        uit.append(
            {
                "bevoegd_gezag": (rij.get("BEVOEGD GEZAG NUMMER") or "").strip(),
                "naam": naam,
                "kvk": kvk,
                "soort": soort,
            }
        )
    return uit


def lees_rio(tekst: str) -> list[dict]:
    """RIO onderwijsbesturen.csv -> [{kvk, naam}], één rij per naamperiode."""
    uit = []
    for rij in csv.DictReader(io.StringIO(tekst.lstrip("\ufeff"))):
        naam = (rij.get("NAAM") or "").strip()
        kvk = _kvk(rij.get("KVK_NUMMER") or "")
        if naam and kvk:
            uit.append({"kvk": kvk, "naam": naam})
    return uit


def bouw_seed(besturen: list[dict], rio: list[dict]) -> list[dict]:
    """De seed-rijen: elke naam van elk schoolbestuur, met de dubbelzinnigheidsvlag."""
    gemeente_kvk = {b["kvk"] for b in besturen if is_gemeente(b["naam"])}
    soort_per_kvk: dict[str, set[str]] = {}
    gezag_per_kvk: dict[str, set[str]] = {}
    for b in besturen:
        if b["kvk"] in gemeente_kvk:
            continue
        soort_per_kvk.setdefault(b["kvk"], set()).add(b["soort"])
        gezag_per_kvk.setdefault(b["kvk"], set()).add(b["bevoegd_gezag"])

    namen: dict[tuple[str, str], str] = {}  # (kvk, naam) -> herkomst
    for b in besturen:
        if b["kvk"] in soort_per_kvk:
            namen[(b["kvk"], b["naam"])] = "besturenlijst"
    for r in rio:
        if r["kvk"] in soort_per_kvk and not is_gemeente(r["naam"]):
            namen.setdefault((r["kvk"], r["naam"]), "rio")

    # Kernen die in RIO (ook) bij een KvK-nummer buiten de besturenlijsten
    # horen, met en zonder plaatsstaart. Bewust zonder rechtsvorm-onderscheid:
    # liever een treffer te weinig.
    elders: set[str] = set()
    for r in rio:
        if r["kvk"] not in soort_per_kvk:
            elders.add(kern(r["naam"])[0])
            elders.add(kern(zonder_plaatsstaart(r["naam"]))[0])

    def vlag(naam: str) -> str:
        # "ja": de naam zelf is dubbelzinnig. "kort": alleen zonder zijn
        # plaatsstaart ("Stichting X te Testdam" is uniek, "Stichting X" niet).
        if kern(naam)[0] in elders:
            return "ja"
        if kern(zonder_plaatsstaart(naam))[0] in elders:
            return "kort"
        return ""

    rijen = []
    for (kvk, naam), herkomst in namen.items():
        rijen.append(
            {
                "kvk": kvk,
                "naam": naam,
                "herkomst": herkomst,
                "soort": "+".join(sorted(soort_per_kvk[kvk])),
                "bevoegd_gezag": "+".join(sorted(gezag_per_kvk[kvk])),
                "ook_elders": vlag(naam),
            }
        )
    rijen.sort(key=lambda r: (r["kvk"], r["herkomst"], r["naam"]))
    return rijen


def bouw_index(rijen: list[dict]) -> dict[str, list[dict]]:
    """Kernnaam -> seed-rijen met die kern (en hun rechtsvorm).

    Elke naam staat er twee keer in: zoals hij is, en zonder plaatsstaart. Zo
    is "Vereniging voor Onderwijs" dubbelzinnig zodra er ook een "Vereniging
    voor Onderwijs te Testdam" bestaat — ook als de lader de staart pas zelf
    afknipt.
    """
    index: dict[str, list[dict]] = {}
    for rij in rijen:
        vlag = rij.get("ook_elders") or ""
        varianten = [(rij["naam"], vlag == "ja")]
        kort = zonder_plaatsstaart(rij["naam"])
        if kort != rij["naam"]:
            varianten.append((kort, vlag in ("ja", "kort")))
        gezien: set[str] = set()
        for naam, elders in varianten:
            sleutel, rechtsvorm = kern(naam)
            if len(sleutel) < MIN_KERN or sleutel in gezien:
                continue
            gezien.add(sleutel)
            index.setdefault(sleutel, []).append(
                {"kvk": rij["kvk"], "rechtsvorm": rechtsvorm, "ook_elders": elders}
            )
    return index


def laad_seed(pad: Path = SEED_PAD) -> list[dict]:
    with pad.open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


_STANDAARD_INDEX: dict | None = None


def zoek_kvk(naam: str, index: dict[str, list[dict]]) -> str | None:
    """Het KvK-nummer van het schoolbestuur met deze naam, of None.

    Eerst de naam zoals hij is, dan zonder plaatsstaart. Een dubbelzinnige
    treffer op de volle naam is het eindantwoord: dan niet alsnog op de kortere
    naam proberen, want die is alleen maar minder precies.
    """
    if is_gemeente(naam):
        return None
    for variant in (naam, zonder_plaatsstaart(naam)):
        sleutel, rechtsvorm = kern(variant)
        if len(sleutel) < MIN_KERN:
            continue
        kandidaten = [
            k
            for k in index.get(sleutel, [])
            if rechtsvorm is None or k["rechtsvorm"] is None or k["rechtsvorm"] == rechtsvorm
        ]
        if not kandidaten:
            continue
        if any(k["ook_elders"] for k in kandidaten):
            return None
        nummers = {k["kvk"] for k in kandidaten}
        return nummers.pop() if len(nummers) == 1 else None
    return None


def is_schoolbestuur(naam: str, index: dict | None = None) -> str | None:
    """KvK-nummer als `naam` eenduidig één schoolbestuur uit de DUO-lijsten is.

    Zonder index wordt de seed in de repository gebruikt (één keer ingelezen).
    """
    global _STANDAARD_INDEX
    if index is None:
        if _STANDAARD_INDEX is None:
            _STANDAARD_INDEX = bouw_index(laad_seed())
        index = _STANDAARD_INDEX
    return zoek_kvk(naam, index)


def kvk_nummers(pad: Path = SEED_PAD) -> set[str]:
    """Alle KvK-nummers van schoolbesturen: de harde sleutel, zonder naamwerk."""
    return {rij["kvk"] for rij in laad_seed(pad)}


def bij_aanmaak(
    naam: str, standaard: str, bekende_kvk, index: dict | None = None
) -> dict:
    """Sector en KvK-kandidaat voor een organisatie die een lader op naam aanmaakt.

    Voor laad_gunningen.py en laad_raadsinformatie.py: die maken een
    opdrachtgever of gecontroleerde partij aan zonder KvK-nummer, met hun eigen
    standaardsector ("overheid"). Is de naam eenduidig een schoolbestuur, dan
    wordt de sector "onderwijs". Het KvK-nummer wordt níet toegekend (keuze 3
    bovenin): het komt terug als `kvk_kandidaat`, en de lader zet daar een
    review-regel voor (`review_kandidaat`). `mogelijk_dubbel` zegt of dat
    nummer al op een andere rij staat (`bekende_kvk`: alles met een `in`); dan
    is de nieuwe rij misschien een dubbel van die rij, en ook dat beslist een
    mens.
    """
    kvk = is_schoolbestuur(naam, index)
    if not kvk:
        return {"sector": standaard, "kvk_kandidaat": None, "mogelijk_dubbel": False}
    return {"sector": "onderwijs", "kvk_kandidaat": kvk, "mogelijk_dubbel": kvk in bekende_kvk}


def review_filter(kvk: str) -> str:
    """PostgREST-filter: is er al een open review-regel voor dit KvK-nummer?

    Eén regel per nummer, wat de reden ook is; de review-queue heeft geen
    unieke sleutel, dus zonder deze check zette elke run hem er opnieuw in.
    """
    return "soort=eq.naam_match&status=eq.open&payload->>kvk_nummer=eq." + kvk


def review_kandidaat(bron: str, keuze: dict, organisatie_ids: list[int]) -> dict:
    """De review-regel bij een `kvk_kandidaat`; alleen id's en het nummer.

    `organisatie_ids`: de nieuwe rij, en bij `mogelijk_dubbel` ook de rij die
    het nummer al draagt. Geen namen: die staan in de database, en een mens
    zoekt ze daar op.
    """
    if keuze["mogelijk_dubbel"]:
        reden = "mogelijk dubbel"
        toelichting = (
            "naam wijst in de DUO-besturenlijsten naar dit KvK-nummer, dat al "
            "bij een andere rij staat; niet samengevoegd"
        )
    else:
        reden = "kvk-kandidaat op naam, niet toegekend"
        toelichting = (
            "naam wijst in de DUO-besturenlijsten naar dit KvK-nummer; een naam "
            "is geen harde sleutel, dus het nummer is niet toegekend"
        )
    return {
        "soort": "naam_match",
        "payload": {
            "bron": bron,
            "reden": reden,
            "kvk_nummer": keuze["kvk_kandidaat"],
            "organisatie_ids": sorted(organisatie_ids),
            "toelichting": toelichting,
        },
    }


def _haal(url: str) -> str:
    verzoek = urllib.request.Request(
        url, headers={"User-Agent": "Mozilla/5.0 (WhoSigns-pipeline)"}
    )
    with urllib.request.urlopen(verzoek, timeout=300) as antwoord:
        return antwoord.read().decode("utf-8-sig")


# Ondergrens voor een verse download: op 2-10-2026 stonden er 1.124 bevoegde
# gezagen in de vijf lijsten. Een lijst die ineens veel korter is, is afgekapt,
# en dan zou de seed stil besturen verliezen.
MINIMUM_BESTUREN = 1000


def main() -> int:
    besturen: list[dict] = []
    for soort, url in BESTUREN_URLS.items():
        besturen.extend(lees_besturen(_haal(url), soort))
    aantal = len({b["kvk"] for b in besturen})
    if aantal < MINIMUM_BESTUREN:
        print(f"::error::maar {aantal} besturen in de DUO-lijsten; de seed blijft staan")
        return 1
    rio = lees_rio(_haal(RIO_URL))
    rijen = bouw_seed(besturen, rio)
    SEED_PAD.parent.mkdir(parents=True, exist_ok=True)
    with SEED_PAD.open("w", newline="", encoding="utf-8") as f:
        schrijver = csv.DictWriter(f, fieldnames=list(rijen[0].keys()))
        schrijver.writeheader()
        schrijver.writerows(rijen)
    print(
        f"{len({r['kvk'] for r in rijen})} schoolbesturen, {len(rijen)} namen "
        f"weggeschreven naar {SEED_PAD}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
