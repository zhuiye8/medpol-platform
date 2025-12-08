"""Agent memory selection for Vanna."""

from __future__ import annotations

from vanna.capabilities.agent_memory import AgentMemory
from vanna.integrations.local.agent_memory.in_memory import DemoAgentMemory


def build_agent_memory() -> AgentMemory:
    """Use in-memory demo memory (can swap to persistent later)."""

    return DemoAgentMemory()


__all__ = ["build_agent_memory"]
