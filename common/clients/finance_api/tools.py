"""AI工具函数定义

定义可供LLM调用的工具函数，用于财务数据查询和分析。
"""

import logging
from typing import List, Dict, Optional

from .client import FinanceAPIClient
from .utils import format_finance_data, format_compare_data, get_finance_type_name

logger = logging.getLogger(__name__)


# OpenAI Function Calling Schema定义
FINANCE_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "query_finance_data",
            "description": "查询指定财务类型和日期的财务报表数据。支持查询特定公司或全部公司的数据。适用场景：查询营业收入、利润、税金等财务指标的具体数据。",
            "parameters": {
                "type": "object",
                "properties": {
                    "finance_type": {
                        "type": "string",
                        "enum": ["01", "02", "03", "04", "05", "06", "07", "08"],
                        "description": "财务类型编号。01=营业收入, 02=利润总额, 03=实现税金, 04=入库税金, 05=所得税, 06=净利润, 07=实现税金(扬州), 08=入库税金(扬州)"
                    },
                    "keep_date": {
                        "type": "string",
                        "pattern": "^\\d{4}-\\d{2}$",
                        "description": "记账日期，格式为YYYY-MM，例如：2024-01"
                    },
                    "company_numbers": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "公司编号列表（可选）。如果不提供，则查询所有公司。例如：['001', '002']"
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
            "description": "多维度对比分析财务数据，支持跨年份、跨月份、跨公司的数据对比。适用场景：同比分析（year）、环比分析（month）、公司对比（company）。",
            "parameters": {
                "type": "object",
                "properties": {
                    "compare_dimension": {
                        "type": "string",
                        "enum": ["year", "month", "company"],
                        "description": "对比维度。year=年度对比, month=月度对比, company=公司对比"
                    },
                    "finance_type": {
                        "type": "string",
                        "enum": ["01", "02", "03", "04", "05", "06", "07", "08"],
                        "description": "财务类型编号"
                    },
                    "company_numbers": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "要对比的公司编号列表"
                    },
                    "years": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "年份列表，例如：['2023', '2024']"
                    },
                    "months": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "月份列表，格式为两位数字，例如：['01', '02', '03']"
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
            "description": "获取适合图表展示的财务数据格式，用于可视化分析。返回包含图表配置的数据结构，可用于生成趋势图、柱状图等。",
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
                        "description": "记账日期，格式为YYYY-MM"
                    },
                    "chart_type": {
                        "type": "string",
                        "enum": ["line", "bar", "pie"],
                        "description": "图表类型。line=折线图, bar=柱状图, pie=饼图。默认为line"
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
            "description": "获取所有可用的财务类型列表及其元数据。当用户询问有哪些财务指标可以查询，或需要了解系统支持的财务类型时使用。",
            "parameters": {
                "type": "object",
                "properties": {}
            }
        }
    }
]


def query_finance_data(
    finance_type: str,
    keep_date: str,
    company_numbers: Optional[List[str]] = None
) -> Dict:
    """查询财务数据工具函数

    Args:
        finance_type: 财务类型编号 ("01"-"08")
        keep_date: 记账日期 (YYYY-MM格式)
        company_numbers: 可选的公司编号列表

    Returns:
        格式化的财务数据字典
    """
    logger.info(
        "工具调用: query_finance_data(finance_type=%s, keep_date=%s, companies=%s)",
        finance_type,
        keep_date,
        company_numbers,
    )

    with FinanceAPIClient() as client:
        raw_data = client.get_finance_date(finance_type, keep_date, company_numbers)

    # 格式化数据
    formatted = format_finance_data(raw_data, finance_type, keep_date, company_numbers)

    logger.info("工具执行完成，返回%d条结果", len(formatted.get("results", [])))
    return formatted


def compare_finance_data(
    compare_dimension: str,
    finance_type: str,
    company_numbers: List[str],
    years: List[str],
    months: List[str]
) -> Dict:
    """对比分析财务数据工具函数

    Args:
        compare_dimension: 对比维度 ("year"/"month"/"company")
        finance_type: 财务类型编号
        company_numbers: 公司编号列表
        years: 年份列表
        months: 月份列表

    Returns:
        对比分析结果字典
    """
    logger.info(
        "工具调用: compare_finance_data(dimension=%s, type=%s, companies=%s, years=%s, months=%s)",
        compare_dimension,
        finance_type,
        company_numbers,
        years,
        months,
    )

    with FinanceAPIClient() as client:
        raw_data = client.get_finance_date_compare(
            compare_type=compare_dimension,
            company_numbers=company_numbers,
            years=years,
            months=months
        )

    # 格式化对比数据
    formatted = format_compare_data(
        raw_data,
        compare_dimension,
        finance_type,
        company_numbers,
        years,
        months
    )

    logger.info("工具执行完成")
    return formatted


def get_finance_chart_data(
    finance_type: str,
    keep_date: str,
    chart_type: str = "line"
) -> Dict:
    """获取图表数据工具函数

    Args:
        finance_type: 财务类型编号
        keep_date: 记账日期
        chart_type: 图表类型 (line/bar/pie)

    Returns:
        图表配置和数据（ECharts兼容格式）
    """
    logger.info(
        "工具调用: get_finance_chart_data(finance_type=%s, keep_date=%s, chart_type=%s)",
        finance_type,
        keep_date,
        chart_type,
    )

    with FinanceAPIClient() as client:
        raw_data = client.get_finance_date_graph(finance_type, keep_date)

    # 转换为通用图表格式
    chart_config = {
        "chart_type": chart_type,
        "title": f"{get_finance_type_name(finance_type)}趋势图",
        "finance_type": finance_type,
        "keep_date": keep_date,
        "data": raw_data
    }

    logger.info("工具执行完成")
    return chart_config


def get_available_finance_types() -> List[Dict]:
    """获取可用的财务类型列表工具函数

    Returns:
        财务类型列表，每项包含编号、名称、状态等信息
    """
    logger.info("工具调用: get_available_finance_types()")

    with FinanceAPIClient() as client:
        types_data = client.get_finance_type()

    logger.info("工具执行完成，返回%d个财务类型", len(types_data))
    return types_data


def execute_tool(tool_name: str, arguments: Dict) -> Dict:
    """工具函数路由器

    根据工具名称执行相应的工具函数。

    Args:
        tool_name: 工具名称
        arguments: 工具参数（字典）

    Returns:
        工具执行结果

    Raises:
        ValueError: 未知的工具名称
    """
    logger.info("执行工具: %s, 参数: %s", tool_name, arguments)

    if tool_name == "query_finance_data":
        return query_finance_data(**arguments)
    elif tool_name == "compare_finance_data":
        return compare_finance_data(**arguments)
    elif tool_name == "get_finance_chart_data":
        return get_finance_chart_data(**arguments)
    elif tool_name == "get_available_finance_types":
        return get_available_finance_types(**arguments)
    else:
        raise ValueError(f"未知的工具名称: {tool_name}")
