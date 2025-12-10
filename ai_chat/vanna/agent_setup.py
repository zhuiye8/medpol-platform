"""Build Vanna Agent with registry/memory/resolver."""

from __future__ import annotations

from vanna import Agent, AgentConfig
from vanna.integrations.local import MemoryConversationStore

from ai_chat.vanna.llm_factory import build_llm_service
from ai_chat.vanna.memory import build_agent_memory
from ai_chat.vanna.tools import register_tools
from ai_chat.vanna.user_resolver import SimpleUserResolver
from ai_chat.vanna.system_prompt_builder import ModePromptBuilder
from ai_chat.vanna.registry import LoggingToolRegistry


def build_agent(mode: str, stream: bool = False):
    """Create a Vanna Agent configured for a given mode (rag|sql|hybrid).

    Args:
        mode: Agent mode - "rag", "sql", or "hybrid"
        stream: Whether to enable streaming responses
    """

    registry = LoggingToolRegistry()
    register_tools(registry, mode)

    agent = Agent(
        llm_service=build_llm_service(),
        tool_registry=registry,
        user_resolver=SimpleUserResolver(),
        agent_memory=build_agent_memory(),
        conversation_store=MemoryConversationStore(),
        config=AgentConfig(stream_responses=stream, temperature=0.2, max_tool_iterations=8),
        system_prompt_builder=ModePromptBuilder(mode=mode),
    )
    return agent


__all__ = ["build_agent"]
