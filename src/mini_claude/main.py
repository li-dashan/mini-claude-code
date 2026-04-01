"""Main entry point for mini-claude-code."""

import asyncio
import logging
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


logger = logging.getLogger(__name__)


def setup_logging() -> None:
    """Setup application logging from env vars."""
    level_name = os.getenv("LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


def load_env() -> None:
    """Load environment variables from .env file."""
    env_path = Path(".env")
    if env_path.exists():
        load_dotenv(env_path)
    else:
        load_dotenv(".env.example")


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
    setup_logging()

    # Load environment
    load_env()

    # Get configuration
    provider_name = os.getenv("LLM_PROVIDER", "anthropic")
    work_dir = os.getenv("WORK_DIR", ".")
    max_iterations = int(os.getenv("MAX_ITERATIONS", "10"))
    ui_mode = os.getenv("UI_MODE", "simple")

    logger.info(
        "Startup config loaded (provider=%s, ui_mode=%s, work_dir=%s, max_iterations=%s)",
        provider_name,
        ui_mode,
        work_dir,
        max_iterations,
    )

    if provider_name == "openai":
        logger.info("OpenAI-compatible base_url=%s", os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1"))

    # Setup components
    provider = get_llm_provider(provider_name)
    tools = setup_tools(work_dir)

    system_prompt = (
        "You are a helpful AI assistant that can use tools to help the user. "
        "You have access to bash, file reading/writing, and file search tools. "
        "Always provide clear explanations of what you're doing."
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
