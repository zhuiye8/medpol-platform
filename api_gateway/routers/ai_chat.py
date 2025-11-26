"""AI 对话路由（财务工具 + 知识搜索），修复历史工具配对问题，并打印返回日志。"""

from __future__ import annotations

import json
import logging
from typing import Any, List, Optional
from uuid import uuid4

from fastapi import APIRouter
from pydantic import BaseModel

from common.ai.orchestrator import AbilityRouter
from common.ai.providers import AIProviderError, AIProviderFactory
from common.ai.memory_store import MemoryStore
from common.ai.conversation_summarizer import ConversationSummarizer
from common.clients.finance_api.tools import FINANCE_TOOLS, execute_tool as execute_finance_tool
from common.clients.tavily_search import KNOWLEDGE_TOOLS, execute_knowledge_tool

logger = logging.getLogger(__name__)
router = APIRouter()
provider_factory = AIProviderFactory()
ability_router = AbilityRouter(provider_factory)
memory_store = MemoryStore()
summarizer = ConversationSummarizer()
ALLOWED_TOOL_NAMES = (
    {tool["function"]["name"] for tool in FINANCE_TOOLS}
    | {tool["function"]["name"] for tool in KNOWLEDGE_TOOLS}
)
SENSITIVE_KEYWORDS = ["finance_records", "ai_results", "sources", "crawler_jobs"]


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    conversation_id: Optional[str] = None
    messages: List[ChatMessage]
    stream: bool = False
    persona: Optional[str] = "general"


class ToolCall(BaseModel):
    tool: str
    arguments: dict
    result: Any


class ChatResponse(BaseModel):
    conversation_id: str
    reply: ChatMessage
    tool_calls: Optional[List[ToolCall]] = None


class ApiEnvelope(BaseModel):
    code: int
    message: str
    data: Optional[ChatResponse] = None


@router.post("/chat")
async def chat(request: ChatRequest):
    conversation_id = request.conversation_id or str(uuid4())
    persona = (request.persona or "general").lower()
    last_user_message = request.messages[-1].content if request.messages else ""

    summary, history = memory_store.load(conversation_id)
    history_messages = history or []

    decision_input = f"{summary}\n{last_user_message}" if summary else last_user_message
    context = ability_router.resolve(persona, decision_input)
    system_prompt = context.prompt
    logger.info(
        "Stage-A 判定",
        extra={
            "conversation_id": conversation_id,
            "persona": persona,
            "decision_input": decision_input[:300],
            "use_finance": context.use_finance,
            "use_knowledge": context.use_knowledge,
            "category": context.category,
        },
    )

    logger.info(
        "收到对话请求",
        extra={
            "conversation_id": conversation_id,
            "persona": persona,
            "message_count": len(request.messages),
            "user_query": request.messages[-1].content if request.messages else None,
        },
    )

    messages = [{"role": "system", "content": system_prompt}]
    if summary:
        messages.append({"role": "system", "content": f"(会话摘要) {summary}"})

    # 过滤历史：仅保留成对的 assistant stub + tool，丢弃孤立 tool
    filtered_history: list[dict] = []
    last_stub_id: Optional[str] = None
    for msg in history_messages:
        if msg.get("role") == "assistant" and msg.get("tool_calls"):
            tc = msg["tool_calls"][0]
            last_stub_id = tc.get("id")
            filtered_history.append(msg)
        elif msg.get("role") == "tool":
            tcid = msg.get("tool_call_id")
            if tcid and tcid == last_stub_id:
                filtered_history.append(msg)
        else:
            filtered_history.append(msg)

    combined = filtered_history + [{"role": m.role, "content": m.content} for m in request.messages]
    messages.extend(combined)

    logger.info(
        "Stage-B 入参",
        extra={
            "conversation_id": conversation_id,
            "summary_present": bool(summary),
            "history_len": len(history_messages),
            "messages_preview": _safe_snippet(messages, 800),
            "tools_enabled": bool(context.use_finance or context.use_knowledge),
        },
    )

    try:
        provider = provider_factory.get_client()
    except AIProviderError as exc:
        logger.error("AI Provider 初始化失败: %s", exc)
        envelope = ApiEnvelope(code=1001, message=f"AI Provider 初始化失败: {exc}", data=None)
        _log_client_payload(conversation_id, envelope)
        return envelope

    client = provider.client
    model = provider.model

    tools_payload = []
    if context.use_finance:
        tools_payload.extend(FINANCE_TOOLS)
    if context.use_knowledge:
        tools_payload.extend(KNOWLEDGE_TOOLS)
    tools_payload = tools_payload or None

    chat_kwargs = {"model": model, "messages": messages}
    if tools_payload:
        chat_kwargs["tools"] = tools_payload
        chat_kwargs["tool_choice"] = "auto"

    try:
        first_response = client.chat.completions.create(**chat_kwargs)
    except Exception as exc:  # pragma: no cover
        logger.error("LLM 调用失败: %s", exc, exc_info=True)
        envelope = ApiEnvelope(code=1002, message=f"AI对话失败: {exc}", data=None)
        _log_client_payload(conversation_id, envelope)
        return envelope

    assistant_message = first_response.choices[0].message
    logger.info(
        "Stage-B 首次响应",
        extra={
            "conversation_id": conversation_id,
            "has_tool_calls": bool(assistant_message.tool_calls),
            "content_preview": _safe_snippet(assistant_message.content, 400),
        },
    )

    if tools_payload and assistant_message.tool_calls:
        logger.info("LLM 工具调用数: %d", len(assistant_message.tool_calls))
        tool_call_results = []
        history_tool_messages: list[dict[str, Any]] = []

        for tool_call in assistant_message.tool_calls:
            tool_name = tool_call.function.name
            if tool_name not in ALLOWED_TOOL_NAMES:
                logger.warning("收到未知工具调用: %s", tool_name)
                continue
            try:
                arguments = json.loads(tool_call.function.arguments)
            except json.JSONDecodeError:
                arguments = {}

            try:
                if tool_name in {t["function"]["name"] for t in FINANCE_TOOLS}:
                    result = execute_finance_tool(tool_name, arguments)
                elif tool_name in {t["function"]["name"] for t in KNOWLEDGE_TOOLS}:
                    if context.category and "category" not in arguments:
                        arguments["category"] = context.category
                    result = execute_knowledge_tool(tool_name, arguments)
                else:
                    raise ValueError(f"未知工具: {tool_name}")
            except Exception as exc:  # pragma: no cover
                logger.error("工具执行失败 %s: %s", tool_name, exc, exc_info=True)
                tool_payload = json.dumps({"error": str(exc)}, ensure_ascii=False)
            else:
                logger.info("工具成功: %s", tool_name)
                tool_call_results.append({"tool": tool_name, "arguments": arguments, "result": result})
                tool_payload = json.dumps(result, ensure_ascii=False)

            assistant_stub = {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "id": tool_call.id,
                        "type": "function",
                        "function": {
                            "name": tool_call.function.name,
                            "arguments": tool_call.function.arguments,
                        },
                    }
                ],
            }
            tool_entry = {
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": tool_payload,
            }
            history_tool_messages.extend([assistant_stub, tool_entry])

            messages.append(assistant_stub)
            messages.append(tool_entry)

        try:
            final_response = client.chat.completions.create(model=model, messages=messages)
        except Exception as exc:  # pragma: no cover
            logger.error("工具阶段 LLM 调用失败: %s", exc, exc_info=True)
            envelope = ApiEnvelope(code=1003, message=f"AI对话失败: {exc}", data=None)
            _log_client_payload(conversation_id, envelope)
            return envelope

        final_message = final_response.choices[0].message
        final_text = sanitize_content(final_message.content or "")
        logger.info(
            "Stage-B 最终响应（工具后）",
            extra={
                "conversation_id": conversation_id,
                "content_preview": _safe_snippet(final_text, 400),
                "tool_calls": tool_call_results,
            },
        )

        new_items = [{"role": m.role, "content": m.content} for m in request.messages]
        new_items.extend(history_tool_messages)
        new_items.append({"role": "assistant", "content": final_text})
        summary, trimmed, need_summary = memory_store.append_and_trim(
            conversation_id, summary, history_messages, new_items
        )
        if need_summary:
            try:
                new_summary = summarizer.summarize(trimmed)
                summary, trimmed, _ = memory_store.append_and_trim(conversation_id, new_summary, trimmed, [])
            except Exception as exc:  # pragma: no cover
                logger.warning("生成会话摘要失败: %s", exc)

        envelope = ApiEnvelope(
            code=0,
            message="ok",
            data=ChatResponse(
                conversation_id=conversation_id,
                reply=ChatMessage(role="assistant", content=final_text),
                tool_calls=[ToolCall(**tc) for tc in tool_call_results],
            ),
        )
        _log_client_payload(conversation_id, envelope)
        return envelope

    # 无工具调用
    final_reply = sanitize_content(assistant_message.content or "")
    logger.info(
        "Stage-B 最终响应（无工具）",
        extra={
            "conversation_id": conversation_id,
            "content_preview": _safe_snippet(final_reply, 400),
        },
    )

    new_items = [{"role": m.role, "content": m.content} for m in request.messages]
    new_items.append({"role": "assistant", "content": final_reply})
    summary, trimmed, need_summary = memory_store.append_and_trim(
        conversation_id, summary, history_messages, new_items
    )
    if need_summary:
        try:
            new_summary = summarizer.summarize(trimmed)
            summary, trimmed, _ = memory_store.append_and_trim(conversation_id, new_summary, trimmed, [])
        except Exception as exc:  # pragma: no cover
            logger.warning("生成会话摘要失败: %s", exc)

    logger.info("对话结束，记忆条数=%d", len(trimmed))
    envelope = ApiEnvelope(
        code=0,
        message="ok",
        data=ChatResponse(
            conversation_id=conversation_id,
            reply=ChatMessage(role="assistant", content=final_reply),
        ),
    )
    _log_client_payload(conversation_id, envelope)
    return envelope


def sanitize_content(content: str) -> str:
    safe = content or ""
    for keyword in SENSITIVE_KEYWORDS:
        if keyword in safe:
            safe = safe.replace(keyword, "***敏感信息***")
    return safe


def _safe_snippet(obj: Any, limit: int = 500) -> str:
    try:
        text = json.dumps(obj, ensure_ascii=False)
    except Exception:
        text = str(obj)
    return text[:limit] + ("..." if len(text) > limit else "")


def _log_client_payload(conversation_id: str, envelope: ApiEnvelope) -> None:
    try:
        data = envelope.model_dump(exclude_none=False)
    except Exception:
        data = str(envelope)
    logger.info(
        "Stage-C 客户响应",
        extra={
            "conversation_id": conversation_id,
            "response_preview": _safe_snippet(data, 1200),
        },
    )
