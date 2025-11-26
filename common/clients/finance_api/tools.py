"""基于本地 finance_records 的 AI 工具函数"""

from __future__ import annotations

import logging
from typing import Dict, List, Optional

from .service import FinanceDataService

logger = logging.getLogger(__name__)

DATA_SERVICE = FinanceDataService()

# 公司名称 → 编号映射表（支持多种表述方式）
COMPANY_MAP = {
    # 集团(合)
    "lhjt": "lhjt",
    "集团": "lhjt",
    "集团(合)": "lhjt",
    # 国药控股
    "gykg": "gykg",
    "国药控股": "gykg",
    # 华天宝
    "htb": "htb",
    "华天宝": "htb",
    # 产业(合)
    "jkcyhb": "jkcyhb",
    "产业": "jkcyhb",
    "产业(合)": "jkcyhb",
    # 康和药业
    "khyy": "khyy",
    "康和药业": "khyy",
    # 联博(合)
    "lbyyhb": "lbyyhb",
    "联博": "lbyyhb",
    "联博(合)": "lbyyhb",
    # 股份(合)
    "lhjthb": "lhjthb",
    "股份": "lhjthb",
    "股份(合)": "lhjthb",
    # 联通医药
    "ltyyhb": "ltyyhb",
    "联通医药": "ltyyhb",
    # 普林斯(合)
    "plshb": "plshb",
    "普林斯": "plshb",
    "普林斯(合)": "plshb",
    # 四川龙一
    "scly": "scly",
    "四川龙一": "scly",
    # 圣氏化学
    "sshx": "sshx",
    "圣氏化学": "sshx",
    # 基因(合)
    "ydjyhb": "ydjyhb",
    "基因": "ydjyhb",
    "基因(合)": "ydjyhb",
    # 颐和堂
    "yhtzy": "yhtzy",
    "颐和堂": "yhtzy",
}


def _normalize_company_identifiers(company_identifiers: Optional[List[str]]) -> List[str]:
    """
    将用户输入的公司名称或编号标准化为编号列表

    示例：
    - ["国药控股", "集团"] → ["gykg", "lhjt"]
    - ["gykg", "shyy"] → ["gykg", "shyy"]
    - [] → []
    """
    if not company_identifiers:
        return []

    normalized = []
    for identifier in company_identifiers:
        identifier = identifier.strip()
        # 查找映射
        normalized_code = COMPANY_MAP.get(identifier)
        if normalized_code:
            if normalized_code not in normalized:  # 去重
                normalized.append(normalized_code)
        else:
            # 未找到映射，保留原值（可能是新增公司）
            logger.warning("未找到公司编号映射: %s，保留原值", identifier)
            if identifier not in normalized:
                normalized.append(identifier)

    return normalized

FINANCE_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "query_finance_data",
            "description": (
                "查询指定财务类型与月份的本地财务数据。"
                "所有金额单位为万元。"
                "支持使用公司名称（如'国药控股'、'集团'）或公司编号（如'gykg'、'lhjt'）查询。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "finance_type": {
                        "type": "string",
                        "enum": ["01", "02", "03", "04", "06", "07", "08"],
                        "description": "财务类型编号（01=营业收入, 02=利润总额, 03=实现税金, 04=入库税金, 06=净利润, 07=实现税金(扬州地区), 08=入库税金(扬州地区)）"
                    },
                    "keep_date": {
                        "type": "string",
                        "pattern": "^\\d{4}-\\d{2}$",
                        "description": "记账日期，格式 YYYY-MM"
                    },
                    "company_numbers": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "公司编号或名称列表（如 ['国药控股', '集团'] 或 ['gykg', 'lhjt']），留空则查询所有公司"
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
            "description": (
                "基于本地财务数据执行同比/环比/公司对比聚合。"
                "所有金额单位为万元。"
                "支持使用公司名称或编号。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "compare_dimension": {
                        "type": "string",
                        "enum": ["year", "month", "company"],
                        "description": "对比维度（year=同比, month=环比, company=公司对比）"
                    },
                    "finance_type": {
                        "type": "string",
                        "enum": ["01", "02", "03", "04", "06", "07", "08"],
                        "description": "财务类型编号（01=营业收入, 02=利润总额, 03=实现税金, 04=入库税金, 06=净利润, 07=实现税金(扬州地区), 08=入库税金(扬州地区)）"
                    },
                    "company_numbers": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "公司编号或名称列表（如 ['国药控股', '集团'] 或 ['gykg', 'lhjt']）"
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
    # 标准化公司标识符（名称 → 编号）
    normalized_companies = _normalize_company_identifiers(company_numbers)
    logger.info(
        "工具调用: query_finance_data type=%s keep_date=%s companies=%s (normalized from %s)",
        finance_type,
        keep_date,
        normalized_companies,
        company_numbers,
    )
    return DATA_SERVICE.query_finance_data(finance_type, keep_date, normalized_companies)


def compare_finance_data(
    compare_dimension: str,
    finance_type: str,
    company_numbers: List[str],
    years: List[str],
    months: List[str],
) -> Dict:
    # 标准化公司标识符（名称 → 编号）
    normalized_companies = _normalize_company_identifiers(company_numbers)
    logger.info(
        "工具调用: compare_finance_data dimension=%s type=%s companies=%s (normalized from %s) years=%s months=%s",
        compare_dimension,
        finance_type,
        normalized_companies,
        company_numbers,
        years,
        months,
    )
    return DATA_SERVICE.compare_finance_data(compare_dimension, finance_type, normalized_companies, years, months)


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
