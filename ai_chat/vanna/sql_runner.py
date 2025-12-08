"""Finance SQL runner implementing Vanna SqlRunner."""

from __future__ import annotations

import re
from typing import Optional

import pandas as pd
import sqlalchemy as sa
from vanna.capabilities.sql_runner.base import SqlRunner
from vanna.capabilities.sql_runner.models import RunSqlToolArgs
from vanna.core.tool import ToolContext

from common.utils.config import get_settings

_settings = get_settings()


def _is_safe_sql(sql: str) -> bool:
    """Basic guards: single statement, read-only, targets finance_records."""

    stripped = sql.strip().rstrip(";")
    if not stripped:
        return False
    # Block multiple statements
    if ";" in stripped:
        return False
    # Only allow SELECT/CTE
    lowered = stripped.lower()
    if not (lowered.startswith("select") or lowered.startswith("with")):
        return False
    # Must touch finance_records
    if "finance_records" not in lowered:
        return False
    # Block obvious write keywords
    forbidden = ["insert", "update", "delete", "drop", "alter", "truncate"]
    if any(f in lowered for f in forbidden):
        return False
    return True


class FinanceSqlRunner(SqlRunner):
    """Run safe, read-only queries against finance_records."""

    def __init__(self, db_url: Optional[str] = None) -> None:
        # 保留原始 URL（含 +psycopg），避免 SQLAlchemy 回退 psycopg2
        self.db_url = db_url or _settings.database_url
        self._engine = None

    def _engine_conn(self):
        if self._engine is None:
            self._engine = sa.create_engine(self.db_url)
        return self._engine

    async def run_sql(self, args: RunSqlToolArgs, context: ToolContext) -> pd.DataFrame:
        sql = args.sql.strip()
        if not _is_safe_sql(sql):
            raise ValueError("仅允许单条只读查询 finance_records 的 SELECT/CTE 语句")

        # Optional safeguard: ensure company_no filter hinted
        if "company_no" not in sql.lower() and "company_name" not in sql.lower():
            sql += " /* 提示：最好过滤 company_no='lhjt' 以聚焦联环集团 */"

        engine = self._engine_conn()
        df = pd.read_sql_query(sa.text(sql), engine)
        return df


__all__ = ["FinanceSqlRunner"]
