"""批量 AI 任务执行工具，供 CLI 与 API 共用。"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import List

from common.persistence.database import get_session_factory, session_scope
from common.persistence.repository import ArticleRepository

from .worker import process_summary, process_translation, process_analysis


@dataclass
class PendingTargets:
    """待处理的文章 ID 列表。"""

    summary_ids: List[str]
    translation_ids: List[str]
    analysis_ids: List[str]

    @property
    def has_pending(self) -> bool:
        return bool(self.summary_ids or self.translation_ids or self.analysis_ids)


@dataclass
class AIQueueResult:
    """AI 任务入队统计。"""

    summary_pending: int = 0
    translation_pending: int = 0
    analysis_pending: int = 0
    summary_enqueued: int = 0
    translation_enqueued: int = 0
    analysis_enqueued: int = 0

    @property
    def total_enqueued(self) -> int:
        return (
            self.summary_enqueued
            + self.translation_enqueued
            + self.analysis_enqueued
        )


def _require_database_url() -> None:
    if not os.getenv("DATABASE_URL"):
        raise RuntimeError("缺少 DATABASE_URL，无法执行 AI 任务")


def collect_pending_targets(limit: int = 5) -> PendingTargets:
    """查询数据库获取待处理的文章列表。"""

    _require_database_url()
    session_factory = get_session_factory()
    with session_scope(session_factory) as session:
        repo = ArticleRepository(session)
        summary_ids = [article.id for article in repo.list_without_summary(limit=limit)]
        translation_ids = [article.id for article in repo.list_without_translation(limit=limit)]
        analysis_ids = [article.id for article in repo.list_without_analysis(limit=limit)]
    return PendingTargets(summary_ids, translation_ids, analysis_ids)


def enqueue_ai_jobs(limit: int = 5) -> AIQueueResult:
    """将待处理文章推送到 Celery 队列，返回入队统计。"""

    targets = collect_pending_targets(limit=limit)
    result = AIQueueResult(
        summary_pending=len(targets.summary_ids),
        translation_pending=len(targets.translation_ids),
        analysis_pending=len(targets.analysis_ids),
    )
    if not targets.has_pending:
        return result

    for article_id in targets.summary_ids:
        process_summary.delay(article_id)
        result.summary_enqueued += 1

    for article_id in targets.translation_ids:
        process_translation.delay(article_id)
        result.translation_enqueued += 1

    for article_id in targets.analysis_ids:
        process_analysis.delay(article_id)
        result.analysis_enqueued += 1

    return result


# 兼容旧接口，便于脚本调用
def run_batch_jobs(limit: int = 5) -> AIQueueResult:  # pragma: no cover
    return enqueue_ai_jobs(limit=limit)
