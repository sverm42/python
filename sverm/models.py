"""models.py — Domenemodeller for sverm.

Frozen dataklasser som representerer kjerneentitetene:
seeds, cases, flights, instanser og prosjektconfig.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional


# ============================================================
# Seeds
# ============================================================

@dataclass(frozen=True)
class SeedWord:
    word: str
    weight: float
    description: str = ""


@dataclass(frozen=True)
class SeedAxis:
    name: str
    words: list[SeedWord] = field(default_factory=list)


@dataclass(frozen=True)
class SeedAssignment:
    """Én instans sin seed — ett ord per akse."""
    words: list[str]
    axis_names: list[str]

    @property
    def label(self) -> str:
        """Seed som pipe-separert streng: 'ord1 | ord2 | ord3'"""
        return " | ".join(self.words)

    @property
    def axis_label(self) -> str:
        """Aksene som pipe-separert streng."""
        return " | ".join(self.axis_names)


# ============================================================
# Cases
# ============================================================

@dataclass(frozen=True)
class CaseConfig:
    """Case fra JSON config (input)."""
    title: str
    description: str
    priority: str = "normal"
    tags: str = ""


@dataclass(frozen=True)
class Case:
    """Case fra database (med ID og status)."""
    id: int
    title: str
    description: str
    priority: str = "normal"
    status: str = "open"
    tags: str = ""


# ============================================================
# Flights og Instanser
# ============================================================

@dataclass(frozen=True)
class FlightConfig:
    """Konfigurasjon for en ny flight."""
    mode: str  # focus, inbox, batch
    model: str  # haiku, sonnet, opus, hybrid
    instance_count: int = 9
    focus_case_id: Optional[int] = None


@dataclass
class Flight:
    """Flight fra database."""
    id: str
    mode: str
    model: str
    instance_count: int
    status: str = "preparing"
    focus_case_id: Optional[int] = None
    launched_at: Optional[str] = None
    landed_at: Optional[str] = None


@dataclass
class Instance:
    """Sverm-instans."""
    id: str
    flight_id: str
    model: str
    seed_words: str
    status: str = "spawned"


# ============================================================
# Prosjektconfig
# ============================================================

@dataclass(frozen=True)
class ProjectConfig:
    """Hel prosjektconfig fra JSON."""
    name: str
    domain: str
    goal: str
    key_info: list[str]
    axes: list[SeedAxis]
    cases: list[CaseConfig]
    raw: dict[str, Any]
