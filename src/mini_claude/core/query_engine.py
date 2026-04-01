"""
Main agentic loop - the core learning component.

This module orchestrates the interaction between the user, LLM, and tools.
It demonstrates the fundamental architecture of an AI agent with tool use.
"""

import asyncio
from collections.abc import AsyncIterator

from mini_claude.core import TextDelta, ToolUseDelta, StopSignal
from mini_claude.llm.provider import LLMProvider
from mini_claude.tools.registry import ToolRegistry
from .context_manager import ContextManager


class QueryEngine:
    """Main agentic loop orchestrator."""

    def __init__(
        self,
        provider: LLMProvider,
        tool_registry: ToolRegistry,
        context_manager: ContextManager,
        max_iterations: int = 10,
    ):
        """Initialize the query engine.

        Args:
            provider: LLM provider to use
            tool_registry: Tool registry with available tools
            context_manager: Context manager for conversation state
            max_iterations: Maximum iterations of agentic loop
        """
        self.provider = provider
        self.tool_registry = tool_registry
        self.context_manager = context_manager
        self.max_iterations = max_iterations

    async def run(self, user_input: str) -> AsyncIterator[str]:
        """
        Execute the agentic loop.

        This is the core learning function. It demonstrates:
        1. Adding user input to context
        2. Streaming LLM response and yielding text in real-time
        3. Collecting tool calls from the streamed response
        4. Executing tools concurrently when all tool calls are collected
        5. Adding tool results back to context
        6. Repeating until the LLM signals completion

        Args:
            user_input: The user's input text

        Yields:
            Text chunks from the assistant's response
        """
        # ── Step 1: Add user message to context ──────────────────────────────

        self.context_manager.add_user_message(user_input)

        # ── Main agentic loop ──────────────────────────────────────────────────

        for iteration in range(self.max_iterations):
            # Check if context needs compression
            await self.context_manager.maybe_compress(self.provider)

            # ── Step 2: Stream LLM response ──────────────────────────────────
            # We stream from the LLM and collect:
            # - Text chunks to yield to the user
            # - Tool use blocks to execute later
            # - Stop signal to know when the LLM is done

            text_buffer: list[str] = []
            pending_tool_calls: list[ToolUseDelta] = []
            is_done = False

            async for chunk in self.provider.stream(
                messages=self.context_manager.get_messages(),
                tools=self.tool_registry.get_definitions(),
                system=self.context_manager.system_prompt,
            ):
                if isinstance(chunk, TextDelta):
                    # ── TextDelta: Yield text immediately to user ──────────────
                    text_buffer.append(chunk.text)
                    yield chunk.text

                elif isinstance(chunk, ToolUseDelta):
                    # ── ToolUseDelta: Collect for later execution ──────────────
                    pending_tool_calls.append(chunk)

                elif isinstance(chunk, StopSignal):
                    # ── StopSignal: LLM has finished responding ──────────────
                    is_done = True
                    break

            # ── Step 3: Add assistant message to context ──────────────────────────
            # We've now collected the complete assistant response.
            # Add it to context before executing tools.

            self.context_manager.add_assistant_turn(
                text_parts=text_buffer,
                tool_uses=pending_tool_calls,
            )

            # ── Step 4: Check if loop should continue ────────────────────────────
            # If no tools were called, the LLM is done and we break the loop.

            if not pending_tool_calls or is_done:
                break

            # ── Step 5: Execute all pending tools concurrently ──────────────────
            # Important: We must execute ALL tools from this turn before
            # continuing to the next LLM call. This matches the Anthropic API
            # requirement that all tool_use blocks must have corresponding
            # tool_result blocks before the next user message.

            tool_results = await asyncio.gather(
                *[self._execute_tool(tool_call) for tool_call in pending_tool_calls],
                return_exceptions=False,
            )

            # ── Step 6: Add tool results to context ──────────────────────────────

            self.context_manager.add_tool_results(tool_results)
            # Continue to next iteration of the loop

        # ── Loop complete ──────────────────────────────────────────────────────

    async def _execute_tool(self, tool_call: ToolUseDelta):
        """Execute a single tool call and return the result.

        Important: Errors are returned as tool_result with is_error=True,
        not raised as exceptions. This allows the LLM to see the error
        and potentially recover or explain the issue to the user.

        Args:
            tool_call: The tool use request from the LLM

        Returns:
            ToolResultContent describing the tool execution result
        """
        from mini_claude.core import ToolResultContent

        try:
            result = await self.tool_registry.execute(tool_call.name, tool_call.input)
            return ToolResultContent(
                tool_use_id=tool_call.id,
                content=result.content,
                is_error=result.is_error,
            )
        except Exception as e:
            return ToolResultContent(
                tool_use_id=tool_call.id,
                content=f"Tool execution failed: {type(e).__name__}: {e}",
                is_error=True,
            )
