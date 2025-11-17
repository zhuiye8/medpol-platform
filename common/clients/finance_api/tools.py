"""基于本地 finance_records 的 AI 工具函数"""

from __future__ import annotations

import logging
from typing import Dict, List, Optional

from .service import FinanceDataService

logger = logging.getLogger(__name__)

DATA_SERVICE = FinanceDataService()

FINANCE_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "query_finance_data",
            "description": "查询指定财务类型与月份的本地财务数据（来源：finance_records）",
            "parameters": {
                "type": "object",
                "properties": {
                    "finance_type": {
                        "type": "string",
                        "enum": ["01", "02", "03", "04", "05", "06", "07", "08"],
                        "description": "财务类型编号"
                    },
                    "keep_date": {
                        "type": "string",
                        "pattern": "^\\d{4}-\\d{2}$",
                        "description": "记账日期，格式 YYYY-MM"
                    },
                    "company_numbers": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "公司编号列表，可选"
                    }
                },
                "required": ["finance_type", "keep_date"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "compare_finance_data",
            "description": "基于本地财务数据执行同比/环比/公司对比聚合",
            "parameters": {
                "type": "object",
                "properties": {
                    "compare_dimension": {
                        "type": "string",
                        "enum": ["year", "month", "company"],
                        "description": "对比维度"
                    },
                    "finance_type": {
                        "type": "string",
                        "enum": ["01", "02", "03", "04", "05", "06", "07", "08"],
                        "description": "财务类型编号"
                    },
                    "company_numbers": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "公司编号列表"
                    },
                    "years": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "年份列表，例如 ['2023', '2024']"
                    },
                    "months": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "月份列表，格式 '01'~'12'"
                    }
                },
                "required": ["compare_dimension", "finance_type", "company_numbers", "years", "months"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_finance_chart_data",
            "description": "获取适合图表展示的财务数据（按月份、类型聚合）",
            "parameters": {
                "type": "object",
                "properties": {
                    "finance_type": {
                        "type": "string",
                        "enum": ["01", "02", "03", "04", "05", "06", "07", "08"],
                        "description": "财务类型编号"
                    },
                    "keep_date": {
                        "type": "string",
                        "pattern": "^\\d{4}-\\d{2}$",
                        "description": "记账日期，格式 YYYY-MM"
                    },
                    "chart_type": {
                        "type": "string",
                        "enum": ["line", "bar", "pie"],
                        "description": "图表类型"
                    }
                },
                "required": ["finance_type", "keep_date"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_available_finance_types",
            "description": "列出当前本地缓存中的财务类型编号及名称",
            "parameters": {"type": "object", "properties": {}}
        }
    },
]


def query_finance_data(
    finance_type: str,
    keep_date: str,
    company_numbers: Optional[List[str]] = None,
) -> Dict:
    logger.info("工具调用: query_finance_data type=%s keep_date=%s", finance_type, keep_date)
    return DATA_SERVICE.query_finance_data(finance_type, keep_date, company_numbers)


def compare_finance_data(
    compare_dimension: str,
    finance_type: str,
    company_numbers: List[str],
    years: List[str],
    months: List[str],
) -> Dict:
    logger.info(
        "工具调用: compare_finance_data dimension=%s type=%s companies=%s years=%s months=%s",
        compare_dimension,
        finance_type,
        company_numbers,
        years,
        months,
    )
    return DATA_SERVICE.compare_finance_data(compare_dimension, finance_type, company_numbers, years, months)


def get_finance_chart_data(
    finance_type: str,
    keep_date: str,
    chart_type: str = "line",
) -> Dict:
    logger.info(
        "工具调用: get_finance_chart_data type=%s keep_date=%s chart=%s",
        finance_type,
        keep_date,
        chart_type,
    )
    return DATA_SERVICE.get_chart_data(finance_type, keep_date, chart_type)


def get_available_finance_types() -> List[Dict]:
    logger.info("工具调用: get_available_finance_types")
    return DATA_SERVICE.list_finance_types()


def execute_tool(tool_name: str, arguments: Dict) -> Dict:
    logger.info("执行工具: %s", tool_name)
    if tool_name == "query_finance_data":
        return query_finance_data(**arguments)
    if tool_name == "compare_finance_data":
        return compare_finance_data(**arguments)
    if tool_name == "get_finance_chart_data":
        return get_finance_chart_data(**arguments)
    if tool_name == "get_available_finance_types":
        return get_available_finance_types()
    raise ValueError(f"未知的工具名: {tool_name}")
