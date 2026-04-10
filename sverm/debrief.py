"""debrief.py - Samle outputs og skriv en enkel debrief-rapport."""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

from sverm import db
from sverm.encoding import write_text
from sverm.paths import discover_project_paths


CONFIDENCE_RE = re.compile(r"confidence:\s*([01](?:\.\d+)?)\s*$", re.IGNORECASE)

# Matcher seksjons-headere i multi-case outputs: "## Case #3:", "##Case #3:",
# "## Case 3:" osv. Fleksibel mot små formateringsfeil fra LLM-en.
CASE_SECTION_RE = re.compile(
    r"^\s{0,3}#{1,3}\s*Case\s*#?\s*(\d+)\b[^\n]*$",
    re.MULTILINE | re.IGNORECASE,
)


def _extract_confidence(content: str) -> float | None:
    for line in reversed(content.splitlines()):
        match = CONFIDENCE_RE.search(line.strip())
        if match:
            try:
                return float(match.group(1))
            except ValueError:
                return None
    return None


def _parse_multi_case_output(content: str) -> list[tuple[int, str, float | None]]:
    """Parse en multi-case output-fil til (case_id, content, confidence)-tupler.

    Forventet format:

        # VS_XXXXX — Inbox/Batch Flight
        seed: ...
        model: ...

        ## Case #1: [tittel]
        [analyse]
        confidence: 0.8

        ## Case #3: [tittel]
        [analyse]
        confidence: 0.7

    Parseren finner alle `## Case #N:`-headere (med noe fleksibilitet for
    formatavvik) og splitter content mellom dem. Hver seksjon får sin egen
    confidence-verdi (søkt bakfra fra seksjonsslutten). Hvis filen ikke har
    noen case-seksjoner, returneres en tom liste.
    """
    matches = list(CASE_SECTION_RE.finditer(content))
    if not matches:
        return []

    results: list[tuple[int, str, float | None]] = []
    for i, match in enumerate(matches):
        try:
            case_id = int(match.group(1))
        except (ValueError, IndexError):
            continue
        section_start = match.start()
        section_end = matches[i + 1].start() if i + 1 < len(matches) else len(content)
        section_content = content[section_start:section_end].strip()
        confidence = _extract_confidence(section_content)
        results.append((case_id, section_content, confidence))

    return results


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


def _store_multi_case_outputs(db_path: Path, flight_id: str, records: list[dict]) -> None:
    """Lagre inbox/batch-outputs: én rad per (instans, case), samt cases_worked på
    instance-raden."""
    with db.transaction(db_path) as conn:
        conn.execute("DELETE FROM outputs WHERE flight_id=?", (flight_id,))
        for record in records:
            instance_id = record["instance_id"]
            completed_at = record["completed_at"]
            sections: list[tuple[int, str, float | None]] = record["sections"]
            case_ids_worked = sorted({cid for cid, _, _ in sections})
            conn.execute(
                "UPDATE instances SET status='done', completed_at=?, cases_worked=? WHERE id=?",
                (completed_at, ",".join(str(c) for c in case_ids_worked), instance_id),
            )
            for case_id, content, confidence in sections:
                conn.execute(
                    "INSERT INTO outputs (instance_id, flight_id, case_id, content, confidence) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (instance_id, flight_id, case_id, content, confidence),
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


def _generate_multi_case_debrief(
    project_dir: Path,
    flight_id: str,
    flight: dict,
    instances: list[dict],
    flight_dir: Path,
    paths,
) -> Path:
    """Lag en debrief for inbox eller batch: aggregering per case istedenfor per instans."""
    mode = flight.get("mode", "focus")
    records: list[dict] = []
    missing_outputs: list[str] = []
    parse_failures: list[str] = []

    for inst in instances:
        output_path = flight_dir / f"{inst['id']}_output.md"
        if not output_path.exists():
            missing_outputs.append(inst["id"])
            continue

        content = output_path.read_text(encoding="utf-8")
        sections = _parse_multi_case_output(content)
        if not sections:
            parse_failures.append(inst["id"])

        records.append({
            "instance_id": inst["id"],
            "raw_content": content,
            "sections": sections,
            "completed_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        })

    # Lagre outputs i DB (en rad per (instans, case))
    _store_multi_case_outputs(paths.database_path, flight_id, records)

    # Bygg dekningskart: case_id → [(instance_id, content, confidence), ...]
    coverage: dict[int, list[tuple[str, str, float | None]]] = {}
    all_case_ids: set[int] = set()
    for rec in records:
        for cid, content, conf in rec["sections"]:
            coverage.setdefault(cid, []).append((rec["instance_id"], content, conf))
            all_case_ids.add(cid)

    # Hent case-titler for de dekte case-ene
    case_titles: dict[int, str] = {}
    for cid in sorted(all_case_ids):
        case = db.get_case(paths.database_path, cid)
        if case is not None:
            case_titles[cid] = case.title
        else:
            case_titles[cid] = f"(case #{cid} ikke funnet i DB)"

    total_sections = sum(len(rec["sections"]) for rec in records)
    all_confidences = [
        conf for rec in records for _, _, conf in rec["sections"] if conf is not None
    ]
    avg_conf = (
        f"{sum(all_confidences) / len(all_confidences):.2f}" if all_confidences else "ukjent"
    )

    lines = [
        f"# Debrief - {flight_id}",
        "",
        f"**Mode:** {mode}",
        f"**Model:** {flight['model']}",
        f"**Instanser:** {flight['instance_count']}",
        f"**Output-filer funnet:** {len(records)}/{len(instances)}",
        f"**Case-analyser totalt:** {total_sections}",
        f"**Unike cases dekket:** {len(all_case_ids)}",
        f"**Gjennomsnittlig confidence:** {avg_conf}",
        "",
    ]

    if missing_outputs:
        lines.extend(["## Manglende outputs", "", ", ".join(missing_outputs), ""])

    if parse_failures:
        lines.extend([
            "## Outputs som ikke kunne parses",
            "",
            f"Disse instansene landet, men følgte ikke multi-case-formatet. "
            f"Du finner rå-output i flight-mappa.",
            "",
            ", ".join(parse_failures),
            "",
        ])

    # Instansoversikt
    lines.extend([
        "## Instansoversikt",
        "",
        "| Instans | Seed | Cases dekket | Avg confidence |",
        "|---------|------|--------------|----------------|",
    ])
    for inst in instances:
        rec = next((r for r in records if r["instance_id"] == inst["id"]), None)
        if rec is None:
            cases_cell = "-"
            conf_cell = "-"
        else:
            case_ids = sorted({cid for cid, _, _ in rec["sections"]})
            cases_cell = ", ".join(f"#{c}" for c in case_ids) if case_ids else "(ingen parset)"
            confs = [c for _, _, c in rec["sections"] if c is not None]
            conf_cell = f"{sum(confs) / len(confs):.2f}" if confs else "-"
        seed_words = _escape_table_cell(inst["seed_words"] or "-")
        lines.append(f"| {inst['id']} | {seed_words} | {cases_cell} | {conf_cell} |")

    # Dekning per case
    lines.extend(["", "## Dekning per Case", ""])
    if coverage:
        lines.extend([
            "| Case | Tittel | Antall instanser | Snitt-confidence |",
            "|------|--------|------------------|------------------|",
        ])
        for cid in sorted(coverage.keys()):
            entries = coverage[cid]
            confs = [c for _, _, c in entries if c is not None]
            snitt = f"{sum(confs) / len(confs):.2f}" if confs else "-"
            title = _escape_table_cell(case_titles.get(cid, "?"))
            lines.append(f"| #{cid} | {title} | {len(entries)} | {snitt} |")
    else:
        lines.append("Ingen cases ble dekket.")
    lines.append("")

    # Sammendrag
    lines.extend(["## Sammendrag", ""])
    if mode == "inbox":
        lines.append(
            "Inbox-flighten er landet. Hver instans valgte selv hvilke cases den ville "
            "analysere basert på seed-affinitet. Se dekningstabellen for å vurdere hvor "
            "svermen konvergerte (mange instanser på samme case) vs. hvor den spredte seg "
            "(få instanser per case)."
        )
    else:
        lines.append(
            "Batch-flighten er landet. Alle cases ble partisjonert mellom instansene og "
            "dekket deterministisk. Se rå outputs per case nedenfor for full dekning."
        )
    lines.append("")

    # Rå outputs gruppert per case
    lines.extend(["## Rå outputs per Case", ""])
    if coverage:
        for cid in sorted(coverage.keys()):
            title = case_titles.get(cid, "?")
            lines.append(f"### Case #{cid}: {title}")
            lines.append("")
            for iid, content, conf in coverage[cid]:
                conf_str = f"{conf:.2f}" if conf is not None else "ukjent"
                lines.append(f"#### {iid} (confidence {conf_str})")
                lines.append("")
                lines.append("```md")
                lines.append(content.rstrip())
                lines.append("```")
                lines.append("")
    else:
        lines.append("Ingen parsede outputs å vise.")

    report = "\n".join(lines).rstrip() + "\n"
    report_path = paths.debrief_dir / f"{flight_id}_debrief.md"
    write_text(report_path, report)
    _store_debrief(paths.database_path, flight_id, report)

    cases_md = db.generate_cases_md(paths.database_path, project_dir=paths.project_root)
    write_text(paths.cases_dir / "CASES.md", cases_md)
    build_index(paths.project_root)
    return report_path


def generate_debrief(project_dir: Path, flight_id: str) -> Path:
    paths = discover_project_paths(project_dir)
    flight, instances = _load_flight_summary(paths.database_path, flight_id)
    flight_dir = paths.flights_dir / flight_id
    if not flight_dir.exists():
        raise FileNotFoundError(f"Flight-mappe finnes ikke: {flight_dir}")

    # Inbox og batch har multi-case outputs — helt annen rapportform
    mode = flight.get("mode", "focus")
    if mode in ("inbox", "batch"):
        return _generate_multi_case_debrief(project_dir, flight_id, flight, instances, flight_dir, paths)

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
