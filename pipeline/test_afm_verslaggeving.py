"""Tests voor het lezen van het AFM-register financiële verslaggeving.

Draaien vanuit de repo-root (geen testframework nodig, geen netwerk):

    python3 pipeline/test_afm_verslaggeving.py

Elk geval is een verkleinde weergave van iets dat in het echte register staat
(gemeten 4-8-2026): de lijstpagina met entiteits-ë's, de detailpagina met het
versleutelde downloadtoken, het ESEF-xhtml waarin inline-XBRL-spans dwars
door woorden heen lopen, en herdeponeringen die de eerdere vervangen.
"""

import io
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "adapters"))

import afm_verslaggeving  # noqa: E402

LIJST = """
<table><tbody>
<tr><td><a href="/nl-nl/sector/registers/meldingenregisters/financiele-verslaggeving/details?id=A2510-03941">03 aug 2026 - 08:23</a></td>
<td>PostNL N.V.</td><td>2026</td><td>Halfjaarlijkse financi&#235;le verslaggeving</td></tr>
<tr><td><a href="details?id=A2510-03597">11 jul 2026 - 22:58</a></td>
<td>Envipco Holding N.V.</td><td>2025</td><td>Jaarlijkse financi&#235;le verslaggeving</td></tr>
<tr><td><a href="details?id=11095">04 apr 2013 - 18:09</a></td>
<td>HAL Trust</td><td>2012</td><td>Jaarlijkse Financi&#235;le verslaggeving</td></tr>
<tr><td><a href="details?id=11090">01 apr 2013 - 09:00</a></td>
<td>HAL Trust</td><td>2012</td><td>Jaarlijkse Financi&#235;le verslaggeving</td></tr>
</tbody></table>
<ul><li><a class="jq_pager" data-page-number="1" href="#">1</a></li>
<li><a class="jq_pager" data-page-number="193" href="#">193</a></li></ul>
"""

DETAIL = """
<table><tr><th>Soort</th><td>Jaarlijkse financi&#235;le verslaggeving</td></tr>
<tr><th>Document</th><td><a href="/downloadregisterfile.aspx?type=financiele-verslaggeving&amp;enc=W3+45r/Abc=">
envipcoholdingnv-2025-12-31-1-en-a2510-03597.zip</a></td></tr></table>
"""

XHTML = """<html><head><style>p { color: red; }</style></head><body>
<p>In our <ix:nonNumeric name="x">opin</ix:nonNumeric>ion, the financial statements give a true and fair view.</p>
<p>Amst<span class="q">elveen</span>, 11 July 2026</p>
<div>For and on behalf of BDO Audit &amp; Assurance B.V.</div>
</body></html>"""


def main() -> int:
    fouten = 0

    def controleer(omschrijving: str, goed: bool, detail: str = "") -> None:
        nonlocal fouten
        fouten += not goed
        print(f"{'✓' if goed else '✗'} {omschrijving}")
        if not goed and detail:
            print(f"    {detail}")

    rijen = afm_verslaggeving.rijen_uit_lijst(LIJST)
    controleer(
        "lijstpagina: vier rijen met id, instelling, boekjaar en soort",
        [r["id"] for r in rijen] == ["A2510-03941", "A2510-03597", "11095", "11090"]
        and rijen[0]["instelling"] == "PostNL N.V."
        and rijen[1]["soort"] == "Jaarlijkse financiële verslaggeving",
        f"gevonden: {rijen}",
    )
    controleer(
        "paginatelling uit de pagineringsknoppen",
        afm_verslaggeving.aantal_paginas(LIJST) == 193,
    )

    jaarlijks = afm_verslaggeving.jaarlijkse(rijen)
    controleer(
        "jaarlijkse filtert halfjaarcijfers weg en de nieuwste herdeponering wint",
        [r["id"] for r in jaarlijks] == ["A2510-03597", "11095"],
        f"gevonden: {[r['id'] for r in jaarlijks]}",
    )

    link = afm_verslaggeving.document_link(DETAIL)
    controleer(
        "detailpagina: documentnaam en ontsleutelde downloadlink",
        link
        == (
            "envipcoholdingnv-2025-12-31-1-en-a2510-03597.zip",
            "https://www.afm.nl/downloadregisterfile.aspx?type=financiele-verslaggeving&enc=W3+45r/Abc=",
        ),
        f"gevonden: {link}",
    )

    tekst = afm_verslaggeving.xhtml_naar_tekst(XHTML)
    controleer(
        "xhtml: inline-tags breken geen woorden, bloktags wél regels, stijl weg",
        "In our opinion, the financial statements" in tekst
        and "Amstelveen, 11 July 2026" in tekst
        and "BDO Audit & Assurance B.V." in tekst
        and "color: red" not in tekst
        and tekst.count("\n") >= 2,
        f"gevonden: {tekst!r}",
    )

    # ESEF-route: het grootste xhtml-bestand in het pakket is het verslag.
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as z:
        z.writestr("pakket/META-INF/klein.xhtml", "<p>bijlage</p>")
        z.writestr("pakket/reports/verslag.xhtml", XHTML)
    pad = Path(__file__).resolve().parent / ".cache" / "test_esef.zip"
    pad.parent.mkdir(exist_ok=True)
    pad.write_bytes(buffer.getvalue())
    uit_zip = afm_verslaggeving.tekst_uit_document(pad)
    pad.unlink()
    controleer(
        "ESEF-zip: verslag gevonden en als tekst gelezen",
        "For and on behalf of BDO Audit & Assurance B.V." in uit_zip,
        f"gevonden: {uit_zip[:120]!r}",
    )

    totaal = 6
    print(f"\n{totaal - fouten}/{totaal} goed")
    return 1 if fouten else 0


if __name__ == "__main__":
    raise SystemExit(main())
