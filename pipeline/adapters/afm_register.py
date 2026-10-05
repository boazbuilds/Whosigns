"""AFM-vergunningenregister accountantsorganisaties -> seed-CSV.

Bron: https://www.afm.nl/nl-nl/sector/registers/vergunningenregisters/accountantsorganisaties
De registerpagina biedt een officiele XML-export; dit script downloadt die en schrijft
pipeline/seed/kantoren.csv, deterministisch gesorteerd op vergunningnummer.

Wekelijkse snapshot: dit script opnieuw draaien en het resultaat committen. De
git-historie is daarmee het mutatielog: een kantoor dat uit het register verdwijnt of
erbij komt is zichtbaar als diff, en voedt later het signaal
'kantoor_vergunning_beeindigd' (ROADMAP Fase 4).

Een snapshot is meer dan een nieuwe kantoren.csv. Vergeleken met de vorige:
- hernoemd (zelfde nummer, andere naam): de oude naam gaat als alias in
  kantoor_alias.csv, want verklaringen van vóór de naamswijziging dragen hem nog;
- verdwenen: het kantoor gaat naar kantoren_vervallen.csv en blijft onder zijn
  eigen nummer vindbaar — nooit automatisch aan een opvolger gekoppeld;
- veel minder vermeldingen dan vorige week: dan weigert het script, want een
  afgekapte export zou anders als massale intrekking binnenkomen.

Veldbetekenis (gecontroleerd tegen de export van 28-7-2026, 233 vermeldingen):
- <vergunningnummer>      AFM-vergunningnummer -> kantoren.afm_nummer (sleutel)
- <wettelijkecontrole>    Ja/Nee = vergunning voor wettelijke controles bij OOB's
                          (28-7-2026 exact 6x Ja: BDO, Deloitte, EY, Forvis Mazars,
                          KPMG, PwC)
- <status>                'Verleend' voor alle vermeldingen
- <begindatum>            vergunning sinds, notatie M/D/YYYY h:mm:ss AM/PM

Guardrail: het register bevat uitsluitend organisatienamen, geen natuurlijke personen.

Geen dependencies buiten de standaardbibliotheek. Draaien vanuit de repo-root:
    python3 pipeline/adapters/afm_register.py

TODO (zodra het Supabase-project bestaat): naast de CSV ook upserten naar de tabel
`kantoren` (sleutel afm_nummer) met een bron-rij (bron_type 'afm_register').
"""

import csv
import sys
import urllib.request
import xml.etree.ElementTree as ET
from datetime import date, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "extractie"))

from kantoor_match import (  # noqa: E402
    ALIAS_PAD,
    MIN_SLEUTELLENGTE,
    TE_GENERIEK,
    VERVALLEN_PAD,
    bouw_index,
    kernnaam,
    laad_aliassen,
    laad_vervallen_kantoren,
    normaliseer,
)

EXPORT_URL = (
    "https://www.afm.nl/export.aspx"
    "?type=b5d6c574-90de-4e1c-a997-5d84e5086c6b&format=xml"
)
SEED_PAD = Path(__file__).resolve().parents[1] / "seed" / "kantoren.csv"

# Ondergrens voor een nieuwe export. Het register telde 233 vermeldingen op
# 28-7-2026 en bleef daarna tussen 233 en 235; de grootste weekmutatie tot
# 28-9-2026 was twee vermeldingen eraf. Een export die ineens een tiende korter
# is, is vrijwel zeker afgekapt of half geladen — en zou zonder deze grens als
# tientallen ingetrokken vergunningen binnenkomen, met inactieve kantoren op de
# site tot gevolg.
MINIMUM_VERMELDINGEN = 200
MINIMUM_AANDEEL = 0.9


def parse_datum(waarde: str) -> str:
    """'9/29/2008 2:00:00 AM' -> '2008-09-29'; leeg blijft leeg."""
    waarde = (waarde or "").strip()
    if not waarde:
        return ""
    return datetime.strptime(waarde.split()[0], "%m/%d/%Y").date().isoformat()


def haal_register_op(url: str = EXPORT_URL) -> bytes:
    # De AFM-site weigert requests zonder browserachtige User-Agent (403).
    verzoek = urllib.request.Request(
        url, headers={"User-Agent": "Mozilla/5.0 (WhoSigns-pipeline)"}
    )
    with urllib.request.urlopen(verzoek, timeout=60) as antwoord:
        return antwoord.read()


def parse_register(xml_bytes: bytes) -> list[dict]:
    root = ET.fromstring(xml_bytes)
    kantoren = []
    for v in root.findall("vermelding"):
        veld = lambda naam: (v.findtext(naam) or "").strip()
        kantoren.append(
            {
                "afm_nummer": veld("vergunningnummer"),
                "naam": veld("naam"),
                "rechtsvorm": veld("rechtsvorm"),
                "plaats": veld("statutairwoonplaats"),
                "oob_vergunning": "ja" if veld("wettelijkecontrole") == "Ja" else "nee",
                "vergunning_sinds": parse_datum(veld("begindatum")),
                "website": veld("websiteadresextern"),
                "status": veld("status"),
            }
        )
    kantoren.sort(key=lambda k: int(k["afm_nummer"]))
    return kantoren


# Wie een OOB-vergunning heeft, en waarom dat een lijst met de hand is.
#
# Een vergunning voor wettelijke controles bij organisaties van openbaar belang
# is zeldzaam en zwaar: jarenlang precies zes kantoren. Komt er een bij, dan is
# dat nieuws — of een fout in de bron. Allebei wil je zien; geen van beide mag
# er ongemerkt in glijden, want deze vlag bepaalt op de site wie er bij de
# grootste opdrachten mag tekenen.
#
# De weekelijkse snapshot draait vanzelf en commit vanzelf. Zonder deze lijst is
# er niets dat de verandering tegenhoudt of zelfs maar opmerkt.
OOB_VERWACHT = {
    "13000015": "Deloitte Accountants B.V.",
    "13000121": "KPMG Accountants N.V.",
    "13000291": "PricewaterhouseCoopers Accountants N.V.",
    "13000311": "BDO Audit & Assurance B.V.",
    "13000408": "Forvis Mazars Accountants N.V.",
    "13020186": "EY Accountants B.V.",
}

# Vermeldingen die de bron als OOB opgeeft en die we gezien én beoordeeld hebben.
# Een regel hier is een bewuste handtekening, geen manier om de test stil te
# krijgen: zet erbij wat je hebt nagekeken en wanneer.
#
# Leeg sinds 5-10-2026. De enige regel die er stond was de AFM zelf (zie
# GEEN_ACCOUNTANTSORGANISATIE hieronder), en die had de AFM toen al vijf weken
# uit haar eigen export gehaald. Laten staan zou betekenen dat dezelfde fout
# ongezien terug kan komen — precies wat deze lijst moet voorkomen.
OOB_AFWIJKINGEN: dict[str, str] = {}

# Vermeldingen die wel in de export hebben gestaan maar nooit een
# accountantsorganisatie waren. Verdwijnen ze, dan gaan ze níet naar
# kantoren_vervallen.csv: daar staan kantoren die destijds bevoegd tekenden en
# daarom in oude verklaringen vindbaar moeten blijven. Een kantoornaam die nooit
# een kantoor was hoort nergens vindbaar te zijn. De lader zet de databaserij op
# inactief, net als bij elk ander nummer dat uit het register verdwijnt.
GEEN_ACCOUNTANTSORGANISATIE = {
    "13020232": (
        "Stichting Autoriteit Financiële Markten, in de export van 15-8 tot "
        "31-8-2026 met wettelijkecontrole=Ja. De AFM verléént deze vergunningen en "
        "is zelf geen accountantsorganisatie; elders in deze pipeline staat ze dan "
        "ook als 'geen accountantskantoor' (resultaat_gunningen.csv). Nagekeken op "
        "17-8-2026 tegen de officiële XML-export, die het toen echt zei. In de "
        "snapshot van 31-8-2026 was de vermelding weg, maar de database hield haar "
        "actief en met OOB-vlag: de lader kende alleen toevoegen. Zo stond ze nog "
        "als zevende OOB-kantoor op de site tot migratie 20261005120000."
    ),
}


class ExportOnvolledig(RuntimeError):
    """De nieuwe export is te kort om te vertrouwen; de oude seed blijft staan."""


def export_lijkt_compleet(nieuw: int, vorig: int) -> bool:
    """Is een lijst van `nieuw` vermeldingen geloofwaardig na `vorig`?

    Zelfde grens voor de seed (hier) en voor de database (laad_kantoren.py):
    wat er ook afgekapt raakt, het mag nooit als massale intrekking landen.
    """
    return nieuw >= MINIMUM_VERMELDINGEN and nieuw >= MINIMUM_AANDEEL * vorig


def lees_seed(pad: Path = SEED_PAD) -> list[dict]:
    if not pad.exists():
        return []
    with pad.open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def vergelijk(oud: list[dict], nieuw: list[dict]) -> dict[str, list]:
    """Wat er tussen twee snapshots veranderde, per vergunningnummer.

    `hernoemd` is een lijst (oud, nieuw)-paren met hetzelfde nummer en een andere
    naam. Een nummer dat verdwijnt en een nieuw nummer met een gelijkende naam zijn
    twee losse mutaties, en dat is opzet: een nieuw vergunningnummer is een nieuwe
    vergunninghouder (13000055 -> 13020234 op 28-9-2026, de maatschap Steens &
    Partners en een B.V. met een vergunning van zes dagen oud).
    """
    oud_per = {k["afm_nummer"]: k for k in oud}
    nieuw_per = {k["afm_nummer"]: k for k in nieuw}
    gedeeld = sorted(oud_per.keys() & nieuw_per.keys(), key=int)
    return {
        "hernoemd": [
            (oud_per[n], nieuw_per[n])
            for n in gedeeld
            if oud_per[n]["naam"] != nieuw_per[n]["naam"]
        ],
        "verdwenen": [oud_per[n] for n in sorted(oud_per.keys() - nieuw_per.keys(), key=int)],
        "erbij": [nieuw_per[n] for n in sorted(nieuw_per.keys() - oud_per.keys(), key=int)],
    }


def _datum_nl(dag: date) -> str:
    return f"{dag.day}-{dag.month}-{dag.year}"


def alias_rijen(
    hernoemd: list[tuple[dict, dict]], index: dict[str, dict], dag: date
) -> tuple[list[dict], list[str]]:
    """De oude registernaam als alias, voor elk hernoemd kantoor.

    Waarom automatisch: hetzelfde vergunningnummer is hetzelfde kantoor, dus hier
    valt niets te gokken. Waarom het nodig is: op 28-9-2026 werd 13000483
    'Countus Accountants + Adviseurs B.V.' omgedoopt tot 'Countus Audit B.V.', en
    daarna vond een verklaring met de oude naam niets meer. Countus had toen 21
    opdrachten in de database; bij een herlading was elke verklaring onder de
    oude naam in de review-queue beland. Diezelfde snapshot deed het met Beuk,
    die van 7-9-2026 met BGH.

    Twee schrijfwijzen per oude naam, zoals de index ze ook voor de registernaam
    zelf maakt: voluit en zonder rechtsvorm. Een sleutel die al naar een ánder
    kantoor wijst wordt overgeslagen en gemeld: dan is de oude naam niet meer
    eenduidig, en liever een gat dan een gok.
    """
    rijen: list[dict] = []
    gemeld: list[str] = []
    for oud, nieuw in hernoemd:
        nummer = oud["afm_nummer"]
        toelichting = (
            f"registernaam van {nummer} tot de snapshot van {_datum_nl(dag)}, daarna "
            f"'{nieuw['naam']}'; automatisch toegevoegd: zelfde vergunningnummer, dus "
            "hetzelfde kantoor, en verklaringen van vóór de naamswijziging dragen nog "
            "de oude naam"
        )
        for tekst in (oud["naam"], kernnaam(oud["naam"])):
            sleutel = normaliseer(tekst)
            if len(sleutel) < MIN_SLEUTELLENGTE or sleutel in TE_GENERIEK:
                continue
            bestaand = index.get(sleutel)
            if bestaand is not None:
                if bestaand.get("afm_nummer") != nummer:
                    gemeld.append(
                        f"oude naam {oud['naam']!r} van {nummer} niet als alias "
                        f"opgenomen: '{sleutel}' wijst al naar {bestaand['naam']}"
                    )
                continue
            rijen.append({"alias": tekst, "afm_nummer": nummer, "toelichting": toelichting})
            index[sleutel] = nieuw
    return rijen, gemeld


VERVALLEN_VELDEN = [
    "afm_nummer", "naam", "rechtsvorm", "plaats", "vergunning_sinds", "website",
    "afwezig_sinds", "toelichting",
]


def vervallen_rijen(verdwenen: list[dict], dag: date) -> list[dict]:
    """Verdwenen vergunninghouders, zoals ze in kantoren_vervallen.csv horen."""
    return [
        {
            "afm_nummer": k["afm_nummer"],
            "naam": k["naam"],
            "rechtsvorm": k.get("rechtsvorm", ""),
            "plaats": k.get("plaats", ""),
            "vergunning_sinds": k.get("vergunning_sinds", ""),
            "website": k.get("website", ""),
            "afwezig_sinds": dag.isoformat(),
            "toelichting": (
                f"niet meer in de export van {_datum_nl(dag)}; automatisch "
                "toegevoegd. Bewust zonder koppeling aan een opvolger: een nieuw "
                "vergunningnummer is een nieuwe vergunninghouder"
            ),
        }
        for k in verdwenen
        if k["afm_nummer"] not in GEEN_ACCOUNTANTSORGANISATIE
    ]


def schrijf_vervallen(rijen: list[dict], pad: Path = VERVALLEN_PAD) -> None:
    with pad.open("w", newline="", encoding="utf-8") as f:
        schrijver = csv.DictWriter(f, fieldnames=VERVALLEN_VELDEN, lineterminator="\n")
        schrijver.writeheader()
        schrijver.writerows(
            sorted(rijen, key=lambda k: int(k["afm_nummer"]))
        )


def voeg_aliassen_toe(rijen: list[dict], pad: Path = ALIAS_PAD) -> None:
    """Achteraan toevoegen: de bestaande regels en hun volgorde blijven staan."""
    if not rijen:
        return
    inhoud = pad.read_text(encoding="utf-8") if pad.exists() else ""
    with pad.open("a", newline="", encoding="utf-8") as f:
        if not inhoud:
            f.write("alias,afm_nummer,toelichting\n")
        elif not inhoud.endswith("\n"):
            f.write("\n")
        schrijver = csv.DictWriter(
            f, fieldnames=["alias", "afm_nummer", "toelichting"], lineterminator="\n"
        )
        schrijver.writerows(rijen)


def ververs_seed(
    kantoren: list[dict],
    dag: date | None = None,
    seed_pad: Path = SEED_PAD,
    alias_pad: Path = ALIAS_PAD,
    vervallen_pad: Path = VERVALLEN_PAD,
    overige: list[dict] | None = None,
) -> dict[str, list]:
    """Schrijft de nieuwe snapshot, met wat er uit de vorige te bewaren valt.

    Geeft de mutaties terug (zie `vergelijk`) plus `aliassen` en `gemeld`.
    Gooit ExportOnvolledig zonder iets te schrijven als de export te kort is.
    `overige` gaat door naar bouw_index; `None` leest kantoren_overig.csv.
    """
    dag = dag or date.today()
    oud = lees_seed(seed_pad)
    if not export_lijkt_compleet(len(kantoren), len(oud)):
        raise ExportOnvolledig(
            f"de export telt {len(kantoren)} vermeldingen, de vorige snapshot "
            f"{len(oud)}; onder {MINIMUM_AANDEEL:.0%} daarvan (of onder "
            f"{MINIMUM_VERMELDINGEN}) is hij eerder afgekapt dan echt. De seed "
            "blijft ongewijzigd."
        )
    mutaties = vergelijk(oud, kantoren)

    # Wat er al vervallen was en weer in het register staat, is niet meer
    # vervallen; de rest blijft, en de verdwenen nummers van deze week komen erbij.
    in_register = {k["afm_nummer"] for k in kantoren}
    vervallen = [
        k for k in laad_vervallen_kantoren(vervallen_pad) if k["afm_nummer"] not in in_register
    ]
    al_vervallen = {k["afm_nummer"] for k in vervallen}
    vervallen += [
        k
        for k in vervallen_rijen(mutaties["verdwenen"], dag)
        if k["afm_nummer"] not in al_vervallen
    ]

    # De index waartegen nieuwe aliassen botsen: de nieuwe snapshot, met alles wat
    # er al naast staat (aliassen, vervallen en overige kantoren). Met dezelfde
    # vlaggen die kantoor_match bij het inlezen zet, anders kan bouw_index een
    # botsing niet beslechten.
    index = bouw_index(
        [{**k, "sleutel": k["afm_nummer"], "wta_vergunning": True} for k in kantoren],
        laad_aliassen(alias_pad),
        overige=overige,
        vervallen=[
            {**k, "sleutel": k["afm_nummer"], "wta_vergunning": False, "wta_ooit": True}
            for k in vervallen
        ],
    )
    aliassen, gemeld = alias_rijen(mutaties["hernoemd"], index, dag)

    schrijf_seed(kantoren, seed_pad)
    if vervallen or vervallen_pad.exists():
        schrijf_vervallen(
            [{veld: k.get(veld, "") for veld in VERVALLEN_VELDEN} for k in vervallen],
            vervallen_pad,
        )
    voeg_aliassen_toe(aliassen, alias_pad)
    return {**mutaties, "aliassen": aliassen, "gemeld": gemeld}


def onverwachte_oob(kantoren: list[dict]) -> list[dict]:
    """Kantoren met een OOB-vergunning die we niet kennen en niet eerder zagen.

    Leeg is goed. Staat er iets in, dan is het register veranderd op een punt
    waar dit project niet mag gokken.
    """
    bekend = set(OOB_VERWACHT) | set(OOB_AFWIJKINGEN)
    return [
        k
        for k in kantoren
        if k["oob_vergunning"] == "ja" and k["afm_nummer"] not in bekend
    ]


def verdwenen_oob(kantoren: list[dict]) -> list[str]:
    """Kantoren uit OOB_VERWACHT die niet meer in het register staan.

    Ook dat is nieuws: een ingetrokken OOB-vergunning is de zwaarste maatregel
    die de AFM kan nemen.
    """
    nu = {k["afm_nummer"] for k in kantoren if k["oob_vergunning"] == "ja"}
    return [f"{nummer} {naam}" for nummer, naam in OOB_VERWACHT.items() if nummer not in nu]


def schrijf_seed(kantoren: list[dict], pad: Path = SEED_PAD) -> None:
    pad.parent.mkdir(parents=True, exist_ok=True)
    with pad.open("w", newline="", encoding="utf-8") as f:
        schrijver = csv.DictWriter(f, fieldnames=list(kantoren[0].keys()))
        schrijver.writeheader()
        schrijver.writerows(kantoren)


def main() -> int:
    kantoren = parse_register(haal_register_op())
    try:
        mutaties = ververs_seed(kantoren)
    except ExportOnvolledig as fout:
        print(f"::error::{fout}")
        return 1
    aantal_oob = sum(1 for k in kantoren if k["oob_vergunning"] == "ja")
    print(f"{len(kantoren)} kantoren weggeschreven naar {SEED_PAD}")
    print(f"waarvan {aantal_oob} met OOB-vergunning")

    # Als annotatie en niet als gewone regel: die staat bovenaan de run-pagina.
    # Een print halverwege het log van een groene run leest niemand.
    for oud, nieuw in mutaties["hernoemd"]:
        print(f"::notice::{oud['afm_nummer']} heet nu {nieuw['naam']} (was {oud['naam']})")
    for rij in mutaties["aliassen"]:
        print(f"  oude naam als alias toegevoegd: {rij['alias']} -> {rij['afm_nummer']}")
    for melding in mutaties["gemeld"]:
        print(f"::warning::{melding}")
    for kantoor in mutaties["verdwenen"]:
        waarheen = (
            "niet naar kantoren_vervallen.csv (GEEN_ACCOUNTANTSORGANISATIE)"
            if kantoor["afm_nummer"] in GEEN_ACCOUNTANTSORGANISATIE
            else "naar kantoren_vervallen.csv"
        )
        print(
            f"::notice::{kantoor['afm_nummer']} {kantoor['naam']} staat niet meer in "
            f"het register; {waarheen}"
        )
    for kantoor in mutaties["erbij"]:
        print(f"::notice::nieuw in het register: {kantoor['afm_nummer']} {kantoor['naam']}")
    for kantoor in onverwachte_oob(kantoren):
        print(
            f"::warning::{kantoor['afm_nummer']} {kantoor['naam']} staat nieuw als OOB "
            f"in het register (sinds {kantoor['vergunning_sinds']}). Nakijken en, als "
            f"het klopt, opnemen in OOB_VERWACHT — anders in OOB_AFWIJKINGEN."
        )
    for weg in verdwenen_oob(kantoren):
        print(f"::warning::{weg} heeft geen OOB-vergunning meer in het register.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
