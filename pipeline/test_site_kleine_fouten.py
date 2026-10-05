"""Test: kleine onjuistheden op de site die eerder live stonden.

Waarom dit bestaat. Elk van deze stond zo op de site, gemeten op 5-10-2026:

- 3.014 organisaties zonder KvK-nummer kregen "(KvK null)" in hun
  metabeschrijving, dus in elk zoekresultaat.
- /sectoren zei "t/m boekjaar 2026", omdat max(boekjaar) uit de opdrachten
  ook negen marktonderzoek-regels meetelt; de controles houden in 2025 op.
- /bevindingen zei hardgecodeerd "in boekjaar 2022 was 0,8%"; het is 1,0%.
- /zoeken noemde alles zonder OOB-vergunning "Wta", ook de 58 kantoren zonder
  Wta-vergunning: 55 zonder AFM-nummer en 3 die uit het register verdwenen.
  De regel daarvoor staat in test_site_vergunning.py; hier alleen dat /zoeken
  hem gebruikt.
- Vijf links naar een kantoor zonder AFM-nummer liepen op een 404 (stijgers en
  dalers op /kantoren, prijsontwikkeling op /honoraria), omdat kantoorPad() er
  geen id meekreeg en `/kantoor/-astrium-…` bouwde.
- Op een telefoon van 375 pixels werd de kantoorpagina 443 en /wisselingen 549
  pixels breed.
- 117 actieve kantoren zonder controle stonden in geen enkele lijst. De eerste
  versie van die lijst telde er 119 en zette er de AFM zelf ("Geen
  accountantsorganisatie") en VBWA tussen, die allebei uit het register
  verdwenen, onder de kop "in het register" — terwijl 19 van de 119 geen
  AFM-nummer hebben.

Tekstcontroles op de paginabron, net als test_site_aandeel.py; commentaar telt
niet mee.
"""

import re
import sys
from pathlib import Path

WEB = Path(__file__).resolve().parent.parent / "web"

goed = 0
fout = 0


def check(omschrijving: str, voorwaarde: bool) -> None:
    global goed, fout
    if voorwaarde:
        goed += 1
    else:
        fout += 1
        print(f"  FOUT: {omschrijving}")


BLOKCOMMENTAAR = re.compile(r"/\*.*?\*/", re.DOTALL)
REGELCOMMENTAAR = re.compile(r"(?m)^[ \t]*//.*$")


def plat(pad: Path) -> str:
    tekst = pad.read_text(encoding="utf-8")
    tekst = BLOKCOMMENTAAR.sub(" ", tekst)
    tekst = REGELCOMMENTAAR.sub(" ", tekst)
    return " ".join(tekst.split())


def pagina(*delen: str) -> str:
    return plat(WEB.joinpath(*delen))


# --- KvK in de metabeschrijving -----------------------------------------------------
org = pagina("app", "organisatie", "[slug]", "page.tsx")
check(
    "de metabeschrijving zet de KvK er niet blind in",
    "(KvK ${org.kvk_nummer})` +" not in org and "org.kvk_nummer ? ` (KvK ${org.kvk_nummer})` : \"\"" in org,
)

# --- t/m welk boekjaar ---------------------------------------------------------------
sectoren = pagina("app", "sectoren", "page.tsx")
check(
    "/sectoren noemt het nieuwste boekjaar mét controles, niet max(boekjaar)",
    "nieuwsteBoekjaar()" not in sectoren and "boekjarenMetControles()" in sectoren,
)

# --- /bevindingen rekent zelf ----------------------------------------------------------
bevindingen = pagina("app", "bevindingen", "page.tsx")
check(
    "/bevindingen heeft geen vast percentage meer in de tekst",
    not re.search(r"\d,\d%", bevindingen),
)
check(
    "/bevindingen haalt de percentages uit v_oordelen_per_jaar en noemt de noemer",
    "oordelenPerJaar()" in bevindingen and "bij jaarrekeningcontroles" in bevindingen,
)
check(
    "hapert die view, dan valt alleen de zin weg en niet de hele pagina",
    "oordelenPerJaar().catch(() => null)" in bevindingen,
)

# --- Wta of niet ---------------------------------------------------------------------
zoeken = pagina("app", "zoeken", "page.tsx")
check(
    "/zoeken toont het gedeelde vergunningslabel, niet langer 'Wta' bij alles zonder OOB",
    "<Vergunning kantoor={kantoor}" in zoeken and '<span className="zacht klein">Wta</span>' not in zoeken,
)
db = pagina("lib", "db.ts")
check(
    "wta_vergunning wordt bij elk kantoor opgehaald",
    re.search(r'const KANTOOR_KERN = "[^"]*\bwta_vergunning\b', db) is not None,
)

# --- kantoorPad zonder id kan niet meer -------------------------------------------------
paden = pagina("lib", "paden.ts")
check(
    "kantoorPad() eist een id, zodat de typecontrole een link zonder id weigert",
    'Pick<Kantoor, "afm_nummer" | "naam"> & { id: number }' in paden
    and "id?: number }, ): string { const sleutel = kantoor.afm_nummer" not in paden,
)
for naam in ("kantoren", "honoraria"):
    tekst = pagina("app", naam, "page.tsx")
    check(
        f"/{naam} geeft het kantoor-id mee aan elke kantoorPad uit een saldo- of prijsrij",
        "kantoorPad({ afm_nummer: rij.afmNummer, naam: rij.naam })" not in tekst
        and "id: rij.kantoorId" in tekst,
    )

# --- mobiel -------------------------------------------------------------------------------
kantoor = pagina("app", "kantoor", "[slug]", "page.tsx")
waar = kantoor.split("<h2>Waar dit kantoor werkt</h2>", 1)[-1].split("</section>", 1)[0]
check(
    "de tabel 'Waar dit kantoor werkt' staat in een eigen schuifkader",
    '<div className="tabel-omhulsel"> <table>' in waar,
)
wisselingen = pagina("app", "wisselingen", "page.tsx")
kop = re.search(r"<h2>Boekjaar \{gekozen\}</h2> (.*?) </div>", wisselingen)
check(
    "de kaartkop op /wisselingen eindigt op een kort getal, niet op een zin "
    "(het laatste kind van een kaartkop breekt niet af)",
    kop is not None and "goedkeurende" not in kop.group(1),
)

# --- overige kantoren ----------------------------------------------------------------------
kantoren = pagina("app", "kantoren", "page.tsx")
check(
    "/kantoren toont de kantoren zonder controle in een eigen lijst",
    "alleKantoren()" in kantoren and "<h2>Overige kantoren</h2>" in kantoren,
)
check(
    "die kop zegt niet 'in het register': 19 ervan hebben geen AFM-nummer",
    "Overige kantoren in het register" not in kantoren,
)
check(
    "alleen actieve kantoren: wie uit het register verdween en hier geen controle "
    "heeft (de AFM zelf, VBWA) hoort niet tussen de kantoren",
    "kantoren.filter((k) => k.actief && !metControles.has(k.id))" in kantoren,
)
check(
    "die lijst heeft geen aantallen: wat ze hebben is vooral marktonderzoek",
    "overige.map((kantoor) =>" in kantoren
    and "aantal" not in kantoren.split("overige.map((kantoor) =>", 1)[1].split("</tbody>", 1)[0],
)

print(f"{goed}/{goed + fout} goed")
sys.exit(1 if fout else 0)
