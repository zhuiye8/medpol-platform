"""Tool registry based on Vanna Tool API."""

from __future__ import annotations

import json
from datetime import date, datetime
from typing import Any, Dict, List, Optional


def _json_serial(obj):
    """JSON serializer for objects not serializable by default."""
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    raise TypeError(f"Type {type(obj)} not serializable")


from pydantic import BaseModel, Field
from vanna.core.tool import Tool, ToolContext, ToolResult
from vanna.tools import RunSqlTool
from vanna.tools.file_system import LocalFileSystem
from vanna.core.registry import ToolRegistry

from ai_chat.vanna.sql_runner import FinanceSqlRunner
from ai_chat.vanna.vectorstore import similarity_search
from ai_chat.prompts.system import FIELD_DISPLAY_MAPPING, COMPANY_MAPPING


def _get_display_name(field: str) -> str:
    """获取字段的中文显示名。"""
    return FIELD_DISPLAY_MAPPING.get(field, field)


def _get_company_name(company_no: str) -> str:
    """将公司编号转换为中文名称。"""
    return COMPANY_MAPPING.get(company_no, company_no)


class SearchArgs(BaseModel):
    query: str = Field(description="检索问题或关键词")
    top_k: int = Field(default=5, ge=1, le=20, description="返回片段数量")


class ChartArgs(BaseModel):
    chart_type: str = Field(default="bar", description="图表类型: line(折线图), bar(柱状图), pie(饼图)")
    title: Optional[str] = Field(default=None, description="图表标题")
    additional_charts: Optional[List[str]] = Field(
        default=None,
        description="仅当用户明确要求多种图表时使用。默认只生成一个图表。"
    )


class SearchResult(BaseModel):
    """Structured search result for frontend rendering."""
    article_id: str
    title: str
    source_name: Optional[str] = None
    publish_time: Optional[str] = None
    text: str
    score: float


class SearchArticlesTool(Tool[SearchArgs]):
    """向量检索工具，直接查 pgvector."""

    @property
    def name(self) -> str:
        return "search_policy_articles"

    @property
    def description(self) -> str:
        return "基于向量检索医药政策/行业资讯片段，返回最相关的段落"

    def get_args_schema(self):
        return SearchArgs

    async def execute(self, context: ToolContext, args: SearchArgs) -> ToolResult:
        results = similarity_search(args.query, top_k=args.top_k)

        # Build structured search results for frontend
        search_results: List[Dict[str, Any]] = []
        summary = []
        for item in results:
            meta = item.get("metadata") or {}
            title = meta.get("title") or "[未命名]"
            text = item.get("text", "")

            # Structured result
            search_results.append({
                "article_id": meta.get("article_id", ""),
                "title": title,
                "source_name": meta.get("source_name"),
                "publish_time": meta.get("publish_time"),
                "text": text[:500] if text else "",  # Truncate for display
                "score": item.get("score", 0),
            })

            # Summary for top 3
            if len(summary) < 3:
                summary.append(f"- {title}")

        # 简化 result_for_llm，只返回精简摘要，不暴露 JSON 细节
        llm_text = (
            "检索到以下相关政策内容，请用自然语言总结回答用户问题：\n"
            + "\n".join([
                f"- 《{item.get('metadata', {}).get('title', '未知')}》: {(item.get('text', '') or '')[:300]}"
                for item in results[:5]
            ])
            if results else "未找到相关内容"
        )
        return ToolResult(
            success=True,
            result_for_llm=llm_text,
            metadata={
                "results": results,
                "search_results": search_results,  # Structured for frontend
            },
        )


class FinanceChartTool(Tool[ChartArgs]):
    """基于最近的财务查询结果生成可视化图表。"""

    @property
    def name(self) -> str:
        return "generate_finance_chart"

    @property
    def description(self) -> str:
        return "基于最近的财务数据查询生成可视化图表（柱状图/折线图/饼图），需先调用 query_finance_sql"

    def get_args_schema(self):
        return ChartArgs

    async def execute(self, context: ToolContext, args: ChartArgs) -> ToolResult:
        # 从 context.metadata 获取上一次 SQL 查询的结果
        tool_log = context.metadata.get("tool_log", [])
        last_sql = next(
            (t for t in reversed(tool_log) if t.get("tool_name") == "query_finance_sql"),
            None,
        )

        if not last_sql:
            return ToolResult(success=False, error="请先调用 query_finance_sql 查询财务数据")

        metadata = last_sql.get("metadata") or {}

        # 优先使用 metadata 中的结构化数据（Vanna RunSqlTool 返回）
        results = metadata.get("results")
        columns = metadata.get("columns")

        if results and columns:
            # 使用结构化数据
            chart_data = {"headers": columns, "rows": results}
        else:
            # 回退到解析 CSV 文本（兼容旧版本）
            result_text = last_sql.get("result_for_llm", "")
            chart_data = self._parse_sql_result(result_text)

        if not chart_data:
            return ToolResult(success=False, error="无法解析财务数据，请重新查询")

        # 图表类型中文名映射
        chart_type_names = {"bar": "柱状图", "line": "折线图", "pie": "饼图"}

        # 构建多个图表
        charts = []
        base_title = args.title or "财务数据"

        # 主图表（Plotly 格式）
        plotly_config = self._build_plotly_config(chart_data, args.chart_type, base_title)
        charts.append({
            "chart_type": args.chart_type,
            "config": plotly_config,
            "title": f"{base_title}{chart_type_names.get(args.chart_type, args.chart_type)}",
        })

        # 额外图表
        if args.additional_charts:
            for ct in args.additional_charts[:2]:  # 最多2个额外图表
                ct = ct.lower().strip()
                if ct in ("bar", "line", "pie") and ct != args.chart_type:
                    extra_config = self._build_plotly_config(chart_data, ct, base_title)
                    charts.append({
                        "chart_type": ct,
                        "config": extra_config,
                        "title": f"{base_title}{chart_type_names.get(ct, ct)}",
                    })

        chart_count = len(charts)
        return ToolResult(
            success=True,
            result_for_llm=f"已生成 {chart_count} 个图表",
            metadata={
                "charts": charts,  # 复数形式，支持多图表
            },
        )

    def _parse_sql_result(self, result_text: str) -> Optional[Dict[str, Any]]:
        """解析 SQL 查询结果文本，提取数据。"""
        if not result_text:
            return None

        lines = result_text.strip().split("\n")
        if len(lines) < 2:
            return None

        # 第一行是列名
        headers = [h.strip() for h in lines[0].split(",")]
        rows = []
        for line in lines[1:]:
            if not line.strip() or line.startswith("Results saved"):
                continue
            values = [v.strip() for v in line.split(",")]
            if len(values) == len(headers):
                rows.append(dict(zip(headers, values)))

        if not rows:
            return None

        return {"headers": headers, "rows": rows}

    def _build_plotly_config(self, data: Dict[str, Any], chart_type: str, title: str = "") -> Dict[str, Any]:
        """根据数据和图表类型构建 Plotly 配置。

        Plotly 格式:
        {
            "data": [{ "type": "bar", "x": [...], "y": [...] }],
            "layout": { "title": {...}, "xaxis": {...}, "yaxis": {...} }
        }
        """
        headers = data["headers"]
        rows = data["rows"]

        # 智能识别 X 轴和数值列（优先使用 keep_date 作为时间轴，company_name 作为分类轴）
        x_col = None
        value_cols = []

        # 优先级：keep_date > company_name > company_no > 其他
        priority_x_cols = ["keep_date", "company_name", "company_no"]
        for prio_col in priority_x_cols:
            if prio_col in headers:
                x_col = prio_col
                break

        # 如果没有优先列，使用原来的逻辑
        if not x_col:
            for h in headers:
                h_lower = h.lower()
                if any(k in h_lower for k in ["date", "month", "time", "company", "name"]):
                    x_col = h
                    break

        # 识别数值列
        for h in headers:
            h_lower = h.lower()
            if any(k in h_lower for k in ["amount", "rate", "total", "revenue", "profit"]):
                value_cols.append(h)

        # 如果没有识别到，使用默认列
        if not x_col and headers:
            x_col = headers[0]
        if not value_cols and len(headers) > 1:
            value_cols = [h for h in headers[1:] if h != x_col][:2]

        # 提取 X 轴数据并转换格式
        x_data = []
        for row in rows:
            val = row.get(x_col, "")
            # company_no 转换为公司名称
            if x_col == "company_no":
                val = _get_company_name(str(val) if val else "")
            # company_name 直接使用 API 返回值
            elif x_col == "company_name":
                val = str(val) if val else ""
            # keep_date 格式化为"X月"
            elif x_col == "keep_date" and val:
                try:
                    # 处理 datetime/date 对象或字符串
                    if hasattr(val, "month"):
                        # datetime 或 date 对象
                        val = f"{val.month}月"
                    else:
                        # 字符串格式 "YYYY-MM-DD"
                        parts = str(val).split("-")
                        if len(parts) >= 2:
                            val = f"{int(parts[1])}月"
                except (ValueError, IndexError, AttributeError):
                    val = str(val)
            else:
                val = str(val) if val else ""
            x_data.append(val)

        # Plotly 配色方案
        colors = ["#3b82f6", "#10b981", "#f59e0b", "#ef4444", "#8b5cf6", "#ec4899"]

        if chart_type == "pie":
            # 饼图（数据库已是万元单位，无需转换）
            val_col = value_cols[0] if value_cols else headers[-1]
            labels = []
            values = []
            for i, row in enumerate(rows):
                try:
                    value = float(row.get(val_col, 0) or 0)
                    name = x_data[i] if i < len(x_data) else str(row.get(x_col, ""))
                    labels.append(name)
                    values.append(value)
                except (ValueError, TypeError):
                    pass

            return {
                "data": [{
                    "type": "pie",
                    "labels": labels,
                    "values": values,
                    "hole": 0.4,  # Donut chart
                    "textinfo": "label+percent",
                    "hovertemplate": "%{label}<br>%{value:,.2f}万元<br>%{percent}<extra></extra>",
                    "marker": {"colors": colors[:len(labels)]},
                }],
                "layout": {
                    "title": {"text": title, "font": {"size": 16}},
                    "showlegend": True,
                    "legend": {"orientation": "v", "x": 0, "y": 1},
                    "margin": {"l": 20, "r": 20, "t": 50, "b": 20},
                },
            }

        # 折线图或柱状图（数据库已是万元单位，无需转换）
        traces = []
        for i, col in enumerate(value_cols):
            display_name = _get_display_name(col)
            y_data = []
            text_data = []  # 格式化的数值文本
            for row in rows:
                try:
                    val = float(row.get(col, 0) or 0)
                    y_data.append(val)
                    # 格式化数值：大于1万显示为x.xx万，否则显示原值
                    if val >= 10000:
                        text_data.append(f"{val/10000:.2f}亿")
                    elif val >= 1:
                        text_data.append(f"{val:,.0f}")
                    else:
                        text_data.append(f"{val:.2f}")
                except (ValueError, TypeError):
                    y_data.append(0)
                    text_data.append("0")

            trace = {
                "type": "scatter" if chart_type == "line" else "bar",
                "name": display_name,
                "x": x_data,
                "y": y_data,
                "marker": {"color": colors[i % len(colors)]},
            }

            if chart_type == "line":
                trace["mode"] = "lines+markers"
                trace["line"] = {"shape": "spline", "smoothing": 1.3}
            else:
                trace["text"] = text_data
                trace["textposition"] = "outside"

            traces.append(trace)

        return {
            "data": traces,
            "layout": {
                "title": {"text": title, "font": {"size": 16}},
                "xaxis": {
                    "title": {"text": _get_display_name(x_col) if x_col else ""},
                    "tickangle": -30 if len(x_data) > 5 else 0,
                },
                "yaxis": {
                    "title": {"text": "金额（万元）"},
                },
                "barmode": "group",
                "showlegend": len(traces) > 1,
                "legend": {"orientation": "h", "y": -0.2},
                "margin": {"l": 60, "r": 20, "t": 50, "b": 80},
                "hovermode": "x unified",
            },
        }


def build_tools(mode: str) -> List[Tool]:
    """Return tools for the given mode."""

    tools: List[Tool] = []
    sql_runner = FinanceSqlRunner()
    sql_tool = RunSqlTool(
        sql_runner=sql_runner,
        file_system=LocalFileSystem(working_directory="vanna_outputs"),
        custom_tool_name="query_finance_sql",
        custom_tool_description="只读查询 finance_records，回答营业收入/利润等财务问题。",
    )

    search_tool = SearchArticlesTool()
    chart_tool = FinanceChartTool()

    if mode == "sql":
        tools.extend([sql_tool, chart_tool])  # SQL 模式也支持图表
    elif mode == "rag":
        tools.append(search_tool)
    else:  # hybrid 默认都带上
        tools.extend([sql_tool, search_tool, chart_tool])
    return tools


def register_tools(registry: ToolRegistry, mode: str) -> None:
    for tool in build_tools(mode):
        registry.register_local_tool(tool, access_groups=[])

    # 可选：注册可视化工具，需搭配 run_sql 生成的 CSV 文件
    # from vanna.tools.visualize_data import VisualizeDataTool
    # registry.register_local_tool(VisualizeDataTool(), access_groups=[])


__all__ = ["build_tools", "SearchArticlesTool", "FinanceChartTool", "register_tools"]
