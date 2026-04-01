"""Runtime configuration manager for mini-claude-code."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from mini_claude.core.query_engine import QueryEngine


@dataclass
class _Entry:
    description: str
    sensitive: bool = False    # mask value in display
    needs_restart: bool = False  # change only takes full effect after restart
    env_key: str | None = None   # backing OS env var (None = runtime-only)


# Display order is preserved
_ENTRIES: dict[str, _Entry] = {
    "LLM_PROVIDER":      _Entry("Active LLM provider (anthropic|openai)",
                                env_key="LLM_PROVIDER", needs_restart=True),
    "ANTHROPIC_API_KEY": _Entry("Anthropic API key",
                                env_key="ANTHROPIC_API_KEY",
                                sensitive=True, needs_restart=True),
    "ANTHROPIC_MODEL":   _Entry("Anthropic model name",
                                env_key="ANTHROPIC_MODEL", needs_restart=True),
    "OPENAI_API_KEY":    _Entry("OpenAI API key",
                                env_key="OPENAI_API_KEY",
                                sensitive=True, needs_restart=True),
    "OPENAI_MODEL":      _Entry("OpenAI model name",
                                env_key="OPENAI_MODEL", needs_restart=True),
    "OPENAI_BASE_URL":   _Entry("Custom API base URL for OpenAI-compatible providers (e.g. 147api)",
                                env_key="OPENAI_BASE_URL", needs_restart=True),
    "MAX_ITERATIONS":    _Entry("Max agentic loop iterations (1–50)",
                                env_key="MAX_ITERATIONS"),
    "WORK_DIR":          _Entry("Working directory for tools",
                                env_key="WORK_DIR", needs_restart=True),
    "system_prompt":     _Entry("System prompt sent to the LLM"),
}

_VALID_PROVIDERS = {"anthropic", "openai"}


def _mask(value: str) -> str:
    """Partially hide a sensitive value."""
    if not value:
        return "(not set)"
    if len(value) <= 8:
        return "****"
    return value[:4] + "..." + value[-4:]


def _update_env_file(key: str, value: str, env_path: Path = Path(".env")) -> None:
    """Insert or replace ``key=value`` in *env_path*, creating it if absent."""
    # Quote values that contain spaces
    quoted = f'"{value}"' if " " in value else value
    new_line = f"{key}={quoted}"

    if not env_path.exists():
        env_path.write_text(new_line + "\n", encoding="utf-8")
        return

    content = env_path.read_text(encoding="utf-8")
    pattern = re.compile(rf"^{re.escape(key)}\s*=.*", re.MULTILINE)
    if pattern.search(content):
        new_content = pattern.sub(new_line, content)
    else:
        new_content = content
        if new_content and not new_content.endswith("\n"):
            new_content += "\n"
        new_content += new_line + "\n"
    env_path.write_text(new_content, encoding="utf-8")


class RuntimeConfig:
    """Reads and writes all configurable settings, persisting env vars to .env."""

    def __init__(self, engine: "QueryEngine", env_path: Path = Path(".env")) -> None:
        self._engine = engine
        self._env_path = env_path

    # ── public API ───────────────────────────────────────────────────────────

    def keys(self) -> list[str]:
        return list(_ENTRIES.keys())

    def get(self, key: str) -> str | None:
        """Return display value (sensitive keys are masked), or None if unknown."""
        entry = _ENTRIES.get(key)
        if entry is None:
            return None
        raw = self._raw(key)
        if entry.sensitive:
            return _mask(raw)
        return raw

    def set(self, key: str, value: str) -> str:
        """
        Apply a setting and persist it.  Returns a Rich-markup result string.
        Never raises — errors surface as strings.
        """
        entry = _ENTRIES.get(key)
        if entry is None:
            valid = ", ".join(_ENTRIES.keys())
            return f"[red]Unknown key [bold]{key!r}[/bold]. Valid: {valid}[/red]"

        # ── per-key validation & apply ────────────────────────────────────────
        if key == "LLM_PROVIDER":
            if value not in _VALID_PROVIDERS:
                return (
                    f"[red]Invalid provider {value!r}. "
                    f"Choose: {', '.join(sorted(_VALID_PROVIDERS))}[/red]"
                )

        if key == "MAX_ITERATIONS":
            try:
                n = int(value)
            except ValueError:
                return f"[red]MAX_ITERATIONS requires an integer, got {value!r}[/red]"
            if not 1 <= n <= 50:
                return "[red]MAX_ITERATIONS must be between 1 and 50[/red]"
            self._engine.max_iterations = n  # immediate effect

        if key == "system_prompt":
            self._engine.context_manager.system_prompt = value
            return (
                f"[green]system_prompt[/green] updated "
                f"([dim]{len(value)} chars[/dim])"
            )

        # ── persist env-backed keys ───────────────────────────────────────────
        if entry.env_key:
            os.environ[entry.env_key] = value  # update current process
            self._persist(entry.env_key, value)

        tag = "[dim] — restart to take full effect[/dim]" if entry.needs_restart else ""
        display = _mask(value) if entry.sensitive else f"[yellow]{value}[/yellow]"
        return f"[green]{key}[/green] = {display}{tag}"

    def all_entries(self) -> list[tuple[str, str, str, bool]]:
        """Return ``(key, display_value, description, needs_restart)`` for every key."""
        return [
            (k, self.get(k) or "", e.description, e.needs_restart)
            for k, e in _ENTRIES.items()
        ]

    # ── internals ────────────────────────────────────────────────────────────

    def _raw(self, key: str) -> str:
        """Unmasked current value."""
        if key == "MAX_ITERATIONS":
            return str(self._engine.max_iterations)
        if key == "system_prompt":
            return self._engine.context_manager.system_prompt
        entry = _ENTRIES.get(key)
        if entry and entry.env_key:
            return os.environ.get(entry.env_key, "")
        return ""

    def _persist(self, env_key: str, value: str) -> None:
        """Write key=value to the .env file (injectable for testing)."""
        _update_env_file(env_key, value, self._env_path)
