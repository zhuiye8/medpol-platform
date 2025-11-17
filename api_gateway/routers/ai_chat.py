"""AI对话路由

提供AI对话接口，支持工具调用（Function Calling）来查询和分析财务数据。
"""

import json
import logging
from uuid import uuid4
from typing import List, Optional, Any
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from common.clients.finance_api.tools import FINANCE_TOOLS, execute_tool
from common.utils.config import get_settings

logger = logging.getLogger(__name__)

router = APIRouter()


class ChatMessage(BaseModel):
    """对话消息"""
    role: str  # "user" | "assistant" | "system"
    content: str


class ChatRequest(BaseModel):
    """对话请求"""
    conversation_id: Optional[str] = None
    messages: List[ChatMessage]
    stream: bool = False


class ToolCall(BaseModel):
    """工具调用记录"""
    tool: str
    arguments: dict
    result: Any  # 可以是dict、list或其他类型


class ChatResponse(BaseModel):
    """对话响应"""
    message: ChatMessage
    tool_calls: Optional[List[ToolCall]] = None
    conversation_id: str


# 系统提示词
SYSTEM_PROMPT = """你是联环药业的专业 AI 助手，熟悉医药行业知识、药企经营逻辑、政策法规、研发体系和财务分析方法。你的核心职责是协助用户完成医疗健康、医药产业、企业经营分析以及内部业务相关的问题处理，并在需要时提供联环药业内部数据的查询与分析。

【你的核心能力】
1. 医药专业能力：药品研发流程、注册法规（如 FDA/EMA/PMDA）、药企运营、市场趋势、医保政策、行业竞争格局。
2. 财务分析能力：能够解读营业收入、利润、税金、成本等项目，并支持年度/季度/月度趋势分析、对比分析和结构分析。
3. 内部数据处理：在用户需要时，可以查询联环药业内部的财务或经营数据，并基于数据给出清晰的分析。
4. 决策辅助：能够结合行业常识、经营逻辑与用户提供的信息，给出专业、务实的建议。

【日期理解规则】
- 标准格式：YYYY-MM
- 季度：Q1=["01","02","03"]，Q2=["04","05","06"]……
- 相对时间如“去年”“上个月”需自动转化逻辑
- 如时间、指标或公司维度不明确，应主动询问用户

【财务项目识别（用于理解用户提问）】
- 营业收入/营收/收入 → 01
- 利润/利润总额 → 02
- 税金/实现税金 → 03
- 入库税金 → 04
- 所得税/企业所得税 → 05
- 净利润/税后利润 → 06

【回答原则】
1. 优先确保结论清晰，其次解释分析逻辑。
2. 如信息不足，应主动询问关键参数，避免误解。
3. 分析内容要专业、简洁、可执行，不绕圈。
4. 在没有数据的情况下，可以使用行业经验、一般规律给出合理判断。
5. 所有回答保持专业客观，避免夸大或偏颇。

你是一个值得信赖的医药与经营分析助手，目标是帮助联环药业的用户快速获得专业、准确且有洞察力的答案。
"""


@router.post("/chat")
async def chat(request: ChatRequest):
    """AI对话接口

    支持工具调用的AI对话，可以查询和分析财务数据。

    Args:
        request: 对话请求

    Returns:
        对话响应，包含AI回复和工具调用记录

    Raises:
        HTTPException: LLM调用失败或其他错误
    """
    conversation_id = request.conversation_id or str(uuid4())

    logger.info(
        "收到对话请求",
        extra={
            "conversation_id": conversation_id,
            "message_count": len(request.messages),
            "user_query": request.messages[-1].content if request.messages else None
        }
    )

    # 构建消息列表
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    messages.extend([{"role": m.role, "content": m.content} for m in request.messages])

    try:
        # 调用LLM（使用OpenAI SDK v1.0+）
        from openai import OpenAI

        settings = get_settings()

        # 创建OpenAI客户端
        if settings.openai_api_key:
            client = OpenAI(
                api_key=settings.openai_api_key,
                base_url=settings.openai_base_url
            )
            model = settings.ai_chat_model
        elif settings.deepseek_api_key and settings.ai_primary == "deepseek":
            client = OpenAI(
                api_key=settings.deepseek_api_key,
                base_url=settings.deepseek_base_url
            )
            model = settings.deepseek_model
        else:
            raise HTTPException(
                status_code=500,
                detail="未配置AI API密钥。请在.env中配置OPENAI_API_KEY或DEEPSEEK_API_KEY"
            )

        # 第一次LLM调用：识别意图和工具
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            tools=FINANCE_TOOLS,
            tool_choice="auto"
        )

        assistant_message = response.choices[0].message

        # 处理工具调用
        if assistant_message.tool_calls:
            logger.info("LLM请求调用工具: %d个", len(assistant_message.tool_calls))

            tool_calls_results = []

            for tool_call in assistant_message.tool_calls:
                tool_name = tool_call.function.name
                try:
                    arguments = json.loads(tool_call.function.arguments)
                except json.JSONDecodeError as e:
                    logger.error("解析工具参数失败: %s", e)
                    arguments = {}

                logger.info("执行工具: %s, 参数: %s", tool_name, arguments)

                # 执行工具函数
                try:
                    tool_result = execute_tool(tool_name, arguments)
                    tool_calls_results.append({
                        "tool": tool_name,
                        "arguments": arguments,
                        "result": tool_result
                    })

                    # 将工具结果添加到对话历史
                    messages.append({
                        "role": "assistant",
                        "content": None,
                        "tool_calls": [{
                            "id": tool_call.id,
                            "type": "function",
                            "function": {
                                "name": tool_call.function.name,
                                "arguments": tool_call.function.arguments
                            }
                        }]
                    })
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": json.dumps(tool_result, ensure_ascii=False)
                    })

                except Exception as e:
                    logger.error("工具执行失败: %s", e, exc_info=True)
                    # 工具执行失败时，告知LLM
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": json.dumps({"error": str(e)}, ensure_ascii=False)
                    })

            # 第二次LLM调用：基于工具结果生成最终回答
            logger.info("基于工具结果生成最终回答")
            final_response = client.chat.completions.create(
                model=model,
                messages=messages
            )

            final_message = final_response.choices[0].message

            logger.info("对话完成，调用了%d个工具", len(tool_calls_results))

            return ChatResponse(
                message=ChatMessage(
                    role="assistant",
                    content=final_message.content
                ),
                tool_calls=[ToolCall(**tc) for tc in tool_calls_results],
                conversation_id=conversation_id
            )
        else:
            # 无需工具调用，直接返回
            logger.info("对话完成，无需工具调用")

            return ChatResponse(
                message=ChatMessage(
                    role="assistant",
                    content=assistant_message.content
                ),
                conversation_id=conversation_id
            )

    except Exception as e:
        logger.error("AI对话失败: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=f"AI对话失败: {str(e)}")


@router.post("/chat/stream")
async def chat_stream(request: ChatRequest):
    """流式对话接口（待实现）

    支持SSE流式输出，提升用户体验。

    Args:
        request: 对话请求

    Returns:
        流式响应

    Raises:
        HTTPException: 功能未实现
    """
    raise HTTPException(status_code=501, detail="流式对话功能暂未实现")
