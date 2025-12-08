"""System prompt builder for chat."""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo


def build_system_prompt(persona: str | None = None, mode: str = "rag") -> str:
    """生成带有模式提示的系统提示。"""

    persona_key = persona or "general"
    now = datetime.now(ZoneInfo("Asia/Shanghai"))
    weekday_cn = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"][now.weekday()]
    time_str = f"{now.year}年{now.month}月{now.day}日{now:%H:%M}（{weekday_cn}）"

    # 财务查询的核心业务知识（SQL 和 Hybrid 共用）
    sql_knowledge = (
        "【财务查询规范】表名：finance_records。"
        "字段：keep_date（月份日期如 2025-09-01）、company_no（公司编号）、company_name（公司名称）、"
        "type_no（类型编号：01=营业收入, 02=利润总额, 03=净利润）、current_amount（本期金额）。"
        "公司编号映射：联环集团=lhjt。"
        "日期过滤：keep_date IN ('2024-08-01','2024-09-01') 或 date_part('year/month', keep_date)。"
        "示例：SELECT keep_date, SUM(current_amount) AS revenue FROM finance_records "
        "WHERE company_no='lhjt' AND type_no='01' GROUP BY keep_date ORDER BY keep_date;"
        "禁止使用 company/year/month/period/revenue 等不存在的字段。"
    )

    mode_hint = {
        "rag": "仅可调用 search_policy_articles 进行向量检索；回答时引用片段信息并用中文总结，不泄露字段/向量细节。",
        "sql": f"仅可调用 query_finance_sql 执行只读 SQL。{sql_knowledge}",
        "hybrid": (
            f"优先调用 query_finance_sql 获取财务事实，再结合 search_policy_articles 检索政策片段，综合回答时标注数据来源。"
            f"{sql_knowledge}"
        ),
    }.get(mode, "")

    return (
        f"【当前时间】请以北京时间理解问题：{time_str}。\n"
        "你是医药政策与财务分析助理，回答需准确、简洁、中文输出，避免无依据的编造。\n"
        f"{mode_hint}\n"
        f"Persona={persona_key}。"
    )


__all__ = ["build_system_prompt"]
