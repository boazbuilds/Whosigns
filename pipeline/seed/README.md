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
