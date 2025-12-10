"""Pydantic schemas for AI chat (new module)."""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional, Union
from uuid import uuid4

from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    conversation_id: Optional[str] = None
    messages: List[ChatMessage]
    persona: Optional[str] = Field(default="general")
    mode: Optional[str] = Field(default="rag", description="rag | sql | hybrid")


class ToolCall(BaseModel):
    tool: str
    arguments: dict
    result: Any


class ChatResponse(BaseModel):
    conversation_id: str = Field(default_factory=lambda: str(uuid4()))
    reply: ChatMessage
    tool_calls: Optional[List[ToolCall]] = None


class ApiEnvelope(BaseModel):
    code: int
    message: str
    data: Optional[ChatResponse] = None


# ======================== SSE Event Types ========================


class SSEEventType(str, Enum):
    """SSE event types for streaming chat."""
    SESSION = "session"
    STATUS = "status"
    TOOL_START = "tool_start"
    TOOL_RESULT = "tool_result"
    TEXT_DELTA = "text_delta"
    COMPONENT = "component"
    DONE = "done"
    ERROR = "error"


class SSESessionEvent(BaseModel):
    """Session initialization event."""
    type: str = SSEEventType.SESSION.value
    conversation_id: str


class SSEStatusEvent(BaseModel):
    """Status/progress update event."""
    type: str = SSEEventType.STATUS.value
    content: str


class SSEToolStartEvent(BaseModel):
    """Tool execution started event."""
    type: str = SSEEventType.TOOL_START.value
    tool: str
    args: Optional[Dict[str, Any]] = None


class SSEToolResultEvent(BaseModel):
    """Tool execution result event."""
    type: str = SSEEventType.TOOL_RESULT.value
    tool: str
    success: bool
    data: Optional[Dict[str, Any]] = None


class SSETextDeltaEvent(BaseModel):
    """Streaming text fragment event."""
    type: str = SSEEventType.TEXT_DELTA.value
    content: str


class SSEComponentEvent(BaseModel):
    """Rich component event (dataframe, chart, search results)."""
    type: str = SSEEventType.COMPONENT.value
    component_type: str  # "dataframe" | "chart" | "search_results"
    data: Dict[str, Any]
    title: Optional[str] = None


class SSEDoneEvent(BaseModel):
    """Stream completion event."""
    type: str = SSEEventType.DONE.value
    conversation_id: str
    tool_calls: Optional[List[ToolCall]] = None


class SSEErrorEvent(BaseModel):
    """Error event."""
    type: str = SSEEventType.ERROR.value
    message: str
    code: Optional[int] = None


SSEEvent = Union[
    SSESessionEvent,
    SSEStatusEvent,
    SSEToolStartEvent,
    SSEToolResultEvent,
    SSETextDeltaEvent,
    SSEComponentEvent,
    SSEDoneEvent,
    SSEErrorEvent,
]


__all__ = [
    "ChatMessage",
    "ChatRequest",
    "ChatResponse",
    "ToolCall",
    "ApiEnvelope",
    "SSEEventType",
    "SSESessionEvent",
    "SSEStatusEvent",
    "SSEToolStartEvent",
    "SSEToolResultEvent",
    "SSETextDeltaEvent",
    "SSEComponentEvent",
    "SSEDoneEvent",
    "SSEErrorEvent",
    "SSEEvent",
]
