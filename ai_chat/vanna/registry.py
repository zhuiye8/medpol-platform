"""Custom ToolRegistry to log tool calls for API response."""

from __future__ import annotations

import logging
from typing import Any, Dict, List

from vanna.core.registry import ToolRegistry
from vanna.core.tool import ToolCall, ToolContext, ToolResult

logger = logging.getLogger(__name__)


# 允许暴露给前端的参数白名单
_SAFE_ARG_KEYS = {"query", "top_k", "chart_type", "title"}


class LoggingToolRegistry(ToolRegistry):
    """Wrap ToolRegistry.execute to capture tool calls and buffer components."""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._last_calls: List[Dict[str, Any]] = []
        self._pending_components: List[Dict[str, Any]] = []
        self._pending_tool_starts: List[str] = []  # 待发送的工具启动事件

    @property
    def last_calls(self) -> List[Dict[str, Any]]:
        return list(self._last_calls)

    def pop_pending_tool_starts(self) -> List[str]:
        """获取并清空待发送的工具启动事件。"""
        starts = self._pending_tool_starts.copy()
        self._pending_tool_starts.clear()
        return starts

    async def execute(self, tool_call: ToolCall, context: ToolContext) -> ToolResult:
        # 工具开始执行时，记录启动事件（用于前端状态更新）
        self._pending_tool_starts.append(tool_call.name)

        result = await super().execute(tool_call, context)

        # 检测搜索结果，加入待发送组件队列
        if result.metadata and "search_results" in result.metadata:
            self._pending_components.append({
                "type": "search_results",
                "data": {"results": result.metadata["search_results"]},
                "title": "相关政策文档",
            })

        # 检测图表数据（支持单图表和多图表）
        if result.metadata:
            if "charts" in result.metadata:
                # 多图表模式
                charts = result.metadata["charts"]
                logger.info(f"🔍 [Registry] Detected 'charts' in metadata, count={len(charts)}")
                for i, chart in enumerate(charts):
                    logger.info(f"🔍 [Registry] Chart {i}: has_config={bool(chart.get('config'))}, chart_type={chart.get('chart_type')}")
                    if chart.get('config'):
                        plotly_data = chart['config'].get('data', [])
                        logger.info(f"🔍 [Registry] Chart {i} plotly data length: {len(plotly_data)}")
                    self._pending_components.append({
                        "type": "chart",
                        "data": chart,
                        "title": chart.get("title"),
                    })
            elif "chart" in result.metadata:
                # 向后兼容单图表模式
                logger.info(f"🔍 [Registry] Detected single 'chart' in metadata")
                self._pending_components.append({
                    "type": "chart",
                    "data": result.metadata["chart"],
                    "title": result.metadata.get("title"),
                })

        # 🔧 检测聚合结果（COUNT/SUM/AVG等统计查询）
        # 注释掉紫色卡片展示，改为只在文字回复中提及统计结果
        # if result.metadata and result.metadata.get("is_aggregate"):
        #     agg_data = result.metadata.get("aggregate_result")
        #     if agg_data:
        #         self._pending_components.append({
        #             "type": "aggregate_result",
        #             "data": {
        #                 "label": agg_data["label"],
        #                 "value": agg_data["value"],
        #                 "format": "number",  # 可扩展：percent, currency等
        #             },
        #             "title": "统计结果",
        #         })

        # 检测 DataFrame 数据（员工查询结果等）
        if result.metadata:
            results = result.metadata.get("results")
            columns = result.metadata.get("columns")
            if results is not None and columns is not None:
                logger.info(f"🔍 [Registry] Detected DataFrame: rows={len(results)}, columns={columns}")
                logger.info(f"🔍 [Registry] DataFrame has is_aggregate={result.metadata.get('is_aggregate')}")
                self._pending_components.append({
                    "type": "dataframe",
                    "data": {
                        "columns": columns,
                        "rows": results,
                        "row_count": len(results),
                        "column_labels": result.metadata.get("column_labels"),
                    },
                    "title": result.metadata.get("title", "查询结果"),
                })

        # 清理记录（不暴露原始数据给前端）
        record = {
            "tool_name": tool_call.name,
            "args": {k: v for k, v in (tool_call.arguments or {}).items() if k in _SAFE_ARG_KEYS},
            "success": result.success,
            "summary": self._summarize(tool_call.name, result),
        }
        self._last_calls.append(record)
        # also stash on context metadata for downstream use (保留完整数据供 LLM 使用)
        context.metadata.setdefault("tool_log", []).append({
            "tool_name": tool_call.name,
            "args": tool_call.arguments,
            "success": result.success,
            "result_for_llm": result.result_for_llm,
            "metadata": result.metadata,
            "error": result.error,
        })
        return result

    def pop_pending_components(self) -> List[Dict[str, Any]]:
        """获取并清空待发送的组件队列。"""
        components = self._pending_components.copy()
        self._pending_components.clear()
        return components

    def clear_log(self) -> None:
        self._last_calls.clear()
        self._pending_components.clear()
        self._pending_tool_starts.clear()

    def _summarize(self, name: str, result: ToolResult) -> str:
        """生成用户友好的工具执行摘要。"""
        if not result.success:
            return f"执行失败: {result.error or '未知错误'}"
        if name == "search_policy_articles":
            count = len((result.metadata or {}).get("results", []))
            return f"找到 {count} 条相关政策"
        if name == "query_finance_sql":
            return "财务数据查询完成"
        if name == "generate_finance_chart":
            return "图表已生成"
        return "操作完成"


__all__ = ["LoggingToolRegistry"]
