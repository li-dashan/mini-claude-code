"""Main entry point for mini-claude-code."""

import asyncio
import os
from pathlib import Path

from dotenv import load_dotenv

from mini_claude.llm import AnthropicProvider, OpenAIProvider
from mini_claude.tools import (
    BashTool,
    ReadFileTool,
    WriteFileTool,
    GlobTool,
    ToolRegistry,
)
from mini_claude.core.context_manager import ContextManager
from mini_claude.core.query_engine import QueryEngine
from mini_claude.ui.simple_repl import SimpleREPL
from mini_claude.ui.tui import TextualTUI


def _find_upwards(filename: str, start: Path) -> Path | None:
    """Search for a file in start dir and its parents."""
    for directory in [start, *start.parents]:
        candidate = directory / filename
        if candidate.exists():
            return candidate
    return None


def load_env() -> None:
    """Load environment variables.

    Priority:
    1. MINI_CLAUDE_ENV_FILE (absolute or relative path)
    2. First `.env` found from CWD upwards
    3. `.env` near installed package/project root
    4. User config env (`~/.config/mini-claude/.env`, `~/.mini-claude/.env`)
    5. `.env.example` from CWD upwards
    6. `.env.example` near installed package/project root
    """
    explicit = os.getenv("MINI_CLAUDE_ENV_FILE")
    if explicit:
        explicit_path = Path(explicit).expanduser().resolve()
        if explicit_path.exists():
            load_dotenv(explicit_path)
            return

    cwd = Path.cwd().resolve()

    # Repository root when running from source tree is usually two levels above this file.
    package_root = Path(__file__).resolve().parents[2]

    candidates = [
        _find_upwards(".env", cwd),
        package_root / ".env",
        Path.home() / ".config" / "mini-claude" / ".env",
        Path.home() / ".mini-claude" / ".env",
        _find_upwards(".env.example", cwd),
        package_root / ".env.example",
    ]

    for path in candidates:
        if path is not None and path.exists():
            load_dotenv(path)
            return


def get_llm_provider(provider_name: str = "anthropic"):
    """Get LLM provider based on env config.

    Args:
        provider_name: Name of the provider (anthropic or openai)

    Returns:
        LLMProvider instance
    """
    if provider_name == "openai":
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY not set in environment")
        model = os.getenv("OPENAI_MODEL", "gpt-4o")
        base_url = os.getenv("OPENAI_BASE_URL") or None
        return OpenAIProvider(api_key=api_key, model=model, base_url=base_url)
    else:
        # Default to Anthropic
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY not set in environment")
        model = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-5-20251022")
        return AnthropicProvider(api_key=api_key, model=model)


def setup_tools(work_dir: str = ".") -> ToolRegistry:
    """Setup tool registry with all available tools.

    Args:
        work_dir: Working directory for tools

    Returns:
        Configured ToolRegistry
    """
    registry = ToolRegistry()

    # Register tools
    registry.register(BashTool(work_dir=work_dir))
    registry.register(ReadFileTool(work_dir=work_dir))
    registry.register(WriteFileTool(work_dir=work_dir))
    registry.register(GlobTool(work_dir=work_dir))

    return registry


def main() -> None:
    """Main entry point."""
    # Load environment
    load_env()

    # Get configuration
    provider_name = os.getenv("LLM_PROVIDER", "anthropic")
    work_dir = os.getenv("WORK_DIR", ".")
    max_iterations = int(os.getenv("MAX_ITERATIONS", "10"))
    ui_mode = os.getenv("UI_MODE", "simple")

    # Setup components
    provider = get_llm_provider(provider_name)
    tools = setup_tools(work_dir)

    system_prompt = (
        "You are a helpful AI assistant that can use tools to help the user. "
        "You have access to bash, file reading/writing, and file search tools. "
        "When a request involves filesystem state, shell commands, or codebase facts, "
        "prefer calling tools over guessing. "
        "Before claiming file contents, command output, or project state, verify with tools. "
        "If a tool fails, explain the failure and retry with corrected arguments when reasonable. "
        "Always provide clear explanations of what you're doing and base conclusions on tool results."
    )

    context_manager = ContextManager(system_prompt=system_prompt)
    query_engine = QueryEngine(
        provider=provider,
        tool_registry=tools,
        context_manager=context_manager,
        max_iterations=max_iterations,
    )

    # Run UI
    if ui_mode == "tui":
        ui = TextualTUI(query_engine)
        asyncio.run(ui.run())
    else:
        # Phase 1: Simple REPL
        ui = SimpleREPL(query_engine)
        asyncio.run(ui.run())


if __name__ == "__main__":
    main()
