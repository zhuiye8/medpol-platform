"""Custom system prompt builder for Vanna Agent."""

from __future__ import annotations

from vanna.core.system_prompt import SystemPromptBuilder
from vanna.core.tool import ToolSchema
from vanna.core.user import User

from ai_chat.prompts.system import build_system_prompt
from common.auth.service import Roles


class ModePromptBuilder(SystemPromptBuilder):
    """Build system prompt based on mode (rag|sql|hybrid) and user role."""

    def __init__(
        self,
        mode: str = "rag",
        persona: str | None = None,
        user_role: str = Roles.VIEWER,
    ):
        self.mode = mode
        self.persona = persona or "general"
        self.user_role = user_role

    async def build_system_prompt(self, user: User, tools: list[ToolSchema]):
        # 从 user metadata 获取角色（如果有）
        role = user.metadata.get("role", self.user_role) if user.metadata else self.user_role
        return build_system_prompt(self.persona, mode=self.mode, user_role=role)


__all__ = ["ModePromptBuilder"]
