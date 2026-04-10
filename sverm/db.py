"""db.py — SQLite-lag for sverm.

Lavt nivå: tilkobling, transaksjoner, schema-init.
Høyt nivå: queries for seeds, cases, flights, instanser.
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator, Optional

from sverm.models import Case, Flight, Instance, SeedAssignment, SeedAxis, SeedWord


def normalize_priority(value: str) -> str:
    """Normaliser priority-felt fra eldre configs."""
    key = (value or "normal").strip().lower()
    aliases = {
        "medium": "normal",
        "default": "normal",
        "normal": "normal",
        "low": "low",
        "high": "high",
        "critical": "critical",
    }
    return aliases.get(key, "normal")


# ============================================================
# Tilkobling
# ============================================================

def connect(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


@contextmanager
def transaction(db_path: Path) -> Iterator[sqlite3.Connection]:
    conn = connect(db_path)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ============================================================
# Schema
# ============================================================

SCHEMA_SQL = """\
CREATE TABLE IF NOT EXISTS seeds (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    context TEXT NOT NULL,
    category TEXT NOT NULL,
    word TEXT NOT NULL,
    weight REAL DEFAULT 0.5
);
CREATE INDEX IF NOT EXISTS idx_seeds_context ON seeds(context, category);

CREATE TABLE IF NOT EXISTS cases (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    category TEXT DEFAULT 'general',
    priority TEXT DEFAULT 'normal'
        CHECK (priority IN ('low', 'normal', 'high', 'critical')),
    status TEXT DEFAULT 'open'
        CHECK (status IN ('open', 'in_progress', 'resolved', 'archived')),
    created_at TEXT DEFAULT (strftime('%Y-%m-%d %H:%M', 'now', 'localtime')),
    updated_at TEXT DEFAULT (strftime('%Y-%m-%d %H:%M', 'now', 'localtime')),
    resolved_by_flight TEXT,
    tags TEXT,
    notes TEXT
);

CREATE TABLE IF NOT EXISTS flights (
    id TEXT PRIMARY KEY,
    mode TEXT NOT NULL CHECK (mode IN ('focus', 'inbox', 'batch')),
    model TEXT DEFAULT 'haiku',
    instance_count INTEGER DEFAULT 20,
    focus_case_id INTEGER,
    status TEXT DEFAULT 'preparing'
        CHECK (status IN ('preparing', 'launched', 'landed', 'debriefed')),
    launched_at TEXT,
    landed_at TEXT,
    debriefed_at TEXT,
    seed_pool TEXT DEFAULT 'default',
    notes TEXT,
    FOREIGN KEY (focus_case_id) REFERENCES cases(id)
);

CREATE TABLE IF NOT EXISTS instances (
    id TEXT PRIMARY KEY,
    flight_id TEXT NOT NULL,
    model TEXT NOT NULL,
    seed_words TEXT,
    status TEXT DEFAULT 'spawned'
        CHECK (status IN ('spawned', 'working', 'done', 'error')),
    spawned_at TEXT DEFAULT (strftime('%Y-%m-%d %H:%M', 'now', 'localtime')),
    completed_at TEXT,
    cases_worked TEXT,
    FOREIGN KEY (flight_id) REFERENCES flights(id)
);

CREATE TABLE IF NOT EXISTS outputs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    instance_id TEXT NOT NULL,
    flight_id TEXT NOT NULL,
    case_id INTEGER,
    content TEXT NOT NULL,
    conclusion TEXT,
    confidence REAL,
    perspective_tags TEXT,
    created_at TEXT DEFAULT (strftime('%Y-%m-%d %H:%M', 'now', 'localtime')),
    FOREIGN KEY (instance_id) REFERENCES instances(id),
    FOREIGN KEY (flight_id) REFERENCES flights(id),
    FOREIGN KEY (case_id) REFERENCES cases(id)
);

CREATE TABLE IF NOT EXISTS debriefs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    flight_id TEXT NOT NULL,
    synthesis TEXT NOT NULL,
    consensus_points TEXT,
    dissent_points TEXT,
    recommendations TEXT,
    created_at TEXT DEFAULT (strftime('%Y-%m-%d %H:%M', 'now', 'localtime')),
    FOREIGN KEY (flight_id) REFERENCES flights(id)
);
"""


def init_schema(db_path: Path) -> None:
    """Opprett tabeller hvis de ikke finnes."""
    with transaction(db_path) as conn:
        conn.executescript(SCHEMA_SQL)


# ============================================================
# Seeds
# ============================================================

def insert_seeds(db_path: Path, axes: list[SeedAxis], context: str = "default") -> None:
    """Sett inn seed-akser i databasen."""
    with transaction(db_path) as conn:
        for i, axis in enumerate(axes, 1):
            category = f"{i:02d}_{axis.name}"
            for word in axis.words:
                conn.execute(
                    "INSERT INTO seeds (context, category, word, weight) VALUES (?, ?, ?, ?)",
                    (context, category, word.word, word.weight),
                )


def get_seed_categories(db_path: Path, context: str = "default") -> list[str]:
    """Hent unike seed-kategorier (akser) sortert."""
    conn = connect(db_path)
    try:
        rows = conn.execute(
            "SELECT DISTINCT category FROM seeds WHERE context=? ORDER BY category",
            (context,),
        ).fetchall()
        return [row["category"] for row in rows]
    finally:
        conn.close()


def pick_seed(db_path: Path, context: str = "default") -> SeedAssignment:
    """Velg én seed — ett tilfeldig vektet ord per akse."""
    categories = get_seed_categories(db_path, context)
    if not categories:
        raise ValueError(f"Ingen seeds funnet for context '{context}'")

    conn = connect(db_path)
    try:
        words = []
        axis_names = []
        for cat in categories:
            row = conn.execute(
                "SELECT word FROM seeds WHERE context=? AND category=? "
                "ORDER BY RANDOM() * weight DESC LIMIT 1",
                (context, cat),
            ).fetchone()
            if row:
                words.append(row["word"])
                # Aksennavn: fjern prefiks "01_" → "perspektiv"
                axis_names.append(cat.split("_", 1)[-1] if "_" in cat else cat)
        return SeedAssignment(words=words, axis_names=axis_names)
    finally:
        conn.close()


# ============================================================
# Cases
# ============================================================

def insert_cases(db_path: Path, cases: list[dict]) -> None:
    """Sett inn cases fra config."""
    with transaction(db_path) as conn:
        for c in cases:
            conn.execute(
                "INSERT INTO cases (title, description, priority, tags) VALUES (?, ?, ?, ?)",
                (
                    c["title"],
                    c["description"],
                    normalize_priority(c.get("priority", "normal")),
                    c.get("tags", ""),
                ),
            )


def get_case(db_path: Path, case_id: int) -> Optional[Case]:
    """Hent én case etter ID."""
    conn = connect(db_path)
    try:
        row = conn.execute("SELECT * FROM cases WHERE id=?", (case_id,)).fetchone()
        if row is None:
            return None
        return Case(
            id=row["id"],
            title=row["title"],
            description=row["description"],
            priority=row["priority"],
            status=row["status"],
            tags=row["tags"] or "",
        )
    finally:
        conn.close()


def get_open_cases(db_path: Path) -> list[Case]:
    """Hent alle åpne cases."""
    conn = connect(db_path)
    try:
        rows = conn.execute(
            "SELECT * FROM cases WHERE status='open' ORDER BY "
            "CASE priority WHEN 'critical' THEN 1 WHEN 'high' THEN 2 "
            "WHEN 'normal' THEN 3 WHEN 'low' THEN 4 END, id"
        ).fetchall()
        return [
            Case(
                id=r["id"], title=r["title"], description=r["description"],
                priority=r["priority"], status=r["status"], tags=r["tags"] or "",
            )
            for r in rows
        ]
    finally:
        conn.close()


# ============================================================
# Flights
# ============================================================

def next_flight_id(db_path: Path) -> str:
    """Generer neste flight-ID (FLT_001, FLT_002, ...)."""
    conn = connect(db_path)
    try:
        row = conn.execute(
            "SELECT COALESCE(MAX(CAST(SUBSTR(id, 5) AS INTEGER)), 0) + 1 AS next_num FROM flights"
        ).fetchone()
        return f"FLT_{row['next_num']:03d}"
    finally:
        conn.close()


def create_flight(db_path: Path, flight: Flight) -> None:
    """Registrer en ny flight."""
    with transaction(db_path) as conn:
        conn.execute(
            "INSERT INTO flights (id, mode, model, instance_count, focus_case_id, status, launched_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (flight.id, flight.mode, flight.model, flight.instance_count,
             flight.focus_case_id, flight.status, flight.launched_at),
        )


def update_flight_status(db_path: Path, flight_id: str, status: str) -> None:
    """Oppdater flight-status."""
    with transaction(db_path) as conn:
        conn.execute("UPDATE flights SET status=? WHERE id=?", (status, flight_id))


# ============================================================
# Instanser
# ============================================================

def register_instances(db_path: Path, instances: list[Instance]) -> None:
    """Registrer instanser for en flight."""
    with transaction(db_path) as conn:
        for inst in instances:
            conn.execute(
                "INSERT INTO instances (id, flight_id, model, seed_words) VALUES (?, ?, ?, ?)",
                (inst.id, inst.flight_id, inst.model, inst.seed_words),
            )


def generate_instance_ids(db_path: Path, count: int, prefix: str = "VS") -> list[str]:
    """Generer sekvensielle instans-IDer fra databasen.
    
    Enkel lokal sekvens — for produksjon på Mac brukes sverm-id (HQ).
    Denne metoden er fallback for Windows/Linux og testing.
    """
    conn = connect(db_path)
    try:
        row = conn.execute(
            "SELECT COALESCE(MAX(CAST(SUBSTR(id, 4) AS INTEGER)), 0) AS last_num "
            "FROM instances WHERE id LIKE ?",
            (f"{prefix}_%",),
        ).fetchone()
        start = (row["last_num"] or 0) + 1
        return [f"{prefix}_{start + i:06d}" for i in range(count)]
    finally:
        conn.close()


# ============================================================
# Mirror: DB → CASES.md
# ============================================================

def generate_cases_md(db_path: Path, project_dir: Path | None = None) -> str:
    """Generer CASES.md-innhold fra databasen.

    Inkluderer copy-paste launch-kommandoer og flight-historikk per case.
    """
    conn = connect(db_path)
    try:
        cases = conn.execute(
            "SELECT * FROM cases ORDER BY "
            "CASE priority WHEN 'critical' THEN 1 WHEN 'high' THEN 2 "
            "WHEN 'normal' THEN 3 WHEN 'low' THEN 4 END, id"
        ).fetchall()

        flights = conn.execute(
            "SELECT * FROM flights ORDER BY launched_at DESC"
        ).fetchall()

        # Bygg flight-historikk per case
        case_flights: dict[int, list] = {}
        for f in flights:
            cid = f["focus_case_id"]
            if cid is not None:
                case_flights.setdefault(cid, []).append(f)

        # Bygg project-shortcut for kommandoer (--project N)
        if project_dir:
            proj_name = project_dir.name
        else:
            proj_name = db_path.parent.name
        # Trekk ut numerisk prefiks: "1-solo-entrepreneur-blindspots" → "1"
        proj_num = proj_name.split("-", 1)[0] if proj_name[0:1].isdigit() else proj_name

        # Statusoversikt
        open_count = sum(1 for c in cases if c["status"] == "open")
        prog_count = sum(1 for c in cases if c["status"] == "in_progress")
        done_count = sum(1 for c in cases if c["status"] == "resolved")

        lines = ["# Sverm — Cases", ""]
        lines.append(f"*Auto-generert fra sverm.db — {len(cases)} cases*")
        lines.append("")

        # Oversikt
        lines.append("## Oversikt")
        lines.append("")
        lines.append("| Status | Antall |")
        lines.append("|--------|--------|")
        lines.append(f"| Open | {open_count} |")
        lines.append(f"| In Progress | {prog_count} |")
        lines.append(f"| Resolved | {done_count} |")
        lines.append(f"| **Totalt** | **{len(cases)}** |")
        lines.append("")

        # Kjør-oversikt
        lines.append("---")
        lines.append("")
        lines.append("## Kjør Sverm")
        lines.append("")
        lines.append("| Modus | Kommando | Beskrivelse |")
        lines.append("|-------|---------|-------------|")
        lines.append(f"| **focus** | `sverm launch focus <case#> --project {proj_num} --medium -n 9` | Alle instanser jobber på **én** case (dybde) |")
        lines.append("")
        lines.append("Modell: `--medium` (default) · `--small` (rask/billig) · `--large` (dyp). `-n 9` = 9 instanser. `--dry-run` for test.")
        lines.append("")

        # Cases
        lines.append("---")
        lines.append("")
        lines.append("## Åpne Cases")
        lines.append("")

        for c in cases:
            if c["status"] not in ("open", "in_progress"):
                continue

            status_icon = {"open": "🔵", "in_progress": "🟡"}.get(c["status"], "⚪")
            lines.append(f"### {status_icon} Case #{c['id']}: {c['title']}")
            lines.append("")
            lines.append(f"**Prioritet:** {c['priority']} | **Status:** {c['status']}")
            if c["tags"]:
                lines.append(f"**Tags:** {c['tags']}")
            lines.append("")
            lines.append(c["description"])
            lines.append("")

            # Launch-kommando
            lines.append("**Kjør:**")
            lines.append("```bash")
            lines.append(f"sverm launch focus {c['id']} --project {proj_num} --medium -n 9")
            lines.append(f"# --small (rask/billig) · --large (dyp) · --dry-run (test)")
            lines.append("```")
            lines.append("")

            # Flight-historikk for denne casen
            cf = case_flights.get(c["id"], [])
            if cf:
                lines.append(f"**Flights:** {len(cf)}")
                lines.append("")
                lines.append("| Dato | Flight | Mode | Model | Instanser | Output |")
                lines.append("|------|--------|------|-------|-----------|--------|")
                for f in cf:
                    lines.append(
                        f"| {f['launched_at'] or '-'} | {f['id']} | {f['mode']} | "
                        f"{f['model']} | {f['instance_count']} | "
                        f"[`20-flights/{f['id']}/`](20-flights/{f['id']}/) |"
                    )
                lines.append("")

            lines.append("---")
            lines.append("")

        # Resolved cases (kompakt)
        resolved = [c for c in cases if c["status"] in ("resolved", "archived")]
        if resolved:
            lines.append("## Avsluttede Cases")
            lines.append("")
            for c in resolved:
                status_icon = {"resolved": "✅", "archived": "📦"}.get(c["status"], "⚪")
                lines.append(f"- {status_icon} **Case #{c['id']}:** {c['title']} ({c['status']})")
            lines.append("")

        return "\n".join(lines)
    finally:
        conn.close()
