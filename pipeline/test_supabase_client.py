"""Hoe selecteer_alles pagineert — zonder database.

Draaien vanuit de repo-root (geen testframework nodig, geen netwerk):

    python3 pipeline/test_supabase_client.py

Waarom dit bestand bestaat: selecteer_alles is de enige leesmethode van de
pipeline-client, en elke lader haalt er zijn kantorenindex en zijn lijst 'al
geladen' mee op. Twee fouten die hier al eens zaten of konden zitten: stil
afkappen op duizend rijen (PostgREST geeft er nooit meer per verzoek), en een
eigen limit in de query die PostgREST stil negeert omdat de laatste wint —
gemeten op 5-10-2026: 'limit=1&…&limit=1000' gaf duizend rijen.
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from supabase_client import Supabase, SupabaseFout  # noqa: E402

goed = 0
fout = 0


def check(omschrijving: str, voorwaarde: bool) -> None:
    global goed, fout
    if voorwaarde:
        goed += 1
    else:
        fout += 1
        print(f"  FOUT: {omschrijving}")


def nep_client(totaal: int) -> tuple[Supabase, list[str]]:
    """Een client waarvan de 'database' `totaal` rijen heeft en elk verzoek onthoudt."""
    client = Supabase(url="https://voorbeeld.invalid", sleutel="nep")
    verzoeken: list[str] = []

    def verzoek(methode: str, pad: str, body=None, extra_koppen=None) -> list:
        verzoeken.append(pad)
        delen = dict(deel.split("=", 1) for deel in pad.split("?", 1)[1].split("&"))
        begin, aantal = int(delen["offset"]), int(delen["limit"])
        return [{"id": i} for i in range(begin, min(begin + aantal, totaal))]

    client._verzoek = verzoek
    return client, verzoeken


client, verzoeken = nep_client(2005)
rijen = client.selecteer_alles("kantoren", "select=id")
check("alle 2005 rijen, niet de eerste duizend", len(rijen) == 2005)
check("elke rij precies één keer", len({r["id"] for r in rijen}) == 2005)
check("drie pagina's: offset 0, 1000 en 2000", len(verzoeken) == 3
      and [v.rsplit("offset=", 1)[1] for v in verzoeken] == ["0", "1000", "2000"])
check("vaste volgorde erbij als de aanroeper er geen gaf",
      all("order=id.asc" in v for v in verzoeken))

client, verzoeken = nep_client(1000)
rijen = client.selecteer_alles("kantoren", "select=id")
check("precies duizend: nog één verzoek om zeker te weten dat het op is",
      len(rijen) == 1000 and len(verzoeken) == 2)

client, verzoeken = nep_client(3)
client.selecteer_alles("kantoren", "select=id&order=naam.asc")
check("een eigen volgorde blijft staan en krijgt er geen tweede bij",
      "order=naam.asc" in verzoeken[0] and "order=id.asc" not in verzoeken[0])

for query in ("select=id&limit=1", "select=id&offset=5", "limit=10"):
    client, verzoeken = nep_client(3)
    try:
        client.selecteer_alles("bronnen", query)
        geweigerd = False
    except SupabaseFout:
        geweigerd = True
    check(f"een eigen limit/offset wordt geweigerd ({query})", geweigerd and not verzoeken)

client, _ = nep_client(3)
check("een filter dat toevallig 'limit' heet mag wel",
      len(client.selecteer_alles("tabel", "select=id&soort=eq.limit")) == 3)

# Lege argumenten vallen terug op de omgeving; die moet hier dus ook leeg zijn,
# anders slaagt deze controle niet in een workflowstap mét secrets.
os.environ.pop("SUPABASE_URL", None)
os.environ.pop("SUPABASE_SERVICE_ROLE_KEY", None)
try:
    Supabase(url="", sleutel="")
    zonder = False
except SupabaseFout:
    zonder = True
check("zonder URL en sleutel een duidelijke fout, geen half werkende client", zonder)

print(f"{goed}/{goed + fout} goed")
sys.exit(1 if fout else 0)
