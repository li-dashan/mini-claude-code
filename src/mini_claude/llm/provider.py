"""
Abstract base class for LLM providers.

This defines the interface that all LLM implementations must follow.
"""

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator

from mini_claude.core import Message, ToolDefinition, LLMChunk


class LLMProvider(ABC):
    """Abstract base class for LLM providers."""

    @abstractmethod
    async def stream(
        self,
        messages: list[Message],
        tools: list[ToolDefinition],
        system: str = "",
    ) -> AsyncIterator[LLMChunk]:
        """
        Stream the LLM response.

        Args:
            messages: Conversation history
            tools: Available tools
            system: System prompt

        Yields:
            LLMChunk objects (TextDelta, ToolUseDelta, or StopSignal)
        """
        ...

    @property
    @abstractmethod
    def model_name(self) -> str:
        """Return the model name being used."""
        ...
