# -*- coding: utf-8 -*-
"""Employee SQL runner with permission-based view selection.

根据用户角色自动选择合适的视图：
- admin: 使用 employees 表（可见敏感字段）
- viewer: 使用 employees_basic 视图（不含敏感字段）
- finance: 无权访问员工数据
"""

from __future__ import annotations

import re
from typing import Optional

import pandas as pd
import sqlalchemy as sa
from vanna.capabilities.sql_runner.base import SqlRunner
from vanna.capabilities.sql_runner.models import RunSqlToolArgs
from vanna.core.tool import ToolContext

from common.auth.service import Roles
from common.utils.config import get_settings

_settings = get_settings()


class EmployeeSqlRunner(SqlRunner):
    """Run read-only queries against employees table with role-based access."""

    # 可以访问完整员工数据的角色
    FULL_ACCESS_ROLES = {Roles.ADMIN}

    # 可以访问基本员工数据的角色（不含敏感字段）
    BASIC_ACCESS_ROLES = {Roles.ADMIN, Roles.VIEWER}

    def __init__(self, user_role: str, db_url: Optional[str] = None) -> None:
        """初始化员工 SQL Runner。

        Args:
            user_role: 用户角色（从认证系统获取）
            db_url: 数据库连接 URL（可选）
        """
        self.user_role = user_role
        self.db_url = db_url or _settings.database_url
        self._engine = None

        # 根据角色决定可访问的视图
        if user_role in self.FULL_ACCESS_ROLES:
            self.target_view = "employees"  # 完整表
            self.can_access = True
        elif user_role in self.BASIC_ACCESS_ROLES:
            self.target_view = "employees_basic"  # 基础视图
            self.can_access = True
        else:
            self.target_view = None
            self.can_access = False

    def _engine_conn(self):
        if self._engine is None:
            self._engine = sa.create_engine(self.db_url)
        return self._engine

    def _is_safe_sql(self, sql: str) -> bool:
        """检查 SQL 是否安全（只读、单条语句）。"""
        stripped = sql.strip().rstrip(";")
        if not stripped:
            return False

        # 禁止多条语句
        if ";" in stripped:
            return False

        lowered = stripped.lower()

        # 只允许 SELECT/CTE
        if not (lowered.startswith("select") or lowered.startswith("with")):
            return False

        # 必须涉及员工表/视图
        if not any(t in lowered for t in ["employees", "employees_basic", "employees_full"]):
            return False

        # 禁止写操作
        forbidden = ["insert", "update", "delete", "drop", "alter", "truncate"]
        if any(f in lowered for f in forbidden):
            return False

        return True

    def _rewrite_sql(self, sql: str) -> str:
        """根据角色重写 SQL，将 employees 表名替换为对应视图。

        如果用户角色是 viewer，会将 SQL 中的：
        - employees -> employees_basic
        - employees_full -> employees_basic（降级）

        这确保了即使 LLM 生成了访问原始表的 SQL，也会被重写为安全的视图。
        """
        if not self.can_access:
            raise PermissionError("无权访问员工数据")

        if self.user_role in self.FULL_ACCESS_ROLES:
            # 管理员可以访问完整数据，不需要重写
            return sql

        # viewer 只能访问基础视图
        # 将 employees_full 和 employees 都替换为 employees_basic
        rewritten = re.sub(
            r'\bemployees_full\b',
            'employees_basic',
            sql,
            flags=re.IGNORECASE
        )
        rewritten = re.sub(
            r'\bemployees\b(?!_)',  # 匹配 employees 但不匹配 employees_xxx
            'employees_basic',
            rewritten,
            flags=re.IGNORECASE
        )
        return rewritten

    async def run_sql(self, args: RunSqlToolArgs, context: ToolContext) -> pd.DataFrame:
        """执行员工查询 SQL。

        Args:
            args: SQL 参数
            context: 工具上下文

        Returns:
            查询结果 DataFrame

        Raises:
            PermissionError: 无权访问员工数据
            ValueError: SQL 不安全
        """
        if not self.can_access:
            raise PermissionError(f"角色 {self.user_role} 无权访问员工数据")

        sql = args.sql.strip()

        if not self._is_safe_sql(sql):
            raise ValueError("仅允许单条只读查询员工数据的 SELECT/CTE 语句")

        # 重写 SQL 以适应角色权限
        safe_sql = self._rewrite_sql(sql)

        engine = self._engine_conn()
        df = pd.read_sql_query(sa.text(safe_sql), engine)
        return df

    def get_schema_description(self) -> str:
        """返回当前角色可见的表结构描述。"""
        if not self.can_access:
            return "无权访问员工数据"

        # 注意：不暴露 id 字段（内部主键，对用户无意义）
        base_fields = (
            "company_no, company_name, name, gender, "
            "department, position, employee_level, is_contract, "
            "highest_education, graduate_school, major, "
            "political_status, professional_title, skill_level, hire_date"
        )

        if self.user_role in self.FULL_ACCESS_ROLES:
            return (
                f"表: {self.target_view}\n"
                f"字段: {base_fields}, id_number(身份证号), phone(电话)"
            )
        else:
            return (
                f"视图: {self.target_view}\n"
                f"字段: {base_fields}\n"
                f"注意: 敏感字段（身份证号、电话）不可见"
            )


__all__ = ["EmployeeSqlRunner"]
