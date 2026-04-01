"""Simple REPL UI using rich library."""

import json

from rich.console import Console
from rich.prompt import Prompt
from rich.panel import Panel

from mini_claude.core.config import RuntimeConfig
from mini_claude.core.query_engine import QueryEngine
from mini_claude.ui.buddy import TerminalBuddy


class SimpleREPL:
    """Simple terminal REPL using rich library."""

    def __init__(self, query_engine: QueryEngine):
        """Initialize the REPL.

        Args:
            query_engine: The query engine to use
        """
        self.query_engine = query_engine
        self.console = Console()
        self._history: list[str] = []
        self.buddy = TerminalBuddy()
        self._config = RuntimeConfig(query_engine)

    def print_banner(self) -> None:
        """Print welcome banner."""
        provider_name = self.query_engine.provider.model_name
        self.console.print(
            Panel(
                f"[bold cyan]mini-claude-code[/] ({provider_name})\n"
                "[dim]An AI Agent framework for learning\n"
                "Type [bold]/exit[/], [bold]/clear[/], [bold]/history[/], [bold]/buddy[/], "
                "[bold]/profile[/], [bold]/pet[/], [bold]/feed[/], [bold]/tools[/], [bold]/tool[/]",
                expand=False,
            )
        )
        self.console.print(self.buddy.render_panel())

    def print_tool_call(self, tool_name: str) -> None:
        """Print tool call notification."""
        self.console.print(f"[bold cyan][Tool][/] {tool_name}")

    def print_tool_result(self, elapsed_ms: float, is_error: bool = False) -> None:
        """Print tool result notification."""
        color = "red" if is_error else "green"
        self.console.print(f"[dim][{color}]✓[/{color}] {elapsed_ms:.0f}ms[/dim]")

    async def run(self) -> None:
        """Run the REPL loop."""
        self.print_banner()

        while True:
            try:
                user_input = Prompt.ask("[bold green]You[/]").strip()

                if not user_input:
                    continue

                # Handle special commands
                if user_input.startswith("/"):
                    await self._handle_command(user_input)
                    continue

                # Add to history
                self._history.append(user_input)
                self.buddy.on_user_message(user_input)
                self.buddy.on_thinking()

                # Run the query
                self.console.print("[bold blue]Claude[/]", end=" ")
                response_parts: list[str] = []
                tool_stats = {"calls": 0, "errors": 0}

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
                        self.console.print(text, end="", soft_wrap=True)
                finally:
                    self.query_engine.tool_registry.execute = original_execute  # type: ignore[method-assign]

                self.buddy.on_response(
                    True,
                    "".join(response_parts),
                    tool_calls=tool_stats["calls"],
                    tool_errors=tool_stats["errors"],
                )
                self.console.print()  # Newline after response
                self.console.print(f"[dim]{self.buddy.render_line()}[/dim]")

            except KeyboardInterrupt:
                self.console.print("\n[yellow]Interrupted[/]")
                break
            except Exception as exc:
                self.buddy.on_response(False, "")
                self.console.print(f"[red]Error:[/] {type(exc).__name__}: {exc}")
                self.console.print(f"[dim]{self.buddy.render_line()}[/dim]")
            except EOFError:
                break

    async def _handle_command(self, command: str) -> None:
        """Handle special commands.

        Args:
            command: The command to handle
        """
        if command == "/exit":
            self.console.print("[yellow]Goodbye![/]")
            raise EOFError

        elif command == "/clear":
            self.query_engine.context_manager.clear()
            self.console.print("[green]History cleared[/]")

        elif command == "/history":
            tokens = self.query_engine.context_manager.get_approx_tokens()
            self.console.print(f"[dim]Estimated tokens: {tokens:,}[/dim]")

        elif command == "/buddy":
            self.console.print(self.buddy.render_panel())
            for line in self.buddy.list_profiles():
                self.console.print(f"[dim]{line}[/dim]")

        elif command == "/profile":
            self.console.print(self.buddy.render_profile_card())

        elif command == "/pet":
            self.console.print(f"[green]{self.buddy.pet()}[/green]")
            self.console.print(f"[dim]{self.buddy.render_line()}[/dim]")

        elif command == "/feed":
            self.console.print(f"[green]{self.buddy.feed()}[/green]")
            self.console.print(f"[dim]{self.buddy.render_line()}[/dim]")

        elif command.startswith("/show-config"):
            parts = command.split(maxsplit=1)
            if len(parts) == 1:
                for key, val, desc, needs_restart in self._config.all_entries():
                    tag = "  [dim](restart)[/dim]" if needs_restart else ""
                    self.console.print(
                        f"  [cyan]{key:<18}[/cyan] [yellow]{val}[/yellow]"
                        f"  [dim]{desc}[/dim]{tag}"
                    )
            else:
                key = parts[1].strip()
                val = self._config.get(key)
                if val is None:
                    self.console.print(f"[red]Unknown key: {key!r}[/red]")
                else:
                    self.console.print(f"[cyan]{key}[/cyan] = [yellow]{val}[/yellow]")

        elif command.startswith("/set-config"):
            parts = command.split(maxsplit=2)
            if len(parts) < 3:
                self.console.print("[dim]Usage: /set-config <key> <value>[/dim]")
            else:
                _, key, value = parts
                self.console.print(self._config.set(key, value))

        elif command == "/tools":
            tools = self.query_engine.tool_registry.get_definitions()
            if not tools:
                self.console.print("[dim]No tools registered.[/dim]")
                return
            for tool in tools:
                self.console.print(
                    f"[cyan]{tool['name']}[/cyan] [dim]- {tool['description']}[/dim]"
                )

        elif command.startswith("/tool"):
            parts = command.split(maxsplit=2)
            if len(parts) < 3:
                self.console.print("[dim]Usage: /tool <name> <json-args>[/dim]")
                self.console.print("[dim]Example: /tool glob {\"pattern\":\"src/**/*.py\"}[/dim]")
                return
            _, name, raw_args = parts
            try:
                parsed = json.loads(raw_args)
            except json.JSONDecodeError as exc:
                self.console.print(f"[red]Invalid JSON args:[/] {exc}")
                return
            if not isinstance(parsed, dict):
                self.console.print("[red]Tool args must be a JSON object.[/red]")
                return

            self.console.print(f"[bold cyan][Tool][/] {name}")
            result = await self.query_engine.tool_registry.execute(name, parsed)
            color = "red" if result.is_error else "green"
            self.console.print(f"[{color}]{result.content}[/{color}]")

        else:
            self.console.print(f"[red]Unknown command: {command}[/red]")
