"""Custom system prompt builder for Vanna Agent."""

from __future__ import annotations

from vanna.core.system_prompt import SystemPromptBuilder
from vanna.core.tool import ToolSchema
from vanna.core.user import User

from ai_chat.prompts.system import build_system_prompt


class ModePromptBuilder(SystemPromptBuilder):
    """Build system prompt based on mode (rag|sql|hybrid)."""

    def __init__(self, mode: str = "rag", persona: str | None = None):
        self.mode = mode
        self.persona = persona or "general"

    async def build_system_prompt(self, user: User, tools: list[ToolSchema]):
        return build_system_prompt(self.persona, mode=self.mode)


__all__ = ["ModePromptBuilder"]
