"""分发服务 Worker，监听消息队列或离线输入。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import List

from common.domain import Article, DistributionEvent

from .service import distribute_event


def process_article_file(file_path: Path, targets: List[str] | None = None) -> None:
    """离线处理单个文章 JSON 文件。"""

    data = json.loads(file_path.read_text(encoding="utf-8"))
    article = Article(**data)
    event = DistributionEvent(
        article=article,
        ai_results=[],
        targets=targets or [],
        delivery_id=f"delivery_{article.id}",
    )
    distribute_event(event)
