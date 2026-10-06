"""Test: de pensioenfondsen-seed en de vertaalregels van de lader.

De seed is handwerk (elke URL met de hand geverifieerd op HTTP 200 +
application/pdf voordat hij erin ging) en de lader vertrouwt daarop. Deze test
bewaakt de vorm — zonder netwerk, want een test die het internet nodig heeft
bewaakt vooral het internet.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent / "adapters"))
sys.path.insert(0, str(Path(__file__).resolve().parent / "extractie"))

import laad_pensioenfondsen as lp  # noqa: E402

goed = 0
fout = 0


def check(omschrijving: str, voorwaarde: bool) -> None:
    global goed, fout
    if voorwaarde:
        goed += 1
    else:
        fout += 1
        print(f"  FOUT: {omschrijving}")


rijen = lp.fondsen()
check("de seed heeft rijen", len(rijen) >= 20)
check(
    "elke rij heeft fonds, boekjaar en url",
    all(r["fonds"].strip() and r["boekjaar"].strip() and r["url"].strip() for r in rijen),
)
check(
    "elk boekjaar is een jaartal in een geloofwaardig bereik",
    all(2010 <= int(r["boekjaar"]) <= 2030 for r in rijen),
)
check(
    "elke url is https en eindigt herkenbaar op pdf",
    all(
        r["url"].startswith("https://") and ".pdf" in r["url"].rsplit("/", 1)[1].lower()
        for r in rijen
    ),
)
check(
    "fonds+boekjaar is uniek (één jaarverslag per fonds per jaar)",
    len({(r["fonds"], r["boekjaar"]) for r in rijen}) == len(rijen),
)
check(
    "fondsnamen zijn statutair (bevatten Stichting — SNPS heeft hem achteraan)",
    all("Stichting" in r["fonds"] for r in rijen),
)

# De vertaalregels: leeg is null en nooit een lege tekst, en zonder vastgesteld
# opdrachttype wordt het controle_onbepaald — geen aanname "wettelijke_controle".
analyse = {
    "opdrachttype": None,
    "oordeel": None,
    "grond_beperking": None,
    "continuiteitsonzekerheid": False,
    "tekenend_accountant": None,
}
rij = lp.opdracht_uit_analyse(analyse, 1, 2, 2024, 3)
check("zonder opdrachttype wordt het controle_onbepaald", rij["type_opdracht"] == "controle_onbepaald")
check("leeg oordeel wordt null", rij["oordeel"] is None)
check("lege tekenaar wordt null", rij["tekenend_accountant"] is None)

analyse2 = {
    "opdrachttype": "wettelijke_controle",
    "oordeel": "goedkeurend",
    "grond_beperking": None,
    "continuiteitsonzekerheid": True,
    "tekenend_accountant": "J. Jansen RA",
}
rij2 = lp.opdracht_uit_analyse(analyse2, 1, 2, 2024, 3)
check("gevulde analyse komt één op één door", rij2["type_opdracht"] == "wettelijke_controle" and rij2["oordeel"] == "goedkeurend" and rij2["continuiteitsonzekerheid"] is True and rij2["tekenend_accountant"] == "J. Jansen RA")
check("de sleutelvelden staan erin", {"organisatie_id", "kantoor_id", "boekjaar", "bron_id"} <= set(rij2))

# De onderwijs-seed rijdt op dezelfde lader (--seed/--sector) en mag "naam" als
# kolomkop gebruiken; verder gelden dezelfde vormeisen als hierboven.
onderwijs = lp.fondsen(Path(__file__).resolve().parent / "seed" / "onderwijsinstellingen.csv")
check("de onderwijs-seed heeft rijen", len(onderwijs) >= 10)
check(
    "elke onderwijsrij heeft naam, boekjaar en https-pdf-url",
    all(
        (r.get("naam") or "").strip()
        and 2010 <= int(r["boekjaar"]) <= 2030
        and r["url"].startswith("https://")
        and (
            ".pdf" in r["url"].rsplit("/", 1)[1].lower()
            # Twee sites serveren de jaarverslag-pdf's vanaf adressen zonder
            # .pdf erin: Fontys vanaf .htm-adressen, De Haagse vanaf
            # extensieloze /media/-adressen. Content-type application/pdf per
            # URL gemeten op 1-9-2026 — de bestandsnaam liegt daar, de server
            # niet. De regel blijft voor al het andere: geen HTML in de seed.
            or r["url"].startswith("https://www.fontys.nl/")
            or r["url"].startswith("https://www.dehaagsehogeschool.nl/media/")
        )
        for r in onderwijs
    ),
)
check(
    "naam+boekjaar is uniek in de onderwijs-seed",
    len({(r["naam"], r["boekjaar"]) for r in onderwijs}) == len(onderwijs),
)

# --- wat er vóór de download afvalt -------------------------------------------
#
# Eén jaarverslag ophalen en lezen kost een halve minuut, met OCR bij een
# mengvorm een paar minuten, en de twee seeds tellen samen bijna driehonderd
# regels. De controle "staat dit boekjaar er al?" stond ná het lezen, dus een
# herhaling kostte net zoveel als de eerste keer. Sinds 22-9-2026 valt dat er
# één stap eerder uit — maar alleen waar het net zo zeker is.
VOORBEELD = {
    lp.normaliseer("Stichting Pensioenfonds Voorbeeld"): [{"id": 7}],
    lp.normaliseer("Stichting Pensioenfonds Marktonderzoek"): [{"id": 8}],
    # Twee organisaties met dezelfde naamsleutel: de lader hoort dat te melden.
    lp.normaliseer("Stichting Pensioenfonds Dubbel"): [{"id": 9}, {"id": 10}],
}
# Alleen gelezen controles tellen mee. Fonds 8 heeft in de database alleen een
# controle_onbepaald uit het marktonderzoek en staat hier dus niet in: dat is
# juist een reden om het verslag te lezen, want daar komt het opdrachttype, het
# oordeel en de ondertekenaar bij.
GELEZEN = {(7, 2024), (9, 2024), (10, 2024)}

regels = [
    {"fonds": "Stichting Pensioenfonds Voorbeeld", "boekjaar": "2024"},
    {"fonds": "Stichting Pensioenfonds Voorbeeld", "boekjaar": "2025"},
    {"fonds": "Stichting Pensioenfonds Marktonderzoek", "boekjaar": "2024"},
    {"fonds": "Stichting Pensioenfonds Dubbel", "boekjaar": "2024"},
    {"naam": "Hogeschool Onbekend", "boekjaar": "2024"},
]
over = {
    (r.get("fonds") or r.get("naam"), r["boekjaar"])
    for r in lp.nog_te_lezen(regels, VOORBEELD, GELEZEN)
}
check(
    "een boekjaar waarvan de verklaring al gelezen is wordt niet opgehaald",
    ("Stichting Pensioenfonds Voorbeeld", "2024") not in over,
)
check(
    "een ander boekjaar van hetzelfde fonds blijft staan",
    ("Stichting Pensioenfonds Voorbeeld", "2025") in over,
)
check(
    "een rij die alleen uit het marktonderzoek komt (controle_onbepaald) wordt "
    "wél gelezen; daar valt nog opdrachttype, oordeel en tekenaar bij te halen",
    ("Stichting Pensioenfonds Marktonderzoek", "2024") in over,
)
check(
    "bij twee organisaties met dezelfde naamsleutel wordt er niets overgeslagen; "
    "die melding hoort iemand te zien",
    ("Stichting Pensioenfonds Dubbel", "2024") in over,
)
check(
    "een organisatie die de database niet kent blijft staan",
    ("Hogeschool Onbekend", "2024") in over,
)
check(
    "zonder database valt er niets af: de eerste run leest alles",
    len(lp.nog_te_lezen(regels, {}, set())) == len(regels),
)

print(f"{goed}/{goed + fout} goed")
sys.exit(1 if fout else 0)
