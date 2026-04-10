"""cli.py — Entry point for sverm Python-orkestrering.

Kommandoer:
  sverm setup <config.json>
  sverm launch focus <case_id> --project 1
  sverm inspect --project 1
  sverm mirror --project 1
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from sverm.config import load_project_config
from sverm.paths import discover_project_paths
from sverm.platform import detect_platform


def _prepare_stdio() -> None:
    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name, None)
        if stream is None:
            continue
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            reconfigure(encoding="utf-8", errors="replace")


# ============================================================
# Prosjekt-resolver: --project 1 → cwd/10-projects/1-*/ eller ~/sverm-projects/1-*/
# ============================================================

def default_user_projects_dir() -> Path:
    """Default lokasjon for brukerens egne sverm-prosjekter."""
    return Path.home() / "sverm-projects"


def _project_search_dirs() -> list[Path]:
    """Mapper som skal sjekkes når --project N skal løses opp.

    Søker i denne rekkefølgen:
      1. cwd/10-projects/  — for repo-bundlede demoer (workshop-flyt)
      2. ~/sverm-projects/ — for prosjekter brukeren har laget med `sverm setup`

    Hvis SVERM_PROJECTS_DIR er satt, prioriteres den foran begge.
    """
    import os

    dirs: list[Path] = []
    env_dir = os.environ.get("SVERM_PROJECTS_DIR")
    if env_dir:
        dirs.append(Path(env_dir).expanduser())
    dirs.append(Path.cwd() / "10-projects")
    dirs.append(default_user_projects_dir())
    return dirs


def resolve_project(project_arg: str | Path | None) -> Path:
    """Løs opp --project til full prosjektpath.

    Aksepterer:
      - None → cwd
      - "1" eller "1-boligkjop" → første match i _project_search_dirs()
      - Full path → brukes direkte
    """
    if project_arg is None:
        return Path.cwd()

    p = str(project_arg)

    # Hvis det ser ut som et nummer eller "N-navn" (uten path-separator),
    # søk gjennom kjente prosjektmapper.
    if p.isdigit() or (p.split("-", 1)[0].isdigit() and "/" not in p and "\\" not in p):
        prefix = p.split("-", 1)[0]
        searched: list[Path] = []
        all_matches: list[Path] = []
        for projects_dir in _project_search_dirs():
            searched.append(projects_dir)
            if not projects_dir.exists():
                continue
            matches = [d for d in projects_dir.iterdir()
                       if d.is_dir() and d.name.startswith(f"{prefix}-")]
            if len(matches) == 1:
                return matches[0]
            if len(matches) > 1:
                names = ", ".join(d.name for d in matches)
                raise ValueError(
                    f"Flere prosjekter matcher '{p}' i {projects_dir}: {names}. "
                    f"Bruk full path eller et mer spesifikt prefix."
                )
            all_matches.extend(matches)

        # Ingen treff — bygg en hjelpsom feilmelding med tilgjengelige prosjekter.
        available: list[str] = []
        for d in searched:
            if d.exists():
                names = sorted(p.name for p in d.iterdir() if p.is_dir())
                if names:
                    available.append(f"  {d}:\n    " + "\n    ".join(names))
        if available:
            raise ValueError(
                f"Ingen prosjekter matcher '{p}'. Tilgjengelige prosjekter:\n"
                + "\n".join(available)
            )
        raise ValueError(
            f"Ingen prosjekter matcher '{p}'. Sjekkede mapper (ingen finnes):\n  "
            + "\n  ".join(str(d) for d in searched)
            + "\n\nKjør `sverm setup <config.json>` for å opprette et prosjekt, "
              "eller cd inn i den klonede sverm42/python-mappen for å bruke demoen."
        )

    # Full path
    return Path(p)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="sverm",
        description="Python-first orkestrering for Sverm — multi-perspektiv AI-analyse.",
    )
    sub = parser.add_subparsers(dest="command")

    # --- setup ---
    setup_p = sub.add_parser("setup", help="Opprett nytt sverm-prosjekt fra JSON config.")
    setup_p.add_argument("config", type=Path, help="Path til JSON config-fil")
    setup_p.add_argument("--projects-dir", type=Path, default=None,
                         help="Mappe for prosjekter (default: ~/sverm-projects/, "
                              "eller cwd/10-projects/ hvis du står i en klonet sverm-repo)")
    setup_p.add_argument("--name", type=str, default=None, help="Overstyr prosjektnavn")

    # --- launch ---
    launch_p = sub.add_parser("launch", help="Start en sverm-flight.")
    launch_sub = launch_p.add_subparsers(dest="mode")

    # launch focus
    focus_p = launch_sub.add_parser("focus", help="Focus mode: alle instanser på én case.")
    focus_p.add_argument("case_id", type=int, help="Case-ID å fokusere på")

    # Modell: --small/--medium/--large (runtime-agnostisk)
    model_group = focus_p.add_mutually_exclusive_group()
    model_group.add_argument("--small", dest="model", action="store_const", const="small",
                             help="Rask/billig (Claude: haiku, Codex: gpt-5.4-mini) [default]")
    model_group.add_argument("--medium", dest="model", action="store_const", const="medium",
                             help="Balansert (Claude: sonnet, Codex: gpt-5.4)")
    model_group.add_argument("--large", dest="model", action="store_const", const="large",
                             help="Dyp/dyr (Claude: opus, Codex: gpt-5.4)")
    focus_p.set_defaults(model="small")

    focus_p.add_argument("-n", "--count", type=int, default=4,
                         help="Antall instanser (default: 4)")
    focus_p.add_argument("--project", default=None,
                         help="Prosjekt: nummer (1), navn (1-boligkjop) eller full path")
    focus_p.add_argument("--runtime", type=str, default=None,
                         help="Runtime: claude, codex, dry-run (default: auto-detect)")
    focus_p.add_argument("--dry-run", action="store_true",
                         help="Simuler flight uten ekte prosesser")
    focus_p.add_argument("--no-monitor", action="store_true",
                         help="Ikke vent på at instanser lander")
    focus_p.add_argument("--timeout", type=int, default=900,
                         help="Maks sekunder å vente på at en instans lander "
                              "(default: 900). 0 = uendelig.")

    # --- inspect ---
    inspect_p = sub.add_parser("inspect", help="Vis prosjektstatus og struktur.")
    inspect_p.add_argument("--project", default=None,
                           help="Prosjekt: nummer (1), navn (1-solo) eller full path")

    # --- mirror ---
    mirror_p = sub.add_parser("mirror", help="Synk DB → CASES.md.")
    mirror_p.add_argument("--project", default=None,
                          help="Prosjekt: nummer (1), navn (1-solo) eller full path")

    # --- debrief ---
    debrief_p = sub.add_parser("debrief", help="Generer debrief for en flight.")
    debrief_p.add_argument("flight_id", type=str, help="Flight-ID, f.eks. FLT_001")
    debrief_p.add_argument("--project", default=None,
                           help="Prosjekt: nummer (1), navn (1-solo) eller full path")

    return parser


def cmd_setup(args: argparse.Namespace) -> int:
    from sverm.setup import setup_project

    projects_dir = args.projects_dir
    if projects_dir is None:
        # Default: ~/sverm-projects/ — predikerbar lokasjon uavhengig av cwd.
        # Hvis brukeren står i en klonet sverm-repo (cwd har 10-projects/),
        # bruk den i stedet — da fungerer demoen og setup samme sted.
        cwd_local = Path.cwd() / "10-projects"
        if cwd_local.exists():
            projects_dir = cwd_local
        else:
            projects_dir = default_user_projects_dir()

    setup_project(args.config, projects_dir, name_override=args.name)
    return 0


def cmd_launch_focus(args: argparse.Namespace) -> int:
    from sverm.launch import launch_focus
    from sverm.runtime import get_runtime

    project_dir = resolve_project(args.project)

    runtime = None
    if args.runtime:
        runtime = get_runtime(args.runtime)

    launch_focus(
        project_dir=project_dir,
        case_id=args.case_id,
        model=args.model,
        instance_count=args.count,
        runtime=runtime,
        dry_run=args.dry_run,
        monitor=not args.no_monitor,
        timeout=args.timeout,
    )
    return 0


def cmd_inspect(project_path: Path) -> int:
    paths = discover_project_paths(project_path)
    platform = detect_platform()

    print(f"Platform: {platform.label}")
    print(f"Project root: {paths.project_root}")
    print(f"Database: {paths.database_path}", end="")
    print(f" ({'exists' if paths.database_path.exists() else 'MISSING'})")

    if paths.database_path.exists():
        from sverm import db
        cases = db.get_open_cases(paths.database_path)
        print(f"\nOpen cases: {len(cases)}")
        for c in cases:
            print(f"  #{c.id} [{c.priority}] {c.title}")

        categories = db.get_seed_categories(paths.database_path)
        print(f"\nSeed axes: {len(categories)}")
        for cat in categories:
            print(f"  {cat}")

    return 0


def cmd_mirror(project_path: Path) -> int:
    from sverm.db import generate_cases_md
    from sverm.encoding import write_text
    
    paths = discover_project_paths(project_path)
    if not paths.database_path.exists():
        print(f"Error: Database not found: {paths.database_path}")
        return 1

    cases_md = generate_cases_md(paths.database_path, project_dir=paths.project_root)
    out_path = paths.cases_dir / "CASES.md"
    write_text(out_path, cases_md)
    print(f"CASES.md updated: {out_path}")
    return 0


def cmd_debrief(project_path: Path, flight_id: str) -> int:
    from sverm.debrief import generate_debrief

    report_path = generate_debrief(project_path, flight_id)
    print(f"Debrief generated: {report_path}")
    return 0


def main() -> int:
    _prepare_stdio()
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "setup":
        return cmd_setup(args)
    if args.command == "launch":
        if args.mode == "focus":
            return cmd_launch_focus(args)
        print("Error: specify launch mode (focus)")
        return 1
    if args.command == "inspect":
        return cmd_inspect(resolve_project(args.project))
    if args.command == "mirror":
        return cmd_mirror(resolve_project(args.project))
    if args.command == "debrief":
        return cmd_debrief(resolve_project(args.project), args.flight_id)

    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
