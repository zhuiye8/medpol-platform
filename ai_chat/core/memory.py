"""Simple chat memory backed by Redis (fallback in-memory)."""

from __future__ import annotations

import json
from typing import Dict, List, Optional, Tuple

import redis

from common.utils.config import get_settings
from ai_chat.core.schemas import ChatMessage

_settings = get_settings()


class ChatMemory:
    """Redis-backed memory with simple window; fallback to in-memory."""

    def __init__(self) -> None:
        self._store: Dict[str, List[Dict]] = {}
        self._redis: Optional[redis.Redis] = None

        try:
            self._redis = redis.from_url(_settings.redis_url)
            self._redis.ping()
        except Exception:
            self._redis = None

    def load(self, conversation_id: str) -> List[Dict]:
        if self._redis:
            raw = self._redis.get(self._key(conversation_id))
            if raw:
                try:
                    data = json.loads(raw.decode("utf-8"))
                    return data.get("messages", [])
                except Exception:
                    return []
        return list(self._store.get(conversation_id, []))

    def save(self, conversation_id: str, messages: List[Dict]) -> None:
        if self._redis:
            payload = json.dumps({"messages": messages}, ensure_ascii=False)
            self._redis.setex(self._key(conversation_id), _settings.memory_ttl_minutes * 60, payload)
        else:
            self._store[conversation_id] = list(messages)

    def append(
        self,
        conversation_id: str,
        history: List[Dict],
        new_items: List[Dict],
    ) -> Tuple[List[Dict], bool]:
        merged = history + new_items
        # 简单窗口控制，保留最近 memory_window 条
        merged = merged[-_settings.memory_window :]
        self.save(conversation_id, merged)
        return merged, False

    def _key(self, conversation_id: str) -> str:
        return f"conv:{conversation_id}"

memory = ChatMemory()

__all__ = ["memory", "ChatMemory"]
