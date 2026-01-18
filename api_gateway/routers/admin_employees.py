# -*- coding: utf-8 -*-
"""Employee admin APIs: upload, preview, import, and data query."""

from __future__ import annotations

import logging
import sys
import tempfile
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd
from fastapi import APIRouter, Depends, File, Query, UploadFile
from pydantic import BaseModel
from celery.result import AsyncResult
from sqlalchemy import func, or_, select

# Add project root to path for importing scripts
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.import_employees import (
    COLUMN_MAPPING,
    detect_excel_format,
    parse_excel_row,
    validate_sheet,
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


# --- Request/Response Models ---


class EmployeeImportRequest(BaseModel):
    """Request for single sheet import."""
    file_id: str
    sheet_name: Optional[str] = None
    company_name: Optional[str] = None  # Optional, auto-detect if not provided


class BatchImportRequest(BaseModel):
    """Request for batch import."""
    file_id: str
    start_sheet_index: int = 1
    end_sheet_index: Optional[int] = None
    skip_validation: bool = False


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


def _find_uploaded_file(file_id: str) -> Optional[Path]:
    """Find uploaded file by ID."""
    for ext in [".xlsx", ".xls"]:
        p = UPLOAD_DIR / f"{file_id}{ext}"
        if p.exists():
            return p
    return None


# --- Endpoints ---


@router.get("/employees/companies")
def get_company_options(user=Depends(require_roles(Roles.ADMIN))):
    """
    Get list of companies from database (extracted from imported employee data).

    No longer uses hardcoded company_no mapping.
    """
    factory = _get_session()
    with session_scope(factory) as session:
        # Query all unique company names from database
        results = (
            session.query(
                EmployeeORM.company_name,
                func.count(EmployeeORM.id).label('count')
            )
            .filter(EmployeeORM.company_name.isnot(None))
            .group_by(EmployeeORM.company_name)
            .order_by(func.count(EmployeeORM.id).desc())
            .all()
        )

        companies = [
            {"name": name, "count": count}
            for name, count in results
        ]

    return {
        "code": 0,
        "message": "ok",
        "data": companies,
    }


@router.get("/employees/stats")
def employees_stats(user=Depends(require_roles(Roles.ADMIN))):
    """Get employee statistics."""
    factory = _get_session()
    with session_scope(factory) as session:
        total = session.scalar(select(func.count()).select_from(EmployeeORM)) or 0

        # Group by company_name instead of company_no
        by_company = dict(
            session.query(EmployeeORM.company_name, func.count(EmployeeORM.id))
            .filter(EmployeeORM.company_name.isnot(None))
            .group_by(EmployeeORM.company_name)
            .all()
        )

    return {
        "code": 0,
        "message": "ok",
        "data": {
            "total": total,
            "by_company": by_company,
        },
    }


@router.get("/employees")
def list_employees(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    company_name: Optional[str] = Query(None),
    keyword: Optional[str] = Query(None),
    user=Depends(require_roles(Roles.ADMIN)),
):
    """
    Get paginated employee list.

    Supports:
    - Filter by company name (fuzzy match)
    - Keyword search (name, department)
    - Pagination
    """
    factory = _get_session()
    with session_scope(factory) as session:
        query = session.query(EmployeeORM)

        # Company filter (fuzzy match)
        if company_name:
            query = query.filter(EmployeeORM.company_name.ilike(f"%{company_name}%"))

        # Keyword search (name or department)
        if keyword:
            query = query.filter(
                or_(
                    EmployeeORM.name.ilike(f"%{keyword}%"),
                    EmployeeORM.department.ilike(f"%{keyword}%")
                )
            )

        # Total count
        total = query.count()

        # Pagination
        offset = (page - 1) * page_size
        employees = (
            query
            .order_by(EmployeeORM.created_at.desc())
            .offset(offset)
            .limit(page_size)
            .all()
        )

        # Convert to dict
        items = []
        for emp in employees:
            items.append({
                "id": emp.id,
                "company_name": emp.company_name,
                "name": emp.name,
                "gender": emp.gender,
                "department": emp.department,
                "position": emp.position,
                "employee_level": emp.employee_level,
                "hire_date": emp.hire_date.isoformat() if emp.hire_date else None,
                "created_at": emp.created_at.isoformat(),
            })

    return {
        "code": 0,
        "message": "ok",
        "data": {
            "total": total,
            "page": page,
            "page_size": page_size,
            "items": items,
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
    file_path = _find_uploaded_file(file_id)
    if not file_path:
        return {"code": 404, "message": "文件不存在或已过期", "data": None}

    try:
        xl = pd.ExcelFile(str(file_path))
        sheets = xl.sheet_names
        return {"code": 0, "message": "ok", "data": sheets}
    except Exception as e:
        logger.exception(f"Failed to list sheets: {e}")
        return {"code": 500, "message": f"读取 Sheet 列表失败: {e}", "data": None}


@router.get("/employees/preview/{file_id}")
def preview_employee_file(
    file_id: str,
    sheet_name: Optional[str] = Query(None, description="Sheet 名称"),
    limit: int = Query(50, ge=1, le=200, description="预览行数"),
    user=Depends(require_roles(Roles.ADMIN)),
):
    """
    Preview employee data from uploaded file.

    - Auto-detects format (full_roster / independent)
    - Auto-extracts company name (from Sheet title or "所属公司" column)
    - No longer requires manual company_no selection
    """
    file_path = _find_uploaded_file(file_id)
    if not file_path:
        return {"code": 404, "message": "文件不存在或已过期", "data": None}

    try:
        # Detect format and extract company name
        format_info = detect_excel_format(str(file_path), sheet_name)

        company_name = None
        if format_info["type"] == "full_roster" and format_info.get("title"):
            company_name = format_info["title"]
        elif format_info["type"] == "independent":
            # Try to extract from first row's "所属公司" column
            df_first = pd.read_excel(
                str(file_path),
                sheet_name=sheet_name or 0,
                skiprows=format_info.get("skip_rows", 0),
                nrows=1
            )
            if "所属公司" in df_first.columns:
                company_name = str(df_first["所属公司"].iloc[0]).strip()

        # Read data
        df = pd.read_excel(
            str(file_path),
            sheet_name=sheet_name or 0,
            skiprows=format_info.get("skip_rows", 0)
        )

        total_rows = len(df)

        # Get mapped fields
        detected_cols = list(df.columns)
        mapped_cols = {
            col: COLUMN_MAPPING[col]
            for col in detected_cols
            if col in COLUMN_MAPPING
        }
        mapped_fields_set = set(mapped_cols.values())
        mapped_fields = [f for f in FIELD_ORDER if f in mapped_fields_set]

        # Build columns info
        columns = [
            {"key": f, "label": FIELD_LABELS.get(f, f)}
            for f in mapped_fields
        ]

        # Parse rows for preview
        preview_rows = []
        valid_count = 0

        for idx, row in df.head(limit).iterrows():
            row_dict = row.to_dict()
            warnings = []

            if company_name:
                try:
                    parsed = parse_excel_row(
                        row_dict,
                        company_name=company_name,
                        sheet_name=sheet_name
                    )

                    if not parsed.get("name"):
                        warnings.append("缺少姓名")

                    # Build result
                    result: Dict[str, Any] = {"row_num": idx + 2, "warnings": warnings}
                    for field in mapped_fields:
                        value = parsed.get(field)
                        if value is not None:
                            if hasattr(value, "isoformat"):
                                value = value.isoformat()
                            elif isinstance(value, bool):
                                value = "是" if value else "否"
                        result[field] = value if value is not None else "-"

                    preview_rows.append(result)
                    if not warnings:
                        valid_count += 1

                except Exception as e:
                    preview_rows.append({
                        "row_num": idx + 2,
                        "warnings": [str(e)],
                    })
            else:
                # Cannot auto-detect, show raw data
                preview_rows.append({
                    "row_num": idx + 2,
                    "warnings": ["无法自动识别公司名称，需要手动指定"],
                    **{k: str(v) for k, v in row_dict.items()}
                })

        return {
            "code": 0,
            "message": "ok",
            "data": {
                "format_type": format_info["type"],
                "company_name": company_name,  # Auto-detected company name
                "total_rows": total_rows,
                "valid_rows": valid_count,
                "invalid_rows": len(preview_rows) - valid_count,
                "columns": columns,
                "preview": preview_rows,
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
    """
    Import single sheet of employee data.

    - If company_name not provided, attempts auto-extraction from sheet
    - If auto-extraction fails and no company_name provided, returns error
    """
    file_path = _find_uploaded_file(req.file_id)
    if not file_path:
        return {"code": 404, "message": "文件不存在或已过期", "data": None}

    # If no company_name provided, try to auto-extract
    company_name = req.company_name
    if not company_name:
        try:
            format_info = detect_excel_format(str(file_path), req.sheet_name)

            if format_info["type"] == "full_roster" and format_info.get("title"):
                company_name = format_info["title"]
            elif format_info["type"] == "independent":
                df_first = pd.read_excel(
                    str(file_path),
                    sheet_name=req.sheet_name or 0,
                    skiprows=format_info.get("skip_rows", 0),
                    nrows=1
                )
                if "所属公司" in df_first.columns:
                    company_name = str(df_first["所属公司"].iloc[0]).strip()
        except Exception as e:
            logger.warning(f"Failed to auto-detect company name: {e}")

    if not company_name:
        return {
            "code": 400,
            "message": "无法自动识别公司名称，请手动指定 company_name 参数",
            "data": None
        }

    # Trigger Celery task
    task = celery_app.send_task(
        "formatter.employee_import",
        kwargs={
            "file_path": str(file_path),
            "company_name": company_name,  # ✅ Use company_name
            "sheet_name": req.sheet_name,
        },
        queue=FORMATTER_QUEUE,
    )

    logger.info(f"Triggered employee import task: {task.id} for company: {company_name}")

    return {
        "code": 0,
        "message": "导入任务已启动",
        "data": {
            "task_id": task.id,
            "company_name": company_name,
        },
    }


@router.post("/employees/batch-import")
def batch_import_employees(
    req: BatchImportRequest,
    user=Depends(require_roles(Roles.ADMIN)),
):
    """
    Batch import multiple sheets (full roster mode).

    - Auto-extracts company name from each sheet's first row
    - Skips improperly formatted sheets
    - Returns task ID for status polling
    """
    file_path = _find_uploaded_file(req.file_id)
    if not file_path:
        return {"code": 404, "message": "文件不存在或已过期", "data": None}

    # Pre-validation
    try:
        xl = pd.ExcelFile(str(file_path))
        sheets = xl.sheet_names[req.start_sheet_index:req.end_sheet_index]

        validation_results = []
        for sheet_name in sheets:
            is_valid, error_msg, details = validate_sheet(str(file_path), sheet_name)
            validation_results.append({
                "sheet_name": sheet_name,
                "is_valid": is_valid,
                "error": error_msg if not is_valid else None,
                "company_name": details.get("title", ""),
                "total_rows": details.get("total_rows", 0),
            })

        valid_count = sum(1 for r in validation_results if r["is_valid"])
        if valid_count == 0:
            return {
                "code": 400,
                "message": "没有有效的Sheet可导入",
                "data": {"validation_results": validation_results}
            }

    except Exception as e:
        logger.exception(f"Pre-validation failed: {e}")
        return {"code": 500, "message": f"预验证失败: {str(e)}", "data": None}

    # Trigger batch import Celery task
    task = celery_app.send_task(
        "formatter.batch_employee_import",
        kwargs={
            "file_path": str(file_path),
            "start_sheet_index": req.start_sheet_index,
            "end_sheet_index": req.end_sheet_index,
            "skip_validation": req.skip_validation,
        },
        queue=FORMATTER_QUEUE,
    )

    logger.info(f"Triggered batch employee import task: {task.id}")

    return {
        "code": 0,
        "message": "批量导入任务已启动",
        "data": {
            "task_id": task.id,
            "total_sheets": len(sheets),
            "valid_sheets": valid_count,
            "validation_results": validation_results,
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
