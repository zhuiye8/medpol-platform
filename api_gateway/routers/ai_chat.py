"""AI 对话路由"""

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
from common.clients.finance_api.tools import FINANCE_TOOLS, execute_tool

logger = logging.getLogger(__name__)
router = APIRouter()
provider_factory = AIProviderFactory()
ability_router = AbilityRouter(provider_factory)
memory_store = MemoryStore()
summarizer = ConversationSummarizer()
ALLOWED_TOOL_NAMES = {tool["function"]["name"] for tool in FINANCE_TOOLS}
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

    # 读取会话记忆
    summary, history = memory_store.load(conversation_id)
    history_messages = history or []

    # 构造能力判定输入（可附带摘要，减少丢失上下文）
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
    # 合并历史窗口 + 本轮用户消息
    combined = history_messages + [{"role": m.role, "content": m.content} for m in request.messages]
    messages.extend(combined)
    logger.info(
        "Stage-B 入参",
        extra={
            "conversation_id": conversation_id,
            "summary_present": bool(summary),
            "history_len": len(history_messages),
            "messages_preview": _safe_snippet(messages, 800),
            "tools_enabled": bool(context.use_finance),
        },
    )

    try:
        provider = provider_factory.get_client()
    except AIProviderError as exc:
        logger.error("AI Provider 初始化失败: %s", exc)
        return ApiEnvelope(code=1001, message=f"AI Provider 初始化失败: {exc}", data=None)

    client = provider.client
    model = provider.model
    tools_payload = FINANCE_TOOLS if context.use_finance else None
    chat_kwargs = {
        "model": model,
        "messages": messages,
    }
    if tools_payload:
        chat_kwargs["tools"] = tools_payload
        chat_kwargs["tool_choice"] = "auto"

    try:
        first_response = client.chat.completions.create(**chat_kwargs)
    except Exception as exc:  # pragma: no cover - LLM 调用异常
        logger.error("LLM 调用失败: %s", exc, exc_info=True)
        return ApiEnvelope(code=1002, message=f"AI对话失败: {exc}", data=None)

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
        logger.info("LLM 请求调用工具: %d", len(assistant_message.tool_calls))
        tool_call_results = []

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
                result = execute_tool(tool_name, arguments)
            except Exception as exc:  # pragma: no cover - 工具执行异常
                logger.error("工具执行失败 %s: %s", tool_name, exc, exc_info=True)
                tool_payload = json.dumps({"error": str(exc)}, ensure_ascii=False)
            else:
                logger.info("工具成功: %s", tool_name)
                tool_call_results.append({"tool": tool_name, "arguments": arguments, "result": result})
                tool_payload = json.dumps(result, ensure_ascii=False)

            messages.append(
                {
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
            )
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": tool_payload,
                }
            )

        try:
            final_response = client.chat.completions.create(
                model=model,
                messages=messages,
            )
        except Exception as exc:  # pragma: no cover - LLM 调用异常
            logger.error("工具结果回传后 LLM 调用失败: %s", exc, exc_info=True)
            return ApiEnvelope(code=1003, message=f"AI对话失败: {exc}", data=None)

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

        # 写回记忆（包含工具调用结果摘要）
        new_items = [{"role": m.role, "content": m.content} for m in request.messages]
        new_items.append({"role": "assistant", "content": final_text})
        # 把工具调用结果作为一条 tool 消息简要存储，避免长 payload
        for tc in tool_call_results:
            new_items.append({"role": "tool", "content": json.dumps(tc, ensure_ascii=False)[:800]})
        summary, trimmed, need_summary = memory_store.append_and_trim(
            conversation_id, summary, history_messages, new_items
        )
        if need_summary:
            try:
                new_summary = summarizer.summarize(trimmed)
                summary, trimmed, _ = memory_store.append_and_trim(conversation_id, new_summary, trimmed, [])
            except Exception as exc:  # pragma: no cover
                logger.warning("生成会话摘要失败: %s", exc)

        return ApiEnvelope(
            code=0,
            message="ok",
            data=ChatResponse(
                conversation_id=conversation_id,
                reply=ChatMessage(role="assistant", content=final_text),
                tool_calls=[ToolCall(**tc) for tc in tool_call_results],
            ),
        )

    final_reply = sanitize_content(assistant_message.content or "")
    logger.info(
        "Stage-B 最终响应（无工具）",
        extra={
            "conversation_id": conversation_id,
            "content_preview": _safe_snippet(final_reply, 400),
        },
    )

    # 写回记忆：追加 user + assistant（如有工具则包含工具消息）
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

    logger.info("对话完成，窗口条数=%d", len(trimmed))
    return ApiEnvelope(
        code=0,
        message="ok",
        data=ChatResponse(
            conversation_id=conversation_id,
            reply=ChatMessage(role="assistant", content=final_reply),
        ),
    )


@router.post("/chat/stream")
async def chat_stream(request: ChatRequest):  # pragma: no cover - 未实现
    return ApiEnvelope(code=1501, message="流式对话功能暂未实现", data=None)


def sanitize_content(content: str) -> str:
    safe = content or ""
    for keyword in SENSITIVE_KEYWORDS:
        if keyword in safe:
            safe = safe.replace(keyword, "本地财务数据")
    return safe
def _safe_snippet(obj: Any, limit: int = 500) -> str:
    try:
        text = json.dumps(obj, ensure_ascii=False)
    except Exception:
        text = str(obj)
    return text[:limit] + ("..." if len(text) > limit else "")
