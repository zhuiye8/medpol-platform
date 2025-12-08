"""Custom ToolRegistry to log tool calls for API response."""

from __future__ import annotations

from typing import Any, Dict, List

from vanna.core.registry import ToolRegistry
from vanna.core.tool import ToolCall, ToolContext, ToolResult


class LoggingToolRegistry(ToolRegistry):
    """Wrap ToolRegistry.execute to capture tool calls."""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._last_calls: List[Dict[str, Any]] = []

    @property
    def last_calls(self) -> List[Dict[str, Any]]:
        return list(self._last_calls)

    async def execute(self, tool_call: ToolCall, context: ToolContext) -> ToolResult:
        result = await super().execute(tool_call, context)
        record = {
            "tool_name": tool_call.name,
            "args": tool_call.arguments,
            "success": result.success,
            "result_for_llm": result.result_for_llm,
            "metadata": result.metadata,
            "error": result.error,
        }
        self._last_calls.append(record)
        # also stash on context metadata for downstream use
        context.metadata.setdefault("tool_log", []).append(record)
        return result

    def clear_log(self) -> None:
        self._last_calls.clear()


__all__ = ["LoggingToolRegistry"]
