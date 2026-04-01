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
    system_prompt: str = "You are helpful."

    def clear(self) -> None:
        self.cleared = True

    def get_approx_tokens(self) -> int:
        return self.tokens


@dataclass
class _FakeProvider:
    model_name: str = "test-model"


class _FakeToolResult:
    def __init__(self, content: str, is_error: bool = False) -> None:
        self.content = content
        self.is_error = is_error


class _FakeToolRegistry:
    def get_definitions(self) -> list[dict]:
        return [
            {
                "name": "read_file",
                "description": "Read files from workspace",
                "input_schema": {"type": "object"},
            },
            {
                "name": "glob",
                "description": "Glob file paths",
                "input_schema": {"type": "object"},
            },
        ]

    async def execute(self, name: str, input_: dict) -> _FakeToolResult:
        if name == "glob":
            pattern = input_.get("pattern", "")
            return _FakeToolResult(content=f"matched: {pattern}", is_error=False)
        return _FakeToolResult(content=f"Tool '{name}' not found", is_error=True)


@dataclass
class _FakeQueryEngine:
    context_manager: _FakeContextManager
    provider: _FakeProvider
    tool_registry: _FakeToolRegistry
    max_iterations: int = 10


@pytest.fixture
def app_with_stubs(monkeypatch: pytest.MonkeyPatch) -> tuple[MiniClaudeApp, _FakeChat, _FakeStatus, _FakeContextManager]:
    context_manager = _FakeContextManager()
    query_engine = _FakeQueryEngine(
        context_manager=context_manager,
        provider=_FakeProvider(),
        tool_registry=_FakeToolRegistry(),
    )
    app = MiniClaudeApp(query_engine=query_engine)  # type: ignore[arg-type]

    # Prevent any .env file writes during tests
    monkeypatch.setattr(app._config, "_persist", lambda key, value: None)

    chat = _FakeChat()
    status = _FakeStatus()
    buddy_card = _FakeStatus()
    buddy_roster = _FakeStatus()
    hint = _FakeStatus()

    def fake_query_one(selector: str, _type):
        if selector == "#chat":
            return chat
        if selector == "#status":
            return status
        if selector == "#buddy_card":
            return buddy_card
        if selector == "#buddy_roster":
            return buddy_roster
        if selector == "#hint":
            return hint
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


@pytest.mark.asyncio
async def test_handle_pet_command_updates_buddy_status(
    app_with_stubs: tuple[MiniClaudeApp, _FakeChat, _FakeStatus, _FakeContextManager],
) -> None:
    app, chat, status, _ = app_with_stubs

    await app._handle_command("/pet")

    assert len(chat.writes) == 1
    assert "seems happier." in chat.writes[0]
    assert chat.writes[0].startswith("[green]")
    assert status.last_text == "Ready"


@pytest.mark.asyncio
async def test_handle_feed_command_updates_buddy_status(
    app_with_stubs: tuple[MiniClaudeApp, _FakeChat, _FakeStatus, _FakeContextManager],
) -> None:
    app, chat, status, _ = app_with_stubs

    await app._handle_command("/feed")

    assert len(chat.writes) == 1
    assert "energy restored." in chat.writes[0]
    assert chat.writes[0].startswith("[green]")
    assert status.last_text == "Ready"


@pytest.mark.asyncio
async def test_handle_profile_command_writes_profile_card(
    app_with_stubs: tuple[MiniClaudeApp, _FakeChat, _FakeStatus, _FakeContextManager],
) -> None:
    from rich.panel import Panel

    app, chat, status, _ = app_with_stubs

    await app._handle_command("/profile")

    assert len(chat.writes) == 1
    assert isinstance(chat.writes[0], Panel)
    assert status.last_text == "Ready"


# ── Buddy system unit tests ────────────────────────────────────────────────────

def test_buddy_faces_are_multiline() -> None:
    """Every mood face must be at least 4 lines of ASCII art."""
    from mini_claude.ui.buddy import TerminalBuddy

    buddy = TerminalBuddy()
    for key, companion in buddy._companions.items():
        for mood, face in companion.profile.faces.items():
            lines = face.split("\n")
            assert len(lines) >= 4, (
                f"{companion.profile.name}/{mood} face has only {len(lines)} line(s)"
            )


def test_buddy_thinking_frames_present() -> None:
    """Every buddy must have at least 4 thinking animation frames."""
    from mini_claude.ui.buddy import TerminalBuddy

    buddy = TerminalBuddy()
    for key, companion in buddy._companions.items():
        frames = companion.profile.thinking_frames
        assert len(frames) >= 4, (
            f"{companion.profile.name} has only {len(frames)} thinking frame(s)"
        )
        for i, frame in enumerate(frames):
            assert "\n" in frame, (
                f"{companion.profile.name} thinking frame {i} is single-line"
            )


def test_render_buddy_card_contains_name_and_stats() -> None:
    """render_buddy_card output must include buddy name, ♥, and ⚡ markers."""
    from mini_claude.ui.buddy import TerminalBuddy
    import re

    buddy = TerminalBuddy()
    card = buddy.render_buddy_card()
    plain = re.sub(r"\[.*?\]", "", card)  # strip Rich markup

    assert buddy.active_name in plain
    assert "♥" in plain
    assert "⚡" in plain


def test_render_line_compact_is_single_line() -> None:
    """`render_line()` must return a single line (no embedded newlines)."""
    from mini_claude.ui.buddy import TerminalBuddy

    buddy = TerminalBuddy()
    line = buddy.render_line()
    assert "\n" not in line


def test_new_animal_keys_present() -> None:
    """The four expected animal keys must exist."""
    from mini_claude.ui.buddy import TerminalBuddy

    buddy = TerminalBuddy()
    keys = set(buddy._companions.keys())
    assert keys == {"kapi", "tanuki", "bao", "ember"}


def test_tick_animation_advances_frame() -> None:
    """tick_animation must advance frame_index while mood is thinking."""
    from mini_claude.ui.buddy import TerminalBuddy

    buddy = TerminalBuddy()
    companion = buddy._active
    companion.state.mood = "thinking"
    companion.frame_index = 0
    buddy.tick_animation()
    assert companion.frame_index == 1


def test_tick_animation_wraps_around() -> None:
    """frame_index must wrap back to 0 after the last frame."""
    from mini_claude.ui.buddy import TerminalBuddy

    buddy = TerminalBuddy()
    companion = buddy._active
    n = len(companion.profile.thinking_frames)
    companion.state.mood = "thinking"
    companion.frame_index = n - 1
    buddy.tick_animation()
    assert companion.frame_index == 0


# ── /show-config and /set-config command tests ────────────────────────────────

@pytest.mark.asyncio
async def test_show_config_all_lists_keys(
    app_with_stubs: tuple[MiniClaudeApp, _FakeChat, _FakeStatus, _FakeContextManager],
) -> None:
    app, chat, status, _ = app_with_stubs

    await app._handle_command("/show-config")

    assert len(chat.writes) == 9  # 8 env-backed + system_prompt
    written = "\n".join(chat.writes)
    assert "MAX_ITERATIONS" in written
    assert "LLM_PROVIDER" in written
    assert "system_prompt" in written
    assert status.last_text == "Ready"


@pytest.mark.asyncio
async def test_show_config_specific_key(
    app_with_stubs: tuple[MiniClaudeApp, _FakeChat, _FakeStatus, _FakeContextManager],
) -> None:
    app, chat, status, _ = app_with_stubs

    await app._handle_command("/show-config system_prompt")

    assert len(chat.writes) == 1
    assert "system_prompt" in chat.writes[0]
    assert "You are helpful." in chat.writes[0]
    assert status.last_text == "Ready"


@pytest.mark.asyncio
async def test_show_config_unknown_key(
    app_with_stubs: tuple[MiniClaudeApp, _FakeChat, _FakeStatus, _FakeContextManager],
) -> None:
    app, chat, status, _ = app_with_stubs

    await app._handle_command("/show-config nonexistent")

    assert len(chat.writes) == 1
    assert "Unknown key" in chat.writes[0]
    assert status.last_text == "Ready"


@pytest.mark.asyncio
async def test_set_config_max_iterations(
    app_with_stubs: tuple[MiniClaudeApp, _FakeChat, _FakeStatus, _FakeContextManager],
) -> None:
    app, chat, status, _ = app_with_stubs

    await app._handle_command("/set-config MAX_ITERATIONS 20")

    assert app.query_engine.max_iterations == 20
    assert len(chat.writes) == 1
    assert "MAX_ITERATIONS" in chat.writes[0]
    assert "20" in chat.writes[0]
    assert status.last_text == "Ready"


@pytest.mark.asyncio
async def test_set_config_system_prompt(
    app_with_stubs: tuple[MiniClaudeApp, _FakeChat, _FakeStatus, _FakeContextManager],
) -> None:
    app, chat, status, _ = app_with_stubs

    await app._handle_command("/set-config system_prompt Be concise.")

    assert app.query_engine.context_manager.system_prompt == "Be concise."
    assert "system_prompt" in chat.writes[0]
    assert status.last_text == "Ready"


@pytest.mark.asyncio
async def test_set_config_invalid_provider(
    app_with_stubs: tuple[MiniClaudeApp, _FakeChat, _FakeStatus, _FakeContextManager],
) -> None:
    """Setting LLM_PROVIDER to an unknown value must be rejected."""
    app, chat, status, _ = app_with_stubs

    await app._handle_command("/set-config LLM_PROVIDER gemini")

    assert "Invalid provider" in chat.writes[0]
    assert status.last_text == "Ready"


@pytest.mark.asyncio
async def test_set_config_invalid_type(
    app_with_stubs: tuple[MiniClaudeApp, _FakeChat, _FakeStatus, _FakeContextManager],
) -> None:
    app, chat, status, _ = app_with_stubs

    await app._handle_command("/set-config MAX_ITERATIONS not_a_number")

    assert "integer" in chat.writes[0]
    assert status.last_text == "Ready"


@pytest.mark.asyncio
async def test_set_config_out_of_range(
    app_with_stubs: tuple[MiniClaudeApp, _FakeChat, _FakeStatus, _FakeContextManager],
) -> None:
    app, chat, status, _ = app_with_stubs

    await app._handle_command("/set-config MAX_ITERATIONS 99")

    assert "1 and 50" in chat.writes[0]
    assert status.last_text == "Ready"


@pytest.mark.asyncio
async def test_set_config_missing_value(
    app_with_stubs: tuple[MiniClaudeApp, _FakeChat, _FakeStatus, _FakeContextManager],
) -> None:
    app, chat, status, _ = app_with_stubs

    await app._handle_command("/set-config MAX_ITERATIONS")

    assert "Usage" in chat.writes[0]
    assert status.last_text == "Ready"


@pytest.mark.asyncio
async def test_set_config_env_key_persisted(
    app_with_stubs: tuple[MiniClaudeApp, _FakeChat, _FakeStatus, _FakeContextManager],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Setting an env-backed key should call _persist (mocked to no-op in fixture)."""
    app, chat, status, _ = app_with_stubs
    persisted: list[tuple[str, str]] = []
    monkeypatch.setattr(app._config, "_persist", lambda k, v: persisted.append((k, v)))

    await app._handle_command("/set-config LLM_PROVIDER anthropic")

    assert persisted == [("LLM_PROVIDER", "anthropic")]
    assert status.last_text == "Ready"


@pytest.mark.asyncio
async def test_tools_command_lists_registered_tools(
    app_with_stubs: tuple[MiniClaudeApp, _FakeChat, _FakeStatus, _FakeContextManager],
) -> None:
    app, chat, status, _ = app_with_stubs

    await app._handle_command("/tools")

    out = "\n".join(chat.writes)
    assert "read_file" in out
    assert "glob" in out
    assert status.last_text == "Ready"


@pytest.mark.asyncio
async def test_tool_command_executes_tool(
    app_with_stubs: tuple[MiniClaudeApp, _FakeChat, _FakeStatus, _FakeContextManager],
) -> None:
    app, chat, status, _ = app_with_stubs

    await app._handle_command('/tool glob {"pattern":"src/**/*.py"}')

    assert "matched: src/**/*.py" in chat.writes[0]
    assert status.last_text == "Ready"


@pytest.mark.asyncio
async def test_tool_command_rejects_invalid_json(
    app_with_stubs: tuple[MiniClaudeApp, _FakeChat, _FakeStatus, _FakeContextManager],
) -> None:
    app, chat, status, _ = app_with_stubs

    await app._handle_command('/tool glob {bad-json}')

    assert "Invalid JSON args" in chat.writes[0]
    assert status.last_text == "Ready"
