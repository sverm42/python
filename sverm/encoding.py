from __future__ import annotations

from pathlib import Path
from typing import Iterable


DEFAULT_ENCODING = "utf-8"


def read_text(path: Path, encoding: str = DEFAULT_ENCODING) -> str:
    return path.read_text(encoding=encoding)


def write_text(path: Path, content: str, encoding: str = DEFAULT_ENCODING) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding=encoding, newline="\n")


def ensure_utf8_lines(lines: Iterable[str]) -> str:
    return "\n".join(lines)

