from __future__ import annotations

import os
import platform as _platform
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class PlatformInfo:
    system: str
    release: str
    machine: str
    home: Path

    @property
    def is_windows(self) -> bool:
        return self.system == "Windows"

    @property
    def is_macos(self) -> bool:
        return self.system == "Darwin"

    @property
    def is_linux(self) -> bool:
        return self.system == "Linux"

    @property
    def label(self) -> str:
        return f"{self.system} {self.release} ({self.machine})"


def detect_platform() -> PlatformInfo:
    return PlatformInfo(
        system=_platform.system(),
        release=_platform.release(),
        machine=_platform.machine(),
        home=Path.home(),
    )


def preferred_text_encoding() -> str:
    return os.environ.get("PYTHONIOENCODING", "utf-8")

