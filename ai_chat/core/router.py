"""FastAPI router using Vanna Agent (no manual tool loop)."""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from datetime import date, datetime
from typing import Any, AsyncGenerator, Dict, List, Optional

from fastapi import APIRouter, Query, HTTPException, Depends
from fastapi.responses import StreamingResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from common.utils.config import get_settings
from common.auth.service import Roles
from vanna.core.user import RequestContext

from ai_chat.core.schemas import (
    ApiEnvelope,
    ChatMessage,
    ChatRequest,
    ChatResponse,
    ToolCall,
    SSESessionEvent,
    SSEStatusEvent,
    SSEToolStartEvent,
    SSETextDeltaEvent,
    SSEComponentEvent,
    SSEDoneEvent,
    SSEErrorEvent,
)
from ai_chat.core.memory import memory
from ai_chat.vanna.agent_setup import build_agent
from ai_chat.vanna.registry import LoggingToolRegistry

logger = logging.getLogger(__name__)
router = APIRouter()
_agent_cache = {}
_stream_agent_cache = {}

# Optional auth scheme for chat endpoints
_auth_scheme = HTTPBearer(auto_error=False)


def _json_serial(obj):
    """JSON serializer for datetime objects."""
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    raise TypeError(f"Type {type(obj)} not serializable")


def _safe_json_dumps(obj) -> str:
    """Safe JSON dumps with datetime handling."""
    return json.dumps(obj, ensure_ascii=False, default=_json_serial)


def _get_agent(mode: str, stream: bool = False, user_role: str = Roles.VIEWER):
    """Get or create a cached agent for the given mode and user role.

    Args:
        mode: Agent mode - "rag", "sql", or "hybrid"
        stream: Whether to enable streaming responses
        user_role: User role for permission control
    """
    key = f"{mode or 'rag'}:{user_role}"
    cache = _stream_agent_cache if stream else _agent_cache
    if key not in cache:
        cache[key] = build_agent(
            mode or "rag",
            stream=stream,
            user_role=user_role,
            use_auth=True,
        )
    return cache[key]


def _get_user_from_token(
    credentials: Optional[HTTPAuthorizationCredentials],
) -> dict:
    """Extract user info from JWT token.

    Returns:
        User info dict with id, username, role, etc.
        If no credentials or invalid token, returns anonymous user with viewer role.
    """
    if credentials is None:
        return {
            "user_id": "anonymous",
            "username": "anonymous",
            "user_role": Roles.VIEWER,
        }

    try:
        from common.persistence import session_scope
        from common.auth import AuthService

        with session_scope() as session:
            auth_service = AuthService(session)
            user_info = auth_service.get_current_user(credentials.credentials)
            return {
                "user_id": user_info.id,
                "username": user_info.username,
                "user_role": user_info.primary_role or Roles.VIEWER,
                "display_name": user_info.display_name,
                "company_no": user_info.company_no,
            }
    except Exception as e:
        logger.warning(f"Token verification failed: {e}")
        return {
            "user_id": "anonymous",
            "username": "anonymous",
            "user_role": Roles.VIEWER,
        }


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
    """Collect tool calls from LoggingToolRegistry if present.

    只返回清理后的摘要信息，不暴露原始数据。
    """
    calls: List[ToolCall] = []
    registry = getattr(agent, "tool_registry", None)
    if isinstance(registry, LoggingToolRegistry):
        for rec in registry.last_calls:
            calls.append(
                ToolCall(
                    tool=rec.get("tool_name") or "",
                    arguments=rec.get("args") or {},
                    result=rec.get("summary") or "操作完成",  # 使用摘要而非原始数据
                )
            )
        registry.clear_log()
    return calls


@router.post("/chat", response_model=ApiEnvelope)
async def chat(
    request: ChatRequest,
    token: Optional[str] = Query(default=None, description="Embed auth token"),
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_auth_scheme),
) -> ApiEnvelope:
    """Chat endpoint with optional authentication.

    Authentication (any of the following):
    1. JWT Bearer token in Authorization header (full user roles)
    2. Simple token via ?token=xxx query param (legacy embed auth)
    3. No auth (anonymous viewer role, if EMBED_AUTH_TOKEN not set)
    """
    conv_id = request.conversation_id or str(uuid.uuid4())
    mode = (request.mode or "rag").lower()
    history = memory.load(conv_id)
    user_messages = request.messages or []
    if not user_messages:
        return ApiEnvelope(code=1, message="缺少用户输入", data=None)

    # Authentication priority:
    # 1. JWT Bearer token -> use JWT roles
    # 2. embed_auth_token query param -> role based on token type (admin_portal or public_chat)
    # 3. No auth -> viewer role (PC public_chat)
    if credentials is not None:
        # JWT authentication - extract user roles
        user_info = _get_user_from_token(credentials)
        user_role = user_info.get("user_role", Roles.VIEWER)
    elif _verify_token(token):
        # Embed token auth - role based on token type (EMBED_AUTH_TOKEN or access code)
        user_role = _get_role_by_token(token, mode)
        user_info = {
            "user_id": "embed_user",
            "username": "embed_user",
            "user_role": user_role,
        }
    else:
        raise HTTPException(status_code=401, detail="Invalid or missing auth token")

    agent = _get_agent(mode, user_role=user_role)
    req_context = RequestContext(metadata={
        "mode": mode,
        **user_info,  # Include user info in context
    })

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


# ======================== SSE Streaming Endpoint ========================


def _sse_line(data: str) -> str:
    """Format a single SSE event line."""
    return f"data: {data}\n\n"


# 工具状态友好文案映射
_TOOL_STATUS_MAP = {
    "search_policy_articles": "正在检索政策文档...",
    "query_finance_sql": "正在查询财务数据...",
    "generate_finance_chart": "正在生成图表...",
}


async def _stream_text_chunks(
    text: str,
    chunk_size: int = 8,
    delay_ms: int = 15,
) -> AsyncGenerator[str, None]:
    """将完整文本分块逐个 yield，模拟流式效果。

    Args:
        text: 完整文本
        chunk_size: 每次发送的字符数
        delay_ms: 每个 chunk 之间的延迟（毫秒）
    """
    for i in range(0, len(text), chunk_size):
        chunk = text[i : i + chunk_size]
        yield _sse_line(_safe_json_dumps(SSETextDeltaEvent(content=chunk).model_dump()))
        await asyncio.sleep(delay_ms / 1000.0)


def _verify_token(token: Optional[str]) -> bool:
    """Verify embed auth token.

    Returns True if:
    - No EMBED_AUTH_TOKEN configured (open access)
    - Token matches EMBED_AUTH_TOKEN (admin_portal scenario)
    - Token exists in ACCESS_CODE_ROLES mapping (public_chat scenario)
    """
    settings = get_settings()

    # Case 1: No EMBED_AUTH_TOKEN configured, allow all requests
    if not settings.embed_auth_token:
        return True

    # Case 2: Token matches EMBED_AUTH_TOKEN (admin_portal)
    if token == settings.embed_auth_token:
        return True

    # Case 3: Token exists in ACCESS_CODE_ROLES mapping (public_chat)
    access_code_mapping = settings.get_access_code_role_mapping()
    if token in access_code_mapping:
        return True

    # Case 4: Token doesn't match any valid credentials
    return False


# Mode to role mapping for embed token auth (admin_portal compatibility)
MODE_ROLE_MAPPING = {
    "hybrid": Roles.ADMIN,    # 全部权限：财务+员工全字段+政策
    "sql": Roles.FINANCE,     # 只有财务
    "rag": Roles.VIEWER,      # 政策+员工基础
}


def _get_role_by_token(token: Optional[str], mode: str) -> str:
    """根据 token 和 mode 参数返回对应的角色。

    认证逻辑（完全隔离 admin_portal 和 public_chat）：

    场景 1 - admin_portal（使用 EMBED_AUTH_TOKEN）：
      - token == EMBED_AUTH_TOKEN → 使用 mode-based 角色分配
      - 保持原有行为，mode 参数决定角色

    场景 2 - public_chat（使用访问码映射）：
      - token 在 ACCESS_CODE_ROLES 映射中 → 使用映射的角色
      - token 不在映射中 → 默认 viewer 角色

    Args:
        token: 访问 token（可能是 EMBED_AUTH_TOKEN 或访问码）
        mode: 对话模式（rag/sql/hybrid）

    Returns:
        用户角色（viewer/admin/finance）
    """
    settings = get_settings()

    # 场景 1：admin_portal 使用统一 token（EMBED_AUTH_TOKEN）
    if settings.embed_auth_token and token == settings.embed_auth_token:
        # 使用 mode-based 角色分配（原逻辑，保持不变）
        user_role = MODE_ROLE_MAPPING.get(mode.lower(), Roles.VIEWER)
        logger.info(f"✓ [Embed Auth] Using EMBED_AUTH_TOKEN, mode-based role: mode='{mode}' → role='{user_role}'")
        return user_role

    # 场景 2：public_chat 使用访问码映射
    access_code_mapping = settings.get_access_code_role_mapping()

    if token in access_code_mapping:
        # 访问码在映射中，使用配置的角色
        user_role = access_code_mapping[token]
        logger.info(f"✓ [Embed Auth] Access code '{token}' mapped to role '{user_role}'")
        return user_role
    else:
        # 访问码未配置，默认 viewer 角色
        logger.warning(f"⚠️ [Embed Auth] Access code '{token}' not in mapping, using default role 'viewer'")
        return Roles.VIEWER


@router.post("/chat/stream")
async def chat_stream(
    request: ChatRequest,
    token: Optional[str] = Query(default=None, description="Embed auth token"),
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_auth_scheme),
):
    """SSE streaming chat endpoint with optional authentication.

    Returns a text/event-stream response with the following event types:
    - session: Initial session info with conversation_id
    - status: Progress status messages
    - tool_start: Tool execution started
    - text_delta: Streaming text fragment
    - component: Rich component (dataframe, chart, search_results)
    - done: Stream completion with final tool_calls
    - error: Error message

    Authentication (any of the following):
    1. JWT Bearer token in Authorization header (full user roles)
    2. Simple token via ?token=xxx query param (role based on mode)
    3. No auth (viewer role for PC public_chat)
    """
    conv_id = request.conversation_id or str(uuid.uuid4())
    mode = (request.mode or "rag").lower()
    user_messages = request.messages or []

    # 🔍 诊断日志：API层
    logger.info(f"🔍 [API] Received chat request with mode={mode}")

    # Authentication priority:
    # 1. JWT Bearer token -> use JWT roles
    # 2. embed_auth_token query param -> role based on token type (admin_portal or public_chat)
    # 3. No auth -> viewer role (PC public_chat)
    if credentials is not None:
        # JWT authentication - extract user roles
        user_info = _get_user_from_token(credentials)
        user_role = user_info.get("user_role", Roles.VIEWER)
        logger.info(f"✓ [API] JWT auth: user_role={user_role}")
    elif _verify_token(token):
        # Embed token auth - role based on token type (EMBED_AUTH_TOKEN or access code)
        user_role = _get_role_by_token(token, mode)
        user_info = {
            "user_id": "embed_user",
            "username": "embed_user",
            "user_role": user_role,
        }
        logger.info(f"✓ [API] Embed token auth: token='{token}', mode='{mode}' → user_role='{user_role}'")
    else:
        raise HTTPException(status_code=401, detail="Invalid or missing auth token")

    async def event_generator() -> AsyncGenerator[str, None]:
        # Validate input
        if not user_messages:
            yield _sse_line(_safe_json_dumps(
                SSEErrorEvent(message="缺少用户输入", code=1).model_dump()
            ))
            yield "data: [DONE]\n\n"
            return

        try:
            # Send session event
            yield _sse_line(_safe_json_dumps(
                SSESessionEvent(conversation_id=conv_id).model_dump()
            ))
            await asyncio.sleep(0)

            # Send initial status
            yield _sse_line(_safe_json_dumps(
                SSEStatusEvent(content="正在处理您的请求...").model_dump()
            ))
            await asyncio.sleep(0)

            # Get streaming agent with user role
            logger.info(f"✓ [API] Creating agent: mode={mode}, user_role={user_role}")
            agent = _get_agent(mode, stream=True, user_role=user_role)
            req_context = RequestContext(metadata={
                "mode": mode,
                **user_info,  # Include user info in context
            })

            # Track components and tool state
            components_collected = []
            current_tool: Optional[str] = None

            # 获取 registry 用于检测工具调用
            registry = getattr(agent, "tool_registry", None)

            # Stream components from agent
            async for component in agent.send_message(
                request_context=req_context,
                message=user_messages[-1].content,
                conversation_id=conv_id,
            ):
                components_collected.append(component)

                # 检查 registry 中是否有新的工具启动事件
                if isinstance(registry, LoggingToolRegistry):
                    for tool_name in registry.pop_pending_tool_starts():
                        if tool_name != current_tool:
                            current_tool = tool_name
                            status_text = _TOOL_STATUS_MAP.get(tool_name, "正在处理...")
                            yield _sse_line(_safe_json_dumps(
                                SSEStatusEvent(content=status_text).model_dump()
                            ))
                            yield _sse_line(_safe_json_dumps(
                                SSEToolStartEvent(tool=tool_name).model_dump()
                            ))
                            await asyncio.sleep(0)

            # 发送工具产生的待处理组件（搜索结果卡片、图表等）
            registry = getattr(agent, "tool_registry", None)
            if isinstance(registry, LoggingToolRegistry):
                pending_comps = registry.pop_pending_components()
                logger.info(f"🔍 [SSE Stream] Registry returned {len(pending_comps)} components")

                # 🎯 组件排序：图表优先，表格延后
                def component_priority(comp):
                    """定义组件优先级：chart > search_results > dataframe"""
                    priority_map = {
                        "chart": 1,
                        "search_results": 2,
                        "dataframe": 3,
                    }
                    return priority_map.get(comp["type"], 99)

                # 按优先级排序
                sorted_comps = sorted(pending_comps, key=component_priority)

                for comp in sorted_comps:
                    logger.info(f"🔍 [SSE Stream] Sending component: type={comp['type']}, has_data={bool(comp.get('data'))}")
                    # 如果是图表组件，打印更详细的信息
                    if comp['type'] == 'chart':
                        chart_config = comp.get('data', {}).get('config', {})
                        plotly_data = chart_config.get('data', [])
                        logger.info(f"🔍 [SSE Stream] Chart component: plotly_data_length={len(plotly_data)}")
                        if plotly_data:
                            logger.info(f"🔍 [SSE Stream] First trace keys: {list(plotly_data[0].keys())}")
                    yield _sse_line(_safe_json_dumps(
                        SSEComponentEvent(
                            component_type=comp["type"],
                            data=comp["data"],
                            title=comp.get("title"),
                        ).model_dump()
                    ))

            # 提取 LLM 最终回复并模拟流式发送
            reply_text = _pick_reply(components_collected) or "暂无回复"
            if reply_text and reply_text != "暂无回复":
                async for chunk_line in _stream_text_chunks(reply_text):
                    yield chunk_line

            # Save to memory
            history = memory.load(conv_id)
            reply = ChatMessage(role="assistant", content=reply_text)
            new_items = [m.model_dump() for m in user_messages] + [reply.model_dump()]
            memory.append(conv_id, history, new_items)

            # Collect tool calls
            tool_calls = _collect_tool_calls(agent) or []

            # Send done event
            yield _sse_line(_safe_json_dumps(
                SSEDoneEvent(
                    conversation_id=conv_id,
                    tool_calls=tool_calls if tool_calls else None,
                ).model_dump()
            ))

        except Exception as e:
            logger.exception("Streaming error")
            yield _sse_line(_safe_json_dumps(
                SSEErrorEvent(message=str(e), code=500).model_dump()
            ))

        # Send final marker
        yield "data: [DONE]\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable Nginx buffering
            "Access-Control-Allow-Origin": "*",
        },
    )
