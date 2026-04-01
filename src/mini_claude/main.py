"""Main entry point for mini-claude-code."""

import asyncio
import getpass
import os
import re
import sys
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


def _persist_env_key(key: str, value: str, env_file: Path = Path.home() / ".mini-claude.env") -> None:
    """Persist one key to the user-level env file."""
    env_file.parent.mkdir(parents=True, exist_ok=True)
    line = f"{key}={value}"
    if not env_file.exists():
        env_file.write_text(line + "\n", encoding="utf-8")
        return

    content = env_file.read_text(encoding="utf-8")
    pattern = re.compile(rf"^{re.escape(key)}\s*=.*", re.MULTILINE)
    if pattern.search(content):
        content = pattern.sub(line, content)
    else:
        if content and not content.endswith("\n"):
            content += "\n"
        content += line + "\n"
    env_file.write_text(content, encoding="utf-8")


def _is_placeholder_api_key(value: str) -> bool:
    """Return True when a key looks like an example/placeholder rather than a real key."""
    val = value.strip().lower()
    if not val:
        return True
    placeholders = {
        "sk-...",
        "sk-ant-...",
        "<api-key>",
        "<your-api-key>",
        "your-api-key",
    }
    return val in placeholders or val.endswith("...")


def load_env() -> None:
    """Load environment variables from a single fixed file.
    
    If ~/.mini-claude.env doesn't exist, create it from .env.example template.
    """
    env_file = Path.home() / ".mini-claude.env"
    
    # If env file doesn't exist, create from template
    if not env_file.exists():
        # Find .env.example in project root
        project_root = Path(__file__).parent.parent.parent
        env_example = project_root / ".env.example"
        
        if env_example.exists():
            env_file.parent.mkdir(parents=True, exist_ok=True)
            example_content = env_example.read_text(encoding="utf-8")
            env_file.write_text(example_content, encoding="utf-8")
    
    load_dotenv(env_file)


def get_llm_provider(provider_name: str = "anthropic"):
    """Get LLM provider based on env config.

    Args:
        provider_name: Name of the provider (anthropic or openai)

    Returns:
        LLMProvider instance
    """
    def _resolve_api_key(var_name: str, provider_label: str) -> str:
        existing = os.getenv(var_name, "").strip()
        if existing and not _is_placeholder_api_key(existing):
            return existing

        # Interactive fallback for CLI usage.
        if sys.stdin.isatty():
            print(f"{var_name} not set (or still placeholder) for {provider_label}.")
            entered = getpass.getpass("Input API key (hidden): ").strip()
            if entered:
                os.environ[var_name] = entered
                _persist_env_key(var_name, entered)
            return entered

        # Non-interactive mode (CI/service): provide explicit guidance.
        raise ValueError(
            f"{var_name} is not configured. Set it in ~/.mini-claude.env "
            "or via MINI_CLAUDE_ENV_FILE."
        )

    if provider_name == "openai":
        api_key = _resolve_api_key("OPENAI_API_KEY", "openai")
        model = os.getenv("OPENAI_MODEL", "gpt-4o")
        base_url = os.getenv("OPENAI_BASE_URL") or None
        return OpenAIProvider(api_key=api_key, model=model, base_url=base_url)
    else:
        # Default to Anthropic
        api_key = _resolve_api_key("ANTHROPIC_API_KEY", "anthropic")
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
    ui_mode = os.getenv("UI_MODE", "tui")

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
