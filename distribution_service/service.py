"""分发服务：写入缓存/搜索，并触发 Webhook。"""

from __future__ import annotations

from typing import Dict, List

from common.domain import DistributionEvent

from .cache import LocalCacheWriter
from .webhook import WebhookDispatcher


cache_writer = LocalCacheWriter()
webhook_dispatcher = WebhookDispatcher()


def distribute_event(event: DistributionEvent) -> None:
    """处理单个分发事件。"""

    payload = event.article.model_dump(mode="json")
    cache_writer.upsert_article(payload)
    if event.targets:
        webhook_dispatcher.dispatch(event.targets, payload)
