"""Kantoornaam uit de tekst van een accountantsverklaring halen.

Deterministisch, zonder LLM: we zoeken namen uit een lijst op in de tekst in plaats
van een naam te "raden". Die lijst bestaat uit twee delen:

- `seed/kantoren.csv` — de ~233 Wta-vergunninghouders uit het AFM-register. Bij een
  **wettelijke** controle kan het kantoor niets anders zijn dan een van deze.
- `seed/kantoren_overig.csv` — kantoren **zonder** Wta-vergunning die wél
  controleverklaringen tekenen. Dat mag: zonder wettelijke controleplicht is er geen
  vergunning nodig. In de goededoelensector doet bijna een derde van de verklaringen
  dat (zie `docs/bronverkenning-stichtingen.md`). Zonder dit tweede deel mist
  WhoSigns die opdrachten volledig.

Elk kantoor in de index heeft daarom `wta_vergunning`: True/False. De aanroeper
gebruikt dat om het opdrachttype te bepalen — een vrijwillige controle is een ander
product dan een wettelijke en mag niet in dezelfde marktaandelen belanden.

Werkwijze:
1. Normaliseer tekst en kantoornamen (kleine letters, leestekens weg, spaties samen).
2. Bouw per kantoor zoeksleutels: de volledige naam en de kernnaam zonder rechtsvorm
   ("Deloitte Accountants B.V." -> "deloitte accountants").
3. Zoek alle sleutels als héle woorden in de tekst; de langste match wint (zo
   verslaat "van ree accountants" een losse match op "accountants").

Geen match, of een match die te kort/te generiek is -> None, zodat de aanroeper het
geval in de review_queue kan zetten. Nooit stil gokken.

Guardrail: deze module raakt alleen kantoorNAMEN. Namen van tekenende accountants
(natuurlijke personen) worden niet gezocht, niet geretourneerd en niet gelogd.
"""

import csv
import re
import unicodedata
from pathlib import Path

SEED_PAD = Path(__file__).resolve().parents[1] / "seed" / "kantoren.csv"
OVERIG_PAD = Path(__file__).resolve().parents[1] / "seed" / "kantoren_overig.csv"
ALIAS_PAD = Path(__file__).resolve().parents[1] / "seed" / "kantoor_alias.csv"

# Rechtsvormen en ruis die we van namen afhalen om de kernnaam te krijgen.
RECHTSVORM_SUFFIX = re.compile(
    r"\s+("
    r"b\s?v|n\s?v|v\s?o\s?f|c\s?v|maatschap|cooperatie|"
    r"besloten vennootschap|naamloze vennootschap|vennootschap onder firma"
    r")\b.*$"
)

# Kernnamen die zo generiek zijn dat ze zonder context niets bewijzen.
TE_GENERIEK = {
    "accountants", "audit", "auditors", "accountancy", "accountant",
    "assurance", "administratiekantoor", "accountants adviseurs",
    "accountants en adviseurs", "registeraccountants", "audit assurance",
}

# Minimale lengte van een match; korter is bijna altijd toeval.
MIN_SLEUTELLENGTE = 6


def normaliseer(tekst: str) -> str:
    """Kleine letters, accenten en leestekens weg, spaties samengevoegd."""
    tekst = unicodedata.normalize("NFKD", tekst)
    tekst = "".join(c for c in tekst if not unicodedata.combining(c))
    tekst = tekst.lower()
    tekst = re.sub(r"[^a-z0-9]+", " ", tekst)
    return re.sub(r"\s+", " ", tekst).strip()


def kernnaam(naam: str) -> str:
    """'Deloitte Accountants B.V.' -> 'deloitte accountants'."""
    genormaliseerd = normaliseer(naam)
    return RECHTSVORM_SUFFIX.sub("", genormaliseerd).strip()


def laad_kantoren(pad: Path = SEED_PAD) -> list[dict]:
    """De AFM-vergunninghouders. `sleutel` = AFM-nummer, `wta_vergunning` = True."""
    with pad.open(encoding="utf-8") as f:
        kantoren = list(csv.DictReader(f))
    for kantoor in kantoren:
        kantoor["sleutel"] = kantoor["afm_nummer"]
        kantoor["wta_vergunning"] = True
    return kantoren


def laad_overige_kantoren(pad: Path = OVERIG_PAD) -> list[dict]:
    """Kantoren zónder Wta-vergunning die controleverklaringen tekenen.

    Bijgehouden met bewijs: elke rij noemt bij welke organisatie en welk boekjaar de
    naam is aangetroffen (`gevonden_bij`). Opgebouwd met
    `verken_stichtingen.py oogst`, altijd met de hand nagekeken — een naam die uit
    een pdf komt rollen is een kandidaat, geen kantoor.
    """
    if not pad.exists():
        return []
    with pad.open(encoding="utf-8") as f:
        kantoren = list(csv.DictReader(f))
    for kantoor in kantoren:
        kantoor["afm_nummer"] = None
        kantoor["wta_vergunning"] = False
        kantoor.setdefault("oob_vergunning", "nee")
    return kantoren


def laad_aliassen(pad: Path = ALIAS_PAD) -> list[dict]:
    """Handelsnamen en oude namen (fusies, rebranding) -> AFM-nummer."""
    if not pad.exists():
        return []
    with pad.open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _rangschik(kantoor: dict) -> tuple:
    """Sorteervoorkeur bij een botsende zoeksleutel: vergunninghouder eerst."""
    return (not kantoor["wta_vergunning"], kantoor.get("sleutel") or "zzz")


def _alias_varianten(kantoor: dict) -> list[str]:
    """Schrijfwijzen uit de kolom `alias` (puntkomma's ertussen), indien aanwezig."""
    return [deel.strip() for deel in (kantoor.get("alias") or "").split(";") if deel.strip()]


def bouw_index(
    kantoren: list[dict],
    aliassen: list[dict] | None = None,
    overige: list[dict] | None = None,
) -> dict[str, dict]:
    """Zoeksleutel -> kantoor. Langere sleutels winnen bij het matchen.

    `overige` zijn de kantoren zonder Wta-vergunning; laat het weg om alleen op het
    AFM-register te matchen (bijvoorbeeld bij een bron waar per definitie een
    wettelijke controle ligt). `None` betekent: lees `seed/kantoren_overig.csv`.
    """
    index: dict[str, dict] = {}

    def voeg_toe(sleutel: str, kantoor: dict) -> None:
        if len(sleutel) < MIN_SLEUTELLENGTE or sleutel in TE_GENERIEK:
            return
        # Bij een botsing wint de vergunninghouder, en daarbinnen het laagste
        # AFM-nummer (oudste vergunning). Botsingen zijn zeldzaam en horen in de
        # review-queue thuis; een kantoor zonder vergunning mag er nooit een mét
        # vergunning verdringen.
        bestaand = index.get(sleutel)
        if bestaand is None or _rangschik(kantoor) < _rangschik(bestaand):
            index[sleutel] = kantoor

    alle = list(kantoren) + (
        laad_overige_kantoren() if overige is None else list(overige)
    )
    for kantoor in alle:
        namen = {kantoor["naam"], *_alias_varianten(kantoor)}
        for naam in namen:
            for sleutel in {normaliseer(naam), kernnaam(naam)}:
                voeg_toe(sleutel, kantoor)

    op_nummer = {k["afm_nummer"]: k for k in kantoren}
    for rij in laad_aliassen() if aliassen is None else aliassen:
        kantoor = op_nummer.get(rij["afm_nummer"])
        if kantoor is None:
            raise ValueError(
                f"alias '{rij['alias']}' verwijst naar onbekend AFM-nummer "
                f"{rij['afm_nummer']}"
            )
        voeg_toe(normaliseer(rij["alias"]), kantoor)

    return index


def _tel_hele_woorden(sleutel: str, tekst: str) -> int:
    """Hoe vaak staat de sleutel als hele woorden in de tekst?

    Waarom niet gewoon `sleutel in tekst`: de sleutel van 'Audit Pro B.V.' is
    'audit pro' en dat zit letterlijk in 'audit procedures' — de standaardzin in
    elk Engelstalig accountantsrapport. Zo tekende Audit Pro B.V. in de meting
    van 29-7-2026 drie Engelstalige jaarverslagen van goede doelen die het
    kantoor nooit heeft gezien; 'accura' (Accura B.V.) deed hetzelfde in
    'accuraat'. Vier valse matches op negentien in één steekproef van veertig.
    Een gemiste match kost een rij in de review-queue, een valse match zet een
    verzonnen relatie in de database — dus hier telt alleen een hele-woord-match.
    """
    return len(re.findall(rf"(?<![a-z0-9]){re.escape(sleutel)}(?![a-z0-9])", tekst))


def zoek_kantoor(tekst: str, index: dict[str, dict]) -> dict | None:
    """Geeft {'kantoor': ..., 'sleutel': ..., 'aantal': n} of None."""
    genormaliseerd = normaliseer(tekst)
    if not genormaliseerd:
        return None
    treffers = [
        (sleutel, kantoor, aantal)
        for sleutel, kantoor in index.items()
        # De substringtest is alleen een goedkope voorselectie; de telling met
        # woordgrenzen hieronder bepaalt of het echt een treffer is.
        if sleutel in genormaliseerd
        and (aantal := _tel_hele_woorden(sleutel, genormaliseerd))
    ]
    if not treffers:
        return None
    # Langste sleutel wint; bij gelijke lengte het vaakst voorkomende.
    sleutel, kantoor, aantal = max(treffers, key=lambda t: (len(t[0]), t[2]))
    return {"kantoor": kantoor, "sleutel": sleutel, "aantal": aantal}
