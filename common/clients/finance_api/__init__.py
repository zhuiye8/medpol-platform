"""财务数据API客户端模块

提供与外部财务报表API的集成，包括：
- HTTP客户端封装
- 数据模型定义
- AI工具函数
"""

from .client import FinanceAPIClient
from .models import (
    FinanceDataItem,
    FinanceTypeItem,
    FinanceQueryParams,
    FinanceCompareParams,
)
from .tools import (
    FINANCE_TOOLS,
    query_finance_data,
    compare_finance_data,
    get_finance_chart_data,
    get_available_finance_types,
    execute_tool,
)

__all__ = [
    "FinanceAPIClient",
    "FinanceDataItem",
    "FinanceTypeItem",
    "FinanceQueryParams",
    "FinanceCompareParams",
    "FINANCE_TOOLS",
    "query_finance_data",
    "compare_finance_data",
    "get_finance_chart_data",
    "get_available_finance_types",
    "execute_tool",
]
