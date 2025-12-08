"""Pydantic schemas for AI chat (new module)."""

from __future__ import annotations

from typing import Any, List, Optional
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


__all__ = ["ChatMessage", "ChatRequest", "ChatResponse", "ToolCall", "ApiEnvelope"]
