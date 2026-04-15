# CLAUDE.md — sverm

> Multi-perspektiv AI-analyse. N instanser, samme problem, ulike perspektiver.

## Hva er sverm?

`sverm` er en Python CLI som starter N parallelle AI-instanser, hver med en unik *frequency seed* — et sett vektede ord som farger perspektivet. Resultatet er genuint forskjellige analyser, ikke varianter av samme svar.

## Kommandoer

```bash
sverm setup <config.json>                        # Opprett prosjekt fra JSON
sverm launch focus <case_id> --project <P>       # N instanser pa 1 case (dybde)
sverm launch inbox --project <P>                 # Instansene velger cases selv (bredde)
sverm launch batch --project <P>                 # Alle cases fordeles (dekning)
sverm inspect --project <P>                      # Vis prosjektstatus
sverm debrief <flight_id> --project <P>          # Generer rapport
sverm mirror --project <P>                       # Synk DB til CASES.md
```

**Vanlige flagg:** `--small` (default) / `--medium` / `--large`, `-n COUNT` (default 4), `--dry-run`, `--timeout SECONDS`

## Workshop-kommandoer (slash commands)

Disse kommandoene er tilgjengelige for Claude Code-brukere:

| Kommando | Beskrivelse |
|----------|-------------|
| `/workshop` | Full veiviser fra null til forste flight. For nybegynnere. |
| `/workshop quick` | Hopp over velkomst og prereqs — rett til problemdesign. |
| `/workshop stage N` | Hopp til et spesifikt steg (0-10). |
| `/workshop-seeds` | Standalone seed-design-hjelper. For erfarne brukere. |
| `/workshop-prereqs` | Sjekk at Python, CLI og sverm er installert. |

For Codex-brukere: si "guide me", "workshop", eller "help me get started" for a starte veiviseren.

## Prosjektstruktur

```
sverm/                    # Hovedpakke (Python 3.10+, ingen eksterne deps)
  cli.py                  # CLI entry point
  config.py               # JSON-config-lasting
  models.py               # Dataklasser (ProjectConfig, SeedAxis, Case, Flight, Instance)
  db.py                   # SQLite-lag
  setup.py                # Prosjektinitialisering
  launch.py               # Flight-orkestrering (focus/inbox/batch)
  debrief.py              # Rapportgenerering
  runtime.py              # Runtime-abstraksjon (Claude/Codex/DryRun)
  paths.py                # Prosjektsti-oppslag
  platform.py             # OS-deteksjon
  encoding.py             # UTF-8-handtering
examples/                 # 5 ferdige JSON-configs
docs/                     # ARCHITECTURE.md, SEED-DESIGN.md
10-projects/              # Innebygd demo (boligkjop)
```

## Modell-mapping

| Flagg | Claude Code | Codex |
|-------|-------------|-------|
| `--small` | haiku | gpt-5.4-mini |
| `--medium` | sonnet | gpt-5.4 |
| `--large` | opus | gpt-5.4 |

## Viktige filer for bidragsytere

- `docs/SEED-DESIGN.md` — Hvordan designe gode frequency seeds
- `docs/ARCHITECTURE.md` — Teknisk arkitektur og datamodell
- `CONTRIBUTING.md` — Retningslinjer for bidrag
- `examples/*.json` — Referanse-configs med 5 akser og vektede ord

## Kodestil

- Python 3.10+ med `from __future__ import annotations`
- Type hints der det gir mening
- Docstrings pa norsk (UTF-8)
- Ingen eksterne Python-avhengigheter (kun stdlib)
