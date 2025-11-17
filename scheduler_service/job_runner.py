"""执行调度任务的辅助函数。"""

from __future__ import annotations

from datetime import datetime, timezone, timedelta
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

try:  # pragma: no cover - croniter 可选依赖
    from croniter import croniter
except ImportError:  # pragma: no cover
    croniter = None  # type: ignore

from common.persistence.repository import SourceRepository
from common.persistence import models
from crawler_service.config_loader import CrawlerRuntimeConfig
from crawler_service.scheduler import run_crawler_config


def _now() -> datetime:
    return datetime.now(timezone.utc)


def calculate_next_run_time(
    job_type: str,
    schedule_cron: Optional[str],
    interval_minutes: Optional[int],
    *,
    enabled: bool = True,
    from_time: Optional[datetime] = None,
) -> Optional[datetime]:
    """根据配置计算下一次运行时间。"""

    if not enabled or job_type != "scheduled":
        return None
    base = from_time or _now()
    if schedule_cron and croniter:
        try:
            itr = croniter(schedule_cron, base)
            return itr.get_next(datetime)
        except (ValueError, KeyError):
            return None
    if schedule_cron and croniter is None:
        return None
    if interval_minutes:
        return base + timedelta(minutes=interval_minutes)
    return None


def calculate_next_run(job: models.CrawlerJobORM, from_time: Optional[datetime] = None) -> Optional[datetime]:
    return calculate_next_run_time(
        job.job_type,
        job.schedule_cron,
        job.interval_minutes,
        enabled=job.enabled,
        from_time=from_time,
    )


def build_runtime_config(
    job: models.CrawlerJobORM,
    payload: Dict[str, Any],
    session: Session,
) -> CrawlerRuntimeConfig:
    """将 job + payload 转成爬虫运行配置。"""

    source_repo = SourceRepository(session)
    source = source_repo.get_by_id(job.source_id)
    if not source:
        raise ValueError(f"未找到 source: {job.source_id}")

    meta = payload.get("meta") or {}
    return CrawlerRuntimeConfig(
        source_id=source.id,
        source_name=source.name,
        crawler_name=job.crawler_name,
        meta=meta,
    )


def execute_job_once(
    job: models.CrawlerJobORM,
    run: models.CrawlerJobRunORM,
    session: Session,
) -> int:
    """执行任务一次，返回结果数量。"""

    payload = dict(job.payload or {})
    payload.update(run.params_snapshot or {})

    runtime_config = build_runtime_config(job, payload, session)
    articles = run_crawler_config(runtime_config)
    return len(articles)
