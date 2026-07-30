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
        # .strip(): een secret die via copy-paste is aangemaakt bevat vaak een
        # onzichtbaar regeleinde, wat urllib laat crashen met InvalidURL.
        self.url = (url or os.environ.get("SUPABASE_URL", "")).strip().rstrip("/")
        self.sleutel = (sleutel or os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")).strip()
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

    def upsert_met_id(self, tabel: str, rij: dict, conflict_kolom: str) -> dict:
        """Upsert van één rij, geeft de rij terug inclusief id — nodig om er
        meteen een andere tabel aan te kunnen koppelen (bijv. organisatie_id op
        een opdracht)."""
        antwoord = self._verzoek(
            "POST",
            f"{tabel}?on_conflict={urllib.parse.quote(conflict_kolom)}",
            [rij],
            {"Prefer": "resolution=merge-duplicates,return=representation"},
        )
        return antwoord[0]

    def bijwerken(self, tabel: str, filter: str, velden: dict) -> None:
        """Werkt bestaande rijen bij zonder ze opnieuw te hoeven opbouwen.

        Nodig omdat een upsert op `opdrachten` alle verplichte kolommen mee wil
        (kantoor_id, bron_id). Als je alleen een paar velden wil aanvullen op een
        rij die er al staat, is dat een update en geen upsert.

        `filter` is een PostgREST-filter, bijv. "organisatie_id=eq.42&boekjaar=eq.2023".
        """
        if not velden:
            return
        self._verzoek("PATCH", f"{tabel}?{filter}", velden, {"Prefer": "return=minimal"})

    def verwijderen(self, tabel: str, filter: str) -> None:
        """Verwijdert rijen die aan het PostgREST-filter voldoen.

        Alleen bedoeld om een eerdere uitkomst van deze pipeline te vervangen als
        de extractie is verbeterd — bijvoorbeeld wanneer het opdrachttype anders
        blijkt te zijn en dus onder een andere unieke sleutel valt. Zonder filter
        weigert PostgREST de opdracht, wat hier precies de bedoeling is.
        """
        if not filter:
            raise SupabaseFout("verwijderen zonder filter is niet toegestaan")
        self._verzoek("DELETE", f"{tabel}?{filter}", None, {"Prefer": "return=minimal"})

    # PostgREST levert er nooit meer dan duizend per verzoek, ook niet met
    # limit=20000 erin. Dat faalt stil: je krijgt gewoon de eerste duizend en
    # niets wijst erop dat er meer was.
    PAGINA = 1000

    def selecteer_alles(self, tabel: str, query: str = "select=*") -> list:
        """Alle rijen, in pagina's van duizend.

        De enige leesmethode die deze klasse aanbiedt, en dat is opzet. Er stond
        hiernaast een `selecteer()` die één verzoek deed, en die kapte dus stil af op
        duizend rijen — met vier aanroepen die er een volledige verzameling uit
        wilden halen (de kantorenindex in drie laders, en de lijst 'al geladen' in
        laad_stichtingen). Zolang de tabellen klein waren viel dat niet op. Zonder
        die methode kan de fout niet terugkomen.

        Er stond ook een `telling()` die `select=id` ophaalde en de rijen télde;
        die gaf 1000 terug bij 5081 opdrachten. Wie een aantal wil, vraagt
        PostgREST om `Prefer: count=exact` — zoals `tel()` in web/lib/db.ts doet.
        """
        alles: list = []
        while True:
            pagina = self._verzoek(
                "GET", f"{tabel}?{query}&limit={self.PAGINA}&offset={len(alles)}"
            )
            alles.extend(pagina)
            if len(pagina) < self.PAGINA:
                return alles
