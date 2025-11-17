"""财务API辅助函数

提供数据格式化、参数解析等辅助功能。
"""

from typing import List, Dict, Optional


# 财务类型映射表
FINANCE_TYPE_NAMES = {
    "01": "营业收入",
    "02": "利润总额",
    "03": "实现税金",
    "04": "入库税金",
    "05": "所得税",
    "06": "净利润",
    "07": "实现税金(扬州地区)",
    "08": "入库税金(扬州地区)",
}


def get_finance_type_name(finance_type: str) -> str:
    """获取财务类型名称

    Args:
        finance_type: 财务类型编号

    Returns:
        财务类型名称
    """
    return FINANCE_TYPE_NAMES.get(finance_type, f"未知类型({finance_type})")


def format_finance_data(
    raw_data: List[Dict],
    finance_type: str,
    keep_date: str,
    company_numbers: Optional[List[str]] = None
) -> Dict:
    """格式化财务数据

    将原始API返回数据转换为更友好的格式。

    Args:
        raw_data: 原始数据列表
        finance_type: 财务类型编号
        keep_date: 记账日期
        company_numbers: 公司编号列表

    Returns:
        格式化的数据字典
    """
    formatted_data = {
        "query": {
            "finance_type": finance_type,
            "finance_type_name": get_finance_type_name(finance_type),
            "keep_date": keep_date,
            "companies": company_numbers
        },
        "results": [],
        "summary": {
            "total_count": 0,
            "total_amount": 0.0,
            "avg_growth_rate": 0.0
        }
    }

    total_amount = 0.0
    total_growth_rate = 0.0
    valid_growth_count = 0

    for item in raw_data:
        formatted_item = {
            "company_no": item.get("companyNo"),
            "company_name": item.get("companyName"),
            "level": item.get("level"),
            "current_amount": item.get("currentAmt", 0),
            "last_year_amount": item.get("lastYearAmt", 0),
            "this_year_total": item.get("thisYearTotalAmt", 0),
            "year_on_year_growth": item.get("yearAddRate", 0),
            "month_on_month_growth": item.get("addRate", 0),
        }

        formatted_data["results"].append(formatted_item)

        # 计算汇总数据
        total_amount += formatted_item["current_amount"]
        if formatted_item["year_on_year_growth"] is not None:
            total_growth_rate += formatted_item["year_on_year_growth"]
            valid_growth_count += 1

    # 更新汇总信息
    formatted_data["summary"]["total_count"] = len(formatted_data["results"])
    formatted_data["summary"]["total_amount"] = round(total_amount, 2)
    if valid_growth_count > 0:
        formatted_data["summary"]["avg_growth_rate"] = round(
            total_growth_rate / valid_growth_count, 2
        )

    return formatted_data


def format_compare_data(
    raw_data: Dict,
    compare_dimension: str,
    finance_type: str,
    company_numbers: List[str],
    years: List[str],
    months: List[str]
) -> Dict:
    """格式化对比分析数据

    Args:
        raw_data: 原始对比数据
        compare_dimension: 对比维度
        finance_type: 财务类型
        company_numbers: 公司编号列表
        years: 年份列表
        months: 月份列表

    Returns:
        格式化的对比数据
    """
    formatted = {
        "compare_dimension": compare_dimension,
        "finance_type": finance_type,
        "finance_type_name": get_finance_type_name(finance_type),
        "parameters": {
            "companies": company_numbers,
            "years": years,
            "months": months
        },
        "summary": {},
        "details": [],
        "insights": []
    }

    # 根据对比维度处理数据
    if compare_dimension == "year":
        formatted["insights"].append("年度对比分析显示同比增长趋势")
    elif compare_dimension == "month":
        formatted["insights"].append("月度对比分析显示环比波动情况")
    elif compare_dimension == "company":
        formatted["insights"].append("公司对比分析显示各公司财务差异")

    # 简单处理：将原始数据放入details
    formatted["details"] = raw_data if isinstance(raw_data, list) else [raw_data]

    return formatted


def parse_month_range(month_desc: str) -> List[str]:
    """解析月份范围描述

    Args:
        month_desc: 月份描述，如"第一季度"、"1-3月"

    Returns:
        月份列表，如["01", "02", "03"]
    """
    quarter_map = {
        "第一季度": ["01", "02", "03"],
        "第二季度": ["04", "05", "06"],
        "第三季度": ["07", "08", "09"],
        "第四季度": ["10", "11", "12"],
        "Q1": ["01", "02", "03"],
        "Q2": ["04", "05", "06"],
        "Q3": ["07", "08", "09"],
        "Q4": ["10", "11", "12"],
    }

    return quarter_map.get(month_desc, [])


def format_amount(amount: float, unit: str = "万元") -> str:
    """格式化金额显示

    Args:
        amount: 金额数值
        unit: 单位（默认"万元"）

    Returns:
        格式化的金额字符串
    """
    if amount is None:
        return "N/A"

    # 如果金额很大，自动转换单位
    if abs(amount) >= 10000:
        return f"{amount / 10000:.2f}亿元"
    else:
        return f"{amount:.2f}{unit}"


def calculate_growth_rate(current: float, previous: float) -> Optional[float]:
    """计算增长率

    Args:
        current: 当前值
        previous: 上期值

    Returns:
        增长率（百分比），如果无法计算则返回None
    """
    if previous is None or previous == 0:
        return None

    return round(((current - previous) / previous) * 100, 2)
