# CHANGELOG

All notable changes to `sverm` are documented here. Format loosely follows [Keep a Changelog](https://keepachangelog.com), versioned by [SemVer](https://semver.org).

## [1.0.0] — 2026-04-10

Første publiserte versjon. Workshop-klar release for "KI-sverm i praksis" (Quben, Kongsberg, 15. april 2026).

### Lagt til
- Python-first orkestrering som fungerer på macOS, Windows og Linux
- Runtime-abstraksjon: støtter både Claude Code CLI og OpenAI Codex CLI på alle tre plattformer
- Auto-detekt av tilgjengelig runtime (Claude prioriteres hvis begge er installert)
- `SVERM_RUNTIME`-miljøvariabel for eksplisitt runtime-override
- `sverm setup` — opprett prosjekt fra JSON-config
- `sverm launch focus` — kjør N instanser på én case med vektede frequency seeds
- `sverm inspect` — vis prosjektstatus og cases
- `sverm debrief` — generer debrief-rapport for en flight
- `sverm mirror` — synk DB til CASES.md
- `--dry-run`-modus for testing uten ekte AI-prosesser
- Innebygd demo-prosjekt: `boligkjop-analyse` — nøytralt, universelt relaterbart
- Fem fullstendige eksempel-configs i `examples/`: boligkjop, restaurant, karriere, produktlansering, kommune-beslutning
- `docs/SEED-DESIGN.md` — dedikert guide for seed-design med regler, eksempler og kvalitetssjekkliste
- `docs/ARCHITECTURE.md` — teknisk oversikt over moduler, datamodell, fil-kontrakter og ekstensjonspunkter
- `Før workshopen`-installeringssjekkliste i README
- PolyForm Noncommercial License 1.0.0

### Tekniske detaljer
- Python 3.11+
- Ingen eksterne Python-dependencies (kun stdlib)
- SQLite-basert prosjektdatabase (seeds, cases, flights, instances, outputs, debriefs)
- UTF-8 overalt — full støtte for æøå i alle lag (kode, DB, filer, prompter)
- Atomisk DEBRIEF.lock for å sikre at kun én instans kjører debrief
- Graceful fallback for instance-ID allokering (lokal sekvens hvis HQ-integrasjon ikke finnes)
- Cross-platform: samme JSON-config og samme kode fungerer på alle plattformer
- ClaudeRuntime bruker `--permission-mode bypassPermissions` med `--add-dir` begrensning for trygg filskriving

### Ikke i v1.0
- **Inbox-modus** (hver instans velger cases selv) — kommer i v1.1
- **Batch-modus** (partisjoner alle cases) — kommer i v1.1
- **PyPI-publisering** — installasjon via `pip install git+https://...` inntil videre

---

## Metodisk opphav

Sverm-metodikken ble utviklet hos [sverm.ai](https://sverm.ai) gjennom 2025-2026 som et praktisk verktøy for konsulentoppdrag innen organisasjonspsykologi, strategi og policyutvikling. Den startet som et bash-basert orkestreringssystem og ble Python-portet for å nå Windows-brukere og gjøre installasjonen enklere.

Denne publiserte versjonen er v1.0 av Python-porten. Bash-versjonen er fortsatt i aktiv bruk internt men er ikke inkludert i dette repoet.
