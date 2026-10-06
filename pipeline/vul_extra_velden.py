"""Vult de extra dataset-velden bij op rijen die al in de database staan.

Waarom dit apart bestaat: `laad_zorg.py` slaat organisatie-boekjaren over die al
een opdracht hebben. Dat is precies goed voor hervatten — je wilt geen pdf's
opnieuw ophalen — maar het betekent ook dat nieuwe kolommen nooit gevuld raken
zodra een boekjaar eenmaal geladen is.

Deze velden komen uit de jaardataset, niet uit het archief. Er hoeft dus niets
gedownload te worden: het is een handvol verzoeken naar Supabase en klaar in
seconden, niet in uren.

    organisaties   subsector, rechtsvorm, gemeente, omzet_eur
    opdrachten     honorarium_controle_eur, honorarium_overig_eur,
                   honorarium_fiscaal_eur, honorarium_nietcontrole_eur,
                   wissel_gerapporteerd

Draaien:
    python3 pipeline/vul_extra_velden.py --boekjaar 2023
    python3 pipeline/vul_extra_velden.py --boekjaren 2023,2022

Eén boekjaar per dataset; `--boekjaren` loopt er meerdere af en gaat door waar
één jaargang faalt — de dataset van het ene jaar mag de honoraria van het
andere niet gijzelen. Het boekjaar is dat van de dataset. Subsector, rechtsvorm
en plaats gaan naar de organisatie en gelden voor alle jaren; de jaarcijfers
(omzet, honoraria, wisselvlag) worden alleen aan de opdracht van dát boekjaar
gehangen.

De jaargangen worden van oud naar nieuw gedraaid, ook als je ze in een andere
volgorde opgeeft. Dat is niet cosmetisch: de velden die bij de organisatie
horen worden overschreven, dus de laatste jaargang wint. Een zorginstelling
die is verhuisd of van rechtsvorm veranderd hoort de nieuwste stand te dragen,
niet die van 2020.

Idempotent: twee keer draaien geeft hetzelfde resultaat. Lege waarden worden
nooit weggeschreven, dus een bestaande waarde raakt niet kwijt aan een leeg veld.

Twee aanvullingen sinds 5-10-2026:

* **Het vorige boekjaar.** Elke dataset draagt de honoraria ook als
  vergelijkend cijfer over het jaar ervoor (`_1`-kolommen). Die gaan naar de
  controle van boekjaar J-1, maar alleen als daar nog géén enkel honorarium
  staat: een eigen opgave over dat jaar gaat altijd voor, want 14% van de
  vergelijkende cijfers wijkt af van wat de organisatie een jaar eerder zelf
  opgaf (gemeten op 724 organisaties tussen de datasets 2020 en 2021). Alles of
  niets, en niet per kolom: een kolom-voor-kolom-aanvulling mengde in 44 rijen
  twee opgaven, en zette zo hetzelfde bedrag soms twee keer in één rij (een
  "overig" uit de eigen opgave naast een "niet-controle" uit het vergelijkende
  cijfer — gemeten in een droogloop op 5-10-2026).
* **Een plausibiliteitscheck.** Drie organisaties verantwoordden bedragen in
  duizenden euro's in plaats van euro's (Treant 2020: € 327.805.000 controle,
  het jaar erna € 336.000). Delen door duizend zou een gok zijn; zo'n bedrag
  wordt niet geschreven en komt in de review-queue.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent / "adapters"))

import digimv_dataset  # noqa: E402
from supabase_client import Supabase, SupabaseFout  # noqa: E402

CACHE = Path(__file__).resolve().parent / ".cache"

# csv-veld -> databasekolom, per tabel.
#
# `plaats` staat hier sinds 22-9-2026. De vestigingsplaats stond wel in elke
# jaardataset maar werd alleen weggeschreven door de zorgoogst zelf; een
# organisatie die via een andere route was aangemaakt hield een lege
# `gemeente`. Van de 17.651 organisaties hadden er 14.251 er geen, en de
# aangeleverde marktonderzoekbestanden dragen de kolom niet (41.109 rijen,
# nul plaatsen) — de bron van dit gegeven is dus de dataset.
ORGANISATIE_VELDEN = {
    "subsector": "subsector",
    "rechtsvorm": "rechtsvorm",
    "plaats": "gemeente",
}
ORGANISATIE_JAARVELDEN = {"omzet": "omzet_eur"}
OPDRACHT_JAARVELDEN = {
    "honorarium_controle": "honorarium_controle_eur",
    "honorarium_overig": "honorarium_overig_eur",
    "honorarium_fiscaal": "honorarium_fiscaal_eur",
    "honorarium_nietcontrole": "honorarium_nietcontrole_eur",
    "wissel_gerapporteerd": "wissel_gerapporteerd",
    # Het oordeel zoals de bron het meldt, náást het oordeel dat wij uit de
    # gedeponeerde verklaring lezen. 97% van de tijd zijn ze het eens; de rest is
    # review-werk (v_oordeel_afwijking).
    "oordeel_gerapporteerd": "oordeel_gerapporteerd",
    "verklaring_datum": "verklaring_datum",
}


# De opdrachttypen waar een jaarrekeninghonorarium bij hoort. Tot 5-10-2026
# schreef deze vuller op álle opdrachten van een organisatie-boekjaar, dus ook op
# een WNT- of productieverantwoording: 70 honoraria en 239 gerapporteerde
# oordelen stonden zo op een opdracht die niet over de jaarrekening gaat, en
# /honoraria toonde ze als "controle WNT-verantwoording" met een
# controlehonorarium. "Voorwerp onbekend" telt mee: dat is een controle waarvan
# alleen niet is vastgesteld waarover; het bedrag zelf komt uit de eigen opgave
# van de organisatie.
CONTROLETYPEN = "wettelijke_controle,vrijwillige_controle,controle_onbepaald"

# Het vergelijkende cijfer gaat alleen naar een controle die wij zelf uit een
# document hebben: daar weten we dat de jaarrekening gecontroleerd is.
VORIG_TYPEN = "wettelijke_controle,vrijwillige_controle"

# Heeft een organisatie-boekjaar zo'n gelezen controle, dan krijgt alléén die
# het honorarium en niet ook een "voorwerp onbekend"-rij uit het marktonderzoek
# ernaast. Anders staat één bedrag twee keer op /honoraria: 11
# organisatie-boekjaren hadden dat op 5-10-2026, en ze telden dubbel mee in het
# totaal, het gemiddelde en de mediaan per jaar.
ALLEEN_ONBEPAALD = "controle_onbepaald"

HONORARIUM_VELDEN = (
    "honorarium_controle",
    "honorarium_overig",
    "honorarium_fiscaal",
    "honorarium_nietcontrole",
)

# Hoe ver een controlehonorarium mag afwijken van een ander jaar van dezelfde
# organisatie. De drie eenheidsfouten liggen een factor ~1.000 uit elkaar. Echte
# sprongen zijn er ook: na deze vuller zijn er 15 jaarparen van één organisatie
# met meer dan een factor 10 verschil en 5 met meer dan 20 (een fusie, een
# eerste jaar met een volledige controle). Vijftig laat die door en vangt elke
# verwisseling van euro's en duizenden; wat ertussen zit is geen eenheidsfout
# maar wel een vraag, en daar is de review-queue niet voor. Bewust geen vaste
# bovengrens in euro's: een groot beursfonds betaalt legitiem tientallen
# miljoenen.
MAXIMALE_FACTOR = 50


def plausibel(bedrag: float, andere_jaren: dict[int, float], boekjaar: int) -> bool:
    """Past dit controlehonorarium bij de andere jaren van dezelfde organisatie?

    Vergelijkt met elk ander boekjaar dat al een bedrag heeft. Eén uitschieter
    in de vergelijking is genoeg om niet te schrijven: dan weten we niet welke
    van de twee fout is, en dan schrijven we liever niets dan het verkeerde. Een
    organisatie zonder andere jaren valt niet te beoordelen en gaat door.
    """
    if bedrag <= 0:
        return False
    for jaar, ander in andere_jaren.items():
        if jaar == boekjaar or not ander or ander <= 0:
            continue
        if max(bedrag, ander) / min(bedrag, ander) > MAXIMALE_FACTOR:
            return False
    return True


def zelfde_rij_plausibel(lopend: str | None, vorig: str | None) -> bool:
    """Het lopende jaar en het vergelijkende cijfer uit dezelfde datasetrij.

    Een goedkope en sterke check: één organisatie, één document, twee
    opeenvolgende jaren. Zo viel HCO op met € 34.073 tegen € 677. Liggen ze meer
    dan MAXIMALE_FACTOR uit elkaar, dan is minstens één van de twee fout en
    weten we niet welke — dan schrijven we geen van beide.
    """
    if not lopend or not vorig:
        return True
    try:
        a, b = float(lopend), float(vorig)
    except ValueError:
        return False
    if a <= 0 or b <= 0:
        return False
    return max(a, b) / min(a, b) <= MAXIMALE_FACTOR


def _waarde(rij: dict, veld: str):
    """Lege tekst wordt None; 'True'/'False' uit de csv wordt een echte boolean."""
    ruw = (rij.get(veld) or "").strip()
    if not ruw:
        return None
    if ruw.lower() in ("true", "false"):
        return ruw.lower() == "true"
    return ruw


def gekozen_boekjaren(argumenten) -> list[int]:
    """De boekjaren uit de argumenten, oudste eerst, zonder dubbelen.

    `--boekjaren "2023,2022"` wint van `--boekjaar`; dat laatste blijft bestaan
    omdat zorgdata.yml het meegeeft. Witruimte en lege stukken ("2023,,2022 ")
    worden vergeven: dit wordt vanuit een workflow-invoerveld getypt.

    `--boekjaren alle` neemt elke jaargang uit `digimv_dataset.DATASET_URL`.
    Dat is wat de workflow meegeeft, en het is er één plek in plaats van drie:
    de lijst stond ook in de twee invoervelden én nog eens hard in de stap zelf.
    Die laatste werd vergeten toen 2025 erbij kwam, en de eerste run daarna
    stopte netjes bij 2024 — groen, want er ging niets kapot; alleen het
    nieuwste boekjaar, waar het om begonnen was, bleef leeg. Nu is de
    downloadtabel de enige lijst: een jaargang toevoegen is één regel.

    Oud naar nieuw, en niet in de volgorde die je typt. De velden die bij de
    organisatie horen (subsector, rechtsvorm, plaats) worden overschreven, dus
    de jaargang die als laatste draait bepaalt wat er staat — 2020 hoort niet
    het laatste woord te hebben over waar een instelling vandaag gevestigd is.
    De jaarcijfers (honoraria, omzet, wisselvlag) hangen aan hun eigen boekjaar
    en merken hier niets van.
    """
    if argumenten.boekjaren.strip().lower() == "alle":
        return sorted(digimv_dataset.DATASET_URL)
    if argumenten.boekjaren:
        gekozen = {
            int(stuk.strip())
            for stuk in argumenten.boekjaren.split(",")
            if stuk.strip()
        }
        return sorted(gekozen)
    return [argumenten.boekjaar]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--boekjaar", type=int, default=2023)
    parser.add_argument("--boekjaren", type=str, default="")
    argumenten = parser.parse_args()
    mislukt = 0
    for boekjaar in gekozen_boekjaren(argumenten):
        try:
            code = vul_boekjaar(boekjaar)
        except Exception as fout:  # noqa: BLE001 — één jaargang mag falen
            print(f"boekjaar {boekjaar}: overgeslagen na een fout: {fout}", flush=True)
            code = 1
        mislukt += 1 if code else 0
    return 1 if mislukt else 0


def vul_boekjaar(boekjaar: int) -> int:
    rijen = digimv_dataset.doelpopulatie_uit_cache(boekjaar, CACHE)
    print(f"{len(rijen)} organisaties in de doelpopulatie van {boekjaar}\n", flush=True)

    try:
        db = Supabase()
    except SupabaseFout as fout:
        print(fout)
        return 1

    # Alleen organisaties die al in de database staan; de rest heeft geen opdracht
    # en hoort hier niet gemaakt te worden.
    id_per_kvk = {
        rij["kvk_nummer"]: rij["id"]
        for rij in db.selecteer_alles("organisaties", "select=id,kvk_nummer")
        if rij.get("kvk_nummer")
    }
    print(f"{len(id_per_kvk)} organisaties in de database", flush=True)

    # De controlehonoraria die er al staan, per organisatie en boekjaar: de
    # maatstaf voor de plausibiliteitscheck. Ook bijgewerkt met wat deze run
    # schrijft, zodat een later boekjaar met een eerder vergeleken wordt.
    bekend: dict[int, dict[int, float]] = {}
    for rij in db.selecteer_alles(
        "opdrachten",
        "select=organisatie_id,boekjaar,honorarium_controle_eur"
        "&honorarium_controle_eur=not.is.null",
    ):
        per_jaar = bekend.setdefault(rij["organisatie_id"], {})
        per_jaar[rij["boekjaar"]] = max(
            per_jaar.get(rij["boekjaar"], 0), float(rij["honorarium_controle_eur"])
        )

    # Welke organisatie-boekjaren een gelezen controle hebben, voor dit en het
    # vorige boekjaar: die krijgen het honorarium, en een marktonderzoekrij
    # ernaast niet.
    gelezen = {
        (rij["organisatie_id"], rij["boekjaar"])
        for rij in db.selecteer_alles(
            "opdrachten",
            "select=organisatie_id,boekjaar"
            f"&type_opdracht=in.({VORIG_TYPEN})&boekjaar=in.({boekjaar - 1},{boekjaar})",
        )
    }

    org_bijgewerkt = 0
    opdracht_verzoeken = 0
    vorig_verzoeken = 0
    onwaarschijnlijk = 0
    overgeslagen = 0

    for rij in rijen:
        organisatie_id = id_per_kvk.get(rij["kvk_nummer"])
        if organisatie_id is None:
            overgeslagen += 1
            continue

        org_velden = {
            kolom: _waarde(rij, veld)
            for veld, kolom in {**ORGANISATIE_VELDEN, **ORGANISATIE_JAARVELDEN}.items()
            if _waarde(rij, veld) is not None
        }
        if org_velden:
            db.bijwerken("organisaties", f"id=eq.{organisatie_id}", org_velden)
            org_bijgewerkt += 1

        opdracht_velden = {
            kolom: _waarde(rij, veld)
            for veld, kolom in OPDRACHT_JAARVELDEN.items()
            if _waarde(rij, veld) is not None
        }
        vorig = {
            OPDRACHT_JAARVELDEN[veld]: _waarde(rij, veld + digimv_dataset.VORIG)
            for veld in HONORARIUM_VELDEN
            if _waarde(rij, veld + digimv_dataset.VORIG) is not None
        }
        lopend_typen = (
            VORIG_TYPEN if (organisatie_id, boekjaar) in gelezen else ALLEEN_ONBEPAALD
        )
        lopend_filter = (
            f"organisatie_id=eq.{organisatie_id}&boekjaar=eq.{boekjaar}"
            f"&type_opdracht=in.({lopend_typen})"
        )
        # Het vergelijkende cijfer gaat alleen naar een controle waar nog géén
        # enkel honorarium staat; zie de kop van dit bestand voor waarom niet per
        # kolom.
        vorig_filter = (
            f"organisatie_id=eq.{organisatie_id}&boekjaar=eq.{boekjaar - 1}"
            f"&type_opdracht=in.({VORIG_TYPEN})"
            + "".join(f"&{OPDRACHT_JAARVELDEN[v]}=is.null" for v in HONORARIUM_VELDEN)
        )

        if not zelfde_rij_plausibel(
            _waarde(rij, "honorarium_controle"),
            _waarde(rij, "honorarium_controle" + digimv_dataset.VORIG),
        ):
            for veld in HONORARIUM_VELDEN:
                opdracht_velden.pop(OPDRACHT_JAARVELDEN[veld], None)
            vorig = {}
            _meld_onwaarschijnlijk(
                db, rij, "", boekjaar, bekend.get(organisatie_id, {}), lopend_filter
            )
            onwaarschijnlijk += 1
        elif not _honoraria_plausibel(rij, "", organisatie_id, boekjaar, bekend):
            for veld in HONORARIUM_VELDEN:
                opdracht_velden.pop(OPDRACHT_JAARVELDEN[veld], None)
            _meld_onwaarschijnlijk(
                db, rij, "", boekjaar, bekend.get(organisatie_id, {}), lopend_filter
            )
            onwaarschijnlijk += 1
        if opdracht_velden:
            db.bijwerken("opdrachten", lopend_filter, opdracht_velden)
            opdracht_verzoeken += 1
            if opdracht_velden.get("honorarium_controle_eur") is not None:
                bekend.setdefault(organisatie_id, {})[boekjaar] = float(
                    opdracht_velden["honorarium_controle_eur"]
                )

        if vorig and not _honoraria_plausibel(
            rij, digimv_dataset.VORIG, organisatie_id, boekjaar - 1, bekend
        ):
            _meld_onwaarschijnlijk(
                db, rij, digimv_dataset.VORIG, boekjaar - 1,
                bekend.get(organisatie_id, {}), vorig_filter,
            )
            onwaarschijnlijk += 1
            vorig = {}
        if vorig:
            db.bijwerken("opdrachten", vorig_filter, vorig)
            vorig_verzoeken += 1
            if "honorarium_controle_eur" in vorig:
                bekend.setdefault(organisatie_id, {}).setdefault(
                    boekjaar - 1, float(vorig["honorarium_controle_eur"])
                )

        if (org_bijgewerkt + overgeslagen) % 200 == 0:
            print(
                f"  {org_bijgewerkt} organisaties bijgewerkt, {opdracht_verzoeken} "
                f"verzoeken op controles, {overgeslagen} niet in de database",
                flush=True,
            )

    print(
        # Verzoeken, geen rijen: een verzoek waarvan het filter niets raakt
        # (geen controle in dat jaar, of er staat al een honorarium) telt hier
        # wel mee. Wat er werkelijk is veranderd, zie je in de database.
        f"\n=== {org_bijgewerkt} organisaties bijgewerkt, "
        f"{opdracht_verzoeken} verzoeken op controles van {boekjaar}, "
        f"{vorig_verzoeken} met een vergelijkend cijfer voor {boekjaar - 1}, "
        f"{onwaarschijnlijk} onwaarschijnlijke bedragen, "
        f"{overgeslagen} organisaties staan niet in de database ==="
    )
    return 0


def _honoraria_plausibel(
    rij: dict, achtervoegsel: str, organisatie_id: int, boekjaar: int, bekend: dict
) -> bool:
    """De check op het controlehonorarium van één rij, voor het lopende jaar
    (achtervoegsel "") of het vergelijkende cijfer (`_vorig`). Zonder
    controlehonorarium valt er niets te vergelijken en gaat de rij door."""
    ruw = _waarde(rij, "honorarium_controle" + achtervoegsel)
    if ruw is None:
        return True
    try:
        bedrag = float(ruw)
    except ValueError:
        return False
    return plausibel(bedrag, bekend.get(organisatie_id, {}), boekjaar)


def _meld_onwaarschijnlijk(
    db, rij: dict, achtervoegsel: str, boekjaar: int, andere_jaren: dict, doel: str
) -> None:
    """Eén review-geval per organisatie-boekjaar, en alleen als er iets te
    schrijven zou zijn geweest.

    Geen geval als het filter `doel` niets zou raken (geen controle in dat jaar,
    of er staat al een honorarium): dan is er niets na te kijken. En de check op
    een bestaand geval kijkt naar élke status, niet alleen 'open' — anders kwam
    een afgehandeld geval bij de volgende run gewoon terug.

    Een mislukte invoeging laat de jaargang niet vallen: het bedrag wordt hoe
    dan ook niet geschreven, en dat is wat telt.
    """
    try:
        if not db.bestaat("opdrachten", doel):
            return
        if db.bestaat(
            "review_queue",
            "soort=eq.plausibiliteit"
            f"&payload->>kvk_nummer=eq.{rij['kvk_nummer']}"
            f"&payload->>boekjaar=eq.{boekjaar}",
        ):
            return
    except SupabaseFout as fout:
        print(f"  review-check mislukt ({fout}); geval overgeslagen", flush=True)
        return
    print(
        f"  onwaarschijnlijk honorarium: kvk {rij['kvk_nummer']}, boekjaar {boekjaar}",
        flush=True,
    )
    try:
        _review_invoegen(db, rij, achtervoegsel, boekjaar, andere_jaren)
    except SupabaseFout as fout:
        print(f"  review-geval niet opgeslagen: {fout}", flush=True)


def _review_invoegen(
    db, rij: dict, achtervoegsel: str, boekjaar: int, andere_jaren: dict
) -> None:
    db.invoegen(
        "review_queue",
        {
            "soort": "plausibiliteit",
            "payload": {
                # Geen naam: de dataset bevat ook eenmanszaken op naam van een
                # persoon, en het KvK-nummer identificeert de organisatie al.
                "bron": "digimv_dataset",
                "kvk_nummer": rij["kvk_nummer"],
                "boekjaar": boekjaar,
                "honoraria": {
                    veld: _waarde(rij, veld + achtervoegsel)
                    for veld in HONORARIUM_VELDEN
                },
                "andere_jaren": {str(j): b for j, b in sorted(andere_jaren.items())},
                "reden": f"wijkt meer dan factor {MAXIMALE_FACTOR} af van een ander jaar",
            },
        },
    )


if __name__ == "__main__":
    raise SystemExit(main())
