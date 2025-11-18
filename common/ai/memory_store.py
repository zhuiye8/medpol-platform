"""会话记忆存储：Redis 热缓存 + Postgres 持久化（摘要 + 窗口）。"""

from __future__ import annotations

import json
import time
from typing import Any, Dict, List, Optional, Tuple

import redis
from sqlalchemy import select

from common.utils.config import get_settings
from common.persistence.database import get_session_factory, session_scope
from common.persistence import models as orm_models


class MemoryStore:
    """会话记忆存储，支持摘要 + 窗口截断 + TTL 刷新，Redis 优先，落库持久化。"""

    def __init__(self) -> None:
        settings = get_settings()
        self.redis = redis.from_url(settings.redis_url)
        self.ttl_seconds = max(1, settings.memory_ttl_minutes * 60)
        self.window = max(1, settings.memory_window)
        self.summary_threshold = max(settings.memory_summary_threshold, self.window + 1)
        self.session_factory = get_session_factory()

    def load(self, conversation_id: str) -> Tuple[Optional[str], List[Dict[str, Any]]]:
        # 1) Redis 尝试
        raw = self.redis.get(self._key(conversation_id))
        if raw:
            try:
                data = json.loads(raw.decode("utf-8"))
                summary = data.get("summary") or None
                messages = data.get("messages") or []
                self.redis.expire(self._key(conversation_id), self.ttl_seconds)
                return summary, messages
            except Exception:
                pass

        # 2) Postgres 回源
        with session_scope(self.session_factory) as session:
            stmt = select(orm_models.ConversationSessionORM).where(
                orm_models.ConversationSessionORM.id == conversation_id
            )
            row = session.scalars(stmt).first()
            if not row:
                return None, []
            summary = row.summary or None
            messages = row.messages_json or []
            # 回写 Redis 缓存
            self._write_redis(conversation_id, summary, messages)
            return summary, messages

    def save(
        self,
        conversation_id: str,
        messages: List[Dict[str, Any]],
        summary: Optional[str] = None,
        persona: Optional[str] = None,
    ) -> None:
        self._write_redis(conversation_id, summary, messages)
        self._write_db(conversation_id, summary, messages, persona)

    def append_and_trim(
        self,
        conversation_id: str,
        summary: Optional[str],
        messages: List[Dict[str, Any]],
        new_items: List[Dict[str, Any]],
        persona: Optional[str] = None,
    ) -> Tuple[Optional[str], List[Dict[str, Any]], bool]:
        """
        追加新消息，必要时触发摘要与截断。
        返回 (summary, trimmed_messages, need_new_summary)
        """
        merged = messages + new_items
        need_summary = len(merged) > self.summary_threshold
        trimmed = merged[-self.window :]
        self.save(conversation_id, trimmed, summary, persona)
        return summary, trimmed, need_summary

    def _write_redis(self, conversation_id: str, summary: Optional[str], messages: List[Dict[str, Any]]):
        payload = {
            "summary": summary or "",
            "messages": messages,
            "updated_at": int(time.time()),
        }
        self.redis.setex(self._key(conversation_id), self.ttl_seconds, json.dumps(payload, ensure_ascii=False))

    def _write_db(
        self,
        conversation_id: str,
        summary: Optional[str],
        messages: List[Dict[str, Any]],
        persona: Optional[str],
    ) -> None:
        with session_scope(self.session_factory) as session:
            stmt = select(orm_models.ConversationSessionORM).where(
                orm_models.ConversationSessionORM.id == conversation_id
            ).with_for_update(of=orm_models.ConversationSessionORM, nowait=False)
            obj = session.scalars(stmt).first()
            if obj:
                obj.summary = summary or ""
                obj.messages_json = messages
                if persona:
                    obj.persona = persona
            else:
                obj = orm_models.ConversationSessionORM(
                    id=conversation_id,
                    summary=summary or "",
                    messages_json=messages,
                    persona=persona or "general",
                )
                session.add(obj)

    def _key(self, conversation_id: str) -> str:
        return f"conv:{conversation_id}"


__all__ = ["MemoryStore"]
