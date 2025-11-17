"""AI 对话路由"""

from __future__ import annotations

import json
import logging
from typing import Any, List, Optional
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from common.ai.providers import AIProviderError, AIProviderFactory
from common.clients.finance_api.tools import FINANCE_TOOLS, execute_tool

logger = logging.getLogger(__name__)
router = APIRouter()
provider_factory = AIProviderFactory()


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
    message: ChatMessage
    tool_calls: Optional[List[ToolCall]] = None
    conversation_id: str


PERSONA_PROMPTS = {
    "general": """你是联环药业的综合智能助手，熟悉集团的业务、政策、产品与流程。请以专业、谨慎的语气回答用户问题，必要时主动确认缺失信息。""",
    "finance": """你是联环药业的财务数据分析助手，能够使用 finance_records 表中的本地财务数据（营业收入、利润、税金等）进行查询、对比和解读。回答时请明确数据来源、分析逻辑和结论，并在需要时调用提供的工具检索最新财务数据。""",
}


@router.post("/chat")
async def chat(request: ChatRequest):
    conversation_id = request.conversation_id or str(uuid4())
    persona = (request.persona or "general").lower()
    system_prompt = PERSONA_PROMPTS.get(persona, PERSONA_PROMPTS["general"])

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
        raise HTTPException(status_code=500, detail=str(exc))

    client = provider.client
    model = provider.model

    try:
        first_response = client.chat.completions.create(
            model=model,
            messages=messages,
            tools=FINANCE_TOOLS,
            tool_choice="auto",
        )
    except Exception as exc:  # pragma: no cover - LLM 调用异常
        logger.error("LLM 调用失败: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=f"AI对话失败: {exc}")

    assistant_message = first_response.choices[0].message

    if assistant_message.tool_calls:
        logger.info("LLM 请求调用工具: %d", len(assistant_message.tool_calls))
        tool_call_results = []

        for tool_call in assistant_message.tool_calls:
            tool_name = tool_call.function.name
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
            raise HTTPException(status_code=500, detail=f"AI对话失败: {exc}")

        final_message = final_response.choices[0].message
        return ChatResponse(
            message=ChatMessage(role="assistant", content=final_message.content or ""),
            tool_calls=[ToolCall(**tc) for tc in tool_call_results],
            conversation_id=conversation_id,
        )

    logger.info("对话完成，无需调用工具")
    return ChatResponse(
        message=ChatMessage(role="assistant", content=assistant_message.content or ""),
        conversation_id=conversation_id,
    )


@router.post("/chat/stream")
async def chat_stream(request: ChatRequest):  # pragma: no cover - 未实现
    raise HTTPException(status_code=501, detail="流式对话功能暂未实现")
