"""Simple REPL UI using rich library."""

from rich.console import Console
from rich.prompt import Prompt
from rich.panel import Panel

from mini_claude.core.query_engine import QueryEngine


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

    def print_banner(self) -> None:
        """Print welcome banner."""
        provider_name = self.query_engine.provider.model_name
        self.console.print(
            Panel(
                f"[bold cyan]mini-claude-code[/] ({provider_name})\n"
                "[dim]An AI Agent framework for learning\n"
                "Type [bold]/exit[/] to quit, [bold]/clear[/] to clear history[/]",
                expand=False,
            )
        )

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

                # Run the query
                self.console.print("[bold blue]Claude[/]", end=" ")

                async for text in self.query_engine.run(user_input):
                    self.console.print(text, end="", soft_wrap=True)

                self.console.print()  # Newline after response

            except KeyboardInterrupt:
                self.console.print("\n[yellow]Interrupted[/]")
                break
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

        else:
            self.console.print(f"[red]Unknown command: {command}[/red]")
