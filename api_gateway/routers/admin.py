"""后台监控路由，提供日志等可视化数据。"""

from __future__ import annotations

import os
from collections import deque
from pathlib import Path

from fastapi import APIRouter, Query

from ..schemas import Envelope, LogLine, LogListData


router = APIRouter()

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _resolve_log_path() -> Path:
    """解析日志路径，允许相对路径写在 .env 内。"""

    configured = os.getenv("LOG_FILE_PATH", "test.log")
    path = Path(configured)
    if path.is_absolute():
        return path
    return (PROJECT_ROOT / path).resolve()


def _load_tail_lines(path: Path, limit: int) -> tuple[list[str], int]:
    """安全读取日志尾部，避免一次性加载过大文件。"""

    if not path.exists():
        return [], 0

    lines: deque[str] = deque(maxlen=limit)
    total = 0
    try:
        with path.open("r", encoding="utf-8", errors="ignore") as fp:
            for line in fp:
                total += 1
                lines.append(line.rstrip("\n"))
    except OSError:
        return [], 0
    return list(lines), total


@router.get("/logs", response_model=Envelope[LogListData])
async def fetch_latest_logs(
    limit: int = Query(200, ge=10, le=2000, description="最多返回的行数"),
) -> Envelope[LogListData]:
    """读取日志尾部内容，便于后台快速巡检。"""

    log_path = _resolve_log_path()
    lines, total = _load_tail_lines(log_path, limit)
    log_items = [
        LogLine(idx=total - len(lines) + index + 1, content=content)
        for index, content in enumerate(lines)
    ]

    data = LogListData(lines=log_items, total=total, truncated=len(lines) < total)
    return Envelope(code=0, msg="success", data=data)
