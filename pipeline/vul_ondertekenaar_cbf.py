"""De ondertekenaar bijvullen bij de goede doelen die al in de database staan.

Draaien vanuit de repo-root:

    python3 pipeline/vul_ondertekenaar_cbf.py                 # droogloop: tellen
    python3 pipeline/vul_ondertekenaar_cbf.py --schrijf       # invullen
    python3 pipeline/vul_ondertekenaar_cbf.py --aantal 40     # een proef

Waarom dit bestaat
------------------
`analyseer()` rekent sinds 20-8-2026 de tekenend accountant uit, maar
`stichtingen._uit_tekst()` gaf hem niet door en `laad_stichtingen.py` schreef hem
niet. Op 5-10-2026 hadden de 1.426 opdrachten uit de CBF-route er geen één. Voor
wat de lus vanaf nu leest is dat gerepareerd; dit script haalt de rest in.

Het jaarverslag staat op een vaste plek bij het CBF, dus het is opnieuw op te
halen: per organisatie-boekjaar één download en `pdftotext`, gemeten op 5-10-2026
gemiddeld 2,1 seconde per stuk over 96 verslagen. Geen OCR: wie een scan
deponeert, zet er zelden een leesbare naam onder, en een runner heeft er geen
tesseract voor.

Wanneer er een naam bij komt
----------------------------
Alleen als het opnieuw gelezen stuk op hetzelfde kantoor (sleutel), hetzelfde
opdrachttype en hetzelfde oordeel uitkomt als de rij. Anders is het niet
aantoonbaar dezelfde verklaring, en dan blijft het veld leeg — dezelfde eis als
`vul_ondertekenaar.py` in de zorg. Daarbovenop de strengere kantooreis van
`stichtingen.naam_bij_kantoor()`. Nooit overschrijven: `tekenend_accountant=
is.null` staat in het bijwerkverzoek zelf, dus ook een rij die tussendoor een
naam kreeg blijft zoals hij is.

Verwachte opbrengst: in twee steekproeven (5-10-2026, 100 CBF-opdrachten) kreeg
38% een naam; eerdere proeven van 20 en 15 kwamen hoger uit. Dus ~500-700 van de
1.407 controles. Wat overblijft heeft geen naam op een ondertekeningsplek (de
handtekening als plaatje) of leest nu anders dan toen, en blijft leeg.

Hervatbaar zonder voortgangsbestand: wat een naam kreeg valt bij een volgende run
af door het filter `is.null`. Wat geen naam opleverde wordt dan wel opnieuw
gelezen; dat is een paar seconden per stuk, en een volgende run komt er alleen als
dit script of zijn workflow verandert.

AVG: de uitvoer bevat alleen tellingen, nooit een naam (zie docs/concept.md §9).
"""

import argparse
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent / "adapters"))
sys.path.insert(0, str(Path(__file__).resolve().parent / "extractie"))

import cbf  # noqa: E402
import stichtingen  # noqa: E402
from kantoor_match import bouw_index, laad_kantoren  # noqa: E402
from supabase_client import Supabase, SupabaseFout  # noqa: E402
from verklaring import pdf_naar_tekst  # noqa: E402

# De twee controlevormen: alleen daar zet analyseer() een naam neer. Een
# beoordeling heeft geen controleverklaring en dus geen ondertekenaar in dit veld.
CONTROLETYPEN = ("wettelijke_controle", "vrijwillige_controle")

# Nieuwste boekjaren eerst: die staan op de voorpagina, en als de run onverhoopt
# wordt afgekapt, is het de staart die wacht.
VRAAG = (
    "select=id,boekjaar,type_opdracht,oordeel,"
    "organisaties!inner(kvk_nummer),kantoren!inner(sleutel),bronnen!inner(bron_type)"
    "&bronnen.bron_type=eq.cbf&tekenend_accountant=is.null"
    f"&type_opdracht=in.({','.join(CONTROLETYPEN)})"
    "&order=boekjaar.desc,id.asc"
)


def naam_voor_rij(rij: dict, gevonden: dict | None) -> str | None:
    """De naam uit het opnieuw gelezen stuk, alleen als die bij déze rij hoort.

    `rij` heeft `type_opdracht`, `oordeel` en `kantoor_sleutel`; `gevonden` is wat
    `stichtingen._uit_tekst()` teruggeeft (of None). Kantoor op sleutel en niet op
    naam: een kantoor kan sindsdien anders heten. Een verkeerde naam is een
    beschuldiging; leeg is gratis.
    """
    if not gevonden:
        return None
    naam = (gevonden.get("tekenend_accountant") or "").strip()
    if not naam:
        return None
    if (gevonden.get("kantoor") or {}).get("sleutel") != rij.get("kantoor_sleutel"):
        return None
    if gevonden.get("opdrachttype") != rij.get("type_opdracht"):
        return None
    if (gevonden.get("oordeel") or None) != (rij.get("oordeel") or None):
        return None
    return naam


def uitkomst(rij: dict, gevonden: dict | None) -> str:
    """Waarom een rij wel of geen naam kreeg, als telling (zonder de naam zelf)."""
    if naam_voor_rij(rij, gevonden):
        return "naam"
    if not gevonden:
        return "geen controleverklaring gelezen"
    if (gevonden.get("kantoor") or {}).get("sleutel") != rij.get("kantoor_sleutel"):
        return "ander kantoor"
    if gevonden.get("opdrachttype") != rij.get("type_opdracht"):
        return "ander opdrachttype"
    if (gevonden.get("oordeel") or None) != (rij.get("oordeel") or None):
        return "ander oordeel"
    return "geen naam op een ondertekeningsplek"


def namen_per_kvk(register: list[dict]) -> dict[str, str]:
    """KvK-nummer -> de naam waaronder het CBF het verslag bewaart.

    Alleen eenduidige: staat één KvK-nummer onder twee namen in het register, dan
    is niet te zeggen welk verslag bij de rij hoort, en dan slaan we hem over.
    Op 5-10-2026 kwam dat niet voor (836 vermeldingen, geen dubbel nummer).
    """
    gezien: dict[str, set[str]] = {}
    for organisatie in register:
        kvk = organisatie.get("kvknummer")
        if kvk and organisatie.get("naam"):
            gezien.setdefault(kvk, set()).add(organisatie["naam"])
    return {kvk: next(iter(namen)) for kvk, namen in gezien.items() if len(namen) == 1}


def lees(naam: str, boekjaar: int, kantoor_index: dict) -> tuple[str, dict | None]:
    """Het verslag ophalen en lezen. Geeft (status, gevonden) terug."""
    inhoud = cbf.jaarverslag(naam, boekjaar)
    if not inhoud:
        return "geen verslag meer bij het CBF", None
    with tempfile.NamedTemporaryFile(suffix=".pdf") as bestand:
        bestand.write(inhoud)
        bestand.flush()
        tekst = pdf_naar_tekst(bestand.name)
    if len(tekst.strip()) < 50:
        return "geen tekstlaag", None
    return "gelezen", stichtingen._uit_tekst(
        tekst, kantoor_index, cbf.jaarverslag_url(naam, boekjaar)
    )


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--schrijf", action="store_true")
    p.add_argument("--aantal", type=int, default=0, help="hoogstens N organisatie-boekjaren")
    p.add_argument("--werkers", type=int, default=4)
    p.add_argument(
        "--tijdbudget", type=int, default=100,
        help="na zoveel minuten geen nieuwe verslagen meer ophalen",
    )
    argumenten = p.parse_args()

    try:
        db = Supabase()
    except SupabaseFout as fout:
        print(fout)
        return 1

    rijen = db.selecteer_alles("opdrachten", VRAAG)
    per_paar: dict[tuple[str, int], list[dict]] = {}
    for rij in rijen:
        kvk = (rij.get("organisaties") or {}).get("kvk_nummer")
        rij["kantoor_sleutel"] = (rij.get("kantoren") or {}).get("sleutel")
        if kvk:
            per_paar.setdefault((kvk, rij["boekjaar"]), []).append(rij)

    register = namen_per_kvk(cbf.organisaties(alleen_actief=False))
    paren = [paar for paar in per_paar if paar[0] in register]
    print(
        f"{len(rijen)} CBF-controles zonder naam, {len(per_paar)} organisatie-boekjaren; "
        f"{len(per_paar) - len(paren)} staan niet eenduidig in het register",
        flush=True,
    )
    if argumenten.aantal:
        paren = paren[: argumenten.aantal]

    kantoor_index = bouw_index(laad_kantoren())
    begin = time.time()

    def verwerk(paar: tuple[str, int]):
        if (time.time() - begin) / 60 > argumenten.tijdbudget:
            return paar, "tijdbudget op", None
        try:
            status, gevonden = lees(register[paar[0]], paar[1], kantoor_index)
        except Exception as fout:  # noqa: BLE001 — bron mag falen, run gaat door
            # Alleen het soort fout: de melding zelf kan uit het document komen.
            return paar, f"bronfout ({type(fout).__name__})", None
        return paar, status, gevonden

    telling: dict[str, int] = {}
    ingevuld = 0
    with ThreadPoolExecutor(max_workers=argumenten.werkers) as pool:
        for teller, (paar, status, gevonden) in enumerate(pool.map(verwerk, paren), start=1):
            for rij in per_paar[paar]:
                reden = uitkomst(rij, gevonden) if status == "gelezen" else status
                telling[reden] = telling.get(reden, 0) + 1
                naam = naam_voor_rij(rij, gevonden) if status == "gelezen" else None
                if naam and argumenten.schrijf:
                    db.bijwerken(
                        "opdrachten",
                        f"id=eq.{rij['id']}&tekenend_accountant=is.null",
                        {"tekenend_accountant": naam},
                    )
                    ingevuld += 1
            if teller % 100 == 0:
                print(
                    f"--- {teller}/{len(paren)} | {telling.get('naam', 0)} namen | "
                    f"{(time.time() - begin) / 60:.0f} min ---",
                    flush=True,
                )

    print(f"\n=== {len(paren)} organisatie-boekjaren in {(time.time() - begin) / 60:.0f} min ===")
    for reden, aantal in sorted(telling.items(), key=lambda p: -p[1]):
        print(f"  {aantal:5d}  {reden}")
    if argumenten.schrijf:
        print(f"\n{ingevuld} namen ingevuld")
    else:
        print(f"\ndroogloop: niets geschreven; met --schrijf komen er "
              f"{telling.get('naam', 0)} namen bij")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
