"""
Core type definitions for mini-claude-code.

All types used throughout the project are defined here to avoid duplication.
Other modules import types from this module only.
"""

from typing import TypedDict, Union, Literal
from dataclasses import dataclass, field


# ── Message System ──────────────────────────────────────────────


@dataclass
class TextContent:
    """A text message content block."""
    type: Literal["text"] = "text"
    text: str = ""


@dataclass
class ToolUseContent:
    """An assistant's request to use a tool."""
    type: Literal["tool_use"] = "tool_use"
    id: str = ""
    name: str = ""
    input: dict = field(default_factory=dict)


@dataclass
class ToolResultContent:
    """The result of a tool execution."""
    type: Literal["tool_result"] = "tool_result"
    tool_use_id: str = ""
    content: str = ""
    is_error: bool = False


MessageContent = Union[TextContent, ToolUseContent, ToolResultContent]


@dataclass
class Message:
    """A single message in the conversation."""
    role: Literal["user", "assistant"]
    content: list[MessageContent]


# ── Tool System ──────────────────────────────────────────────


@dataclass
class ToolResult:
    """The result returned by a tool execution."""
    content: str
    is_error: bool = False


class ToolDefinition(TypedDict):
    """Tool definition sent to the LLM."""
    name: str
    description: str
    input_schema: dict  # JSON Schema


# ── LLM Streaming Output ──────────────────────────────────────────


@dataclass
class TextDelta:
    """A chunk of streamed text from the LLM."""
    type: Literal["text_delta"] = "text_delta"
    text: str = ""


@dataclass
class ToolUseDelta:
    """A complete tool_use block from the LLM (collected after complete)."""
    type: Literal["tool_use"] = "tool_use"
    id: str = ""
    name: str = ""
    input: dict = field(default_factory=dict)


@dataclass
class StopSignal:
    """Signal that the LLM has finished responding."""
    type: Literal["stop"] = "stop"
    stop_reason: str = "end_turn"


LLMChunk = Union[TextDelta, ToolUseDelta, StopSignal]


# ── Permission System (Phase 2) ────────────────────────────────────


class PermissionLevel:
    """Permission levels for tool execution."""
    AUTO = "auto"   # Auto-approve
    ASK = "ask"     # Ask user
    DENY = "deny"   # Always deny
