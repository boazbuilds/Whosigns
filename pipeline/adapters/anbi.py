"""ANBI-bestand van de Belastingdienst — de complete populatielijst stichtingen/NGO's.

Echte open data: één zip met XML, wekelijks bijgewerkt, vrij herbruikbaar zonder
bronvermeldingsplicht (Belastingdienst, "Open data ANBI").

    https://download.belastingdienst.nl/data/anbi/anbi.zip

Gemeten op de versie van 24-7-2026 (2,5 MB zip, 18 MB XML):

| | Aantal |
|---|---|
| `beschikking`-elementen | 54.824 |
| — met een intrekkingsdatum (niet meer ANBI) | 9.265 |
| — **actief** | **45.559** |
| actief én met een websiteveld | 45.554 |
| actieve culturele ANBI | 8.199 |

Velden per beschikking: `fiscaalNummer` (RSIN, 9 cijfers, soms zonder voorloopnullen),
`dossierNummer`, `naam`, `aliasNaam`, `vestigingsPlaats`, `webSite`, `ingangsDatum`,
`intrekkingsDatum`, plus de cultuur-varianten (`ingangsDatumCultuur` e.a.).

Wat het bestand **niet** heeft: geen KvK-nummer (wel RSIN — dat is de brug naar het
CBF-register, dat beide heeft), geen financiële cijfers, geen accountant. De eerste
vijf beschikkingen zijn groepsbeschikkingen zonder RSIN ("Staat der Nederlanden",
"Gemeente", …) en horen niet in de organisatietabel.

Waar dit bestand voor dient:
1. **Populatielijst en sectorafbakening** — 45.559 actieve ANBI's is de bovengrens
   van de sector; het CBF-register (714) is daarvan de erkende, controleplichtige kern.
2. **Websiteveld** — de publicatieplicht dwingt elke ANBI om gegevens op internet te
   zetten, dus we hebben van bijna alle organisaties een vindplaats. Let op: die
   eigen-site-route is gemeten en tegenvallend (1 kantoor uit 12 sites, zie
   `docs/bronverkenning-stichtingen.md` §Route 2) — het veld is nuttig als vangnet,
   niet als hoofdroute.
3. **Mutatiesignaal** — een ingetrokken ANBI-status is publieke informatie over een
   organisatie in de problemen; wekelijkse snapshots maken dat zichtbaar als diff.

Geen dependencies buiten de standaardbibliotheek.
"""

import io
import urllib.request
import xml.etree.ElementTree as ET
import zipfile

BESTAND_URL = "https://download.belastingdienst.nl/data/anbi/anbi.zip"
USER_AGENT = "WhoSigns/0.1 (open-data-import; contact via repo)"

VELDEN = (
    "fiscaalNummer",
    "dossierNummer",
    "naam",
    "aliasNaam",
    "vestigingsPlaats",
    "webSite",
    "ingangsDatum",
    "intrekkingsDatum",
)


def download_xml(url: str = BESTAND_URL) -> bytes:
    verzoek = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(verzoek, timeout=120) as antwoord:
        zip_bytes = antwoord.read()
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as archief:
        return archief.read("anbi.xml")


def lees(xml_bytes: bytes, alleen_actief: bool = True) -> list[dict]:
    """Beschikkingen als lijst dicts; `rsin` is genormaliseerd op 9 cijfers.

    Groepsbeschikkingen zonder RSIN worden overgeslagen: dat zijn categorieën
    ("alle gemeenten van NL"), geen organisaties.
    """
    wortel = ET.fromstring(xml_bytes)
    rijen = []
    for beschikking in wortel.findall("beschikking"):
        rij = {veld: (beschikking.findtext(veld) or "").strip() for veld in VELDEN}
        if not rij["fiscaalNummer"]:
            continue
        if alleen_actief and rij["intrekkingsDatum"]:
            continue
        rij["rsin"] = rij["fiscaalNummer"].zfill(9)
        rijen.append(rij)
    return rijen


def index_op_rsin(rijen: list[dict]) -> dict[str, dict]:
    """RSIN -> beschikking. RSIN is de sleutel die het CBF-register ook heeft."""
    return {rij["rsin"]: rij for rij in rijen}
