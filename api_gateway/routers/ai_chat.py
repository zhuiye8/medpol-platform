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
from common.clients.finance_api.tools import FINANCE_TOOLS, execute_tool

logger = logging.getLogger(__name__)
router = APIRouter()
provider_factory = AIProviderFactory()
ability_router = AbilityRouter(provider_factory)
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
    context = ability_router.resolve(persona, last_user_message)
    system_prompt = context.prompt

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
    messages.extend([{"role": m.role, "content": m.content} for m in request.messages])

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
        return ApiEnvelope(
            code=0,
            message="ok",
            data=ChatResponse(
                conversation_id=conversation_id,
                reply=ChatMessage(role="assistant", content=final_text),
                tool_calls=[ToolCall(**tc) for tc in tool_call_results],
            ),
        )

    logger.info("对话完成，无需调用工具")
    return ApiEnvelope(
        code=0,
        message="ok",
        data=ChatResponse(
            conversation_id=conversation_id,
            reply=ChatMessage(role="assistant", content=sanitize_content(assistant_message.content or "")),
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
