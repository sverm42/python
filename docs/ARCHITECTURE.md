# Arkitektur

Kort teknisk oversikt over hvordan `sverm` er bygd. Lese-tid: ~10 minutter.

---

## Lag-for-lag

```
  ┌─────────────────────────────────────────────────────────┐
  │                     CLI (sverm/cli.py)                   │
  │   sverm setup | launch | inspect | mirror | debrief     │
  └──────────────────────────┬──────────────────────────────┘
                             │
          ┌──────────────────┼──────────────────┐
          ▼                  ▼                  ▼
  ┌────────────┐     ┌────────────┐     ┌────────────┐
  │  setup.py  │     │ launch.py  │     │ debrief.py │
  │  Config →  │     │ Orchestra- │     │  Collect   │
  │  Project   │     │  tor       │     │  outputs   │
  └─────┬──────┘     └──────┬─────┘     └─────┬──────┘
        │                   │                 │
        └──────────┬────────┘                 │
                   ▼                          │
          ┌────────────────┐                  │
          │  db.py         │◄─────────────────┘
          │  SQLite lag    │
          └────────┬───────┘
                   │
                   ▼
          ┌────────────────┐
          │  runtime.py    │
          │  ClaudeRuntime │  →  subprocess.Popen(["claude", ...])
          │  CodexRuntime  │  →  subprocess.Popen(["codex", ...])
          │  DryRunRuntime │  →  mock output
          └────────────────┘
```

### Modulene

| Modul | Ansvar |
|-------|--------|
| `cli.py` | Parser argumenter, dispatcher til riktig kommando |
| `config.py` | Leser og validerer JSON-config |
| `models.py` | Domenemodeller (ProjectConfig, SeedAxis, SeedWord, Case, Flight, Instance) |
| `paths.py` | Oppdager prosjektstruktur, normaliserer path-er |
| `platform.py` | OS-deteksjon (macOS/Windows/Linux) |
| `encoding.py` | UTF-8 lese/skrive som wrapper |
| `db.py` | SQLite-lag: init, CRUD, query, CASES.md-generering |
| `setup.py` | Oppretter nytt prosjekt fra JSON (erstatter bash `setup.sh`) |
| `launch.py` | Starter flight, allokerer seeds, spawner prosesser, monitorerer .done |
| `debrief.py` | Samler outputs, generer rapport, oppdaterer INDEX og CASES |
| `runtime.py` | Runtime-abstraksjon: kjører `claude` eller `codex` som subprocess |

---

## Datamodell

### Prosjektstruktur på disk

```
10-projects/1-prosjektnavn/
├── sverm.db                    ← Alt tilstand lever her
├── CLAUDE.md                   ← Kontekst for AI-instanser
├── CONTEXT.md                  ← Kortversjon, for raske oppslag
├── INDEX.md                    ← Auto-generert flight-liste
├── 10-cases/
│   └── CASES.md                ← Auto-generert fra DB
├── 20-flights/
│   └── FLT_001/                ← Én flight
│       ├── MANIFEST.json       ← Metadata: hvem, hva, når, med hvilke seeds
│       ├── VS_001_prompt.md    ← Prompten instansen fikk
│       ├── VS_001_output.md    ← Instansens analyse
│       ├── VS_001_log.txt      ← Subprocess stdout/stderr
│       ├── VS_001.done         ← Signal: instansen er ferdig
│       └── DEBRIEF.lock/       ← Atomisk lås — én debrief kjører per flight
└── 30-debrief/
    └── FLT_001_debrief.md      ← Samlet rapport med alle outputs
```

### SQLite-skjema (forenklet)

`sverm.db` har disse hovedtabellene:

- **seeds** — alle ord per akse med vekt
- **cases** — alle problemstillinger knyttet til prosjektet
- **flights** — hver kjøring med mode, modell, status, tidsstempel
- **instances** — hver enkeltinstans i en flight med sin tildelte seed
- **outputs** — analysen hver instans produserte (innhold + confidence)
- **debriefs** — samlede rapporter per flight

All endring går gjennom `sverm/db.py` som bruker `connect()` + context manager for transaksjoner.

---

## Prosess-livssyklus

Én `sverm launch focus 1 --project 1` kjøring (default `--small -n 4`):

```
1.  CLI-kommando → cli.py → cmd_launch()
2.  Les prosjekt-path, kontekst, database
3.  Hent case #1 fra DB
4.  Generer N unike seeds (vektet random per akse)
5.  Alloker N instans-IDer (via sverm-id HQ hvis tilgjengelig, ellers lokal sekvens)
6.  Bygg prompt per instans (case + seed + CLAUDE.md-referanse + landing-protokoll)
7.  Skriv MANIFEST.json med all metadata
8.  Auto-detekt runtime (Claude eller Codex)
9.  For hver instans:
    a. Skriv VS_XXXX_prompt.md
    b. runtime.run() → subprocess.Popen(...) 
    c. Proses leser prompt fra stdin, skriver output via Write-tool
10. Monitorer .done-filer i sanntid
11. Når en prosess eksiterer:
    a. Lukk stashede fil-handles
    b. Opprett .done hvis Claude/Codex ikke gjorde det
    c. Hvis output_path mangler: skriv fallback-melding
12. Når ALLE instanser har .done:
    a. mkdir DEBRIEF.lock (atomisk)
    b. debrief.py → samle outputs, regne confidence-snitt
    c. Skriv FLT_XXX_debrief.md til 30-debrief/
    d. Oppdater CASES.md og INDEX.md
13. Skriv ut sammendrag til terminal og eksit
```

### Runtime-kontrakten

Alle runtime-klasser implementerer `Runtime`-abstraksjonen:

```python
class Runtime(ABC):
    name: str
    
    @abstractmethod
    def run(
        self, *,
        prompt: str,
        model: str,
        cwd: Path,
        output_path: Path,
        log_path: Path,
        instance_id: str,
        seed: str,
        env: Optional[dict] = None,
    ) -> subprocess.Popen: ...
    
    @abstractmethod
    def is_available(self) -> bool: ...
    
    def resolve_model(self, alias: str) -> str: ...
```

En runtime får ansvar for å:
1. Starte en subprocess som kjører AI-en
2. Sørge for at prompten leveres til AI-en
3. Sørge for at output havner i `output_path`
4. Returnere en `Popen` så `launch.py` kan monitorere

**Modell-aliaser** er runtime-agnostiske: `small` → haiku (Claude) eller gpt-5.4-mini (Codex). Samme config fungerer på begge.

### Auto-detect

```python
def detect_runtime() -> Runtime:
    # Eksplisitt override
    if override := os.environ.get("SVERM_RUNTIME"):
        return _RUNTIMES[override]()
    
    # Claude prioriteres (mest modent per v1.0)
    if ClaudeRuntime().is_available():
        return ClaudeRuntime()
    
    # Codex som fallback
    if CodexRuntime().is_available():
        return CodexRuntime()
    
    raise RuntimeError("Ingen runtime funnet.")
```

---

## Fil-kontrakter

Disse filformatene er kontrakten mellom lagene. Endres de, kan andre kjørende flights eller eldre rapporter bli inkompatible.

### `VS_XXXX_output.md` — instansens analyse

```markdown
# VS_XXXX — {case-tittel}
seed: {ord1} | {ord2} | {ord3} | {ord4} | {ord5}
model: {model-alias}

## Oppsummering
...

## Analyse
...

## Anbefaling
...

---

confidence: 0.XX
```

- Headeren må være de første 3 linjene
- `confidence: 0.XX` skal være siste ikke-tomme linje i filen
- Alt imellom er fritt format — markdown med seksjoner

`debrief.py` parser confidence-tallet via regex på siste linje.

### `MANIFEST.json` — flight-metadata

```json
{
  "flight_id": "FLT_001",
  "mode": "focus",
  "launched_at": "2026-04-10 14:32",
  "instance_count": 9,
  "focus_case_id": 1,
  "focus_case_title": "Bør familien kjøpe rekkehuset nå?",
  "instances": [
    {
      "id": "VS_008288",
      "seed_words": "økonom | umiddelbart | renterisk | livskvalitet | analytisk",
      "seed_axes": "perspektiv | tidshorisont | risiko | verdi | beslutningsmodell",
      "model": "medium"
    }
  ]
}
```

### `VS_XXXX.done` — landing-signal

Tom fil. Eksistens betyr "denne instansen har levert". Opprettes enten av instansen selv (via Write-verktøyet) eller av `launch.py`-cleanup når prosessen eksiterer.

### `DEBRIEF.lock/` — atomisk debrief-lås

Tom mappe. Opprettes via `mkdir()` som er atomisk på de fleste filsystemer. Første prosess som klarer å opprette mappen vinner retten til å kjøre debrief. Andre prosesser sjekker og hopper over.

---

## Ekstensjonspunkter

### Legge til en ny runtime

1. Arv fra `Runtime` i `sverm/runtime.py`
2. Implementer `is_available()` og `run()`
3. Registrer i `_RUNTIMES`-dict
4. Legg til i `detect_runtime()`-fallback-logikken

Eksempel: en `GeminiRuntime` som kjører `gemini-cli` som subprocess.

### Legge til et nytt mode (inbox, batch)

Focus-modus er implementert per v1.0. For å legge til flere:

1. Legg til mode-håndtering i `cli.py` launch parser
2. Skriv `cmd_launch_inbox()` / `cmd_launch_batch()` i launch.py
3. Tilpass prompt-generering — inbox lar instanser velge case, batch partisjonerer
4. Oppdater `build_focus_prompt()` til å bli `build_prompt()` med mode-parameter
5. Oppdater debrief til å forstå mode-spesifikk aggregering

### Legge til en ny seed-dimensjon

Ingen kode-endring trengs. Bare legg til flere akser i JSON-configen. `setup.py` og `launch.py` håndterer variabelt antall akser.

### Legge til en ny kommando

1. Registrer subparser i `cli.py`
2. Legg til kommando-handler (`cmd_YOUR_COMMAND()`)
3. Implementer logikken i en ny modul eller eksisterende

---

## Databasedesign — hvorfor SQLite?

- **Portable** — `sverm.db` er én fil. Hele prosjektet kan kopieres, versjonskontrolleres, sendes som zip
- **Transaksjoner** — flight-state kan ikke bli korrupt ved krasj
- **Null server** — ingen daemon, ingen port, ingen config
- **Biblioteksstøtte** — sqlite3 er i Python-standard
- **Mange små skriv** — svermen er skrive-intensiv men ikke tung (få tusen rader per flight)

Ulempe: dårlig samtidighet ved mange parallelle skriv. Vi har mitigert ved å sørge for at bare launch.py/debrief.py skriver til DB — instansene selv skriver bare til flat-filer.

---

## Feilhåndtering og resiliens

- **Instans som krasjer** — `launch.py` monitor-loop oppdager, logger fallback-melding, oppretter .done
- **Runtime som mangler** — `detect_runtime()` gir klar feilmelding med install-link
- **JSON-config med feil** — `config.py` validerer med klare feilmeldinger per felt
- **SQLite-lock** — sjeldent, men ved samtidige skriv prøver vi tre ganger med backoff
- **Interrupted flight** — MANIFEST.json finnes, .done-filer mangler. `launch.py` har ingen resume i v1.0 — manuelt cleanup kreves. Planlagt for v1.1.

---

## Ytelse

På en moderne Mac eller Windows-laptop:
- **9 instanser haiku**: ~30-60 sekunder total wall-clock (parallelle subprocesser)
- **9 instanser sonnet**: ~90-180 sekunder
- **9 instanser opus**: ~3-8 minutter

Parallellisering er naturlig — hver instans er et separat subprocess. CPU er ikke flaskehalsen, det er API-tiden.

Disk I/O er minimal. SQLite-skriv er få per sekund. Fil-writes fra AI-instansene er serielle.

---

## Hva som IKKE er implementert per v1.0

- Inbox-modus (hver instans velger cases selv)
- Batch-modus (partisjoner alle cases)
- Resume av avbrutt flight
- Sub-agents (instanser som spawner egne hjelper-instanser)
- Synthesis-modus (meta-analyse på tvers av flere flights)
- Heatmap og visualisering
- PyPI-publisering (kommer)
- Web-UI (sannsynligvis aldri — CLI er bevisst)

Alt ovenfor er enten planlagt for v1.1 eller bevisst utelatt.

---

## Filer å lese hvis du vil forstå mer

- **Grunnleggende:** `sverm/cli.py` → `sverm/launch.py` → `sverm/runtime.py`
- **Datamodell:** `sverm/models.py` → `sverm/db.py`
- **Prosjektoppsett:** `sverm/setup.py` → `sverm/config.py`
- **Rapportgenerering:** `sverm/debrief.py`

Alle moduler er dokumentert med norske kommentarer og docstrings.
