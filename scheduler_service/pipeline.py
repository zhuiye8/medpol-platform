"""一键运行采集、格式化与 AI 的流水线工具。"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from sqlalchemy.orm import Session

from crawler_service.scheduler import run_active_crawlers
from formatter_service.worker import process_raw_article
from ai_processor.batch import enqueue_ai_jobs, AIQueueResult


PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUTBOX_DIR = PROJECT_ROOT / "sample_data" / "outbox"
NORMALIZED_DIR = PROJECT_ROOT / "sample_data" / "normalized"
NORMALIZED_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class OutboxStats:
    files: int = 0
    processed: int = 0
    skipped: int = 0


@dataclass
class PipelineResult:
    crawled: int
    outbox: OutboxStats
    ai: AIQueueResult


def _process_outbox_queue() -> OutboxStats:
    """将 sample_data/outbox 中的文件落库，并在 normalized 目录生成调试副本。"""

    stats = OutboxStats()
    if not OUTBOX_DIR.exists():
        return stats

    files = sorted(OUTBOX_DIR.glob("raw_*.json"))
    stats.files = len(files)
    for raw_file in files:
        try:
            payload = json.loads(raw_file.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            stats.skipped += 1
            raw_file.unlink(missing_ok=True)
            continue

        result = process_raw_article(payload)
        if result.get("skipped"):
            stats.skipped += 1
        else:
            stats.processed += 1
            article = result["article"]
            target = NORMALIZED_DIR / f"article_{result['article_id']}.json"
            target.write_text(json.dumps(article, ensure_ascii=False, indent=2), encoding="utf-8")
        raw_file.unlink(missing_ok=True)
    return stats


def run_full_pipeline(session: Optional[Session] = None, ai_limit: int | None = None) -> PipelineResult:
    """依次执行爬虫、outbox 落库、AI 入队（默认无限制），并返回统计。"""

    crawled = run_active_crawlers(session=session)
    outbox_stats = _process_outbox_queue()
    ai_stats = enqueue_ai_jobs(limit=ai_limit)
    return PipelineResult(crawled=crawled, outbox=outbox_stats, ai=ai_stats)


def run_quick_pipeline(session: Optional[Session] = None, ai_limit: int | None = None) -> PipelineResult:
    """
    快速检测：每个爬虫只取 1 条，完整经过 formatter + AI 队列。
    适合上线前自检，避免大规模入库。
    """

    crawled = run_active_crawlers(session=session, quick_mode=True)
    outbox_stats = _process_outbox_queue()
    ai_stats = enqueue_ai_jobs(limit=ai_limit)
    return PipelineResult(crawled=crawled, outbox=outbox_stats, ai=ai_stats)
