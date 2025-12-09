"""Finance admin APIs: stats, sync logs, records, trigger sync."""

from __future__ import annotations

from datetime import date
from typing import List, Optional

from fastapi import APIRouter, Query
from sqlalchemy import func, select, distinct

from celery import Celery
from celery.result import AsyncResult

from common.persistence.database import get_session_factory, session_scope
from common.persistence.models import FinanceRecordORM, FinanceSyncLogORM
from common.utils.env import load_env
from formatter_service.worker import celery_app, FORMATTER_QUEUE

router = APIRouter()

# ensure .env loaded when uvicorn direct run
load_env()

# 指标类型名称映射
TYPE_NO_NAMES = {
    "01": "营业收入",
    "02": "利润总额",
    "03": "实现税金",
    "04": "入库税金",
    "05": "所得税",
    "06": "净利润",
    "07": "实现税金(扬州)",
    "08": "入库税金(扬州)",
}


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


@router.get("/finance/meta")
def finance_meta():
    """Return available months and companies for filtering."""

    factory = _get_session()
    with session_scope(factory) as session:
        # 获取所有可用月份（去重并排序）
        months_rows = session.execute(
            select(distinct(FinanceRecordORM.keep_date))
            .order_by(FinanceRecordORM.keep_date.desc())
        ).scalars().all()

        # 获取所有公司（去重）
        companies_rows = session.execute(
            select(
                distinct(FinanceRecordORM.company_no),
                FinanceRecordORM.company_name,
                FinanceRecordORM.level,
            )
            .order_by(FinanceRecordORM.level, FinanceRecordORM.company_no)
        ).all()

    # 格式化月份为 YYYY-MM 字符串
    months = []
    for d in months_rows:
        if d:
            months.append(d.strftime("%Y-%m"))

    # 格式化公司列表
    companies = []
    for row in companies_rows:
        company_no, company_name, level = row
        companies.append({
            "company_no": company_no,
            "company_name": company_name or company_no,
            "level": level,
        })

    # 指标类型列表
    type_list = [{"type_no": k, "type_name": v} for k, v in TYPE_NO_NAMES.items()]

    return {
        "code": 0,
        "message": "ok",
        "data": {
            "months": months,
            "companies": companies,
            "types": type_list,
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
    month: Optional[str] = None,
    type_no: Optional[str] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    limit: int = Query(500, ge=1, le=1000),
):
    """List finance records with filters.

    Args:
        company_no: Filter by company code
        month: Filter by month (YYYY-MM format, e.g., '2025-10')
        type_no: Filter by type code (01-08)
        start_date: Filter by start date
        end_date: Filter by end date
        limit: Max records to return
    """

    factory = _get_session()
    with session_scope(factory) as session:
        q = session.query(FinanceRecordORM)
        if company_no:
            q = q.filter(FinanceRecordORM.company_no == company_no)
        if month:
            # 解析 YYYY-MM 格式，筛选该月的数据
            try:
                year, mon = month.split("-")
                month_start = date(int(year), int(mon), 1)
                q = q.filter(FinanceRecordORM.keep_date == month_start)
            except (ValueError, AttributeError):
                pass  # 忽略无效月份格式
        if type_no:
            q = q.filter(FinanceRecordORM.type_no == type_no)
        if start_date:
            q = q.filter(FinanceRecordORM.keep_date >= start_date)
        if end_date:
            q = q.filter(FinanceRecordORM.keep_date <= end_date)
        rows = q.order_by(
            FinanceRecordORM.keep_date.desc(),
            FinanceRecordORM.level,
            FinanceRecordORM.company_no,
            FinanceRecordORM.type_no,
        ).limit(limit).all()
    data = []
    for r in rows:
        # 使用映射表获取类型名称，如果数据库没有存储
        type_name = r.type_name or TYPE_NO_NAMES.get(r.type_no, f"类型{r.type_no}")
        data.append(
            {
                "id": r.id,
                "keep_date": r.keep_date,
                "company_no": r.company_no,
                "company_name": r.company_name,
                "high_company_no": r.high_company_no,
                "level": r.level,
                "type_no": r.type_no,
                "type_name": type_name,
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
