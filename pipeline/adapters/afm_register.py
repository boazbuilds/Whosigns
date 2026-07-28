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
