"""一键运行采集、格式化与 AI 的流水线工具。"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, List
from uuid import uuid4
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from crawler_service.scheduler import run_active_crawlers
from formatter_service.worker import process_raw_article
from ai_processor.batch import enqueue_ai_jobs, AIQueueResult
from common.persistence import models
from common.persistence.repository import PipelineRunRepository


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
    details: list
    run_id: Optional[str] = None


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

    crawled, details = run_active_crawlers(session=session)
    outbox_stats = _process_outbox_queue()
    ai_stats = enqueue_ai_jobs(limit=ai_limit)
    run_id = _persist_run(session, "full", crawled, outbox_stats, ai_stats, details)
    return PipelineResult(crawled=crawled, outbox=outbox_stats, ai=ai_stats, details=details, run_id=run_id)


def run_quick_pipeline(session: Optional[Session] = None, ai_limit: int | None = None) -> PipelineResult:
    """
    快速检测：每个爬虫只取 1 条，完整经过 formatter + AI 队列。
    适合上线前自检，避免大规模入库。
    """

    crawled, details = run_active_crawlers(session=session, quick_mode=True)
    outbox_stats = _process_outbox_queue()
    ai_stats = enqueue_ai_jobs(limit=ai_limit)
    run_id = _persist_run(session, "quick", crawled, outbox_stats, ai_stats, details)
    return PipelineResult(crawled=crawled, outbox=outbox_stats, ai=ai_stats, details=details, run_id=run_id)


def _persist_run(
    session: Optional[Session],
    run_type: str,
    crawled: int,
    outbox_stats: OutboxStats,
    ai_stats: AIQueueResult,
    details: List[dict],
) -> Optional[str]:
    """持久化 pipeline run 统计与明细；无 session 时跳过。"""

    if session is None:
        return None
    # 如果没有详情，也不落库，保持轻量
    if details is None:
        details = []
    repo = PipelineRunRepository(session)
    run_id = str(uuid4())
    now = datetime.now(timezone.utc)
    failed_crawlers = sum(1 for d in details if d.get("status") != "success")
    successful_crawlers = sum(1 for d in details if d.get("status") == "success")
    run = models.CrawlerPipelineRunORM(
        id=run_id,
        run_type=run_type,
        status="running",
        total_crawlers=len(details),
        successful_crawlers=successful_crawlers,
        failed_crawlers=failed_crawlers,
        total_articles=crawled,
        started_at=now,
        finished_at=None,
        error_message=None,
    )
    repo.add_run(run)
    session.flush()

    log_root = Path("logs") / "crawler" / run_id
    log_root.mkdir(parents=True, exist_ok=True)

    for d in details:
        # 生成日志路径，如未生成则落一个简单的摘要文件
        log_path = d.get("log_path")
        if not log_path:
            attempt_suffix = f"_a{d.get('attempt_number')}" if d.get("attempt_number") else ""
            log_path = str(log_root / f"{d.get('crawler_name','crawler')}{attempt_suffix}.log")
            try:
                with open(log_path, "w", encoding="utf-8") as fh:
                    fh.write(
                        f"crawler={d.get('crawler_name')}, status={d.get('status')}, "
                        f"result={d.get('result_count')}, error_type={d.get('error_type')}, "
                        f"error_message={d.get('error_message')}\n"
                    )
            except Exception:
                log_path = None
        d["log_path"] = log_path

        detail = models.CrawlerPipelineRunDetailORM(
            id=str(uuid4()),
            run_id=run_id,
            crawler_name=d.get("crawler_name", ""),
            source_id=d.get("source_id"),
            status=d.get("status", "failed"),
            started_at=d.get("started_at"),
            finished_at=d.get("finished_at"),
            duration_ms=d.get("duration_ms"),
            attempt_number=d.get("attempt_number"),
            max_attempts=d.get("max_attempts"),
            result_count=d.get("result_count", 0),
            error_type=d.get("error_type"),
            error_message=d.get("error_message"),
            log_path=log_path,
            config_snapshot={
                "meta": d.get("meta", {}),
                "retry_config": d.get("retry_config"),
            },
        )
        repo.add_detail(detail)
        d["id"] = detail.id
    run.finished_at = datetime.now(timezone.utc)
    run.status = "success" if failed_crawlers == 0 else "failed"
    if failed_crawlers:
        run.error_message = f"{failed_crawlers}/{len(details)} 爬虫失败"
    session.commit()
    return run_id
