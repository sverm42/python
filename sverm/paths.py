from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ProjectPaths:
    project_root: Path
    cases_dir: Path
    flights_dir: Path
    debrief_dir: Path
    scripts_dir: Path
    system_dir: Path
    database_path: Path
    context_path: Path
    claude_path: Path
    index_path: Path


def discover_project_paths(start: Path) -> ProjectPaths:
    root = start.resolve()
    if root.is_file():
        root = root.parent

    return ProjectPaths(
        project_root=root,
        cases_dir=root / "10-cases",
        flights_dir=root / "20-flights",
        debrief_dir=root / "30-debrief",
        scripts_dir=root / "90-scripts",
        system_dir=root / "99-system",
        database_path=root / "sverm.db",
        context_path=root / "CONTEXT.md",
        claude_path=root / "CLAUDE.md",
        index_path=root / "INDEX.md",
    )

