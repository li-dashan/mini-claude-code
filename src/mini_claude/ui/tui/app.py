"""Textual-based TUI for mini-claude-code."""

from __future__ import annotations

from rich.panel import Panel
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.events import Key
from textual.widgets import Footer, Header, Input, RichLog, Static

from mini_claude.core.config import RuntimeConfig
from mini_claude.core.query_engine import QueryEngine
from mini_claude.ui.buddy import TerminalBuddy


class MiniClaudeApp(App[None]):
    """Main Textual application."""

    CSS = """
    #status {
        height: 1;
        padding: 0 2;
        background: #1f2937;
        color: #f8fafc;
    }

    #body {
        height: 1fr;
        padding: 1 1;
    }

    #workspace {
        width: 1fr;
        border: round #334155;
        padding: 1;
        margin-right: 1;
        background: #0b1220;
    }

    #chat {
        height: 1fr;
        border: round #475569;
        padding: 0 1;
        background: #111827;
    }

    #live_response {
        min-height: 3;
        border: round #0ea5e9;
        padding: 0 1;
        margin-top: 1;
        background: #0f172a;
    }

    #input {
        margin-top: 1;
    }

    #hint {
        height: 1;
        padding: 0 2;
        color: #475569;
        background: #0b1220;
    }

    #buddy_zone {
        width: 34;
        min-width: 30;
        border: round #0f766e;
        padding: 1;
        background: #042f2e;
    }

    #buddy_card {
        height: auto;
        border: round #2dd4bf;
        padding: 0 1;
        background: #134e4a;
    }

    #buddy_roster {
        margin-top: 1;
        height: auto;
        border: round #14b8a6;
        padding: 0 1;
        background: #115e59;
    }
    """

    BINDINGS = [Binding("ctrl+c", "quit", "Quit")]

    _COMMANDS = [
        "/exit", "/clear", "/history",
        "/buddy", "/profile", "/pet", "/feed",
        "/show-config", "/set-config",
    ]
    _CMD_DESC = {
        "/exit":        "quit",
        "/clear":       "clear history",
        "/history":     "token count",
        "/buddy":       "buddy status",
        "/profile":     "profile card",
        "/pet":         "pet buddy",
        "/feed":        "feed buddy",
        "/show-config": "show setting [key]",
        "/set-config":  "change setting <key> <value>",
    }

    def __init__(self, query_engine: QueryEngine):
        super().__init__()
        self.query_engine = query_engine
        self._is_busy = False
        self.buddy = TerminalBuddy()
        self._buddy_timer = None
        self._input_history: list[str] = []
        self._history_cursor: int = -1
        self._history_draft: str = ""
        self._completion_matches: list[str] = []
        self._completion_idx: int = -1
        self._config = RuntimeConfig(query_engine)

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield Static("Ready", id="status")
        with Horizontal(id="body"):
            with Vertical(id="workspace"):
                yield RichLog(id="chat", markup=True, wrap=True, highlight=True)
                yield Static("", id="live_response")
                yield Input(
                    placeholder="Ask anything — or type / for commands (Tab to complete)",
                    id="input",
                )
                yield Static("", id="hint")
            with Vertical(id="buddy_zone"):
                yield Static("", id="buddy_card")
                yield Static("", id="buddy_roster")
        yield Footer()

    def on_mount(self) -> None:
        chat = self.query_one("#chat", RichLog)
        provider_name = self.query_engine.provider.model_name
        chat.write(
            Panel(
                f"[bold cyan]mini-claude-code[/] ({provider_name})\n"
                "[dim]Textual TUI mode[/]\n"
                "[dim]Type [cyan]/[/cyan] and press [cyan]Tab[/cyan] to browse commands[/]",
                expand=False,
            )
        )
        self._refresh_buddy()
        self.query_one("#input", Input).focus()

    def on_input_changed(self, event: Input.Changed) -> None:
        """Update inline command hint and reset Tab-completion if user typed."""
        val = event.value
        hint = self.query_one("#hint", Static)
        # Reset completion state when user types (not when Tab filled a value)
        if val not in self._completion_matches:
            self._completion_matches = []
            self._completion_idx = -1
        if val == "/":
            parts = "  ".join(
                f"[dim cyan]{c}[/dim cyan][dim] {self._CMD_DESC[c]}[/dim]"
                for c in self._COMMANDS
            )
            hint.update(parts)
        elif val.startswith("/show-config") or val.startswith("/set-config"):
            tokens = val.split()
            cmd = tokens[0]
            # After command + space, hint available keys
            if len(tokens) >= 2 or val.endswith(" "):
                key_hint = "  ".join(
                    f"[cyan]{k}[/cyan]"
                    + ("[dim] ↺[/dim]" if restart else "")
                    for k, _, _, restart in self._config.all_entries()
                )
                hint.update(f"[dim]keys:[/dim] {key_hint}")
            else:
                hint.update(
                    f"[cyan]{cmd}[/cyan][dim] {self._CMD_DESC.get(cmd, '')}[/dim]"
                )
        elif val.startswith("/"):
            matches = [c for c in self._COMMANDS if c.startswith(val)]
            if matches:
                parts = "  ".join(
                    f"[cyan]{c}[/cyan][dim] {self._CMD_DESC[c]}[/dim]"
                    for c in matches
                )
                hint.update(parts)
            else:
                hint.update("[dim red]no matching command[/dim red]")
        else:
            hint.update("")

    def on_key(self, event: Key) -> None:
        """Handle up/down arrows for history and Tab for completion."""
        input_widget = self.query_one("#input", Input)
        if not input_widget.has_focus:
            return
        if event.key == "tab":
            val = input_widget.value
            if not val.startswith("/"):
                return
            tokens = val.split()
            # Second-level Tab: complete config key name after /show-config or /set-config
            if len(tokens) == 2 or (len(tokens) == 1 and val.endswith(" ")
                                    and tokens[0] in ("/show-config", "/set-config")):
                cmd = tokens[0]
                if cmd in ("/show-config", "/set-config"):
                    prefix = tokens[1] if len(tokens) == 2 else ""
                    key_matches = [k for k in self._config.keys() if k.startswith(prefix)]
                    if not self._completion_matches or val not in self._completion_matches:
                        self._completion_matches = [
                            f"{cmd} {k}" for k in key_matches
                        ]
                        self._completion_idx = -1
                    if self._completion_matches:
                        self._completion_idx = (self._completion_idx + 1) % len(self._completion_matches)
                        input_widget.value = self._completion_matches[self._completion_idx]
                        input_widget.cursor_position = len(input_widget.value)
                    event.prevent_default()
                    event.stop()
                    return
            # Top-level Tab: complete command name
            if not self._completion_matches or val not in self._completion_matches:
                self._completion_matches = [c for c in self._COMMANDS if c.startswith(val)]
                self._completion_idx = -1
            if self._completion_matches:
                self._completion_idx = (self._completion_idx + 1) % len(self._completion_matches)
                input_widget.value = self._completion_matches[self._completion_idx]
                input_widget.cursor_position = len(input_widget.value)
            event.prevent_default()
            event.stop()
            return
        if event.key == "up":
            if not self._input_history:
                return
            if self._history_cursor == -1:
                self._history_draft = input_widget.value
                self._history_cursor = len(self._input_history) - 1
            elif self._history_cursor > 0:
                self._history_cursor -= 1
            input_widget.value = self._input_history[self._history_cursor]
            input_widget.cursor_position = len(input_widget.value)
            event.prevent_default()
        elif event.key == "down":
            if self._history_cursor == -1:
                return
            if self._history_cursor < len(self._input_history) - 1:
                self._history_cursor += 1
                input_widget.value = self._input_history[self._history_cursor]
            else:
                self._history_cursor = -1
                input_widget.value = self._history_draft
            input_widget.cursor_position = len(input_widget.value)
            event.prevent_default()

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        user_input = event.value.strip()
        event.input.value = ""

        if not user_input:
            return

        if self._is_busy:
            self._set_status("Busy: wait for current response to finish")
            return

        # Track history; avoid consecutive duplicates
        if not self._input_history or self._input_history[-1] != user_input:
            self._input_history.append(user_input)
        self._history_cursor = -1
        self._history_draft = ""

        if user_input.startswith("/"):
            await self._handle_command(user_input)
            return

        await self._run_query(user_input)

    async def _run_query(self, user_input: str) -> None:
        chat = self.query_one("#chat", RichLog)
        live = self.query_one("#live_response", Static)

        self._set_busy(True)
        self.buddy.on_user_message(user_input)
        self.buddy.on_thinking()
        self._refresh_buddy()
        self._set_status("Thinking...")
        chat.write(f"[bold green]You:[/] {user_input}")

        response_parts: list[str] = []
        tool_stats = {"calls": 0, "errors": 0}
        live.update("[bold blue]Claude:[/] ")

        original_execute = self.query_engine.tool_registry.execute

        async def tracked_execute(name: str, input_: dict):
            tool_stats["calls"] += 1
            result = await original_execute(name, input_)
            if result.is_error:
                tool_stats["errors"] += 1
            return result

        self.query_engine.tool_registry.execute = tracked_execute  # type: ignore[method-assign]

        try:
            async for text in self.query_engine.run(user_input):
                response_parts.append(text)
                live.update("[bold blue]Claude:[/] " + "".join(response_parts))

            response = "".join(response_parts).strip() or "[dim](no response)[/]"
            chat.write(f"[bold blue]Claude:[/] {response}")
            chat.write("")
            live.update("")
            self.buddy.on_response(
                True,
                response,
                tool_calls=tool_stats["calls"],
                tool_errors=tool_stats["errors"],
            )
            self._refresh_buddy()
            self._set_status("Ready")
        except Exception as exc:
            live.update("")
            chat.write(f"[bold red]Error:[/] {type(exc).__name__}: {exc}")
            self.buddy.on_response(False, "")
            self._refresh_buddy()
            self._set_status("Error")
        finally:
            self.query_engine.tool_registry.execute = original_execute  # type: ignore[method-assign]
            self._set_busy(False)

    async def _handle_command(self, command: str) -> None:
        chat = self.query_one("#chat", RichLog)

        if command == "/exit":
            self.exit()
            return

        if command == "/clear":
            self.query_engine.context_manager.clear()
            chat.clear()
            self._set_status("History cleared")
            return

        if command == "/history":
            tokens = self.query_engine.context_manager.get_approx_tokens()
            chat.write(f"[dim]Estimated tokens: {tokens:,}[/dim]")
            self._set_status("Ready")
            return

        if command == "/buddy":
            chat.write(f"[dim]{self.buddy.render_line()}[/dim]")
            for line in self.buddy.list_profiles():
                chat.write(f"[dim]{line}[/dim]")
            self._set_status("Ready")
            self._refresh_buddy()
            return

        if command == "/profile":
            chat.write(self.buddy.render_profile_card())
            self._set_status("Ready")
            return

        if command == "/pet":
            chat.write(f"[green]{self.buddy.pet()}[/green]")
            self._refresh_buddy()
            self._set_status("Ready")
            return

        if command == "/feed":
            chat.write(f"[green]{self.buddy.feed()}[/green]")
            self._refresh_buddy()
            self._set_status("Ready")
            return

        if command.startswith("/show-config"):
            parts = command.split(maxsplit=1)
            if len(parts) == 1:
                # show all
                for key, val, desc, needs_restart in self._config.all_entries():
                    tag = "  [dim](restart)[/dim]" if needs_restart else ""
                    chat.write(
                        f"  [cyan]{key:<18}[/cyan] [yellow]{val}[/yellow]"
                        f"  [dim]{desc}[/dim]{tag}"
                    )
            else:
                key = parts[1].strip()
                val = self._config.get(key)
                if val is None:
                    chat.write(f"[red]Unknown key: {key!r}[/red]")
                else:
                    chat.write(f"[cyan]{key}[/cyan] = [yellow]{val}[/yellow]")
            self._set_status("Ready")
            return

        if command.startswith("/set-config"):
            parts = command.split(maxsplit=2)
            if len(parts) < 3:
                chat.write("[dim]Usage: /set-config <key> <value>[/dim]")
                self._set_status("Ready")
                return
            _, key, value = parts
            chat.write(self._config.set(key, value))
            self._set_status("Ready")
            return

        chat.write(f"[bold red]Unknown command:[/] {command}")
        self._set_status("Ready")

    def _set_busy(self, busy: bool) -> None:
        self._is_busy = busy
        input_widget = self.query_one("#input", Input)
        input_widget.disabled = busy
        if busy:
            self._buddy_timer = self.set_interval(0.2, self._animate_buddy)
        elif self._buddy_timer is not None:
            self._buddy_timer.stop()
            self._buddy_timer = None
        if not busy:
            input_widget.focus()

    def _set_status(self, status: str) -> None:
        self.query_one("#status", Static).update(status)

    def _refresh_buddy(self) -> None:
        self.query_one("#buddy_card", Static).update(self.buddy.render_buddy_card())
        roster_text = "\n".join(self.buddy.list_profiles())
        self.query_one("#buddy_roster", Static).update(roster_text)

    def _animate_buddy(self) -> None:
        if self._is_busy and self.buddy.state.mood == "thinking":
            self.buddy.tick_animation()
            self._refresh_buddy()


class TextualTUI:
    """Async wrapper matching the SimpleREPL interface."""

    def __init__(self, query_engine: QueryEngine):
        self._app = MiniClaudeApp(query_engine=query_engine)

    async def run(self) -> None:
        """Run the TUI app."""
        await self._app.run_async()
