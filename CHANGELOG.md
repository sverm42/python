# CHANGELOG

All notable changes to `sverm` are documented here. Format loosely follows [Keep a Changelog](https://keepachangelog.com), versioned by [SemVer](https://semver.org).

## [1.1.1] — 2026-04-10

### Fikset
- **Python-krav senket fra 3.11 til 3.10.** Det opprinnelige `>=3.11`-kravet i `pyproject.toml` var arbitrært — koden bruker ingen 3.11-spesifikke features (alle filer har `from __future__ import annotations`, ingen `match/case`, ingen `tomllib`, ingen `ExceptionGroup`). Workshop-deltakere med Python 3.10 (Ubuntu 22.04 LTS, mange Windows-maskiner) ble unødvendig blokkert. Alt fungerer identisk på 3.10.

## [1.1.0] — 2026-04-10

Workshop-klargjøring for "KI-sverm i praksis" (Quben, Kongsberg, 15. april 2026).

### Lagt til
- **Inbox-modus** (`sverm launch inbox`) — hver instans ser hele listen av åpne cases og velger `--pick-min`..`--pick-max` selv basert på seed-affinitet. Gir bredde med agency: en «økonom»-seed dras mot penger-cases, en «forelder»-seed mot familie-cases.
- **Batch-modus** (`sverm launch batch`) — alle åpne cases partisjoneres deterministisk (round-robin) mellom N instanser. Full dekning — hver case får minst én instans.
- Multi-case debrief-format for inbox og batch: aggregering per case (hvor mange instanser dekket hver case, snitt-confidence per case) + rå outputs gruppert per case.
- `--timeout SECONDS` for alle launch-moduser (default 900s) — dreper hengende prosesser og lar debrief kjøre på det som landet.
- Bedre prosjekt-resolver: `sverm launch focus 1 --project 1` fungerer nå pålitelig med pipx-install. Søker både `cwd/10-projects/` og `~/sverm-projects/`. `SVERM_PROJECTS_DIR` overstyrer.
- Hjelpsom feilmelding når `--project N` ikke finner noe — lister tilgjengelige prosjekter eller forklarer hvordan man oppretter et.
- `sverm setup` defaulter nå til `~/sverm-projects/` istedenfor `cwd/10-projects/`, slik at workshopdeltakere ikke får uncommitted changes i den klonede repoen.

### Endret
- Default-modell endret fra `--medium -n 9` til `--small -n 4` for å spare abonnementskvoten på første flight. Eskalér manuelt med `--medium -n 9` eller `--large -n 9` når oppsettet er validert.
- Codex `--large` mapper nå til `gpt-5.4` istedenfor `o3` (o3 finnes ikke i Codex CLI per april 2026). Codex har ingen dedikert reasoning-tier utover gpt-5.4, så «large» mapper midlertidig til samme modell som «medium» for Codex.

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
- Python 3.11+ *(senket til 3.10+ i v1.1.1)*
- Ingen eksterne Python-dependencies (kun stdlib)
- SQLite-basert prosjektdatabase (seeds, cases, flights, instances, outputs, debriefs)
- UTF-8 overalt — full støtte for æøå i alle lag (kode, DB, filer, prompter)
- Atomisk DEBRIEF.lock for å sikre at kun én instans kjører debrief
- Graceful fallback for instance-ID allokering (lokal sekvens hvis HQ-integrasjon ikke finnes)
- Cross-platform: samme JSON-config og samme kode fungerer på alle plattformer
- ClaudeRuntime bruker `--permission-mode bypassPermissions` med `--add-dir` begrensning for trygg filskriving

### Ikke i v1.0
- **PyPI-publisering** — installasjon via `pip install git+https://...` inntil videre

---

## Metodisk opphav

Sverm-metodikken ble utviklet hos [sverm.ai](https://sverm.ai) gjennom 2025-2026 som et praktisk verktøy for konsulentoppdrag innen organisasjonspsykologi, strategi og policyutvikling. Den startet som et bash-basert orkestreringssystem og ble Python-portet for å nå Windows-brukere og gjøre installasjonen enklere.

Denne publiserte versjonen er v1.0 av Python-porten. Bash-versjonen er fortsatt i aktiv bruk internt men er ikke inkludert i dette repoet.
