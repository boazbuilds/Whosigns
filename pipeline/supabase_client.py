"""Minimale Supabase-client voor de pipeline (alleen standaardbibliotheek).

Praat met PostgREST, de REST-API die Supabase automatisch op de database zet.
Geen extra pakketten nodig — scheelt onderhoud en installatiegedoe.

Twee omgevingsvariabelen, in GitHub Actions gezet als repository secrets:
    SUPABASE_URL                 https://<project>.supabase.co
    SUPABASE_SERVICE_ROLE_KEY    geheime sleutel; omzeilt RLS, dus alleen server-side

De service-role-sleutel hoort NOOIT in de repo, in een chat of in de frontend.
De website gebruikt straks de publieke anon-sleutel, die alleen leesrechten heeft.
"""

import json
import os
import urllib.error
import urllib.parse
import urllib.request


class SupabaseFout(RuntimeError):
    pass


class Supabase:
    def __init__(self, url: str | None = None, sleutel: str | None = None):
        self.url = (url or os.environ.get("SUPABASE_URL", "")).rstrip("/")
        self.sleutel = sleutel or os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
        if not self.url or not self.sleutel:
            raise SupabaseFout(
                "SUPABASE_URL en SUPABASE_SERVICE_ROLE_KEY ontbreken. "
                "Zie docs/setup-supabase.md."
            )

    def _verzoek(
        self, methode: str, pad: str, body: object = None, extra_koppen: dict | None = None
    ) -> list:
        data = json.dumps(body).encode() if body is not None else None
        koppen = {
            "apikey": self.sleutel,
            "Authorization": f"Bearer {self.sleutel}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        koppen.update(extra_koppen or {})
        verzoek = urllib.request.Request(
            f"{self.url}/rest/v1/{pad}", data=data, headers=koppen, method=methode
        )
        try:
            with urllib.request.urlopen(verzoek, timeout=120) as antwoord:
                inhoud = antwoord.read()
                return json.loads(inhoud) if inhoud else []
        except urllib.error.HTTPError as fout:
            raise SupabaseFout(
                f"{methode} {pad} gaf HTTP {fout.code}: {fout.read().decode()[:500]}"
            ) from fout

    def upsert(self, tabel: str, rijen: list[dict], conflict_kolom: str) -> int:
        """Voegt toe of werkt bij op de unieke sleutel. Twee keer draaien = zelfde
        resultaat (principe 2 uit README: idempotent)."""
        if not rijen:
            return 0
        for begin in range(0, len(rijen), 500):  # PostgREST aan een redelijke batch houden
            self._verzoek(
                "POST",
                f"{tabel}?on_conflict={urllib.parse.quote(conflict_kolom)}",
                rijen[begin : begin + 500],
                {"Prefer": "resolution=merge-duplicates,return=minimal"},
            )
        return len(rijen)

    def invoegen(self, tabel: str, rij: dict) -> dict:
        """Voegt één rij toe en geeft hem terug, inclusief het toegekende id."""
        antwoord = self._verzoek(
            "POST", tabel, [rij], {"Prefer": "return=representation"}
        )
        return antwoord[0]

    def selecteer(self, tabel: str, query: str = "select=*") -> list:
        return self._verzoek("GET", f"{tabel}?{query}")

    def telling(self, tabel: str) -> int:
        rijen = self._verzoek("GET", f"{tabel}?select=id")
        return len(rijen)
