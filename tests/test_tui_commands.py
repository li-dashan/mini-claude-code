"""Tests for Textual TUI slash-command handling."""

from __future__ import annotations

from dataclasses import dataclass

import pytest
from textual.widgets import Static

from mini_claude.ui.tui.app import MiniClaudeApp


class _FakeChat:
    def __init__(self) -> None:
        self.writes: list[str] = []
        self.cleared = False

    def write(self, message: str) -> None:
        self.writes.append(message)

    def clear(self) -> None:
        self.cleared = True


class _FakeStatus(Static):
    def __init__(self) -> None:
        super().__init__("")
        self.last_text = ""

    def update(self, renderable) -> None:  # type: ignore[override]
        self.last_text = str(renderable)


@dataclass
class _FakeContextManager:
    cleared: bool = False
    tokens: int = 1234

    def clear(self) -> None:
        self.cleared = True

    def get_approx_tokens(self) -> int:
        return self.tokens


@dataclass
class _FakeProvider:
    model_name: str = "test-model"


@dataclass
class _FakeQueryEngine:
    context_manager: _FakeContextManager
    provider: _FakeProvider


@pytest.fixture
def app_with_stubs(monkeypatch: pytest.MonkeyPatch) -> tuple[MiniClaudeApp, _FakeChat, _FakeStatus, _FakeContextManager]:
    context_manager = _FakeContextManager()
    query_engine = _FakeQueryEngine(context_manager=context_manager, provider=_FakeProvider())
    app = MiniClaudeApp(query_engine=query_engine)  # type: ignore[arg-type]

    chat = _FakeChat()
    status = _FakeStatus()

    def fake_query_one(selector: str, _type):
        if selector == "#chat":
            return chat
        if selector == "#status":
            return status
        raise AssertionError(f"Unexpected selector: {selector}")

    monkeypatch.setattr(app, "query_one", fake_query_one)
    return app, chat, status, context_manager


@pytest.mark.asyncio
async def test_handle_history_command_shows_token_count(
    app_with_stubs: tuple[MiniClaudeApp, _FakeChat, _FakeStatus, _FakeContextManager],
) -> None:
    app, chat, status, _ = app_with_stubs

    await app._handle_command("/history")

    assert chat.writes == ["[dim]Estimated tokens: 1,234[/dim]"]
    assert status.last_text == "Ready"


@pytest.mark.asyncio
async def test_handle_clear_command_clears_context_and_chat(
    app_with_stubs: tuple[MiniClaudeApp, _FakeChat, _FakeStatus, _FakeContextManager],
) -> None:
    app, chat, status, context_manager = app_with_stubs

    await app._handle_command("/clear")

    assert context_manager.cleared is True
    assert chat.cleared is True
    assert status.last_text == "History cleared"


@pytest.mark.asyncio
async def test_handle_unknown_command_reports_error(
    app_with_stubs: tuple[MiniClaudeApp, _FakeChat, _FakeStatus, _FakeContextManager],
) -> None:
    app, chat, status, _ = app_with_stubs

    await app._handle_command("/unknown")

    assert chat.writes == ["[bold red]Unknown command:[/] /unknown"]
    assert status.last_text == "Ready"


@pytest.mark.asyncio
async def test_handle_exit_command_calls_exit(
    app_with_stubs: tuple[MiniClaudeApp, _FakeChat, _FakeStatus, _FakeContextManager],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app, _chat, _status, _ = app_with_stubs
    called = False

    def fake_exit() -> None:
        nonlocal called
        called = True

    monkeypatch.setattr(app, "exit", fake_exit)

    await app._handle_command("/exit")

    assert called is True
