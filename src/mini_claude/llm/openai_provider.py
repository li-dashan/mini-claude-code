"""OpenAI LLM provider implementation."""

import json
import logging
from collections.abc import AsyncIterator

import openai

from mini_claude.core import (
    Message,
    ToolDefinition,
    LLMChunk,
    TextDelta,
    ToolUseDelta,
    StopSignal,
    TextContent,
    ToolResultContent,
)
from .provider import LLMProvider


logger = logging.getLogger(__name__)


class OpenAIProvider(LLMProvider):
    """OpenAI-compatible provider (works with OpenAI, 147api, and any OpenAI-compatible endpoint)."""

    def __init__(self, api_key: str, model: str = "gpt-4o", base_url: str | None = None):
        """Initialize OpenAI-compatible provider.

        Args:
            api_key: API key for the service
            model: Model name (default: gpt-4o)
            base_url: Optional custom API base URL for third-party providers
                      (e.g. https://api.147api.com/v1). Defaults to OpenAI's endpoint.
        """
        self.client = openai.AsyncOpenAI(api_key=api_key, base_url=base_url or None)
        self._model = model
        self._base_url = base_url or "https://api.openai.com/v1"
        logger.info(
            "OpenAIProvider initialized (model=%s, base_url=%s)",
            self._model,
            self._base_url,
        )

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
        """Stream response from OpenAI.

        Converts mini-claude Message format to OpenAI API format,
        collects tool_calls and yields complete ToolUseDelta objects.
        """
        # Convert internal Message format to OpenAI format
        openai_messages = []

        # Add system message if provided
        if system:
            openai_messages.append({
                "role": "system",
                "content": system,
            })

        for msg in messages:
            if msg.role == "user":
                # User messages are simple text content
                text_parts = []
                tool_results = []
                for content in msg.content:
                    if isinstance(content, TextContent):
                        text_parts.append(content.text)
                    elif isinstance(content, ToolResultContent):
                        tool_results.append({
                            "type": "tool",
                            "tool_use_id": content.tool_use_id,
                            "content": content.content,
                        })

                # Add text message
                if text_parts:
                    openai_messages.append({
                        "role": "user",
                        "content": "\n".join(text_parts),
                    })

                # Add tool results as separate messages
                for result in tool_results:
                    openai_messages.append({
                        "role": "tool",
                        "tool_call_id": result["tool_use_id"],
                        "content": result["content"],
                    })

            else:  # assistant message
                assistant_content = []
                tool_calls = []

                for content in msg.content:
                    if isinstance(content, TextContent):
                        if content.text:
                            assistant_content.append({
                                "type": "text",
                                "text": content.text,
                            })
                    # Note: ToolUseContent would be in tool_calls in OpenAI format

                openai_messages.append({
                    "role": "assistant",
                    "content": assistant_content if assistant_content else [{"type": "text", "text": ""}],
                })

        # Convert ToolDefinition to OpenAI format
        openai_tools = None
        if tools:
            openai_tools = [
                {
                    "type": "function",
                    "function": {
                        "name": tool["name"],
                        "description": tool["description"],
                        "parameters": tool["input_schema"],
                    },
                }
                for tool in tools
            ]

        # Stream from OpenAI-compatible endpoint.
        # `chat.completions.create(..., stream=True)` returns a coroutine that
        # resolves to an async iterator, not an async context manager.
        logger.debug(
            "Starting OpenAI-compatible stream request (model=%s, base_url=%s, messages=%d, tools=%d)",
            self._model,
            self._base_url,
            len(openai_messages),
            len(openai_tools or []),
        )

        try:
            stream = await self.client.chat.completions.create(
                model=self._model,
                max_tokens=4096,
                tools=openai_tools,
                messages=openai_messages,
                stream=True,
            )
            logger.debug("Stream established successfully (model=%s)", self._model)

            accumulated_tool_calls: dict = {}

            async for chunk in stream:
                if chunk.choices and len(chunk.choices) > 0:
                    choice = chunk.choices[0]

                    if choice.delta.content:
                        yield TextDelta(text=choice.delta.content)

                    if choice.delta.tool_calls:
                        for tool_call in choice.delta.tool_calls:
                            idx = tool_call.index
                            if idx not in accumulated_tool_calls:
                                accumulated_tool_calls[idx] = {
                                    "id": "",
                                    "name": "",
                                    "arguments": "",
                                }

                            if tool_call.id:
                                accumulated_tool_calls[idx]["id"] = tool_call.id
                            if tool_call.function.name:
                                accumulated_tool_calls[idx]["name"] = tool_call.function.name
                            if tool_call.function.arguments:
                                accumulated_tool_calls[idx]["arguments"] += tool_call.function.arguments

                    if choice.finish_reason == "tool_calls":
                        # Yield all accumulated tool calls
                        for tool_call in accumulated_tool_calls.values():
                            try:
                                input_dict = json.loads(tool_call["arguments"])
                            except json.JSONDecodeError:
                                input_dict = {}

                            yield ToolUseDelta(
                                id=tool_call["id"],
                                name=tool_call["name"],
                                input=input_dict,
                            )
                        accumulated_tool_calls = {}

                    if choice.finish_reason == "stop":
                        yield StopSignal(stop_reason="end_turn")

        except openai.APIConnectionError as err:
            cause = repr(getattr(err, "__cause__", None))
            logger.exception(
                "APIConnectionError to OpenAI-compatible endpoint "
                "(model=%s, base_url=%s, messages=%d, tools=%d, cause=%s)",
                self._model,
                self._base_url,
                len(openai_messages),
                len(openai_tools or []),
                cause,
            )
            raise
        except openai.APIStatusError as err:
            logger.exception(
                "APIStatusError from OpenAI-compatible endpoint "
                "(status=%s, model=%s, base_url=%s)",
                err.status_code,
                self._model,
                self._base_url,
            )
            raise
        except Exception:
            logger.exception(
                "Unexpected error during OpenAI-compatible stream "
                "(model=%s, base_url=%s)",
                self._model,
                self._base_url,
            )
            raise
