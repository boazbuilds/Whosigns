"""Test: een bronfout mag nooit als "bekeken" worden afgeschreven.

Waarom dit bestaat. `haal_op` in laad_zorg.py vangt élke uitzondering af. Tot
20-8-2026 gaf hij daarna `None` terug — precies dezelfde `None` als een
organisatie die niets had gedeponeerd. De lus kon die twee niet uit elkaar
houden, schreef ze allebei weg met `noteer_bekeken`, en met `--hervat` betekent
dat "nooit meer". Een archief dat tien minuten 502 geeft schreef zo tientallen
organisaties permanent af, terwijl de run netjes groen eindigde.

Drie dingen maakten het onzichtbaar:

- De foutregel begint met twee spaties en werd door het grep-filter van
  oogst_zorg.sh uit het log gehouden.
- De rem in oogst_zorg.sh (drie lege blokken achter elkaar = stoppen) trok juist
  níét aan, want die kijkt of de bekekenlijst groeide — en die groeide van de
  afgeschreven organisaties. Tijdens een storing raasde de lus dus door de
  wachtrij heen.
- Op de site splitst analyse.ts een kantoorrelatie bij een ontbrekend jaar, dus
  een opgeslokte bronfout wordt daar een kortere relatieduur: een bewering, niet
  alleen een leemte.

De regel zit in de lus van `main()` en is niet los aan te roepen. Deze test leest
daarom de echte broncode met `ast` in plaats van met een regex, want een
regex-test zou meegroeien met mijn aannames over hoe de code eruitziet.
"""

import ast
import sys
from pathlib import Path

BRON = Path(__file__).resolve().parent / "laad_zorg.py"

goed = 0
fout = 0


def check(omschrijving: str, voorwaarde: bool) -> None:
    global goed, fout
    if voorwaarde:
        goed += 1
    else:
        fout += 1
        print(f"  FOUT: {omschrijving}")


boom = ast.parse(BRON.read_text(encoding="utf-8"))


def zoek_functie(naam: str):
    for knoop in ast.walk(boom):
        if isinstance(knoop, ast.FunctionDef) and knoop.name == naam:
            return knoop
    return None


# --- haal_op geeft de fout apart terug -----------------------------------------
haal_op = zoek_functie("haal_op")
check("haal_op bestaat nog", haal_op is not None)

if haal_op is not None:
    returns = [k for k in ast.walk(haal_op) if isinstance(k, ast.Return)]
    check("haal_op heeft twee return-paden (gelukt en mislukt)", len(returns) == 2)
    check(
        "beide paden geven drie dingen terug, zodat een fout onderscheidbaar is "
        "van 'niets gevonden'",
        all(isinstance(r.value, ast.Tuple) and len(r.value.elts) == 3 for r in returns),
    )
    # Het foutpad is de return binnen de except-tak.
    handlers = [k for k in ast.walk(haal_op) if isinstance(k, ast.ExceptHandler)]
    check("haal_op vangt de bron nog steeds af", len(handlers) == 1)
    if handlers:
        fout_returns = [k for k in ast.walk(handlers[0]) if isinstance(k, ast.Return)]
        check(
            "het foutpad geeft de uitzondering mee in plaats van hem weg te gooien",
            bool(fout_returns)
            and isinstance(fout_returns[0].value, ast.Tuple)
            and any(
                isinstance(e, ast.Name) and e.id == "fout"
                for e in fout_returns[0].value.elts
            ),
        )
        check(
            "het foutpad geeft geen resultaat terug (dat weten we immers niet)",
            bool(fout_returns)
            and any(
                isinstance(e, ast.Constant) and e.value is None
                for e in fout_returns[0].value.elts
            ),
        )


# --- de lus schrijft een bronfout niet weg als bekeken --------------------------
def lus_over_haal_op():
    """De for-lus die pool.map(haal_op, ...) uitpakt."""
    for knoop in ast.walk(boom):
        if not isinstance(knoop, ast.For):
            continue
        if "haal_op" in ast.dump(knoop.iter):
            return knoop
    return None


lus = lus_over_haal_op()
check("de lus over haal_op bestaat nog", lus is not None)

if lus is not None:
    doel = ast.dump(lus.target)
    check(
        "de lus pakt drie dingen uit, dus ook de fout",
        doel.count("Name(") >= 3 or "Tuple" in doel,
    )

    # Alle if-takken op het eerste niveau van de lus, op volgorde.
    takken = [k for k in lus.body if isinstance(k, ast.If)]
    check("de lus heeft nog voorwaardelijke takken", bool(takken))

    def noemt(knoop, naam: str) -> bool:
        return any(
            isinstance(k, ast.Call)
            and isinstance(k.func, ast.Name)
            and k.func.id == naam
            for k in ast.walk(knoop)
        )

    fout_tak = next(
        (t for t in takken if "fout" in ast.dump(t.test) and "None" in ast.dump(t.test)),
        None,
    )
    check(
        "er is een tak die expliciet op een bronfout test",
        fout_tak is not None,
    )
    check(
        "die tak roept noteer_bekeken NIET aan -- dat is de hele bug",
        fout_tak is not None and not noemt(fout_tak, "noteer_bekeken"),
    )
    check(
        "die tak slaat de organisatie over (continue), zodat hij vooraan in de "
        "wachtrij blijft staan",
        fout_tak is not None
        and any(isinstance(k, ast.Continue) for k in ast.walk(fout_tak)),
    )

    resultaat_tak = next(
        (t for t in takken if "resultaat" in ast.dump(t.test)),
        None,
    )
    check(
        "de tak voor 'niets gevonden' bestaat nog",
        resultaat_tak is not None,
    )
    check(
        "en die mag wél noteren, want daar staat de uitkomst vast",
        resultaat_tak is not None and noemt(resultaat_tak, "noteer_bekeken"),
    )
    if fout_tak is not None and resultaat_tak is not None:
        check(
            "de fouttak staat vóór de niets-gevonden-tak, anders vangt de tweede "
            "de fout alsnog af",
            takken.index(fout_tak) < takken.index(resultaat_tak),
        )


# --- de eindregel maakt bronfouten zichtbaar -----------------------------------
tekst = BRON.read_text(encoding="utf-8")
check(
    "er is een teller voor bronfouten",
    "bronfouten = 0" in tekst,
)
check(
    "de eindregel noemt bronfouten, want de losse foutregels worden door het "
    "grep-filter van oogst_zorg.sh weggelaten",
    "overgeslagen na een bronfout" in tekst,
)

# Die eindregel moet ook echt door dat filter komen. oogst_zorg.sh laat door:
# '^---', 'opdrachten,' en '^[0-9]+ organisaties'.
check(
    "de eindregel bevat 'opdrachten,' en komt dus door het filter van oogst_zorg.sh",
    "opdrachten, " in tekst and "=== boekjaar {boekjaar}: {gevonden} opdrachten, " in tekst,
)

print(f"{goed}/{goed + fout} goed")
sys.exit(1 if fout else 0)
