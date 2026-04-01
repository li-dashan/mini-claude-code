"""Context manager for handling conversation history and tokens."""

from mini_claude.core import Message, TextContent, ToolResultContent, ToolUseContent


class ContextManager:
    """Manages conversation history and token budgets."""

    def __init__(self, system_prompt: str = "", max_tokens: int = 200000):
        """Initialize context manager.

        Args:
            system_prompt: System prompt for the conversation
            max_tokens: Maximum tokens to keep in context
        """
        self.system_prompt = system_prompt
        self.max_tokens = max_tokens
        self.compression_threshold = int(max_tokens * 0.75)
        self._messages: list[Message] = []
        self._approx_tokens = 0  # Rough estimate: chars // 4

    def add_user_message(self, text: str) -> None:
        """Add a user message.

        Args:
            text: User message text
        """
        msg = Message(
            role="user",
            content=[TextContent(text=text)],
        )
        self._messages.append(msg)
        self._approx_tokens += len(text) // 4

    def add_assistant_turn(
        self,
        text_parts: list[str],
        tool_uses: list = None,
    ) -> None:
        """Add an assistant message from a turn.

        Args:
            text_parts: List of text content parts
            tool_uses: List of ToolUseDelta objects
        """
        if tool_uses is None:
            tool_uses = []

        content: list = []

        # Add text content
        for text in text_parts:
            if text:
                content.append(TextContent(text=text))
                self._approx_tokens += len(text) // 4

        # Add tool uses
        for tool_use in tool_uses:
            content.append(ToolUseContent(
                id=tool_use.id,
                name=tool_use.name,
                input=tool_use.input,
            ))
            self._approx_tokens += 500  # estimate tool call at 500 tokens

        if content:
            msg = Message(role="assistant", content=content)
            self._messages.append(msg)

    def add_tool_results(self, results: list[ToolResultContent]) -> None:
        """Add tool results to the last assistant message.

        Args:
            results: List of ToolResultContent objects
        """
        if not self._messages or self._messages[-1].role != "assistant":
            # Create a new assistant message with tool results
            msg = Message(role="assistant", content=results)
            self._messages.append(msg)
        else:
            # Add to last message
            self._messages[-1].content.extend(results)

        # Track token estimate
        for result in results:
            self._approx_tokens += len(result.content) // 4

    def get_messages(self) -> list[Message]:
        """Get all messages in history."""
        return self._messages

    def get_approx_tokens(self) -> int:
        """Get approximate token count."""
        return self._approx_tokens

    def clear(self) -> None:
        """Clear conversation history."""
        self._messages = []
        self._approx_tokens = 0

    async def maybe_compress(self, provider=None) -> bool:
        """Check if compression is needed and compress if necessary.

        Args:
            provider: LLM provider (for Phase 2 compression)

        Returns:
            True if compression was performed, False otherwise
        """
        # Phase 1: just return False, compression is not implemented yet
        if self._approx_tokens < self.compression_threshold:
            return False
        # TODO: Implement Phase 2 compression
        return False
