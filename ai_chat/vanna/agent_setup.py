"""Build Vanna Agent with registry/memory/resolver."""

from __future__ import annotations

from typing import Optional

from vanna import Agent, AgentConfig
from vanna.integrations.local import MemoryConversationStore

from ai_chat.vanna.llm_factory import build_llm_service
from ai_chat.vanna.memory import build_agent_memory
from ai_chat.vanna.tools import register_tools
from ai_chat.vanna.user_resolver import SimpleUserResolver, AuthUserResolver
from ai_chat.vanna.system_prompt_builder import ModePromptBuilder
from ai_chat.vanna.registry import LoggingToolRegistry
from common.auth.service import Roles


def build_agent(
    mode: str,
    stream: bool = False,
    user_role: str = Roles.VIEWER,
    use_auth: bool = False,
):
    """Create a Vanna Agent configured for a given mode (rag|sql|hybrid).

    Args:
        mode: Agent mode - "rag", "sql", or "hybrid"
        stream: Whether to enable streaming responses
        user_role: User role for permission control
        use_auth: Whether to use AuthUserResolver (for authenticated sessions)
    """

    registry = LoggingToolRegistry()
    register_tools(registry, mode, user_role)

    # 选择用户解析器
    if use_auth:
        user_resolver = AuthUserResolver(default_role=user_role)
    else:
        user_resolver = SimpleUserResolver()

    agent = Agent(
        llm_service=build_llm_service(),
        tool_registry=registry,
        user_resolver=user_resolver,
        agent_memory=build_agent_memory(),
        conversation_store=MemoryConversationStore(),
        config=AgentConfig(stream_responses=stream, temperature=0.2, max_tool_iterations=5),
        system_prompt_builder=ModePromptBuilder(mode=mode, user_role=user_role),
    )
    return agent


__all__ = ["build_agent"]
