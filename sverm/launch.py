"""launch.py — Start en sverm-flight.

Tre moduser støttes:
- **focus**: alle N instanser jobber på én case (dybde)
- **inbox**: hver instans ser alle åpne cases og velger 1-3 selv basert på seed (bredde m/ agency)
- **batch**: alle åpne cases partisjoneres deterministisk mellom N instanser (full dekning)

Felles flyt:
1. Les cases og seeds fra sverm.db
2. Alloker seeds (vektet random, én per akse per instans)
3. Bygg modus-spesifikke prompter
4. Registrer flight og instanser i DB
5. Skriv MANIFEST.json
6. Start N parallelle prosesser via runtime
7. Overvåk .done-filer (med --timeout)
8. Når alle er ferdige: oppdater DB-status og kjør debrief
"""

from __future__ import annotations

import json
import subprocess
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

from sverm import db
from sverm.debrief import generate_debrief
from sverm.encoding import write_text
from sverm.models import Case, Flight, Instance, SeedAssignment
from sverm.paths import discover_project_paths
from sverm.runtime import Runtime, RuntimeProcess, get_runtime, detect_runtime


# ============================================================
# Prompt-bygging
# ============================================================

def build_focus_prompt(
    *,
    instance_id: str,
    flight_id: str,
    model: str,
    seed: SeedAssignment,
    case_id: int,
    case_title: str,
    case_description: str,
    instance_count: int,
    flight_dir: Path,
    project_dir: Path,
    db_path: Path,
    debrief_dir: Path,
) -> str:
    """Bygg prompt for focus mode."""
    
    # Sjekk for tidligere syntese
    synthesis_ref = ""
    case_prefix = f"CASE_{case_id:03d}_synthesis"
    synthesis_files = sorted(debrief_dir.glob(f"{case_prefix}*.md"), reverse=True)
    if synthesis_files:
        latest = synthesis_files[0]
        size = latest.stat().st_size
        if size >= 100_000:
            synthesis_ref = (
                f"\n## Syntese fra Tidligere Runder\n\n"
                f"En syntese finnes (`30-debrief/{latest.name}`) men er for stor "
                f"til å inkludere inline. Les den for kontekst.\n"
            )
        else:
            content = latest.read_text(encoding="utf-8")
            synthesis_ref = (
                f"\n## Syntese fra Tidligere Runder\n\n"
                f"En meta-syntese av tidligere flights på denne casen. "
                f"**Ikke gjenta det som allerede er funnet** — utdyp, utfordre, "
                f"utforsk blindsonene.\n\n"
                f"<synthesis>\n{content}\n</synthesis>\n"
            )

    # Sjekk for tidligere debriefs (kun hvis ingen syntese)
    prev_debriefs = ""
    if not synthesis_files:
        conn = db.connect(db_path)
        try:
            rows = conn.execute(
                "SELECT id FROM flights WHERE focus_case_id=? AND id!=? "
                "AND status IN ('landed','debriefed') ORDER BY launched_at",
                (case_id, flight_id),
            ).fetchall()
            debrief_files = []
            for row in rows:
                dfile = debrief_dir / f"{row['id']}_debrief.md"
                if dfile.exists():
                    debrief_files.append(f"- `30-debrief/{dfile.name}`")
            if debrief_files:
                prev_debriefs = (
                    "\n## Tidligere Analyser\n\n"
                    "Denne casen har blitt analysert i tidligere flights. "
                    "Les debrief-rapportene for å bygge videre.\n"
                    + "\n".join(debrief_files) + "\n"
                )
        finally:
            conn.close()

    prompt = f"""# Sverm-Instans

## Din Identitet
- **Instans-ID:** {instance_id}
- **Flight:** {flight_id}
- **Modell:** {model}

## Din Frequency Seed
`{seed.label}`

La disse ordene farge perspektivet ditt. De er ikke begrensninger — de er linser.
Aksene er: {seed.axis_label}

## Oppdrag (Focus Mode)
**Case #{case_id}: {case_title}**

{case_description}

## Instruksjoner
1. Les casen nøye
2. La din frequency seed påvirke *hvordan* du ser problemet
3. Skriv din analyse/forslag (500-1500 ord)
4. Skriv output til: {flight_dir}/{instance_id}_output.md
5. Start output-filen med:
   ```
   # {instance_id} — {case_title}
   seed: {seed.label}
   model: {model}
   ```
6. Avslutt output-filen med denne linjen helt til slutt (ETTER all analyse):
   ```
   confidence: 0.X
   ```
   (0.0 = veldig usikker, 1.0 = svært sikker. Vær ærlig.)

## Sub-Agents
Hvis du trenger å spawne sub-agents, gi dem ID: **{instance_id}_XXXXX** (5 tilfeldige siffer).

## Prosjektkontekst
Se prosjektets CLAUDE.md for kontekst.
Database med cases: {db_path}
{prev_debriefs}{synthesis_ref}
## Landing-Protokoll

Når du er ferdig:

1. **Skriv output-filen** til den oppgitte pathen
2. **Avslutt**

Python-orkestratoren håndterer `.done`, `DEBRIEF.lock`, monitorering og debrief etter at prosessen din er ferdig.
"""
    return prompt


def _format_cases_inbox(cases: list[Case]) -> str:
    """Formater en liste med cases til en markdown-inbox som kan vises til en instans."""
    lines: list[str] = []
    for c in cases:
        lines.append(f"### Case #{c.id}: {c.title}")
        lines.append(f"*Prioritet: {c.priority}*" + (f" · *Tags: {c.tags}*" if c.tags else ""))
        lines.append("")
        lines.append(c.description)
        lines.append("")
    return "\n".join(lines).rstrip()


def _multi_case_output_format_block(instance_id: str, cases_label: str) -> str:
    """Felles beskrivelse av output-format for inbox/batch. Må matche parseren i debrief.py."""
    return f"""## Output-format (KRITISK — MÅ følges eksakt)

Skriv output-filen slik:

```
# {instance_id} — Multi-Case Flight
seed: [dine seed-ord]
model: [modellnavn]
cases_worked: {cases_label}

## Case #N: [case-tittel]

[din analyse av case N, 300-800 ord]

confidence: 0.X

## Case #M: [case-tittel]

[din analyse av case M]

confidence: 0.X
```

Regler:
- Start HVER case-analyse med `## Case #N:` der N er case-ID (samme tall som i oppgaven)
- Avslutt HVER case-analyse med `confidence: 0.X` på egen linje (0.0 = veldig usikker, 1.0 = svært sikker)
- `cases_worked:` på metadata-linja er en kommaseparert liste over case-ID-ene du faktisk analyserer
- Orkestratoren parser disse headerne automatisk — hvis du skriver dem feil, havner analysen din ikke i debriefen
"""


def build_inbox_prompt(
    *,
    instance_id: str,
    flight_id: str,
    model: str,
    seed: SeedAssignment,
    cases: list[Case],
    pick_min: int,
    pick_max: int,
    flight_dir: Path,
    project_dir: Path,
    db_path: Path,
) -> str:
    """Bygg prompt for inbox mode.

    Instansen får hele listen av åpne cases og blir bedt om å velge pick_min-pick_max
    basert på seed-affinitet. Den har agency — velger selv hva den dras mot.
    """
    inbox_text = _format_cases_inbox(cases)
    format_block = _multi_case_output_format_block(instance_id, "1, 3  (eksempel)")

    prompt = f"""# Sverm-Instans (Inbox Mode)

## Din Identitet
- **Instans-ID:** {instance_id}
- **Flight:** {flight_id}
- **Modell:** {model}

## Din Frequency Seed
`{seed.label}`

La disse ordene farge perspektivet ditt og — i denne modusen — hvilke cases du dras mot.
Aksene er: {seed.axis_label}

## Oppdrag (Inbox Mode)

Du ser en inbox med {len(cases)} åpne cases. Ditt oppdrag er å velge
**{pick_min}-{pick_max} cases** som din frequency seed er spesielt godt rustet til
å analysere, og skrive en analyse for hver av dem.

La seeden farge hvilke cases du velger — en instans med seeden
"økonom | ..." vil kanskje dras mot cases om penger, mens en
"forelder | ..."-instans dras mot livskvalitet-cases. Dette er hele
poenget med inbox mode: du ser det DU ser tydeligst fra din linse.

Du trenger ikke dekke alle cases. Andre instanser i flighten dekker de
du velger bort. Velg det du er best rustet for, og gå i dybden.

## Inbox — {len(cases)} Åpne Cases

{inbox_text}

## Instruksjoner

1. Les hele inboxen
2. Velg {pick_min}-{pick_max} cases som din seed er best rustet for — vær ærlig
3. Skriv én analyse (300-800 ord) per valgt case
4. Skriv output til: {flight_dir}/{instance_id}_output.md

{format_block}

## Sub-Agents
Hvis du trenger å spawne sub-agents, gi dem ID: **{instance_id}_XXXXX** (5 tilfeldige siffer).

## Prosjektkontekst
Se prosjektets CLAUDE.md for kontekst.
Database med cases: {db_path}

## Landing-Protokoll

Når du er ferdig:

1. **Skriv output-filen** med alle valgte case-analyser i riktig format
2. **Avslutt**

Python-orkestratoren håndterer `.done`, monitorering og debrief etter at prosessen din er ferdig.
"""
    return prompt


def build_batch_prompt(
    *,
    instance_id: str,
    flight_id: str,
    model: str,
    seed: SeedAssignment,
    assigned_cases: list[Case],
    total_cases: int,
    instance_count: int,
    flight_dir: Path,
    project_dir: Path,
    db_path: Path,
) -> str:
    """Bygg prompt for batch mode.

    Instansen får en fastsatt delmengde av alle åpne cases og blir bedt om å analysere
    ALLE sammen. Orkestratoren har partisjonert på forhånd — instansen har ingen agency.
    """
    cases_text = _format_cases_inbox(assigned_cases)
    cases_label = ", ".join(str(c.id) for c in assigned_cases)
    format_block = _multi_case_output_format_block(instance_id, cases_label)

    prompt = f"""# Sverm-Instans (Batch Mode)

## Din Identitet
- **Instans-ID:** {instance_id}
- **Flight:** {flight_id}
- **Modell:** {model}

## Din Frequency Seed
`{seed.label}`

La disse ordene farge perspektivet ditt. Aksene er: {seed.axis_label}

## Oppdrag (Batch Mode)

Flighten partisjonerer alle {total_cases} åpne cases mellom {instance_count} instanser.
Du er tildelt **{len(assigned_cases)} cases** — analyser ALLE sammen, én etter én.
La seeden farge *hvordan* du leser hver case, men dropp ingen.

Forskjellen fra inbox mode: her har orkestratoren bestemt hva du skal ta.
Du har ingen valg. Full dekning er målet — andre instanser har fått de øvrige casene.

## Dine {len(assigned_cases)} Tildelte Cases

{cases_text}

## Instruksjoner

1. Les alle dine tildelte cases
2. Skriv én analyse (300-800 ord) per case — analyser ALLE, ikke hopp over noen
3. Skriv output til: {flight_dir}/{instance_id}_output.md

{format_block}

## Sub-Agents
Hvis du trenger å spawne sub-agents, gi dem ID: **{instance_id}_XXXXX** (5 tilfeldige siffer).

## Prosjektkontekst
Se prosjektets CLAUDE.md for kontekst.
Database med cases: {db_path}

## Landing-Protokoll

Når du er ferdig:

1. **Skriv output-filen** med alle dine tildelte case-analyser i riktig format
2. **Avslutt**

Python-orkestratoren håndterer `.done`, monitorering og debrief etter at prosessen din er ferdig.
"""
    return prompt


# ============================================================
# Instans-ID allokering
# ============================================================

def allocate_instance_ids(
    db_path: Path,
    count: int,
    project_name: str,
    flight_id: str,
) -> list[str]:
    """Alloker instans-IDer.
    
    Prøver sverm-id (HQ) først. Faller tilbake til lokal sekvens.
    """
    import shutil
    import subprocess

    if shutil.which("sverm-id"):
        try:
            result = subprocess.run(
                ["sverm-id", "alloc", "vs",
                 "--n", str(count),
                 "--project", project_name,
                 "--flight", flight_id],
                capture_output=True, text=True, timeout=10,
            )
            # Filtrer ut advarsler, ta siste linje med IDer
            lines = [l for l in result.stdout.strip().split("\n")
                     if l and not l.startswith("⚠") and not l.startswith("  ")]
            if lines:
                ids = lines[-1].split()
                if len(ids) == count:
                    return ids
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass

    # Fallback: lokal sekvens fra DB
    return db.generate_instance_ids(db_path, count)


# ============================================================
# MANIFEST
# ============================================================

def write_manifest(
    flight_dir: Path,
    flight_id: str,
    mode: str,
    timestamp: str,
    instances: list[dict],
    focus_case_id: Optional[int] = None,
    focus_case_title: Optional[str] = None,
) -> Path:
    """Skriv MANIFEST.json for flighten."""
    manifest = {
        "flight_id": flight_id,
        "mode": mode,
        "launched_at": timestamp,
        "instance_count": len(instances),
    }
    if focus_case_id is not None:
        manifest["focus_case_id"] = focus_case_id
    if focus_case_title:
        manifest["focus_case_title"] = focus_case_title
    manifest["instances"] = instances

    path = flight_dir / "MANIFEST.json"
    write_text(path, json.dumps(manifest, indent=2, ensure_ascii=False))
    return path


# ============================================================
# Monitor
# ============================================================

def monitor_flight(
    flight_dir: Path,
    instance_count: int,
    processes: list[RuntimeProcess],
    poll_interval: float = 2.0,
    timeout: int = 900,
) -> int:
    """Overvåk flight-progresjon via .done-filer.

    Returnerer antall ferdige instanser.

    `timeout` er maks antall sekunder hele flighten får på seg fra start til
    siste instans har landet. 0 = uendelig (gammel oppførsel). Hvis timeout
    overskrides, terminerer monitor alle gjenværende prosesser, skriver en
    timeout-markør i output-filen og returnerer antall instanser som rakk
    å lande.
    """
    print(f"\n  Monitoring {instance_count} instances...")
    if timeout > 0:
        print(f"  Timeout: {timeout}s for hele flighten")
    last_count = 0
    start = time.monotonic()

    def _close_handles(proc: subprocess.Popen) -> None:
        for attr in ("_sverm_prompt_handle", "_sverm_log_handle"):
            handle = getattr(proc, attr, None)
            if handle is not None and not handle.closed:
                handle.close()

    def _force_done(runtime_proc: RuntimeProcess, reason: str) -> None:
        """Skriv en stub-output og .done-fil for en instans som ikke landet."""
        if not runtime_proc.output_path.exists():
            runtime_proc.output_path.write_text(
                "# Flight output mangler\n\n"
                f"Instans: {runtime_proc.instance_id}\n"
                f"Årsak: {reason}\n",
                encoding="utf-8",
            )
        done_path = flight_dir / f"{runtime_proc.instance_id}.done"
        done_path.touch()

    while True:
        for runtime_proc in processes:
            proc = runtime_proc.process
            if proc.poll() is not None:
                _close_handles(proc)
                done_path = flight_dir / f"{runtime_proc.instance_id}.done"
                if not done_path.exists():
                    _force_done(
                        runtime_proc,
                        f"prosessen avsluttet med kode {proc.returncode} "
                        "før output-filen ble skrevet",
                    )

        done_files = list(flight_dir.glob("*.done"))
        done_count = len(done_files)

        if done_count != last_count:
            print(f"  {done_count}/{instance_count} instances landed")
            last_count = done_count

        if done_count >= instance_count:
            print(f"  All {instance_count} instances landed!")
            return done_count

        # Sjekk om prosesser har krasjet
        all_dead = all(p.process.poll() is not None for p in processes)
        if all_dead and done_count < instance_count:
            print(f"  WARNING: All processes exited but only {done_count}/{instance_count} .done files found")
            return done_count

        # Timeout-vakt: drep hengende prosesser og marker dem som timeout.
        if timeout > 0 and (time.monotonic() - start) > timeout:
            print(
                f"  TIMEOUT: {timeout}s nådd — terminerer "
                f"{instance_count - done_count} hengende instans(er)"
            )
            for runtime_proc in processes:
                proc = runtime_proc.process
                done_path = flight_dir / f"{runtime_proc.instance_id}.done"
                if done_path.exists():
                    continue
                if proc.poll() is None:
                    try:
                        proc.terminate()
                        try:
                            proc.wait(timeout=5)
                        except subprocess.TimeoutExpired:
                            proc.kill()
                            proc.wait(timeout=5)
                    except Exception:
                        pass
                _close_handles(proc)
                _force_done(runtime_proc, f"timeout etter {timeout}s")
            done_count = len(list(flight_dir.glob("*.done")))
            return done_count

        time.sleep(poll_interval)


# ============================================================
# Launch: Focus Mode
# ============================================================

def launch_focus(
    *,
    project_dir: Path,
    case_id: int,
    model: str = "small",
    instance_count: int = 4,
    runtime: Optional[Runtime] = None,
    dry_run: bool = False,
    monitor: bool = True,
    timeout: int = 900,
) -> str:
    """Start en focus-flight.

    Returnerer flight-ID.
    """
    from sverm.runtime import DryRunRuntime

    paths = discover_project_paths(project_dir)
    db_path = paths.database_path

    if not db_path.exists():
        raise FileNotFoundError(f"Database ikke funnet: {db_path}. Kjør setup først.")

    # Hent case
    case = db.get_case(db_path, case_id)
    if case is None:
        raise ValueError(f"Case #{case_id} ikke funnet")

    print(f"\n  FOCUS MODE: Case #{case_id} — {case.title}")

    # Velg runtime
    if dry_run:
        rt = DryRunRuntime()
    elif runtime:
        rt = runtime
    else:
        rt = detect_runtime()
    print(f"  Runtime: {rt.name}")

    # Opprett flight
    flight_id = db.next_flight_id(db_path)
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")

    flight_dir = paths.flights_dir / flight_id
    flight_dir.mkdir(parents=True, exist_ok=True)

    # Registrer flight i DB
    flight = Flight(
        id=flight_id,
        mode="focus",
        model=model,
        instance_count=instance_count,
        focus_case_id=case_id,
        status="preparing",
        launched_at=timestamp,
    )
    db.create_flight(db_path, flight)

    print(f"  Flight: {flight_id} ({instance_count} instances)")

    # Generer seeds
    print("  Generating frequency seeds...")
    seeds: list[SeedAssignment] = []
    for _ in range(instance_count):
        seed = db.pick_seed(db_path)
        seeds.append(seed)

    # Alloker instans-IDer
    print("  Allocating instance IDs...")
    instance_ids = allocate_instance_ids(
        db_path, instance_count,
        project_dir.name, flight_id,
    )
    print(f"  IDs: {instance_ids[0]} — {instance_ids[-1]}")

    # Vis seeds
    for i, (iid, seed) in enumerate(zip(instance_ids, seeds)):
        print(f"    {iid}: {seed.label}")

    # Bygg prompts og skriv til filer
    print("  Writing prompt files...")
    prompt_files: list[Path] = []
    for iid, seed in zip(instance_ids, seeds):
        prompt_text = build_focus_prompt(
            instance_id=iid,
            flight_id=flight_id,
            model=model,
            seed=seed,
            case_id=case_id,
            case_title=case.title,
            case_description=case.description,
            instance_count=instance_count,
            flight_dir=flight_dir,
            project_dir=project_dir,
            db_path=db_path,
            debrief_dir=paths.debrief_dir,
        )
        prompt_path = flight_dir / f"{iid}_prompt.md"
        write_text(prompt_path, prompt_text)
        prompt_files.append(prompt_path)

    # Registrer instanser i DB
    instances = [
        Instance(
            id=iid,
            flight_id=flight_id,
            model=model,
            seed_words=seed.label,
        )
        for iid, seed in zip(instance_ids, seeds)
    ]
    db.register_instances(db_path, instances)

    # Skriv MANIFEST.json
    manifest_instances = [
        {"id": iid, "model": model, "seed": seed.label}
        for iid, seed in zip(instance_ids, seeds)
    ]
    write_manifest(
        flight_dir, flight_id, "focus", timestamp,
        manifest_instances,
        focus_case_id=case_id,
        focus_case_title=case.title,
    )

    # Start prosesser
    print(f"\n  Launching {instance_count} instances via {rt.name}...")
    processes: list[RuntimeProcess] = []

    for iid, seed, prompt_path in zip(instance_ids, seeds, prompt_files):
        prompt_text = prompt_path.read_text(encoding="utf-8")
        output_path = flight_dir / f"{iid}_output.md"
        log_path = flight_dir / f"{iid}_log.txt"

        proc = rt.run(
            prompt=prompt_text,
            model=model,
            cwd=project_dir,
            output_path=output_path,
            log_path=log_path,
            instance_id=iid,
            seed=seed.label,
        )

        processes.append(RuntimeProcess(
            instance_id=iid,
            process=proc,
            output_path=output_path,
            log_path=log_path,
            model=model,
            seed=seed.label,
        ))

    # Oppdater flight-status
    db.update_flight_status(db_path, flight_id, "launched")

    # Oppsummering
    print()
    print("  ==========================================")
    print(f"  FLIGHT {flight_id} LAUNCHED")
    print("  ==========================================")
    print(f"  Mode:      focus")
    print(f"  Case:      #{case_id} — {case.title}")
    print(f"  Instances: {instance_count}")
    print(f"  Runtime:   {rt.name}")
    print(f"  IDs:       {instance_ids[0]} — {instance_ids[-1]}")
    print(f"  Directory: {flight_dir}")
    print("  ==========================================")

    _finalize_flight(
        project_dir=project_dir,
        db_path=db_path,
        flight_id=flight_id,
        flight_dir=flight_dir,
        instance_count=instance_count,
        processes=processes,
        monitor=monitor,
        dry_run=dry_run,
        timeout=timeout,
    )

    return flight_id


# ============================================================
# Felles helpers for alle moduser
# ============================================================

def _finalize_flight(
    *,
    project_dir: Path,
    db_path: Path,
    flight_id: str,
    flight_dir: Path,
    instance_count: int,
    processes: list[RuntimeProcess],
    monitor: bool,
    dry_run: bool,
    timeout: int,
) -> None:
    """Kjør monitor → debrief → DB-oppdatering. Felles for alle moduser."""
    if monitor and not dry_run:
        landed = monitor_flight(flight_dir, instance_count, processes, timeout=timeout)
        if landed >= instance_count:
            db.update_flight_status(db_path, flight_id, "landed")
            lock_dir = flight_dir / "DEBRIEF.lock"
            try:
                lock_dir.mkdir()
            except FileExistsError:
                pass
            report_path = generate_debrief(project_dir, flight_id)
            print(f"\n  Flight {flight_id} landed successfully.")
            print(f"  Debrief: {report_path}")
    elif dry_run:
        # Dry-run: alle er allerede "ferdige"
        db.update_flight_status(db_path, flight_id, "landed")
        report_path = generate_debrief(project_dir, flight_id)
        print(f"\n  [dry-run] Flight {flight_id} completed.")
        print(f"  Debrief: {report_path}")


def _partition_cases(cases: list[Case], n: int) -> list[list[Case]]:
    """Partisjoner cases round-robin i n bøtter. Returnerer n lister (noen kan være tomme
    hvis n > len(cases))."""
    buckets: list[list[Case]] = [[] for _ in range(n)]
    for i, c in enumerate(cases):
        buckets[i % n].append(c)
    return buckets


def _write_multi_case_dry_run_output(
    output_path: Path, instance_id: str, seed_label: str, model: str, cases: list[Case]
) -> None:
    """Skriv en realistisk-formatert multi-case stub-output for dry-run, slik at
    debrief-parseren faktisk har noe å jobbe med."""
    lines = [
        f"# {instance_id} — Multi-Case Flight (dry-run)",
        f"seed: {seed_label}",
        f"model: {model}",
        f"cases_worked: {', '.join(str(c.id) for c in cases)}",
        "",
    ]
    for c in cases:
        lines.extend([
            f"## Case #{c.id}: {c.title}",
            "",
            "(Dry run — ingen ekte analyse. Dette er en stub for å verifisere",
            f"parser og debrief-flyt for {instance_id}.)",
            "",
            "confidence: 0.0",
            "",
        ])
    output_path.write_text("\n".join(lines), encoding="utf-8")


# ============================================================
# Launch: Inbox Mode
# ============================================================

def launch_inbox(
    *,
    project_dir: Path,
    model: str = "small",
    instance_count: int = 4,
    pick_min: int = 1,
    pick_max: int = 3,
    runtime: Optional[Runtime] = None,
    dry_run: bool = False,
    monitor: bool = True,
    timeout: int = 900,
) -> str:
    """Start en inbox-flight: hver instans ser alle åpne cases og velger pick_min-pick_max
    selv basert på seed-affinitet."""
    from sverm.runtime import DryRunRuntime

    paths = discover_project_paths(project_dir)
    db_path = paths.database_path

    if not db_path.exists():
        raise FileNotFoundError(f"Database ikke funnet: {db_path}. Kjør setup først.")

    # Hent alle åpne cases
    cases = db.get_open_cases(db_path)
    if not cases:
        raise ValueError("Ingen åpne cases i databasen. Legg inn cases først.")

    # Juster pick-range mot faktisk antall cases
    pick_max = min(pick_max, len(cases))
    pick_min = min(pick_min, pick_max)

    print(f"\n  INBOX MODE: {len(cases)} åpne cases, hver instans velger {pick_min}-{pick_max}")

    # Velg runtime
    if dry_run:
        rt = DryRunRuntime()
    elif runtime:
        rt = runtime
    else:
        rt = detect_runtime()
    print(f"  Runtime: {rt.name}")

    # Opprett flight
    flight_id = db.next_flight_id(db_path)
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")

    flight_dir = paths.flights_dir / flight_id
    flight_dir.mkdir(parents=True, exist_ok=True)

    flight = Flight(
        id=flight_id,
        mode="inbox",
        model=model,
        instance_count=instance_count,
        focus_case_id=None,
        status="preparing",
        launched_at=timestamp,
    )
    db.create_flight(db_path, flight)
    print(f"  Flight: {flight_id} ({instance_count} instances)")

    # Generer seeds
    print("  Generating frequency seeds...")
    seeds: list[SeedAssignment] = [db.pick_seed(db_path) for _ in range(instance_count)]

    # Alloker instans-IDer
    print("  Allocating instance IDs...")
    instance_ids = allocate_instance_ids(db_path, instance_count, project_dir.name, flight_id)
    print(f"  IDs: {instance_ids[0]} — {instance_ids[-1]}")

    for iid, seed in zip(instance_ids, seeds):
        print(f"    {iid}: {seed.label}")

    # Bygg prompts
    print("  Writing prompt files...")
    prompt_files: list[Path] = []
    for iid, seed in zip(instance_ids, seeds):
        prompt_text = build_inbox_prompt(
            instance_id=iid,
            flight_id=flight_id,
            model=model,
            seed=seed,
            cases=cases,
            pick_min=pick_min,
            pick_max=pick_max,
            flight_dir=flight_dir,
            project_dir=project_dir,
            db_path=db_path,
        )
        prompt_path = flight_dir / f"{iid}_prompt.md"
        write_text(prompt_path, prompt_text)
        prompt_files.append(prompt_path)

    # Registrer instanser i DB
    instances = [
        Instance(id=iid, flight_id=flight_id, model=model, seed_words=seed.label)
        for iid, seed in zip(instance_ids, seeds)
    ]
    db.register_instances(db_path, instances)

    # MANIFEST
    manifest_instances = [
        {"id": iid, "model": model, "seed": seed.label}
        for iid, seed in zip(instance_ids, seeds)
    ]
    write_manifest(flight_dir, flight_id, "inbox", timestamp, manifest_instances)

    # Start prosesser
    print(f"\n  Launching {instance_count} instances via {rt.name}...")
    processes: list[RuntimeProcess] = []
    import random
    for iid, seed, prompt_path in zip(instance_ids, seeds, prompt_files):
        prompt_text = prompt_path.read_text(encoding="utf-8")
        output_path = flight_dir / f"{iid}_output.md"
        log_path = flight_dir / f"{iid}_log.txt"

        proc = rt.run(
            prompt=prompt_text,
            model=model,
            cwd=project_dir,
            output_path=output_path,
            log_path=log_path,
            instance_id=iid,
            seed=seed.label,
        )

        # Dry-run: overskriv DryRunRuntime's generiske output med en multi-case stub
        # som er konsistent med hva parseren forventer
        if dry_run:
            picked_n = random.randint(pick_min, pick_max)
            picked = random.sample(cases, picked_n)
            picked.sort(key=lambda c: c.id)
            _write_multi_case_dry_run_output(output_path, iid, seed.label, model, picked)

        processes.append(RuntimeProcess(
            instance_id=iid,
            process=proc,
            output_path=output_path,
            log_path=log_path,
            model=model,
            seed=seed.label,
        ))

    db.update_flight_status(db_path, flight_id, "launched")

    print()
    print("  ==========================================")
    print(f"  FLIGHT {flight_id} LAUNCHED")
    print("  ==========================================")
    print(f"  Mode:      inbox")
    print(f"  Cases:     {len(cases)} åpne (instanser velger {pick_min}-{pick_max} hver)")
    print(f"  Instances: {instance_count}")
    print(f"  Runtime:   {rt.name}")
    print(f"  IDs:       {instance_ids[0]} — {instance_ids[-1]}")
    print(f"  Directory: {flight_dir}")
    print("  ==========================================")

    _finalize_flight(
        project_dir=project_dir,
        db_path=db_path,
        flight_id=flight_id,
        flight_dir=flight_dir,
        instance_count=instance_count,
        processes=processes,
        monitor=monitor,
        dry_run=dry_run,
        timeout=timeout,
    )

    return flight_id


# ============================================================
# Launch: Batch Mode
# ============================================================

def launch_batch(
    *,
    project_dir: Path,
    model: str = "small",
    instance_count: int = 4,
    runtime: Optional[Runtime] = None,
    dry_run: bool = False,
    monitor: bool = True,
    timeout: int = 900,
) -> str:
    """Start en batch-flight: alle åpne cases partisjoneres deterministisk mellom
    instance_count instanser. Full dekning."""
    from sverm.runtime import DryRunRuntime

    paths = discover_project_paths(project_dir)
    db_path = paths.database_path

    if not db_path.exists():
        raise FileNotFoundError(f"Database ikke funnet: {db_path}. Kjør setup først.")

    cases = db.get_open_cases(db_path)
    if not cases:
        raise ValueError("Ingen åpne cases i databasen. Legg inn cases først.")

    # Cap instance_count til antall cases — ingen vits i tomme instanser
    if instance_count > len(cases):
        print(f"  NOTE: reduserer instance_count fra {instance_count} til {len(cases)} "
              f"(en per case).")
        instance_count = len(cases)

    partitions = _partition_cases(cases, instance_count)
    total_cases = len(cases)

    print(f"\n  BATCH MODE: {total_cases} cases partisjonert mellom {instance_count} instanser")

    # Velg runtime
    if dry_run:
        rt = DryRunRuntime()
    elif runtime:
        rt = runtime
    else:
        rt = detect_runtime()
    print(f"  Runtime: {rt.name}")

    # Opprett flight
    flight_id = db.next_flight_id(db_path)
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")

    flight_dir = paths.flights_dir / flight_id
    flight_dir.mkdir(parents=True, exist_ok=True)

    flight = Flight(
        id=flight_id,
        mode="batch",
        model=model,
        instance_count=instance_count,
        focus_case_id=None,
        status="preparing",
        launched_at=timestamp,
    )
    db.create_flight(db_path, flight)
    print(f"  Flight: {flight_id}")

    # Seeds + IDer
    print("  Generating frequency seeds...")
    seeds: list[SeedAssignment] = [db.pick_seed(db_path) for _ in range(instance_count)]

    print("  Allocating instance IDs...")
    instance_ids = allocate_instance_ids(db_path, instance_count, project_dir.name, flight_id)
    print(f"  IDs: {instance_ids[0]} — {instance_ids[-1]}")

    for iid, seed, part in zip(instance_ids, seeds, partitions):
        assigned = ", ".join(f"#{c.id}" for c in part)
        print(f"    {iid}: [{assigned}] · seed: {seed.label}")

    # Bygg prompts
    print("  Writing prompt files...")
    prompt_files: list[Path] = []
    for iid, seed, part in zip(instance_ids, seeds, partitions):
        prompt_text = build_batch_prompt(
            instance_id=iid,
            flight_id=flight_id,
            model=model,
            seed=seed,
            assigned_cases=part,
            total_cases=total_cases,
            instance_count=instance_count,
            flight_dir=flight_dir,
            project_dir=project_dir,
            db_path=db_path,
        )
        prompt_path = flight_dir / f"{iid}_prompt.md"
        write_text(prompt_path, prompt_text)
        prompt_files.append(prompt_path)

    # Registrer instanser
    instances = [
        Instance(id=iid, flight_id=flight_id, model=model, seed_words=seed.label)
        for iid, seed in zip(instance_ids, seeds)
    ]
    db.register_instances(db_path, instances)

    # MANIFEST
    manifest_instances = [
        {"id": iid, "model": model, "seed": seed.label,
         "assigned_cases": [c.id for c in part]}
        for iid, seed, part in zip(instance_ids, seeds, partitions)
    ]
    write_manifest(flight_dir, flight_id, "batch", timestamp, manifest_instances)

    # Start prosesser
    print(f"\n  Launching {instance_count} instances via {rt.name}...")
    processes: list[RuntimeProcess] = []
    for iid, seed, prompt_path, part in zip(instance_ids, seeds, prompt_files, partitions):
        prompt_text = prompt_path.read_text(encoding="utf-8")
        output_path = flight_dir / f"{iid}_output.md"
        log_path = flight_dir / f"{iid}_log.txt"

        proc = rt.run(
            prompt=prompt_text,
            model=model,
            cwd=project_dir,
            output_path=output_path,
            log_path=log_path,
            instance_id=iid,
            seed=seed.label,
        )

        if dry_run:
            _write_multi_case_dry_run_output(output_path, iid, seed.label, model, part)

        processes.append(RuntimeProcess(
            instance_id=iid,
            process=proc,
            output_path=output_path,
            log_path=log_path,
            model=model,
            seed=seed.label,
        ))

    db.update_flight_status(db_path, flight_id, "launched")

    print()
    print("  ==========================================")
    print(f"  FLIGHT {flight_id} LAUNCHED")
    print("  ==========================================")
    print(f"  Mode:      batch")
    print(f"  Cases:     {total_cases} partisjonert ({'/'.join(str(len(p)) for p in partitions)})")
    print(f"  Instances: {instance_count}")
    print(f"  Runtime:   {rt.name}")
    print(f"  IDs:       {instance_ids[0]} — {instance_ids[-1]}")
    print(f"  Directory: {flight_dir}")
    print("  ==========================================")

    _finalize_flight(
        project_dir=project_dir,
        db_path=db_path,
        flight_id=flight_id,
        flight_dir=flight_dir,
        instance_count=instance_count,
        processes=processes,
        monitor=monitor,
        dry_run=dry_run,
        timeout=timeout,
    )

    return flight_id
