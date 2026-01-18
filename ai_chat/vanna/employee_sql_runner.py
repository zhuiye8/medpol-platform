# -*- coding: utf-8 -*-
"""Employee SQL runner with permission-based view selection.

根据用户角色自动选择合适的视图：
- admin: 使用 employees 表（可见敏感字段）
- viewer: 使用 employees_basic 视图（不含敏感字段）
- finance: 无权访问员工数据
"""

from __future__ import annotations

import logging
import re
from typing import Optional

import pandas as pd
import sqlalchemy as sa
from vanna.capabilities.sql_runner.base import SqlRunner
from vanna.capabilities.sql_runner.models import RunSqlToolArgs
from vanna.core.tool import ToolContext

from common.auth.service import Roles
from common.utils.config import get_settings

logger = logging.getLogger(__name__)

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
        # 🔍 诊断日志：入参
        logger.info(f"🔍 [EmployeeSqlRunner] Initializing with user_role='{user_role}'")

        self.user_role = user_role
        self.db_url = db_url or _settings.database_url
        self._engine = None

        # 根据角色决定可访问的视图
        if user_role in self.FULL_ACCESS_ROLES:
            self.target_view = "employees"  # 完整表
            self.can_access = True
            # 🔍 诊断日志：完整权限
            logger.info(f"✓ [EmployeeSqlRunner] FULL ACCESS: target_view='employees', can_access=True")
        elif user_role in self.BASIC_ACCESS_ROLES:
            self.target_view = "employees_basic"  # 基础视图
            self.can_access = True
            # 🔍 诊断日志：基础权限
            logger.info(f"✓ [EmployeeSqlRunner] BASIC ACCESS: target_view='employees_basic', can_access=True")
        else:
            self.target_view = None
            self.can_access = False
            # 🔍 诊断日志：无权限
            logger.warning(f"⚠️ [EmployeeSqlRunner] NO ACCESS: user_role='{user_role}' not in allowed roles")

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
        # 🔍 诊断日志：SQL重写入口
        logger.info(f"🔄 [_rewrite_sql] Input SQL: {sql[:100]}...")
        logger.info(f"🔐 [_rewrite_sql] user_role='{self.user_role}', in FULL_ACCESS={self.user_role in self.FULL_ACCESS_ROLES}")

        if not self.can_access:
            raise PermissionError("无权访问员工数据")

        if self.user_role in self.FULL_ACCESS_ROLES:
            # 管理员可以访问完整数据，不需要重写
            logger.info(f"✓ [_rewrite_sql] FULL ACCESS role, SQL unchanged")
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

        # 🔍 诊断日志：SQL重写结果
        if rewritten != sql:
            logger.info(f"🔄 [_rewrite_sql] SQL was rewritten for BASIC ACCESS role")
            logger.info(f"📝 [_rewrite_sql] Rewritten SQL: {rewritten[:100]}...")
        else:
            logger.info(f"✓ [_rewrite_sql] No changes needed (already using correct view)")

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
        # 🔍 诊断日志：角色和权限
        logger.info(f"[EmployeeSqlRunner] Role={self.user_role}, TargetView={self.target_view}, CanAccess={self.can_access}")

        if not self.can_access:
            logger.warning(f"[EmployeeSqlRunner] Permission denied for role {self.user_role}")
            raise PermissionError(f"角色 {self.user_role} 无权访问员工数据")

        sql = args.sql.strip()

        # 🔍 诊断日志：原始 SQL
        logger.info(f"[EmployeeSqlRunner] Original SQL: {sql}")

        if not self._is_safe_sql(sql):
            logger.error(f"[EmployeeSqlRunner] Unsafe SQL detected: {sql}")
            raise ValueError("仅允许单条只读查询员工数据的 SELECT/CTE 语句")

        # 🔧 自动添加LIMIT（兜底保护，防止返回过多数据）
        sql_lower = sql.lower()
        has_agg = any(f in sql_lower for f in ['count(', 'sum(', 'avg(', 'max(', 'min(', 'group by'])
        has_limit = 'limit' in sql_lower

        if not has_agg and not has_limit:
            sql = f"{sql} LIMIT 500"
            logger.info(f"[EmployeeSqlRunner] Auto-added LIMIT 500 to prevent excessive data return")

        # 重写 SQL 以适应角色权限
        safe_sql = self._rewrite_sql(sql)

        # 🔍 诊断日志：重写后的 SQL
        if safe_sql != sql:
            logger.info(f"[EmployeeSqlRunner] Rewritten SQL: {safe_sql}")
        else:
            logger.info("[EmployeeSqlRunner] SQL not rewritten (admin role or no changes needed)")

        engine = self._engine_conn()
        df = pd.read_sql_query(sa.text(safe_sql), engine)

        # 🔧 如果达到LIMIT上限，记录警告
        if len(df) >= 500 and not has_limit and not has_agg:
            logger.warning(f"[EmployeeSqlRunner] Result reached LIMIT of 500 rows, more data may exist but not returned")

        # 🔍 诊断日志：查询结果
        logger.info(f"✓ [EmployeeSqlRunner] Query returned {len(df)} rows, {len(df.columns)} columns")
        if len(df) > 0:
            logger.info(f"📊 [EmployeeSqlRunner] Columns: {df.columns.tolist()}")
            # 检查是否包含敏感字段
            has_phone = 'phone' in df.columns
            has_id = 'id_number' in df.columns
            logger.info(f"🔐 [EmployeeSqlRunner] Sensitive fields: phone={has_phone}, id_number={has_id}")
        if len(df) == 0:
            logger.warning("[EmployeeSqlRunner] Query returned empty result!")

        return df

    def get_schema_description(self) -> str:
        """返回当前角色可见的表结构描述。"""
        if not self.can_access:
            return "无权访问员工数据"

        # 注意：不暴露 id 字段（内部主键，对用户无意义）
        # 注意：company_no 字段已废弃，已从视图中移除
        base_fields = (
            "company_name, name, gender, "
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
