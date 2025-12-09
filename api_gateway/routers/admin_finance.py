"""Finance admin APIs: stats, sync logs, records, trigger sync."""

from __future__ import annotations

from datetime import date
from typing import Optional

from fastapi import APIRouter, Query
from sqlalchemy import func, select

from celery import Celery
from celery.result import AsyncResult

from common.persistence.database import get_session_factory, session_scope
from common.persistence.models import FinanceRecordORM, FinanceSyncLogORM
from common.utils.env import load_env
from formatter_service.worker import celery_app, FORMATTER_QUEUE

router = APIRouter()

# ensure .env loaded when uvicorn direct run
load_env()


def _get_session():
    return get_session_factory()


@router.get("/finance/stats")
def finance_stats():
    """Return finance records stats: total, latest sync, coverage months."""

    factory = _get_session()
    with session_scope(factory) as session:
        total = session.scalar(select(func.count()).select_from(FinanceRecordORM)) or 0
        latest_sync = session.scalar(select(func.max(FinanceSyncLogORM.finished_at)))
        min_date = session.scalar(select(func.min(FinanceRecordORM.keep_date)))
        max_date = session.scalar(select(func.max(FinanceRecordORM.keep_date)))
    return {
        "code": 0,
        "message": "ok",
        "data": {
            "total_records": total,
            "latest_sync": latest_sync,
            "date_coverage": {"min": min_date, "max": max_date},
        },
    }


@router.get("/finance/sync-logs")
def finance_sync_logs(limit: int = Query(50, ge=1, le=500)):
    """List recent finance sync logs."""

    factory = _get_session()
    with session_scope(factory) as session:
        rows = (
            session.query(FinanceSyncLogORM)
            .order_by(FinanceSyncLogORM.started_at.desc())
            .limit(limit)
            .all()
        )
    data = []
    for r in rows:
        data.append(
            {
                "id": r.id,
                "source": r.source,
                "mode": r.mode,
                "status": r.status,
                "started_at": r.started_at,
                "finished_at": r.finished_at,
                "fetched_count": r.fetched_count,
                "inserted_count": r.inserted_count,
                "updated_count": r.updated_count,
                "error_message": r.error_message,
            }
        )
    return {"code": 0, "message": "ok", "data": data}


@router.get("/finance/records")
def finance_records(
    company_no: Optional[str] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    limit: int = Query(50, ge=1, le=500),
):
    """List finance records (paged)."""

    factory = _get_session()
    with session_scope(factory) as session:
        q = session.query(FinanceRecordORM)
        if company_no:
            q = q.filter(FinanceRecordORM.company_no == company_no)
        if start_date:
            q = q.filter(FinanceRecordORM.keep_date >= start_date)
        if end_date:
            q = q.filter(FinanceRecordORM.keep_date <= end_date)
        rows = q.order_by(FinanceRecordORM.keep_date.desc()).limit(limit).all()
    data = []
    for r in rows:
        data.append(
            {
                "id": r.id,
                "keep_date": r.keep_date,
                "company_no": r.company_no,
                "company_name": r.company_name,
                "high_company_no": r.high_company_no,
                "level": r.level,
                "type_no": r.type_no,
                "type_name": r.type_name,
                "current_amount": r.current_amount,
                "last_year_amount": r.last_year_amount,
                "last_year_total_amount": r.last_year_total_amount,
                "this_year_total_amount": r.this_year_total_amount,
                "add_amount": r.add_amount,
                "add_rate": r.add_rate,
                "year_add_amount": r.year_add_amount,
                "year_add_rate": r.year_add_rate,
                "raw_payload": r.raw_payload,
            }
        )
    return {"code": 0, "message": "ok", "data": data}


@router.post("/finance/sync")
def finance_sync(month: Optional[str] = None):
    """Trigger finance sync via Celery."""

    task = celery_app.send_task(
        "formatter.finance_sync",
        kwargs={"month": month, "dry_run": False},
        queue=FORMATTER_QUEUE,
    )
    return {"code": 0, "message": "sync triggered", "data": {"task_id": task.id}}


@router.get("/tasks/{task_id}")
def task_status(task_id: str):
    """Get Celery task status/result."""

    res = AsyncResult(task_id, app=celery_app)
    return {
        "code": 0,
        "message": "ok",
        "data": {
            "task_id": task_id,
            "state": res.state,
            "result": res.result if res.ready() else None,
        },
    }
