"""调度管理相关 API。"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4
from typing import Optional, List
from pathlib import Path
from collections import deque

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from common.persistence import models
from common.persistence.repository import (
    CrawlerJobRepository,
    SourceRepository,
    PipelineRunRepository,
)
from crawler_service.registry import registry as crawler_registry
from common.domain import ArticleCategory
from ..deps import get_db_session
from ..schemas import (
    CrawlerMeta,
    CrawlerJobCreate,
    CrawlerJobItem,
    CrawlerJobListData,
    CrawlerJobRunItem,
    CrawlerJobRunListData,
    CrawlerJobUpdate,
    Envelope,
    RunJobRequest,
    CrawlerJobPayload,
    PipelineRunData,
    PipelineRunDetailItem,
    PipelineRunItem,
    PipelineRunListData,
    CeleryStatus,
    ResetResultData,
    LogListData,
    LogLine,
)
from scheduler_service.job_runner import (
    calculate_next_run,
    calculate_next_run_time,
    execute_job_once,
)
from crawler_service.scheduler import list_available_crawlers, run_crawler_config
from crawler_service.config_loader import CrawlerRuntimeConfig
from scheduler_service.pipeline import run_full_pipeline, run_quick_pipeline
from formatter_service.worker import celery_app as formatter_celery
from scripts.reset_data import reset_all, DEFAULT_DIRS
from common.utils.config import get_settings
from common.persistence.database import get_session_factory
import threading


router = APIRouter()


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _to_payload(payload_dict: dict | None) -> CrawlerJobPayload:
    if payload_dict is None:
        return CrawlerJobPayload()
    return CrawlerJobPayload(**payload_dict)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
LOG_ROOT = (PROJECT_ROOT / "logs").resolve()


def _resolve_log_path(log_path: str) -> Path:
    """Normalize and guard log path to stay under LOG_ROOT."""

    path = Path(log_path)
    if not path.is_absolute():
        path = (PROJECT_ROOT / path).resolve()
    else:
        path = path.resolve()
    if LOG_ROOT not in path.parents and path != LOG_ROOT:
        raise HTTPException(status_code=400, detail="日志路径不被允许")
    return path


def _read_log_tail(log_path: str, limit: int) -> LogListData:
    """Read the tail of a log file safely to avoid huge payloads."""

    path = _resolve_log_path(log_path)
    if not path.exists():
        raise HTTPException(status_code=404, detail="日志不存在")

    lines: deque[str] = deque(maxlen=limit)
    total = 0
    try:
        with path.open("r", encoding="utf-8", errors="ignore") as fp:
            for line in fp:
                total += 1
                lines.append(line.rstrip("\n"))
    except OSError as exc:  # pragma: no cover - IO error path
        raise HTTPException(status_code=500, detail=f"读取日志失败: {exc}") from exc

    log_items = [
        LogLine(idx=total - len(lines) + index + 1, content=content) for index, content in enumerate(lines)
    ]
    return LogListData(lines=log_items, total=total, truncated=len(lines) < total)


def _to_job_item(job: models.CrawlerJobORM) -> CrawlerJobItem:
    return CrawlerJobItem(
        id=job.id,
        name=job.name,
        crawler_name=job.crawler_name,
        source_id=job.source_id,
        job_type=job.job_type,
        schedule_cron=job.schedule_cron,
        interval_minutes=job.interval_minutes,
        payload=_to_payload(job.payload),
        retry_config=job.retry_config or {},
        enabled=job.enabled,
        next_run_at=job.next_run_at,
        last_run_at=job.last_run_at,
        last_status=job.last_status,
    )


def _to_run_item(run: models.CrawlerJobRunORM) -> CrawlerJobRunItem:
    return CrawlerJobRunItem(
        id=run.id,
        status=run.status,
        started_at=run.started_at,
        finished_at=run.finished_at,
        executed_crawler=run.executed_crawler,
        result_count=run.result_count,
        duration_ms=run.duration_ms,
        retry_attempts=run.retry_attempts,
        error_type=run.error_type,
        pipeline_run_id=run.pipeline_run_id,
        log_path=run.log_path,
        error_message=run.error_message,
    )


def _to_pipeline_run_detail(item: models.CrawlerPipelineRunDetailORM) -> PipelineRunDetailItem:
    return PipelineRunDetailItem(
        id=item.id,
        crawler_name=item.crawler_name,
        source_id=item.source_id,
        status=item.status,
        result_count=item.result_count,
        duration_ms=item.duration_ms,
        attempt_number=item.attempt_number,
        max_attempts=item.max_attempts,
        error_type=item.error_type,
        error_message=item.error_message,
        log_path=item.log_path,
    )


def _to_pipeline_run_item(
    run: models.CrawlerPipelineRunORM, details: list[models.CrawlerPipelineRunDetailORM]
) -> PipelineRunItem:
    return PipelineRunItem(
        id=run.id,
        run_type=run.run_type,
        status=run.status,
        total_crawlers=run.total_crawlers,
        successful_crawlers=run.successful_crawlers,
        failed_crawlers=run.failed_crawlers,
        total_articles=run.total_articles,
        started_at=run.started_at,
        finished_at=run.finished_at,
        error_message=run.error_message,
        details=[_to_pipeline_run_detail(d) for d in details],
    )


@router.get("/crawlers/meta", response_model=Envelope[list[CrawlerMeta]])
def list_crawlers_meta() -> Envelope[list[CrawlerMeta]]:
    crawlers = [CrawlerMeta(**item) for item in list_available_crawlers()]
    return Envelope(code=0, msg="success", data=crawlers)


@router.get("/crawler-jobs", response_model=Envelope[CrawlerJobListData])
def list_crawler_jobs(db: Session = Depends(get_db_session)) -> Envelope[CrawlerJobListData]:
    repo = CrawlerJobRepository(db)
    items = [_to_job_item(job) for job in repo.list()]
    return Envelope(code=0, msg="success", data=CrawlerJobListData(items=items))


def _validate_job_payload(payload: CrawlerJobCreate | CrawlerJobUpdate) -> None:
    if payload.job_type == "scheduled":
        has_interval = bool(payload.interval_minutes)
        has_cron = bool(payload.schedule_cron)
        if not (has_interval or has_cron):
            raise HTTPException(status_code=400, detail="定时任务需设置 interval_minutes 或 schedule_cron")


@router.post("/crawler-jobs", response_model=Envelope[CrawlerJobItem])
def create_crawler_job(
    job_data: CrawlerJobCreate,
    db: Session = Depends(get_db_session),
) -> Envelope[CrawlerJobItem]:
    _validate_job_payload(job_data)
    source_repo = SourceRepository(db)
    source_id = job_data.source_id
    crawler_cls = crawler_registry.available().get(job_data.crawler_name)
    category = getattr(crawler_cls, "category", ArticleCategory.FRONTIER)
    label = getattr(crawler_cls, "label", job_data.crawler_name)
    if not source_id:
        source = source_repo.get_or_create_default(
            crawler_name=job_data.crawler_name,
            category=getattr(category, "value", category),
            label=label,
            base_url=f"https://{job_data.crawler_name}.example.com",
        )
        source_id = source.id
    elif not source_repo.get_by_id(source_id):
        source = source_repo.get_or_create_default(
            crawler_name=job_data.crawler_name,
            category=getattr(category, "value", category),
            label=label,
            base_url=f"https://{job_data.crawler_name}.example.com",
        )
        source_id = source.id

    repo = CrawlerJobRepository(db)
    now = _utc_now()
    payload_dict = job_data.payload.model_dump()
    next_run = calculate_next_run_time(
        job_data.job_type,
        job_data.schedule_cron,
        job_data.interval_minutes,
        enabled=job_data.enabled,
        from_time=now,
    )
    job = models.CrawlerJobORM(
        id=str(uuid4()),
        name=job_data.name,
        crawler_name=job_data.crawler_name,
        source_id=source_id,
        job_type=job_data.job_type,
        schedule_cron=job_data.schedule_cron,
        interval_minutes=job_data.interval_minutes,
        payload=payload_dict,
        retry_config=job_data.retry_config or {},
        enabled=job_data.enabled,
        next_run_at=next_run,
        last_run_at=None,
        last_status=None,
        created_at=now,
        updated_at=now,
    )
    repo.add(job)
    db.commit()
    db.refresh(job)
    return Envelope(code=0, msg="success", data=_to_job_item(job))


@router.patch("/crawler-jobs/{job_id}", response_model=Envelope[CrawlerJobItem])
def update_crawler_job(
    job_id: str,
    job_data: CrawlerJobUpdate,
    db: Session = Depends(get_db_session),
) -> Envelope[CrawlerJobItem]:
    repo = CrawlerJobRepository(db)
    job = repo.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="任务不存在")

    if job_data.job_type:
        job.job_type = job_data.job_type
    if job_data.name is not None:
        job.name = job_data.name
    if job_data.crawler_name is not None:
        job.crawler_name = job_data.crawler_name
    if job_data.source_id is not None:
        job.source_id = job_data.source_id
    if job_data.schedule_cron is not None:
        job.schedule_cron = job_data.schedule_cron
    if job_data.interval_minutes is not None:
        job.interval_minutes = job_data.interval_minutes
    if job_data.payload is not None:
        job.payload = job_data.payload.model_dump()
    if job_data.retry_config is not None:
        job.retry_config = job_data.retry_config
    if job_data.enabled is not None:
        job.enabled = job_data.enabled

    _validate_job_payload(
        CrawlerJobCreate(
            name=job.name,
            crawler_name=job.crawler_name,
            source_id=job.source_id,
            job_type=job.job_type,
            schedule_cron=job.schedule_cron,
            interval_minutes=job.interval_minutes,
            payload=CrawlerJobPayload(**job.payload),
            retry_config=job.retry_config,
            enabled=job.enabled,
        )
    )

    job.updated_at = _utc_now()
    job.next_run_at = calculate_next_run(job)
    db.commit()
    db.refresh(job)
    return Envelope(code=0, msg="success", data=_to_job_item(job))


@router.get("/crawler-jobs/{job_id}/runs", response_model=Envelope[CrawlerJobRunListData])
def list_job_runs(job_id: str, db: Session = Depends(get_db_session)) -> Envelope[CrawlerJobRunListData]:
    repo = CrawlerJobRepository(db)
    job = repo.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="任务不存在")
    runs = [_to_run_item(run) for run in repo.list_runs(job_id)]
    return Envelope(code=0, msg="success", data=CrawlerJobRunListData(items=runs))


@router.get("/crawler-jobs/runs/{run_id}/log", response_model=Envelope[LogListData])
def get_job_run_log(
    run_id: str,
    limit: int = Query(400, ge=10, le=2000, description="最多返回的行数"),
    db: Session = Depends(get_db_session),
) -> Envelope[LogListData]:
    repo = CrawlerJobRepository(db)
    run = repo.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="运行不存在")
    if not run.log_path:
        raise HTTPException(status_code=404, detail="暂无日志")
    data = _read_log_tail(run.log_path, limit)
    return Envelope(code=0, msg="success", data=data)


@router.post("/crawler-jobs/{job_id}/run", response_model=Envelope[CrawlerJobRunItem])
def trigger_job(
    job_id: str,
    request: RunJobRequest,
    db: Session = Depends(get_db_session),
) -> Envelope[CrawlerJobRunItem]:
    repo = CrawlerJobRepository(db)
    job = repo.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="任务不存在")

    run = models.CrawlerJobRunORM(
        id=str(uuid4()),
        job_id=job.id,
        status="running",
        started_at=_utc_now(),
        finished_at=None,
        executed_crawler=job.crawler_name,
        params_snapshot=request.payload_override or {},
        result_count=0,
        log_path=None,
        error_message=None,
    )
    repo.create_run(run)
    db.flush()

    try:
        count = execute_job_once(job, run, db)
        run.status = "success"
        run.result_count = count
        message = "success"
    except Exception as exc:  # pylint: disable=broad-except
        run.status = "failed"
        run.error_message = str(exc)
        message = "failed"
    finally:
        run.finished_at = _utc_now()
        job.last_run_at = run.finished_at
        job.last_status = run.status
        job.next_run_at = calculate_next_run(job, run.finished_at)
        db.commit()

    db.refresh(run)
    return Envelope(code=0, msg=message, data=_to_run_item(run))


@router.delete("/crawler-jobs/{job_id}", response_model=Envelope[dict])
def delete_job(job_id: str, db: Session = Depends(get_db_session)) -> Envelope[dict]:
    repo = CrawlerJobRepository(db)
    job = repo.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="任务不存在")
    repo.delete(job)
    db.commit()
    return Envelope(code=0, msg="success", data={"deleted": True})


@router.post("/pipeline/run", response_model=Envelope[PipelineRunData])
def run_pipeline(db: Session = Depends(get_db_session)) -> Envelope[PipelineRunData]:
    result = run_full_pipeline(session=db)
    data = PipelineRunData(
        crawled=result.crawled,
        outbox_files=result.outbox.files,
        outbox_processed=result.outbox.processed,
        outbox_skipped=result.outbox.skipped,
        ai_summary_pending=result.ai.summary_pending,
        ai_summary_enqueued=result.ai.summary_enqueued,
        ai_translation_pending=result.ai.translation_pending,
        ai_translation_enqueued=result.ai.translation_enqueued,
        ai_analysis_pending=result.ai.analysis_pending,
        ai_analysis_enqueued=result.ai.analysis_enqueued,
        details=[
            PipelineRunDetailItem(
                crawler_name=item.get("crawler_name", ""),
                source_id=item.get("source_id"),
                status=item.get("status", ""),
                result_count=item.get("result_count", 0),
                duration_ms=item.get("duration_ms"),
                attempt_number=item.get("attempt_number"),
                max_attempts=item.get("max_attempts"),
                error_type=item.get("error_type"),
                error_message=item.get("error_message"),
                log_path=item.get("log_path"),
            )
            for item in result.details
        ],
    )
    return Envelope(code=0, msg="success", data=data)


@router.post("/pipeline/quick-run", response_model=Envelope[PipelineRunData])
def run_pipeline_quick(db: Session = Depends(get_db_session)) -> Envelope[PipelineRunData]:
    """
    快速检测：每个爬虫抓 1 条，完整走 formatter + AI。
    """

    result = run_quick_pipeline(session=db)
    data = PipelineRunData(
        crawled=result.crawled,
        outbox_files=result.outbox.files,
        outbox_processed=result.outbox.processed,
        outbox_skipped=result.outbox.skipped,
        ai_summary_pending=result.ai.summary_pending,
        ai_summary_enqueued=result.ai.summary_enqueued,
        ai_translation_pending=result.ai.translation_pending,
        ai_translation_enqueued=result.ai.translation_enqueued,
        ai_analysis_pending=result.ai.analysis_pending,
        ai_analysis_enqueued=result.ai.analysis_enqueued,
        details=[
            PipelineRunDetailItem(
                crawler_name=item.get("crawler_name", ""),
                source_id=item.get("source_id"),
                status=item.get("status", ""),
                result_count=item.get("result_count", 0),
                duration_ms=item.get("duration_ms"),
                attempt_number=item.get("attempt_number"),
                max_attempts=item.get("max_attempts"),
                error_type=item.get("error_type"),
                error_message=item.get("error_message"),
                log_path=item.get("log_path"),
            )
            for item in result.details
        ],
    )
    return Envelope(code=0, msg="success", data=data)


@router.get("/pipeline/runs", response_model=Envelope[PipelineRunListData])
def list_pipeline_runs(
    limit: int = 20,
    offset: int = 0,
    run_type: Optional[str] = None,
    status: Optional[str] = None,
    db: Session = Depends(get_db_session),
) -> Envelope[PipelineRunListData]:
    repo = PipelineRunRepository(db)
    runs = repo.list_runs(limit=limit, offset=offset, run_type=run_type, status=status)
    total = repo.count_runs(run_type=run_type, status=status)
    items: list[PipelineRunItem] = []
    for run in runs:
        details = repo.list_details(run.id)
        items.append(_to_pipeline_run_item(run, details))
    return Envelope(code=0, msg="success", data=PipelineRunListData(items=items, total=total))


@router.get("/pipeline/runs/{run_id}", response_model=Envelope[PipelineRunItem])
def get_pipeline_run(run_id: str, db: Session = Depends(get_db_session)) -> Envelope[PipelineRunItem]:
    repo = PipelineRunRepository(db)
    run = repo.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="运行不存在")
    details = repo.list_details(run_id)
    item = _to_pipeline_run_item(run, details)
    return Envelope(code=0, msg="success", data=item)


@router.get("/pipeline/runs/{detail_id}/log", response_model=Envelope[LogListData])
def get_pipeline_detail_log(
    detail_id: str,
    limit: int = Query(400, ge=10, le=2000, description="最多返回的行数"),
    db: Session = Depends(get_db_session),
) -> Envelope[LogListData]:
    repo = PipelineRunRepository(db)
    detail = repo.get_detail(detail_id)
    if not detail:
        raise HTTPException(status_code=404, detail="运行不存在")
    if not detail.log_path:
        raise HTTPException(status_code=404, detail="暂无日志")
    data = _read_log_tail(detail.log_path, limit)
    return Envelope(code=0, msg="success", data=data)


def _retry_worker(detail_id: str) -> None:
    """后台线程重跑单个爬虫 detail。"""

    session_factory = get_session_factory()
    with session_factory() as session:
        repo = PipelineRunRepository(session)
        detail = repo.get_detail(detail_id)
        if not detail:
            return
        source_id = detail.source_id
        source_repo = SourceRepository(session)
        source = source_repo.get_by_id(source_id) if source_id else None
        snapshot = detail.config_snapshot or {}
        meta = snapshot.get("meta") if "meta" in snapshot else snapshot
        retry_conf = snapshot.get("retry_config") or {}
        runtime_cfg = CrawlerRuntimeConfig(
            source_id=source_id or "",
            source_name=source.name if source else detail.crawler_name,
            crawler_name=detail.crawler_name,
            meta=meta or {},
        )
        max_attempts = int(retry_conf.get("max_attempts", 1) or 1)
        attempt_backoff = float(retry_conf.get("attempt_backoff", 1.5) or 1.5)

        run_id = str(uuid4())
        now = datetime.now(timezone.utc)
        run = models.CrawlerPipelineRunORM(
            id=run_id,
            run_type="manual_retry",
            status="running",
            total_crawlers=1,
            successful_crawlers=0,
            failed_crawlers=0,
            total_articles=0,
            started_at=now,
            finished_at=None,
            error_message=None,
        )
        repo.add_run(run)
        session.flush()

        log_root = Path("logs") / "crawler" / run_id
        log_root.mkdir(parents=True, exist_ok=True)

        status = "failed"
        err_type = None
        err_msg = None
        result_count = 0
        duration_ms = 0
        attempt_number = 0
        detail_log_path = None

        import time

        for attempt in range(1, max_attempts + 1):
            attempt_number = attempt
            start_ts = time.time()
            started_at = datetime.now(timezone.utc)
            try:
                articles = run_crawler_config(runtime_cfg)
                duration_ms = int((time.time() - start_ts) * 1000)
                result_count = len(articles)
                status = "success"
                err_type = None
                err_msg = None
                finished_at = datetime.now(timezone.utc)
                break
            except Exception as exc:  # pylint: disable=broad-except
                duration_ms = int((time.time() - start_ts) * 1000)
                err_text = str(exc).lower()
                if "timeout" in err_text:
                    err_type = "timeout"
                elif "403" in err_text or "412" in err_text or "anti" in err_text:
                    err_type = "anti_spider"
                elif "parse" in err_text or "selector" in err_text or "keyerror" in err_text:
                    err_type = "parse_error"
                else:
                    err_type = "network"
                err_msg = str(exc)
                status = "failed"
                finished_at = datetime.now(timezone.utc)
                if attempt < max_attempts:
                    time.sleep(attempt_backoff ** attempt)
                else:
                    break

        attempt_suffix = f"_a{attempt_number}"
        detail_log_path = log_root / f"{detail.crawler_name}{attempt_suffix}.log"
        try:
            with open(detail_log_path, "w", encoding="utf-8") as fh:
                fh.write(
                    f"crawler={detail.crawler_name}, status={status}, result={result_count}, "
                    f"error_type={err_type}, error_message={err_msg}\n"
                )
        except Exception:
            detail_log_path = None

        new_detail = models.CrawlerPipelineRunDetailORM(
            id=str(uuid4()),
            run_id=run_id,
            crawler_name=detail.crawler_name,
            source_id=detail.source_id,
            status=status,
            started_at=started_at,
            finished_at=finished_at,
            duration_ms=duration_ms,
            attempt_number=attempt_number,
            max_attempts=max_attempts,
            result_count=result_count,
            error_type=err_type,
            error_message=err_msg,
            log_path=str(detail_log_path) if detail_log_path else None,
            config_snapshot=detail.config_snapshot or {},
        )
        repo.add_detail(new_detail)

        run.finished_at = datetime.now(timezone.utc)
        run.total_articles = result_count
        run.total_crawlers = 1
        run.successful_crawlers = 1 if status == "success" else 0
        run.failed_crawlers = 0 if status == "success" else 1
        run.status = "success" if status == "success" else "failed"
        run.error_message = err_msg
        session.commit()


@router.post("/pipeline/runs/{detail_id}/retry", response_model=Envelope[dict])
def retry_pipeline_detail(detail_id: str) -> Envelope[dict]:
    """异步重跑单个 pipeline detail。"""

    t = threading.Thread(target=_retry_worker, args=(detail_id,), daemon=True)
    t.start()
    return Envelope(code=0, msg="accepted", data={"detail_id": detail_id})


def _celery_health() -> tuple[bool, str]:
    app = formatter_celery
    if app is None:
        return False, "Celery 未初始化"
    try:
        inspector = app.control.inspect(timeout=2)  # type: ignore[attr-defined]
        response = inspector.ping() if inspector else None
    except Exception as exc:  # pylint: disable=broad-except
        return False, str(exc)
    if not response:
        return False, "未检测到 worker"
    workers = ", ".join(response.keys())
    return True, f"在线 worker: {workers}"


@router.get("/celery/health", response_model=Envelope[CeleryStatus])
def celery_status() -> Envelope[CeleryStatus]:
    running, detail = _celery_health()
    return Envelope(code=0, msg="success", data=CeleryStatus(running=running, detail=detail))


@router.post("/pipeline/reset", response_model=Envelope[ResetResultData])
def reset_pipeline() -> Envelope[ResetResultData]:
    settings = get_settings()
    result = reset_all(settings.database_url, settings.redis_url, DEFAULT_DIRS)
    data = ResetResultData(
        truncated_tables=result.truncated_tables,
        cleared_dirs=result.cleared_dirs,
        dedupe_reset=result.dedupe_reset,
        redis_cleared=result.redis_cleared,
    )
    return Envelope(code=0, msg="success", data=data)
