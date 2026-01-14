# -*- coding: utf-8 -*-
"""Employee admin APIs: upload, preview, import."""

from __future__ import annotations

import logging
import os
import sys
import tempfile
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd
from fastapi import APIRouter, Depends, File, Query, UploadFile
from pydantic import BaseModel
from celery.result import AsyncResult
from sqlalchemy import func, select

# Add project root to path for importing scripts
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.import_employees import (
    COLUMN_MAPPING,
    clean_string,
    list_sheets,
    parse_date,
    parse_excel_row,
    parse_is_contract,
)
from api_gateway.deps import require_roles
from common.auth.service import Roles
from common.persistence.database import get_session_factory, session_scope
from common.persistence.models import EmployeeORM
from common.utils.env import load_env
from formatter_service.worker import FORMATTER_QUEUE, celery_app

load_env()

router = APIRouter()
logger = logging.getLogger(__name__)

# 临时文件存储目录
UPLOAD_DIR = Path(tempfile.gettempdir()) / "medpol_employee_uploads"
UPLOAD_DIR.mkdir(exist_ok=True)

# 最大文件大小 10MB
MAX_FILE_SIZE = 10 * 1024 * 1024

# 公司编号映射（用于下拉选择）
COMPANY_OPTIONS = {
    "ydjyhb": "扬大基因(合)",
    "lbyyhb": "联博(合)",
    "plshb": "普林斯(合)",
    "lhjthb": "股份(合)",
    "lhjt": "集团(合)",
    "gykg": "国药控股",
    "htb": "华天宝",
    "ltyyhb": "联通医药",
    "yhtzy": "颐和堂",
    "sshx": "圣氏化学",
    "khyy": "康和药业",
    "scly": "四川龙一",
    "jkcyhb": "产业(合)",
}


# --- Request/Response Models ---


# 字段显示名映射（数据库字段 -> 中文名）
FIELD_LABELS = {
    "company_name": "公司",
    "name": "姓名",
    "gender": "性别",
    "department": "部门",
    "position": "职务",
    "employee_level": "员工级别",
    "is_contract": "合同制",
    "highest_education": "最高学历",
    "graduate_school": "毕业院校",
    "major": "专业",
    "political_status": "政治面貌",
    "professional_title": "职称",
    "skill_level": "技能等级",
    "hire_date": "入职日期",
    "id_number": "身份证号",
    "phone": "电话",
}

# 字段显示顺序
FIELD_ORDER = [
    "name", "company_name", "department", "position", "gender",
    "employee_level", "is_contract", "hire_date", "highest_education",
    "graduate_school", "major", "political_status", "professional_title",
    "skill_level", "id_number", "phone",
]


class EmployeeImportRequest(BaseModel):
    """Request for triggering import."""

    file_id: str
    company_no: str
    sheet_name: Optional[str] = None


# --- Helper Functions ---


def _get_session():
    return get_session_factory()


def _validate_file(file: UploadFile) -> tuple[bool, str]:
    """Validate uploaded file."""
    if not file.filename:
        return False, "未提供文件名"
    if not file.filename.lower().endswith((".xlsx", ".xls")):
        return False, "仅支持 Excel 文件 (.xlsx, .xls)"
    return True, ""


def _parse_row_for_preview(
    row: Dict[str, Any], row_num: int, company_no: str, mapped_fields: List[str]
) -> Dict[str, Any]:
    """Parse a row for preview display.

    Returns a dict with row_num, warnings, and all mapped field values.
    """
    warnings = []
    parsed = parse_excel_row(row, company_no)

    # Check for required fields
    if not parsed.get("name"):
        warnings.append("缺少姓名")

    # Build result with all mapped fields
    result: Dict[str, Any] = {"row_num": row_num, "warnings": warnings}

    for field in mapped_fields:
        value = parsed.get(field)
        # Format special types for display
        if value is not None:
            if hasattr(value, "isoformat"):  # date/datetime
                value = value.isoformat()
            elif isinstance(value, bool):
                value = "是" if value else "否"
        result[field] = value if value is not None else "-"

    return result


# --- Endpoints ---


@router.get("/employees/companies")
def get_company_options(user=Depends(require_roles(Roles.ADMIN))):
    """Get available company options for import."""
    return {
        "code": 0,
        "message": "ok",
        "data": [{"value": k, "label": v} for k, v in COMPANY_OPTIONS.items()],
    }


@router.get("/employees/stats")
def employees_stats(user=Depends(require_roles(Roles.ADMIN))):
    """Get employee statistics."""
    factory = _get_session()
    with session_scope(factory) as session:
        total = session.scalar(select(func.count()).select_from(EmployeeORM)) or 0
        by_company = dict(
            session.query(EmployeeORM.company_no, func.count(EmployeeORM.id))
            .group_by(EmployeeORM.company_no)
            .all()
        )
    return {
        "code": 0,
        "message": "ok",
        "data": {
            "total": total,
            "by_company": {
                COMPANY_OPTIONS.get(k, k): v for k, v in by_company.items()
            },
        },
    }


@router.post("/employees/upload")
async def upload_employee_file(
    file: UploadFile = File(...),
    user=Depends(require_roles(Roles.ADMIN)),
):
    """Upload Excel file for preview. Returns file_id."""
    # Validate file type
    valid, error_msg = _validate_file(file)
    if not valid:
        return {"code": 400, "message": error_msg, "data": None}

    # Read content
    content = await file.read()

    # Check file size
    if len(content) > MAX_FILE_SIZE:
        return {"code": 400, "message": f"文件过大，最大 {MAX_FILE_SIZE // 1024 // 1024}MB", "data": None}

    # Save to temp location
    file_id = str(uuid.uuid4())
    ext = Path(file.filename).suffix.lower()
    file_path = UPLOAD_DIR / f"{file_id}{ext}"
    file_path.write_bytes(content)

    logger.info(f"Uploaded employee file: {file.filename} -> {file_path}")

    return {
        "code": 0,
        "message": "ok",
        "data": {
            "file_id": file_id,
            "filename": file.filename,
            "size": len(content),
        },
    }


@router.get("/employees/preview/{file_id}/sheets")
def get_file_sheets(
    file_id: str,
    user=Depends(require_roles(Roles.ADMIN)),
):
    """List sheets in uploaded Excel file."""
    # Find file
    file_path = None
    for ext in [".xlsx", ".xls"]:
        p = UPLOAD_DIR / f"{file_id}{ext}"
        if p.exists():
            file_path = p
            break

    if not file_path:
        return {"code": 404, "message": "文件不存在或已过期", "data": None}

    try:
        sheets = list_sheets(str(file_path))
        return {"code": 0, "message": "ok", "data": sheets}
    except Exception as e:
        logger.exception(f"Failed to list sheets: {e}")
        return {"code": 500, "message": f"读取 Sheet 列表失败: {e}", "data": None}


@router.get("/employees/preview/{file_id}")
def preview_employee_file(
    file_id: str,
    company_no: str = Query(..., description="公司编号"),
    sheet_name: Optional[str] = Query(None, description="Sheet 名称"),
    limit: int = Query(50, ge=1, le=200, description="预览行数"),
    user=Depends(require_roles(Roles.ADMIN)),
):
    """Preview parsed employee data from uploaded file."""
    # Find file
    file_path = None
    for ext in [".xlsx", ".xls"]:
        p = UPLOAD_DIR / f"{file_id}{ext}"
        if p.exists():
            file_path = p
            break

    if not file_path:
        return {"code": 404, "message": "文件不存在或已过期", "data": None}

    try:
        # Read Excel
        if sheet_name:
            df = pd.read_excel(str(file_path), sheet_name=sheet_name)
        else:
            df = pd.read_excel(str(file_path), sheet_name=0)

        total_rows = len(df)
        detected_cols = list(df.columns)

        # Get mapped fields (Excel col -> DB field)
        mapped_cols = {
            col: COLUMN_MAPPING[col]
            for col in detected_cols
            if col in COLUMN_MAPPING
        }

        # Get unique mapped DB fields, sorted by FIELD_ORDER
        mapped_fields_set = set(mapped_cols.values())
        mapped_fields = [f for f in FIELD_ORDER if f in mapped_fields_set]

        # Build columns info for frontend (field key + label)
        columns = [
            {"key": f, "label": FIELD_LABELS.get(f, f)}
            for f in mapped_fields
        ]

        # Parse rows for preview
        preview_rows = []
        valid_count = 0
        for idx, row in df.head(limit).iterrows():
            row_dict = row.to_dict()
            parsed = _parse_row_for_preview(row_dict, idx + 2, company_no, mapped_fields)
            preview_rows.append(parsed)
            if not parsed["warnings"]:
                valid_count += 1

        return {
            "code": 0,
            "message": "ok",
            "data": {
                "total_rows": total_rows,
                "valid_rows": valid_count,
                "invalid_rows": len(preview_rows) - valid_count,
                "columns": columns,  # [{key, label}, ...]
                "preview": preview_rows,  # [{row_num, warnings, field1, field2, ...}, ...]
            },
        }
    except Exception as e:
        logger.exception(f"Failed to preview file: {e}")
        return {"code": 500, "message": f"预览失败: {e}", "data": None}


@router.post("/employees/import")
def import_employees(
    req: EmployeeImportRequest,
    user=Depends(require_roles(Roles.ADMIN)),
):
    """Trigger async employee import via Celery."""
    # Find file
    file_path = None
    for ext in [".xlsx", ".xls"]:
        p = UPLOAD_DIR / f"{req.file_id}{ext}"
        if p.exists():
            file_path = p
            break

    if not file_path:
        return {"code": 404, "message": "文件不存在或已过期", "data": None}

    # Validate company_no
    if req.company_no not in COMPANY_OPTIONS:
        return {"code": 400, "message": f"无效的公司编号: {req.company_no}", "data": None}

    # Trigger Celery task
    task = celery_app.send_task(
        "formatter.employee_import",
        kwargs={
            "file_path": str(file_path),
            "company_no": req.company_no,
            "sheet_name": req.sheet_name,
        },
        queue=FORMATTER_QUEUE,
    )

    logger.info(f"Triggered employee import task: {task.id}")

    return {
        "code": 0,
        "message": "导入任务已启动",
        "data": {
            "task_id": task.id,
            "company_no": req.company_no,
            "company_name": COMPANY_OPTIONS.get(req.company_no),
        },
    }


@router.get("/employees/tasks/{task_id}")
def employee_task_status(
    task_id: str,
    user=Depends(require_roles(Roles.ADMIN)),
):
    """Get employee import task status."""
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
