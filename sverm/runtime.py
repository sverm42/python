"""runtime.py — Abstraksjon over Codex og Claude Code som sverm-runtime.

Hver runtime vet hvordan den starter én AI-instans som subprocess.
Orkestreringen (launch.py) bruker runtime-grensesnittet uten å vite
hvilken motor som faktisk kjører.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


# ============================================================
# Modellmapping
# ============================================================

# Generiske alias → faktiske modellnavn per runtime.
# "small/medium/large" er runtime-agnostisk.
# "haiku/sonnet/opus" er Claude-spesifikke men mappes for begge.

CODEX_MODELS: dict[str, str] = {
    "small": "gpt-5.4-mini",
    "medium": "gpt-5.4",
    "large": "o3",
    "haiku": "gpt-5.4-mini",
    "sonnet": "gpt-5.4",
    "opus": "o3",
}

CLAUDE_MODELS: dict[str, str] = {
    "small": "haiku",
    "medium": "sonnet",
    "large": "opus",
    "haiku": "haiku",
    "sonnet": "sonnet",
    "opus": "opus",
}


def resolve_model(alias: str, model_map: dict[str, str]) -> str:
    """Løs opp et modellalias til faktisk modellnavn."""
    key = alias.lower().strip()
    if key in model_map:
        return model_map[key]
    # Ukjent alias — returner som-er (brukeren kan ha oppgitt direkte modellnavn)
    return key


# ============================================================
# RuntimeResult — container for subprocess-info
# ============================================================

@dataclass
class RuntimeProcess:
    """Wrapper rundt en startet instans-prosess."""
    instance_id: str
    process: subprocess.Popen
    output_path: Path
    log_path: Path
    model: str
    seed: str


# ============================================================
# Abstract Runtime
# ============================================================

class Runtime(ABC):
    """Grensesnitt for en sverm-runtime (Codex, Claude, etc.)."""

    name: str = "abstract"

    @abstractmethod
    def run(
        self,
        *,
        prompt: str,
        model: str,
        cwd: Path,
        output_path: Path,
        log_path: Path,
        instance_id: str,
        seed: str,
        env: Optional[dict[str, str]] = None,
    ) -> subprocess.Popen:
        """Start én instans. Returnerer Popen for asynkron overvåkning."""
        ...

    @abstractmethod
    def is_available(self) -> bool:
        """Sjekk om runtime-binæren finnes i PATH."""
        ...

    def resolve_model(self, alias: str) -> str:
        """Løs opp modellalias til faktisk modellnavn."""
        raise NotImplementedError


# ============================================================
# Claude Code Runtime
# ============================================================

class ClaudeRuntime(Runtime):
    """Kjører instanser via `claude -p` (Claude Code CLI)."""

    name = "claude"

    def resolve_model(self, alias: str) -> str:
        return resolve_model(alias, CLAUDE_MODELS)

    def is_available(self) -> bool:
        return shutil.which("claude") is not None

    def run(
        self,
        *,
        prompt: str,
        model: str,
        cwd: Path,
        output_path: Path,
        log_path: Path,
        instance_id: str,
        seed: str,
        env: Optional[dict[str, str]] = None,
    ) -> subprocess.Popen:
        resolved = self.resolve_model(model)

        # Finn claude-binæren i PATH
        claude_bin = shutil.which("claude")
        if claude_bin is None:
            raise RuntimeError(
                "Fant ikke Claude Code CLI ('claude' i PATH). "
                "Installer fra https://docs.claude.com/en/docs/claude-code."
            )

        # Skriv prompt til fil — sendes via stdin til claude-prosessen
        prompt_file = output_path.parent / f"{instance_id}_prompt.md"
        prompt_file.write_text(prompt, encoding="utf-8")

        # Sørg for at output-mappene finnes
        output_path.parent.mkdir(parents=True, exist_ok=True)
        log_path.parent.mkdir(parents=True, exist_ok=True)

        # Miljø: isoler fra en eventuell parent Claude Code-prosess
        proc_env = os.environ.copy()
        proc_env["CLAUDE_CODE_MAX_OUTPUT_TOKENS"] = "128000"
        proc_env.setdefault("PYTHONIOENCODING", "utf-8")
        for key in ["CLAUDECODE", "CLAUDE_CODE_ENTRYPOINT", "CLAUDE_CODE_EXECPATH"]:
            proc_env.pop(key, None)
        if env:
            proc_env.update(env)

        # Åpne fil-handles — må leve gjennom hele subprocess-livet.
        # launch.py lukker dem etter at prosessen har terminert.
        # stdout og stderr går begge til log_path. output_path skrives av
        # Claude selv via Write-verktøyet basert på prompten.
        stdin_handle = prompt_file.open("r", encoding="utf-8")
        log_handle = log_path.open("w", encoding="utf-8")

        cmd = [
            claude_bin, "-p",
            "--model", resolved,
            "--output-format", "text",
            "--max-turns", "50",
            "--permission-mode", "bypassPermissions",
            "--add-dir", str(output_path.parent),
        ]

        try:
            proc = subprocess.Popen(
                cmd,
                cwd=str(cwd),
                stdin=stdin_handle,
                stdout=log_handle,
                stderr=subprocess.STDOUT,
                env=proc_env,
            )
        except Exception:
            stdin_handle.close()
            log_handle.close()
            raise

        # Stash handles slik at launch.py kan lukke dem etter prosess-eksitt
        proc._sverm_prompt_handle = stdin_handle  # type: ignore[attr-defined]
        proc._sverm_log_handle = log_handle  # type: ignore[attr-defined]
        return proc


# ============================================================
# Codex Runtime
# ============================================================

class CodexRuntime(Runtime):
    """Kjører instanser via `codex exec` (OpenAI Codex CLI)."""

    name = "codex"

    def resolve_model(self, alias: str) -> str:
        return resolve_model(alias, CODEX_MODELS)

    def is_available(self) -> bool:
        return self._find_binary() is not None

    @staticmethod
    def _candidate_binaries() -> list[Path | str]:
        candidates: list[Path | str] = []

        env_bin = os.environ.get("CODEX_BIN")
        if env_bin:
            candidates.append(Path(env_bin))

        home = Path.home()
        candidates.extend(
            [
                home / ".codex" / ".sandbox-bin" / "codex.exe",
                home / ".codex" / ".sandbox-bin" / "codex",
                "codex.exe",
                "codex",
            ]
        )
        return candidates

    @classmethod
    def _find_binary(cls) -> Optional[str]:
        for candidate in cls._candidate_binaries():
            if isinstance(candidate, Path):
                if candidate.exists():
                    return str(candidate)
                continue

            found = shutil.which(candidate)
            if found:
                return found

        return None

    def run(
        self,
        *,
        prompt: str,
        model: str,
        cwd: Path,
        output_path: Path,
        log_path: Path,
        instance_id: str,
        seed: str,
        env: Optional[dict[str, str]] = None,
    ) -> subprocess.Popen:
        resolved = self.resolve_model(model)
        codex_bin = self._find_binary()
        if codex_bin is None:
            raise RuntimeError(
                "Fant ikke Codex CLI. Sett CODEX_BIN eller installer en kjørbar codex.exe."
            )

        prompt_file = output_path.parent / f"{instance_id}_prompt.md"
        prompt_file.write_text(prompt, encoding="utf-8")
        last_message_path = output_path.parent / f"{instance_id}_last_message.txt"

        output_path.parent.mkdir(parents=True, exist_ok=True)
        log_path.parent.mkdir(parents=True, exist_ok=True)

        cmd = [
            codex_bin,
            "exec",
            "-",
            "--model",
            resolved,
            "-C",
            str(cwd),
            "--skip-git-repo-check",
            "--output-last-message",
            str(last_message_path),
            "--sandbox",
            "workspace-write",
        ]

        proc_env = os.environ.copy()
        proc_env.setdefault("PYTHONIOENCODING", "utf-8")
        proc_env.setdefault("CODEX_BIN", codex_bin)
        if env:
            proc_env.update(env)

        prompt_handle = prompt_file.open("r", encoding="utf-8")
        log_file = log_path.open("w", encoding="utf-8")

        try:
            proc = subprocess.Popen(
                cmd,
                cwd=str(cwd),
                stdin=prompt_handle,
                stdout=log_file,
                stderr=subprocess.STDOUT,
                env=proc_env,
            )
        except Exception:
            prompt_handle.close()
            log_file.close()
            raise

        proc._sverm_prompt_handle = prompt_handle  # type: ignore[attr-defined]
        proc._sverm_log_handle = log_file  # type: ignore[attr-defined]
        return proc


# ============================================================
# Dry-Run Runtime (for testing)
# ============================================================

class DryRunRuntime(Runtime):
    """Simulerer en flight uten å starte ekte prosesser.
    
    Skriver prompten til output-filen og lager .done umiddelbart.
    Nyttig for å verifisere setup, seed-allokering og filstruktur.
    """

    name = "dry-run"

    def resolve_model(self, alias: str) -> str:
        return f"dry-run-{alias}"

    def is_available(self) -> bool:
        return True

    def run(
        self,
        *,
        prompt: str,
        model: str,
        cwd: Path,
        output_path: Path,
        log_path: Path,
        instance_id: str,
        seed: str,
        env: Optional[dict[str, str]] = None,
    ) -> subprocess.Popen:
        # Skriv mock output
        output_path.write_text(
            f"# {instance_id} — Dry Run\n"
            f"seed: {seed}\n"
            f"model: {model}\n\n"
            f"(Dry run — ingen ekte analyse)\n\n"
            f"confidence: 0.0\n",
            encoding="utf-8",
        )

        # Lag .done-fil
        done_path = output_path.parent / f"{instance_id}.done"
        done_path.touch()

        # Logg
        log_path.write_text(
            f"[dry-run] {instance_id} prompt written to {output_path}\n",
            encoding="utf-8",
        )

        # Returner en allerede-ferdig prosess (echo)
        return subprocess.Popen(
            [sys.executable, "-c", "print('dry-run')"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )


# ============================================================
# Factory
# ============================================================

_RUNTIMES: dict[str, type[Runtime]] = {
    "claude": ClaudeRuntime,
    "codex": CodexRuntime,
    "dry-run": DryRunRuntime,
}


def detect_runtime() -> Runtime:
    """Auto-detekter tilgjengelig runtime.

    Claude Code prioriteres hvis begge er installert, uavhengig av plattform.
    Sverm fungerer like godt med begge — valget avhenger av hvilken CLI du
    har autentisert og hvilket abonnement/API-nøkkel du har.

    Override ved å sette miljøvariabelen SVERM_RUNTIME til 'claude', 'codex'
    eller 'dry-run'.
    """
    # Eksplisitt override via miljøvariabel
    override = os.environ.get("SVERM_RUNTIME", "").strip().lower()
    if override in _RUNTIMES:
        runtime = _RUNTIMES[override]()
        if runtime.is_available() or override == "dry-run":
            return runtime

    # Claude prioriteres hvis tilgjengelig (mest modent per v1.0)
    claude = ClaudeRuntime()
    if claude.is_available():
        return claude

    # Codex som fallback
    codex = CodexRuntime()
    if codex.is_available():
        return codex

    raise RuntimeError(
        "Ingen runtime funnet. Installer Claude Code (claude) eller "
        "OpenAI Codex (codex) og sørg for at CLI-en er i PATH."
    )


def get_runtime(name: str) -> Runtime:
    """Hent en spesifikk runtime etter navn."""
    if name not in _RUNTIMES:
        available = ", ".join(_RUNTIMES.keys())
        raise ValueError(f"Ukjent runtime '{name}'. Tilgjengelige: {available}")
    return _RUNTIMES[name]()
