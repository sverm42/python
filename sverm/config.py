from __future__ import annotations

import json
from pathlib import Path

from sverm.models import CaseConfig, ProjectConfig, SeedAxis, SeedWord


def load_project_config(path: Path) -> ProjectConfig:
    data = json.loads(path.read_text(encoding="utf-8"))

    axes = [
        SeedAxis(
            name=axis["name"],
            words=[
                SeedWord(
                    word=word["word"],
                    weight=float(word["weight"]),
                    description=word.get("description", ""),
                )
                for word in axis.get("words", [])
            ],
        )
        for axis in data.get("axes", [])
    ]

    cases = [
        CaseConfig(
            title=case["title"],
            description=case["description"],
            priority=case.get("priority", "normal"),
            tags=case.get("tags", ""),
        )
        for case in data.get("cases", [])
    ]

    return ProjectConfig(
        name=data["name"],
        domain=data["domain"],
        goal=data["goal"],
        key_info=list(data.get("key_info", [])),
        axes=axes,
        cases=cases,
        raw=data,
    )
