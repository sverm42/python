"""debrief.py - Samle outputs og skriv en enkel debrief-rapport."""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

from sverm import db
from sverm.encoding import write_text
from sverm.paths import discover_project_paths


CONFIDENCE_RE = re.compile(r"confidence:\s*([01](?:\.\d+)?)\s*$", re.IGNORECASE)


def _extract_confidence(content: str) -> float | None:
    for line in reversed(content.splitlines()):
        match = CONFIDENCE_RE.search(line.strip())
        if match:
            try:
                return float(match.group(1))
            except ValueError:
                return None
    return None


def _load_flight_summary(db_path: Path, flight_id: str) -> tuple[dict, list[dict]]:
    conn = db.connect(db_path)
    try:
        flight = conn.execute(
            "SELECT * FROM flights WHERE id=?",
            (flight_id,),
        ).fetchone()
        if flight is None:
            raise ValueError(f"Flight {flight_id} finnes ikke")

        instances = conn.execute(
            "SELECT * FROM instances WHERE flight_id=? ORDER BY id",
            (flight_id,),
        ).fetchall()
        return dict(flight), [dict(row) for row in instances]
    finally:
        conn.close()


def _store_outputs(db_path: Path, flight_id: str, case_id: int | None, records: list[dict]) -> None:
    with db.transaction(db_path) as conn:
        conn.execute("DELETE FROM outputs WHERE flight_id=?", (flight_id,))
        for record in records:
            conn.execute(
                "UPDATE instances SET status='done', completed_at=? WHERE id=?",
                (record["completed_at"], record["instance_id"]),
            )
            conn.execute(
                "INSERT INTO outputs (instance_id, flight_id, case_id, content, confidence) "
                "VALUES (?, ?, ?, ?, ?)",
                (
                    record["instance_id"],
                    flight_id,
                    case_id,
                    record["content"],
                    record["confidence"],
                ),
            )


def _store_debrief(db_path: Path, flight_id: str, report: str) -> None:
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    with db.transaction(db_path) as conn:
        conn.execute("DELETE FROM debriefs WHERE flight_id=?", (flight_id,))
        conn.execute(
            "INSERT INTO debriefs (flight_id, synthesis) VALUES (?, ?)",
            (flight_id, report),
        )
        conn.execute(
            "UPDATE flights SET status='debriefed', landed_at=COALESCE(landed_at, ?), debriefed_at=? WHERE id=?",
            (timestamp, timestamp, flight_id),
        )


def _escape_table_cell(value: str) -> str:
    return value.replace("|", "\\|")


def build_index(project_dir: Path) -> Path:
    paths = discover_project_paths(project_dir)
    conn = db.connect(paths.database_path)
    try:
        flights = conn.execute(
            "SELECT id, mode, model, instance_count, focus_case_id, status, launched_at, debriefed_at "
            "FROM flights ORDER BY launched_at DESC, id DESC"
        ).fetchall()

        lines = ["# Sverm - Index", ""]
        lines.append(f"*Auto-generert {datetime.now().strftime('%Y-%m-%d %H:%M')}*")
        lines.append("")
        if not flights:
            lines.append("Ingen flights registrert ennå.")
        else:
            lines.append("| Flight | Mode | Case | Model | Instanser | Status | Debrief |")
            lines.append("|--------|------|------|-------|-----------|--------|---------|")
            for row in flights:
                case_cell = f"#{row['focus_case_id']}" if row["focus_case_id"] is not None else "-"
                debrief_path = paths.debrief_dir / f"{row['id']}_debrief.md"
                debrief_cell = (
                    f"[`30-debrief/{debrief_path.name}`](30-debrief/{debrief_path.name})"
                    if debrief_path.exists()
                    else "-"
                )
                lines.append(
                    f"| {row['id']} | {row['mode']} | {case_cell} | {row['model']} | "
                    f"{row['instance_count']} | {row['status']} | {debrief_cell} |"
                )

        write_text(paths.index_path, "\n".join(lines) + "\n")
        return paths.index_path
    finally:
        conn.close()


def generate_debrief(project_dir: Path, flight_id: str) -> Path:
    paths = discover_project_paths(project_dir)
    flight, instances = _load_flight_summary(paths.database_path, flight_id)
    flight_dir = paths.flights_dir / flight_id
    if not flight_dir.exists():
        raise FileNotFoundError(f"Flight-mappe finnes ikke: {flight_dir}")

    case_title = "Ukjent case"
    case_id = flight.get("focus_case_id")
    if case_id is not None:
        case = db.get_case(paths.database_path, int(case_id))
        if case is not None:
            case_title = case.title

    output_records: list[dict] = []
    missing_outputs: list[str] = []
    confidence_values: list[float] = []

    for inst in instances:
        output_path = flight_dir / f"{inst['id']}_output.md"
        if not output_path.exists():
            missing_outputs.append(inst["id"])
            continue

        content = output_path.read_text(encoding="utf-8")
        confidence = _extract_confidence(content)
        if confidence is not None:
            confidence_values.append(confidence)

        output_records.append(
            {
                "instance_id": inst["id"],
                "content": content,
                "confidence": confidence,
                "completed_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
            }
        )

    _store_outputs(paths.database_path, flight_id, case_id, output_records)

    avg_conf = (
        f"{sum(confidence_values) / len(confidence_values):.2f}"
        if confidence_values
        else "ukjent"
    )

    lines = [
        f"# Debrief - {flight_id}",
        "",
        f"**Mode:** {flight['mode']}",
        f"**Case:** #{case_id} - {case_title}" if case_id is not None else "**Case:** -",
        f"**Model:** {flight['model']}",
        f"**Instanser:** {flight['instance_count']}",
        f"**Output-filer funnet:** {len(output_records)}/{len(instances)}",
        f"**Gjennomsnittlig confidence:** {avg_conf}",
        "",
    ]

    if missing_outputs:
        lines.extend(
            [
                "## Manglende outputs",
                "",
                ", ".join(missing_outputs),
                "",
            ]
        )

    lines.extend(
        [
            "## Instansoversikt",
            "",
            "| Instans | Seed | Confidence | Output |",
            "|--------|------|------------|--------|",
        ]
    )
    confidence_map = {record["instance_id"]: record["confidence"] for record in output_records}
    for inst in instances:
        output_name = f"{inst['id']}_output.md"
        output_cell = (
            f"[`20-flights/{flight_id}/{output_name}`](../20-flights/{flight_id}/{output_name})"
            if (flight_dir / output_name).exists()
            else "-"
        )
        conf = confidence_map.get(inst["id"])
        conf_cell = "-" if conf is None else f"{conf:.2f}"
        seed_words = _escape_table_cell(inst["seed_words"] or "-")
        lines.append(f"| {inst['id']} | {seed_words} | {conf_cell} | {output_cell} |")

    lines.extend(["", "## Sammendrag", ""])
    if output_records:
        lines.append(
            "Flighten er landet. Bruk output-filene over som primærkilde for videre vurdering, "
            "syntese og eventuelle nye runder."
        )
    else:
        lines.append("Ingen output-filer ble funnet. Sjekk loggene i flight-mappen før ny launch.")

    lines.extend(["", "## Rå outputs", ""])
    for record in output_records:
        lines.extend(
            [
                f"### {record['instance_id']}",
                "",
                "```md",
                record["content"].rstrip(),
                "```",
                "",
            ]
        )

    report = "\n".join(lines).rstrip() + "\n"
    report_path = paths.debrief_dir / f"{flight_id}_debrief.md"
    write_text(report_path, report)
    _store_debrief(paths.database_path, flight_id, report)

    cases_md = db.generate_cases_md(paths.database_path, project_dir=paths.project_root)
    write_text(paths.cases_dir / "CASES.md", cases_md)
    build_index(paths.project_root)
    return report_path
