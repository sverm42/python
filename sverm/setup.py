"""setup.py — Opprett et nytt sverm-prosjekt fra JSON config.

Erstatter setup.sh. Samme filstruktur, samme DB-kontrakt,
men i ren Python — fungerer på Mac, Windows og Linux.
"""

from __future__ import annotations

from pathlib import Path

from sverm.config import load_project_config
from sverm.db import init_schema, insert_seeds, insert_cases, generate_cases_md
from sverm.encoding import write_text
from sverm.models import ProjectConfig
from sverm.paths import discover_project_paths


# ============================================================
# Prosjektopprettelse
# ============================================================

def find_next_prefix(projects_dir: Path) -> int:
    """Finn neste ledige numerisk prefiks i prosjektmappen."""
    if not projects_dir.exists():
        return 1
    existing = []
    for d in projects_dir.iterdir():
        if d.is_dir():
            name = d.name
            # Prøv å hente det numeriske prefikset
            parts = name.split("-", 1)
            if parts[0].isdigit():
                existing.append(int(parts[0]))
    return max(existing, default=0) + 1


def generate_claude_md(config: ProjectConfig, project_dir: Path) -> str:
    """Generer CLAUDE.md fra prosjektconfig."""
    lines = [
        f"# CLAUDE.md — Sverm-Prosjekt: {config.name}",
        "",
        "---",
        "",
        "## Prosjektkontekst",
        "",
        f"**Domene:** {config.domain}",
        "",
        "**Nøkkelinfo:**",
    ]

    for item in config.key_info:
        lines.append(f"- {item}")

    lines.extend([
        "",
        f"**Mål:** {config.goal}",
        "",
        "---",
        "",
        "## For Sverm-Instanser",
        "",
        "Hvis du er en AI-instans spawnet av dette systemet:",
        "",
        "1. **Les prompten din** — den inneholder din ID, seed og oppdrag",
        "2. **Les forrige debrief(er) i `30-debrief/`** — bygg videre, ikke gjenta",
        "3. **La seeden farge perspektivet aktivt**",
        "4. **Skriv output til angitt fil** — `20-flights/FLT_XXX/VS_XXXX_output.md`",
        "5. **Start output med metadata-header:**",
        "   ```",
        "   # VS_XXXX — [Case-tittel]",
        "   seed: ord1 | ord2 | ord3 | ord4 | ord5",
        "   model: haiku/sonnet/opus",
        "   ```",
        "",
        "### Output-kvalitet",
        "",
        "- **Vær konkret og gjennomførbar**",
        "- **Navngi ressursbehov** — tid, penger, kompetanse, koordinering",
        "- **Dissens er verdifullt** — si hva som er naivt, hva som vil mislykkes",
        "- **Avslutt med neste steg** — ett konkret handlingspunkt",
        "",
        "---",
        "",
        "## Sverm-Arkitektur",
        "",
        "### Quick Start",
        "",
        "```bash",
        "# Se alle åpne cases",
        "sverm launch --help",
        "",
        "# Start flight: 9 instanser på case #1",
        "sverm launch focus 1 --medium -n 9",
        "",
        "# Dry-run (test uten å starte ekte instanser)",
        "sverm launch focus 1 --medium -n 4 --dry-run",
        "```",
        "",
        "Hvis du ikke har `sverm` installert globalt, kan du bytte ut `sverm` med",
        "`python cli.py` fra prosjektets rotmappe.",
        "",
        "### Tre Flight-Modi",
        "",
        "| Mode | Beskrivelse |",
        "|------|-------------|",
        "| **Focus** | Alle instanser jobber med én case. 9+ perspektiver på én problemstilling. |",
        "| **Inbox** | Hver instans velger 1-3 cases selv. Dekker mange cases bredt. |",
        "| **Batch** | Partisjonér alle cases og fordel på instansene. Full dekning. |",
        "",
        "---",
        "",
        "## Frequency Seeds",
        "",
        "Hver instans får en unik kombinasjon av ord, ett fra hver akse.",
        "Ordene farger perspektivet uten å begrense det.",
        "",
    ])

    # Seed-akser
    for i, axis in enumerate(config.axes, 1):
        lines.append(f"### Dimensjon {i}: {axis.name.capitalize()}")
        lines.append("")
        has_desc = any(w.description for w in axis.words)
        if has_desc:
            lines.append("| Ord | Vekt | Hva det gjør |")
            lines.append("|-----|------|-------------|")
            for w in axis.words:
                lines.append(f"| {w.word} | {w.weight} | {w.description} |")
        else:
            lines.append("| Ord | Vekt |")
            lines.append("|-----|------|")
            for w in axis.words:
                lines.append(f"| {w.word} | {w.weight} |")
        lines.append("")

    return "\n".join(lines)


def generate_context_md(config: ProjectConfig) -> str:
    """Generer CONTEXT.md — kortfattet prosjektkontekst for instanser."""
    lines = [
        f"# {config.name}",
        "",
        f"**Domene:** {config.domain}",
        "",
        f"**Mål:** {config.goal}",
        "",
        "**Nøkkelinfo:**",
    ]
    for item in config.key_info:
        lines.append(f"- {item}")
    lines.append("")
    return "\n".join(lines)


def setup_project(
    config_path: Path,
    projects_dir: Path,
    name_override: str | None = None,
) -> Path:
    """Opprett et komplett sverm-prosjekt fra JSON config.
    
    Returnerer path til opprettet prosjektmappe.
    """
    config = load_project_config(config_path)
    name = name_override or config.name

    # Finn neste prefiks
    prefix = find_next_prefix(projects_dir)
    project_dir = projects_dir / f"{prefix}-{name}"

    print(f"\n  sverm setup")
    print(f"  ===========")
    print(f"  Project: {name}")
    print(f"  Domain:  {config.domain[:60]}...")
    print(f"  Directory: {project_dir}")
    print()

    # [1/5] Opprett mappestruktur
    print("  [1/5] Creating directory structure...")
    paths = discover_project_paths(project_dir)
    for d in [paths.cases_dir, paths.flights_dir, paths.debrief_dir,
              paths.scripts_dir, paths.system_dir]:
        d.mkdir(parents=True, exist_ok=True)

    # [2/5] Skriv CLAUDE.md
    print("  [2/5] Writing CLAUDE.md...")
    claude_content = generate_claude_md(config, project_dir)
    write_text(paths.claude_path, claude_content)

    # Skriv CONTEXT.md
    context_content = generate_context_md(config)
    write_text(paths.context_path, context_content)

    # [3/5] Initialiser database
    print("  [3/5] Initializing database...")
    init_schema(paths.database_path)

    # Sett inn seeds
    insert_seeds(paths.database_path, config.axes)

    # Sett inn cases
    cases_data = [
        {"title": c.title, "description": c.description,
         "priority": c.priority, "tags": c.tags}
        for c in config.cases
    ]
    insert_cases(paths.database_path, cases_data)

    # [4/5] Generer CASES.md
    print("  [4/5] Generating CASES.md...")
    cases_md = generate_cases_md(paths.database_path, project_dir=project_dir)
    write_text(paths.cases_dir / "CASES.md", cases_md)

    # [5/5] Skriv runtime-markør
    print("  [5/5] Writing runtime marker...")
    write_text(paths.system_dir / "RUNTIME", "python\n")

    print()
    print("  ==========================================")
    print("  PROSJEKT OPPRETTET")
    print("  ==========================================")
    print(f"  {project_dir}")
    print()
    print("  Neste steg:")
    print(f"    sverm launch focus 1 --medium -n 9 --project {project_dir}")
    print(f"    sverm launch focus 1 --medium -n 4 --dry-run --project {project_dir}")
    print("  ==========================================")

    return project_dir
