"""Kantoornaam uit de tekst van een accountantsverklaring halen.

Deterministisch, zonder LLM: de AFM-lijst (pipeline/seed/kantoren.csv) is een
gesloten verzameling van ~233 vergunninghouders, dus we zoeken die namen op in de
tekst in plaats van een naam te "raden".

Werkwijze:
1. Normaliseer tekst en kantoornamen (kleine letters, leestekens weg, spaties samen).
2. Bouw per kantoor zoeksleutels: de volledige naam en de kernnaam zonder rechtsvorm
   ("Deloitte Accountants B.V." -> "deloitte accountants").
3. Zoek alle sleutels in de tekst; de langste match wint (zo verslaat
   "van ree accountants" een losse match op "accountants").

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
    with pad.open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def laad_aliassen(pad: Path = ALIAS_PAD) -> list[dict]:
    """Handelsnamen en oude namen (fusies, rebranding) -> AFM-nummer."""
    if not pad.exists():
        return []
    with pad.open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def bouw_index(
    kantoren: list[dict], aliassen: list[dict] | None = None
) -> dict[str, dict]:
    """Zoeksleutel -> kantoor. Langere sleutels winnen bij het matchen."""
    index: dict[str, dict] = {}

    def voeg_toe(sleutel: str, kantoor: dict) -> None:
        if len(sleutel) < MIN_SLEUTELLENGTE or sleutel in TE_GENERIEK:
            return
        # Bij een botsing wint het kantoor met het laagste AFM-nummer (oudste
        # vergunning); botsingen zijn zeldzaam en horen in de review-queue thuis.
        bestaand = index.get(sleutel)
        if bestaand is None or kantoor["afm_nummer"] < bestaand["afm_nummer"]:
            index[sleutel] = kantoor

    for kantoor in kantoren:
        for sleutel in {normaliseer(kantoor["naam"]), kernnaam(kantoor["naam"])}:
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


def zoek_kantoor(tekst: str, index: dict[str, dict]) -> dict | None:
    """Geeft {'kantoor': ..., 'sleutel': ..., 'aantal': n} of None."""
    genormaliseerd = normaliseer(tekst)
    if not genormaliseerd:
        return None
    treffers = [
        (sleutel, kantoor, genormaliseerd.count(sleutel))
        for sleutel, kantoor in index.items()
        if sleutel in genormaliseerd
    ]
    if not treffers:
        return None
    # Langste sleutel wint; bij gelijke lengte het vaakst voorkomende.
    sleutel, kantoor, aantal = max(treffers, key=lambda t: (len(t[0]), t[2]))
    return {"kantoor": kantoor, "sleutel": sleutel, "aantal": aantal}
