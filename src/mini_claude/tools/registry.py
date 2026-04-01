"""Tool registry for managing and executing tools."""

from mini_claude.core import ToolResult, ToolDefinition
from .base import Tool


class ToolRegistry:
    """Registry for tools available to the agent."""

    def __init__(self) -> None:
        """Initialize the tool registry."""
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        """Register a tool."""
        self._tools[tool.name] = tool

    def get_definitions(self) -> list[ToolDefinition]:
        """Get all tool definitions for sending to LLM."""
        return [tool.definition for tool in self._tools.values()]

    async def execute(self, name: str, input_: dict) -> ToolResult:
        """Execute a tool by name with the given input.

        Args:
            name: Tool name
            input_: Input parameters

        Returns:
            ToolResult with content and error flag
        """
        if name not in self._tools:
            return ToolResult(
                content=f"Tool '{name}' not found",
                is_error=True,
            )

        tool = self._tools[name]
        try:
            return await tool.execute(**input_)
        except TypeError as e:
            return ToolResult(
                content=f"Invalid arguments for tool '{name}': {e}",
                is_error=True,
            )
        except Exception as e:
            return ToolResult(
                content=f"Tool execution failed: {type(e).__name__}: {e}",
                is_error=True,
            )
