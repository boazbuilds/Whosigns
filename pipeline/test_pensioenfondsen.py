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

print(f"{goed}/{goed + fout} goed")
sys.exit(1 if fout else 0)
