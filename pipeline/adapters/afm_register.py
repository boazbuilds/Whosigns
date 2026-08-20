"""AFM-vergunningenregister accountantsorganisaties -> seed-CSV.

Bron: https://www.afm.nl/nl-nl/sector/registers/vergunningenregisters/accountantsorganisaties
De registerpagina biedt een officiele XML-export; dit script downloadt die en schrijft
pipeline/seed/kantoren.csv, deterministisch gesorteerd op vergunningnummer.

Wekelijkse snapshot: dit script opnieuw draaien en het resultaat committen. De
git-historie is daarmee het mutatielog: een kantoor dat uit het register verdwijnt of
erbij komt is zichtbaar als diff, en voedt later het signaal
'kantoor_vergunning_beeindigd' (ROADMAP Fase 4).

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
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path

EXPORT_URL = (
    "https://www.afm.nl/export.aspx"
    "?type=b5d6c574-90de-4e1c-a997-5d84e5086c6b&format=xml"
)
SEED_PAD = Path(__file__).resolve().parents[1] / "seed" / "kantoren.csv"


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
OOB_AFWIJKINGEN = {
    "13020232": (
        "Stichting Autoriteit Financiële Markten, in de export sinds 15-8-2026 met "
        "wettelijkecontrole=Ja. De AFM verléént deze vergunningen en is zelf geen "
        "accountantsorganisatie; elders in deze pipeline staat ze dan ook als "
        "'geen accountantskantoor' (resultaat_gunningen.csv). Vrijwel zeker een "
        "fout in het register zelf, nagekeken op 17-8-2026 tegen de officiële "
        "XML-export — die zegt het echt, dus wij nemen het over zoals het er "
        "staat en verzinnen er niets bij. Sinds 17-8-2026 staat ze daardoor op de "
        "site als zevende OOB-kantoor, naast de Big Four, BDO en Forvis Mazars. "
        "Nog te beslissen: die vlag hier onderdrukken, of wachten tot de AFM haar "
        "eigen export corrigeert. Zolang dat openstaat is dít de vindplaats."
    ),
}


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


if __name__ == "__main__":
    kantoren = parse_register(haal_register_op())
    schrijf_seed(kantoren)
    aantal_oob = sum(1 for k in kantoren if k["oob_vergunning"] == "ja")
    print(f"{len(kantoren)} kantoren weggeschreven naar {SEED_PAD}")
    print(f"waarvan {aantal_oob} met OOB-vergunning")
    for kantoor in onverwachte_oob(kantoren):
        print(
            f"  LET OP: {kantoor['afm_nummer']} {kantoor['naam']} staat nieuw als OOB "
            f"in het register (sinds {kantoor['vergunning_sinds']}). Nakijken en, als "
            f"het klopt, opnemen in OOB_VERWACHT — anders in OOB_AFWIJKINGEN."
        )
    for weg in verdwenen_oob(kantoren):
        print(f"  LET OP: {weg} heeft geen OOB-vergunning meer in het register.")
