"""Anthropic Claude LLM provider implementation."""

import json
from collections.abc import AsyncIterator

import anthropic

from mini_claude.core import (
    Message,
    ToolDefinition,
    LLMChunk,
    TextDelta,
    ToolUseDelta,
    StopSignal,
    TextContent,
    ToolUseContent,
    ToolResultContent,
)
from .provider import LLMProvider


class AnthropicProvider(LLMProvider):
    """Claude provider using Anthropic's official SDK."""

    def __init__(self, api_key: str, model: str = "claude-sonnet-4-5-20251022"):
        """Initialize Anthropic provider.

        Args:
            api_key: Anthropic API key
            model: Model name (default: claude-sonnet-4-5-20251022)
        """
        self.client = anthropic.AsyncAnthropic(api_key=api_key)
        self._model = model

    @property
    def model_name(self) -> str:
        """Return the model name."""
        return self._model

    async def stream(
        self,
        messages: list[Message],
        tools: list[ToolDefinition],
        system: str = "",
    ) -> AsyncIterator[LLMChunk]:
        """Stream response from Claude.

        Converts mini-claude Message format to Anthropic API format,
        collects tool_use blocks and yields complete ToolUseDelta objects.
        """
        # Convert internal Message format to Anthropic format
        anthropic_messages = []
        for msg in messages:
            anthropic_content = []
            for content in msg.content:
                if isinstance(content, TextContent):
                    anthropic_content.append({
                        "type": "text",
                        "text": content.text,
                    })
                elif isinstance(content, ToolResultContent):
                    anthropic_content.append({
                        "type": "tool_result",
                        "tool_use_id": content.tool_use_id,
                        "content": content.content,
                        "is_error": content.is_error,
                    })
                # ToolUseContent is for assistant messages only, handled in stream

            anthropic_messages.append({
                "role": msg.role,
                "content": anthropic_content,
            })

        # Convert ToolDefinition to Anthropic format
        anthropic_tools = [
            {
                "name": tool["name"],
                "description": tool["description"],
                "input_schema": tool["input_schema"],
            }
            for tool in tools
        ]

        # Stream from Claude
        async with self.client.messages.stream(
            model=self._model,
            max_tokens=4096,
            system=system,
            tools=anthropic_tools if anthropic_tools else None,
            messages=anthropic_messages,
        ) as stream:
            current_tool_use: dict | None = None

            async for event in stream:
                if event.type == "content_block_start":
                    if event.content_block.type == "tool_use":
                        current_tool_use = {
                            "id": event.content_block.id,
                            "name": event.content_block.name,
                            "input_str": "",
                        }

                elif event.type == "content_block_delta":
                    if event.delta.type == "text_delta":
                        yield TextDelta(text=event.delta.text)
                    elif event.delta.type == "input_json_delta":
                        if current_tool_use is not None:
                            current_tool_use["input_str"] += event.delta.partial_json

                elif event.type == "content_block_stop":
                    if current_tool_use is not None:
                        # Parse the accumulated JSON
                        try:
                            input_dict = json.loads(current_tool_use["input_str"])
                        except json.JSONDecodeError:
                            input_dict = {}

                        yield ToolUseDelta(
                            id=current_tool_use["id"],
                            name=current_tool_use["name"],
                            input=input_dict,
                        )
                        current_tool_use = None

                elif event.type == "message_stop":
                    yield StopSignal(stop_reason="end_turn")
