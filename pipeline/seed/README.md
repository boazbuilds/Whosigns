# Seed-data

## kantoren.csv

Momentopname van het **AFM-vergunningenregister accountantsorganisaties**, gemaakt met
`../adapters/afm_register.py` (officiële XML-export van afm.nl). Stand 28-7-2026:
233 kantoren, waarvan 6 met OOB-vergunning (BDO, Deloitte, EY, Forvis Mazars, KPMG, PwC).

- **Verversen:** script draaien en het gewijzigde bestand committen
  (`python3 pipeline/adapters/afm_register.py`).
- **Mutatielog:** de git-historie van dit bestand. Een kantoor dat verdwijnt =
  vergunning beëindigd → later signaal `kantoor_vergunning_beeindigd` (Fase 4);
  een nieuw kantoor = toetreder.
- **Supabase:** zodra het project bestaat wordt deze lijst bij elke run ge-upsert naar
  de tabel `kantoren` (sleutel `afm_nummer`), met bronregistratie (`afm_register`).
- **Dubbelrol:** dit is ook de matchlijst waarmee we in Fase 1 kantoornamen uit de
  verklaring-pdf's vissen (tekstmatch, geen LLM) — zie `../adapters/digimv.md`.
- **Wat de snapshot verder doet** (sinds 5-10-2026): een hernoemd kantoor (zelfde
  nummer, andere naam) krijgt zijn oude naam als regel in `kantoor_alias.csv`, een
  verdwenen kantoor gaat naar `kantoren_vervallen.csv`, en een export die ineens
  een tiende korter is wordt geweigerd. De workflow draait daarna alle tests tegen
  de nieuwe seed en wordt rood als er een faalt.

## kantoren_vervallen.csv

Vergunninghouders die uit het AFM-register zijn verdwenen. Hun oude verklaringen
bestaan nog, dus ze blijven onder hun eigen AFM-nummer vindbaar
(`wta_vergunning` onwaar, `wta_ooit` waar); in de database worden ze inactief en
verliezen ze hun OOB- en Wta-vlag. Bewust nooit aan een opvolger gekoppeld: een
nieuw vergunningnummer is een nieuwe vergunninghouder.

`afwezig_sinds` is de datum van de eerste wekelijkse snapshot zonder het nummer,
niet de datum waarop de vergunning eindigde. Wat nooit een accountantsorganisatie
was (de AFM zelf, 15-8 tot 31-8-2026) komt hier niet in — zie
`GEEN_ACCOUNTANTSORGANISATIE` in `../adapters/afm_register.py`.

## duo_besturen.csv

De schoolbesturen uit de vijf besturenlijsten van **DUO Open Onderwijsdata**
(bo, so, vo, mbo, ho; licentie CC BY 4.0), met hun oudere namen uit het
RIO-bestand `onderwijsbesturen.csv` van dezelfde bron. Gemaakt met
`../adapters/duo_besturen.py`. Stand 6-10-2026: 1.120 besturen, 3.176 namen.

- **Waarvoor:** een organisatie op naam als schoolbestuur herkennen (sector
  onderwijs; het KvK-nummer gaat als kandidaat naar de review-queue, want een
  naam is geen harde sleutel), en een KvK-nummer uit een aanlevering als
  schoolbestuur herkennen. Zie de toelichting in de adapter en migratie
  20261006110000.
- **Alleen organisatiegegevens:** KvK-nummer, naam, bevoegd-gezagnummer, soort
  onderwijs. Geen adressen of telefoonnummers. De vier gemeenten die bevoegd
  gezag van hun eigen openbare scholen zijn, staan er niet in.
- **`ook_elders`:** `ja` als de naam in RIO ook bij een KvK-nummer buiten de
  besturenlijsten hoort; zo'n naam levert geen treffer op. `kort` als dat alleen
  geldt voor de naam zonder plaatsstaart ("Stichting X te Testdam" is uniek,
  "Stichting X" niet); dan telt alleen de volle naam. Die andere namen zelf
  staan er bewust niet in: RIO kent ook niet-bekostigde aanbieders, en daar kan
  een eenmanszaak tussen zitten.
- **Verversen:** `python3 pipeline/adapters/duo_besturen.py` en het resultaat
  committen. Het script weigert als de lijsten samen ineens minder dan duizend
  besturen tellen.
