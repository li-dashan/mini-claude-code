"""Abstract base class for tools."""

from abc import ABC, abstractmethod

from mini_claude.core import ToolResult, ToolDefinition


class Tool(ABC):
    """Abstract base class for all tools."""

    name: str
    description: str

    @property
    @abstractmethod
    def definition(self) -> ToolDefinition:
        """Return the tool definition to be sent to the LLM."""
        ...

    @abstractmethod
    async def execute(self, **kwargs) -> ToolResult:
        """Execute the tool with the given arguments."""
        ...
