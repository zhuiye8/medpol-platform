"""FastAPI router using Vanna Agent (no manual tool loop)."""

from __future__ import annotations

import json
import uuid
from typing import List

from fastapi import APIRouter
from vanna.core.user import RequestContext

from ai_chat.core.schemas import ApiEnvelope, ChatMessage, ChatRequest, ChatResponse, ToolCall
from ai_chat.core.memory import memory
from ai_chat.vanna.agent_setup import build_agent
from ai_chat.vanna.registry import LoggingToolRegistry

router = APIRouter()
_agent_cache = {}


def _stringify(obj) -> str:
    try:
        return json.dumps(obj, ensure_ascii=False)
    except Exception:
        return str(obj)


def _get_agent(mode: str):
    key = mode or "rag"
    if key not in _agent_cache:
        _agent_cache[key] = build_agent(key)
    return _agent_cache[key]


def _pick_reply(components: List) -> str:
    """Prefer last text component."""

    text = ""
    for comp in components:
        if hasattr(comp, "content") and comp.content:
            text = comp.content
        elif getattr(comp, "simple_component", None) and getattr(comp.simple_component, "text", None):
            text = comp.simple_component.text
    return (text or "").strip()


def _collect_tool_calls(agent) -> List[ToolCall]:
    """Collect tool calls from LoggingToolRegistry if present."""

    calls: List[ToolCall] = []
    registry = getattr(agent, "tool_registry", None)
    if isinstance(registry, LoggingToolRegistry):
        for rec in registry.last_calls:
            calls.append(
                ToolCall(
                    tool=rec.get("tool_name") or "",
                    arguments=rec.get("args") or {},
                    result=rec.get("metadata") or rec.get("result_for_llm"),
                )
            )
        registry.clear_log()
    return calls


@router.post("/chat", response_model=ApiEnvelope)
async def chat(request: ChatRequest) -> ApiEnvelope:
    conv_id = request.conversation_id or str(uuid.uuid4())
    mode = (request.mode or "rag").lower()
    history = memory.load(conv_id)
    user_messages = request.messages or []
    if not user_messages:
        return ApiEnvelope(code=1, message="缺少用户输入", data=None)

    agent = _get_agent(mode)
    req_context = RequestContext(metadata={"mode": mode})

    components = []
    async for comp in agent.send_message(
        request_context=req_context,
        message=user_messages[-1].content,
        conversation_id=conv_id,
    ):
        components.append(comp)

    reply_text = _pick_reply(components) or "暂无回复"

    reply = ChatMessage(role="assistant", content=reply_text)
    new_items = [m.model_dump() for m in user_messages] + [reply.model_dump()]
    memory.append(conv_id, history, new_items)

    tool_calls = _collect_tool_calls(agent) or None
    response = ChatResponse(conversation_id=conv_id, reply=reply, tool_calls=tool_calls)
    return ApiEnvelope(code=0, message="ok", data=response)
