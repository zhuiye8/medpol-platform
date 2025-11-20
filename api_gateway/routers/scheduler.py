"""调度管理相关 API。"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from common.persistence import models
from common.persistence.repository import CrawlerJobRepository, SourceRepository
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
    CeleryStatus,
    ResetResultData,
)
from scheduler_service.job_runner import (
    calculate_next_run,
    calculate_next_run_time,
    execute_job_once,
)
from crawler_service.scheduler import list_available_crawlers
from scheduler_service.pipeline import run_full_pipeline, run_quick_pipeline
from formatter_service.worker import celery_app as formatter_celery
from scripts.reset_data import reset_all, DEFAULT_DIRS
from common.utils.config import get_settings


router = APIRouter()


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _to_payload(payload_dict: dict | None) -> CrawlerJobPayload:
    if payload_dict is None:
        return CrawlerJobPayload()
    return CrawlerJobPayload(**payload_dict)


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
        log_path=run.log_path,
        error_message=run.error_message,
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
    if not source_repo.get_by_id(job_data.source_id):
        raise HTTPException(status_code=404, detail="来源不存在")

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
        source_id=job_data.source_id,
        job_type=job_data.job_type,
        schedule_cron=job_data.schedule_cron,
        interval_minutes=job_data.interval_minutes,
        payload=payload_dict,
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
    )
    return Envelope(code=0, msg="success", data=data)


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
