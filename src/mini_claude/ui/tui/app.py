"""Textual-based TUI for mini-claude-code."""

from __future__ import annotations

from rich.panel import Panel
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.widgets import Footer, Header, Input, RichLog, Static

from mini_claude.core.query_engine import QueryEngine


class MiniClaudeApp(App[None]):
    """Main Textual application."""

    CSS = """
    #status {
        height: 1;
        padding: 0 1;
    }

    #chat {
        height: 1fr;
        border: round #666666;
        padding: 0 1;
    }

    #live_response {
        min-height: 3;
        border: round #3b82f6;
        padding: 0 1;
        margin-top: 1;
    }

    #input {
        margin-top: 1;
    }
    """

    BINDINGS = [Binding("ctrl+c", "quit", "Quit")]

    def __init__(self, query_engine: QueryEngine):
        super().__init__()
        self.query_engine = query_engine
        self._is_busy = False

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield Static("Ready", id="status")
        yield RichLog(id="chat", markup=True, wrap=True, highlight=True)
        yield Static("", id="live_response")
        yield Input(placeholder="Type a message or /exit, /clear, /history", id="input")
        yield Footer()

    def on_mount(self) -> None:
        chat = self.query_one("#chat", RichLog)
        provider_name = self.query_engine.provider.model_name
        chat.write(
            Panel(
                f"[bold cyan]mini-claude-code[/] ({provider_name})\n"
                "[dim]Textual TUI mode[/]\n"
                "[dim]Commands: /exit /clear /history[/]",
                expand=False,
            )
        )
        self.query_one("#input", Input).focus()

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        user_input = event.value.strip()
        event.input.value = ""

        if not user_input:
            return

        if self._is_busy:
            self._set_status("Busy: wait for current response to finish")
            return

        if user_input.startswith("/"):
            await self._handle_command(user_input)
            return

        await self._run_query(user_input)

    async def _run_query(self, user_input: str) -> None:
        chat = self.query_one("#chat", RichLog)
        live = self.query_one("#live_response", Static)

        self._set_busy(True)
        self._set_status("Thinking...")
        chat.write(f"[bold green]You:[/] {user_input}")

        response_parts: list[str] = []
        live.update("[bold blue]Claude:[/] ")

        try:
            async for text in self.query_engine.run(user_input):
                response_parts.append(text)
                live.update("[bold blue]Claude:[/] " + "".join(response_parts))

            response = "".join(response_parts).strip() or "[dim](no response)[/]"
            chat.write(f"[bold blue]Claude:[/] {response}")
            chat.write("")
            live.update("")
            self._set_status("Ready")
        except Exception as exc:
            live.update("")
            chat.write(f"[bold red]Error:[/] {type(exc).__name__}: {exc}")
            self._set_status("Error")
        finally:
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

        chat.write(f"[bold red]Unknown command:[/] {command}")
        self._set_status("Ready")

    def _set_busy(self, busy: bool) -> None:
        self._is_busy = busy
        input_widget = self.query_one("#input", Input)
        input_widget.disabled = busy
        if not busy:
            input_widget.focus()

    def _set_status(self, status: str) -> None:
        self.query_one("#status", Static).update(status)


class TextualTUI:
    """Async wrapper matching the SimpleREPL interface."""

    def __init__(self, query_engine: QueryEngine):
        self._app = MiniClaudeApp(query_engine=query_engine)

    async def run(self) -> None:
        """Run the TUI app."""
        await self._app.run_async()
