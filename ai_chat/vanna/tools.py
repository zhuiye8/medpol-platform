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
from ai_chat.vanna.employee_sql_runner import EmployeeSqlRunner
from ai_chat.vanna.vectorstore import similarity_search
from ai_chat.prompts.system import FIELD_DISPLAY_MAPPING, COMPANY_MAPPING
from common.auth.service import Roles


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


# 员工表字段 -> 中文显示名映射
EMPLOYEE_COLUMN_LABELS = {
    "name": "姓名",
    "company_name": "公司",
    "company_no": "公司编号",
    "department": "部门",
    "position": "职务",
    "gender": "性别",
    "employee_level": "员工级别",
    "is_contract": "是/否劳动合同工",
    "highest_education": "学历",
    "graduate_school": "毕业院校",
    "major": "专业",
    "political_status": "政治面貌",
    "professional_title": "职称",
    "skill_level": "技能等级",
    "hire_date": "入职日期",
    "id_number": "身份证号",
    "phone": "电话",
}


class EmployeeQueryArgs(BaseModel):
    sql: str = Field(description="查询员工数据的 SQL 语句")


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

        智能检测数据维度，支持：
        - 多公司时间序列：按公司分组，每公司一条线/柱
        - 多公司单时间点：X轴为公司，柱状图对比
        - 多指标时间序列：按指标分组
        - 单系列：原有逻辑
        """
        headers = data["headers"]
        rows = data["rows"]

        # Plotly 配色方案（扩展到支持更多系列）
        colors = [
            "#3b82f6", "#10b981", "#f59e0b", "#ef4444", "#8b5cf6", "#ec4899",
            "#06b6d4", "#84cc16", "#f97316", "#6366f1", "#14b8a6", "#a855f7",
        ]

        # 1. 识别数据维度
        has_company = "company_name" in headers
        has_time = "keep_date" in headers
        has_type = "type_name" in headers

        # 识别数值列
        value_cols = []
        for h in headers:
            h_lower = h.lower()
            if any(k in h_lower for k in ["amount", "rate", "total", "revenue", "profit"]):
                value_cols.append(h)
        if not value_cols and len(headers) > 1:
            # 排除已知的分类列
            exclude = {"company_name", "company_no", "keep_date", "type_name", "type_no"}
            value_cols = [h for h in headers if h not in exclude][:2]

        val_col = value_cols[0] if value_cols else headers[-1]

        # 2. 饼图特殊处理
        if chart_type == "pie":
            return self._build_pie_config(rows, headers, val_col, colors, title)

        # 3. 确定分组策略
        group_col = None
        x_col = None

        if has_company and has_time:
            # 场景1：多公司时间序列 → 按公司分组，X轴为时间
            group_col = "company_name"
            x_col = "keep_date"
        elif has_type and has_time:
            # 场景3：多指标时间序列 → 按指标分组
            group_col = "type_name"
            x_col = "keep_date"
        elif has_company and not has_time:
            # 场景2：多公司单时间点 → X轴为公司
            group_col = None
            x_col = "company_name"
        elif has_time:
            # 单公司时间序列
            group_col = None
            x_col = "keep_date"
        else:
            # 默认：使用第一列作为X轴
            x_col = headers[0] if headers else None

        # 4. 构建 traces
        if group_col:
            traces = self._build_grouped_traces(rows, group_col, x_col, val_col, chart_type, colors)
        else:
            traces = self._build_single_traces(rows, x_col, value_cols, chart_type, colors)

        # 5. 智能布局配置
        series_count = len(traces)
        x_data_len = len(traces[0]["x"]) if traces and traces[0].get("x") else 0

        layout = {
            "title": {"text": title, "font": {"size": 14}},
            "xaxis": {
                "title": {"text": _get_display_name(x_col) if x_col else ""},
                "tickangle": -45 if x_data_len > 6 else (-30 if x_data_len > 4 else 0),
                "tickfont": {"size": 10},
            },
            "yaxis": {
                "title": {"text": "金额（万元）"},
                "tickfont": {"size": 10},
            },
            "barmode": "group",
            "showlegend": series_count > 1,
            "hovermode": "x unified",
        }

        # 图例策略：>3 系列时竖向放右侧，否则水平放下方
        if series_count > 3:
            layout["legend"] = {
                "orientation": "v",
                "x": 1.02,
                "y": 1,
                "xanchor": "left",
                "font": {"size": 10},
            }
            layout["margin"] = {"l": 50, "r": 120, "t": 40, "b": 70}
        else:
            layout["legend"] = {
                "orientation": "h",
                "y": -0.2,
                "x": 0.5,
                "xanchor": "center",
                "font": {"size": 10},
            }
            layout["margin"] = {"l": 50, "r": 20, "t": 40, "b": 80}

        return {"data": traces, "layout": layout}

    def _build_pie_config(self, rows, headers, val_col, colors, title):
        """构建饼图配置。"""
        # 确定标签列
        label_col = None
        for col in ["company_name", "type_name", "company_no"]:
            if col in headers:
                label_col = col
                break
        if not label_col:
            label_col = headers[0] if headers else None

        labels = []
        values = []
        for row in rows:
            try:
                value = float(row.get(val_col, 0) or 0)
                label = row.get(label_col, "")
                if label_col == "company_no":
                    label = _get_company_name(str(label))
                labels.append(str(label) if label else "未知")
                values.append(value)
            except (ValueError, TypeError):
                pass

        return {
            "data": [{
                "type": "pie",
                "labels": labels,
                "values": values,
                "hole": 0.4,
                "textinfo": "label+percent",
                "hovertemplate": "%{label}<br>%{value:,.2f}万元<br>%{percent}<extra></extra>",
                "marker": {"colors": colors[:len(labels)]},
            }],
            "layout": {
                "title": {"text": title, "font": {"size": 14}},
                "showlegend": True,
                "legend": {"orientation": "v", "x": 1.02, "y": 1, "font": {"size": 10}},
                "margin": {"l": 20, "r": 100, "t": 40, "b": 20},
            },
        }

    def _build_grouped_traces(self, rows, group_col, x_col, val_col, chart_type, colors):
        """按分组列构建多系列 traces（多公司/多指标）。"""
        # 获取所有分组
        groups = sorted(set(str(row.get(group_col, "")) for row in rows if row.get(group_col)))

        traces = []
        for i, group in enumerate(groups):
            # 筛选该分组的数据
            group_rows = [r for r in rows if str(r.get(group_col, "")) == group]
            # 按X轴排序
            group_rows.sort(key=lambda r: str(r.get(x_col, "")))

            x_data = []
            y_data = []
            for row in group_rows:
                # X轴格式化
                x_val = row.get(x_col, "")
                if x_col == "keep_date" and x_val:
                    x_val = self._format_date(x_val)
                else:
                    x_val = str(x_val) if x_val else ""
                x_data.append(x_val)

                # Y轴数值
                try:
                    y_val = float(row.get(val_col, 0) or 0)
                except (ValueError, TypeError):
                    y_val = 0
                y_data.append(y_val)

            trace = {
                "type": "scatter" if chart_type == "line" else "bar",
                "name": group,  # 使用分组名作为图例
                "x": x_data,
                "y": y_data,
                "marker": {"color": colors[i % len(colors)]},
            }

            if chart_type == "line":
                trace["mode"] = "lines+markers"
                trace["line"] = {"shape": "spline", "smoothing": 1.3}

            traces.append(trace)

        return traces

    def _build_single_traces(self, rows, x_col, value_cols, chart_type, colors):
        """构建单系列或按数值列分组的 traces。"""
        # 提取 X 轴数据
        x_data = []
        for row in rows:
            val = row.get(x_col, "")
            if x_col == "company_no":
                val = _get_company_name(str(val) if val else "")
            elif x_col == "company_name":
                val = str(val) if val else ""
            elif x_col == "keep_date" and val:
                val = self._format_date(val)
            else:
                val = str(val) if val else ""
            x_data.append(val)

        traces = []
        for i, col in enumerate(value_cols):
            display_name = _get_display_name(col)
            y_data = []
            text_data = []
            for row in rows:
                try:
                    val = float(row.get(col, 0) or 0)
                    y_data.append(val)
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

        return traces

    def _format_date(self, val) -> str:
        """将日期格式化为 'X月' 形式。"""
        try:
            if hasattr(val, "month"):
                return f"{val.month}月"
            else:
                parts = str(val).split("-")
                if len(parts) >= 2:
                    return f"{int(parts[1])}月"
        except (ValueError, IndexError, AttributeError):
            pass
        return str(val)


class EmployeeQueryTool(Tool[EmployeeQueryArgs]):
    """员工数据查询工具，带权限控制。

    根据用户角色自动选择合适的视图：
    - admin, hr_manager: 可见全部字段（含敏感信息）
    - hr_viewer: 仅可见基础字段（不含身份证、电话）
    - 其他角色: 无权访问
    """

    def __init__(self, user_role: str):
        self.user_role = user_role
        self.sql_runner = EmployeeSqlRunner(user_role)

    @property
    def name(self) -> str:
        return "query_employees"

    @property
    def description(self) -> str:
        if not self.sql_runner.can_access:
            return "员工数据查询（当前角色无权访问）"

        schema_desc = self.sql_runner.get_schema_description()
        return f"查询员工数据（姓名、部门、职务、学历等）。\n{schema_desc}"

    def get_args_schema(self):
        return EmployeeQueryArgs

    async def execute(self, context: ToolContext, args: EmployeeQueryArgs) -> ToolResult:
        if not self.sql_runner.can_access:
            return ToolResult(
                success=False,
                error=f"角色 {self.user_role} 无权访问员工数据"
            )

        try:
            from vanna.capabilities.sql_runner.models import RunSqlToolArgs
            sql_args = RunSqlToolArgs(sql=args.sql)
            df = await self.sql_runner.run_sql(sql_args, context)

            # 构建结果
            if df.empty:
                return ToolResult(
                    success=True,
                    result_for_llm="查询结果为空，没有找到符合条件的员工记录。",
                    metadata={}  # 不返回 results/columns，避免创建空表格组件
                )

            # 转换为列表格式，过滤掉内部字段
            hidden_columns = {"id", "raw_data", "created_at", "updated_at"}
            columns = [col for col in df.columns if col not in hidden_columns]
            results = [
                {k: v for k, v in row.items() if k not in hidden_columns}
                for row in df.to_dict(orient="records")
            ]

            # 生成中文列名映射
            column_labels = {col: EMPLOYEE_COLUMN_LABELS.get(col, col) for col in columns}

            # 生成数据摘要供 LLM 引用（避免 LLM 编造数据）
            summary_lines = []
            for row in results[:10]:  # 最多显示前10条
                name = row.get("name", "")
                dept = row.get("department", "")
                pos = row.get("position", "")
                edu = row.get("highest_education", "")
                summary_lines.append(f"- {name}，{dept}，{pos}，{edu}")

            data_summary = "\n".join(summary_lines)
            if len(results) > 10:
                data_summary += f"\n... 共 {len(results)} 条记录"

            return ToolResult(
                success=True,
                result_for_llm=(
                    f"查询到 {len(results)} 条员工记录：\n{data_summary}\n\n"
                    "以上数据已在表格组件中完整展示。请用自然语言总结回答，禁止生成 markdown 表格。"
                ),
                metadata={
                    "results": results,
                    "columns": columns,
                    "column_labels": column_labels,
                    "total": len(results),
                    "title": "员工查询结果",
                }
            )

        except PermissionError as e:
            return ToolResult(success=False, error=str(e))
        except ValueError as e:
            return ToolResult(success=False, error=str(e))
        except Exception as e:
            return ToolResult(success=False, error=f"查询出错: {str(e)}")


def build_tools(mode: str, user_role: str = "viewer") -> List[Tool]:
    """Return tools for the given mode and user role.

    Args:
        mode: 模式 - "rag", "sql", "hybrid"
        user_role: 用户角色 - "admin", "finance", "viewer"

    Returns:
        工具列表

    权限矩阵：
    - admin: 财务 + 员工全字段 + 政策（hybrid模式）
    - finance: 只有财务（sql模式）
    - viewer: 政策 + 员工基础（rag模式、PC对话）
    """
    tools: List[Tool] = []

    # 财务查询工具（仅 admin 和 finance 角色可用）
    if user_role in {Roles.ADMIN, Roles.FINANCE}:
        sql_runner = FinanceSqlRunner()
        sql_tool = RunSqlTool(
            sql_runner=sql_runner,
            file_system=LocalFileSystem(working_directory="vanna_outputs"),
            custom_tool_name="query_finance_sql",
            custom_tool_description="只读查询 finance_records，回答营业收入/利润等财务问题。",
        )
        chart_tool = FinanceChartTool()
    else:
        sql_tool = None
        chart_tool = None

    # 政策检索工具（admin 和 viewer 可用，finance 不可用）
    search_tool = SearchArticlesTool() if user_role != Roles.FINANCE else None

    # 员工查询工具（admin 和 viewer 可用，finance 不可用）
    employee_tool = EmployeeQueryTool(user_role)

    # 根据模式组合工具
    if mode == "sql":
        # sql 模式：只有财务工具（finance 角色专用）
        if sql_tool:
            tools.extend([sql_tool, chart_tool])
    elif mode == "rag":
        # rag 模式：政策 + 员工基础（viewer 角色）
        if search_tool:
            tools.append(search_tool)
        if employee_tool.sql_runner.can_access:
            tools.append(employee_tool)
    else:  # hybrid 模式：全部工具（admin 角色）
        if sql_tool:
            tools.extend([sql_tool, chart_tool])
        if search_tool:
            tools.append(search_tool)
        if employee_tool.sql_runner.can_access:
            tools.append(employee_tool)

    return tools


def register_tools(registry: ToolRegistry, mode: str, user_role: str = "viewer") -> None:
    """注册工具到 registry。

    Args:
        registry: Vanna ToolRegistry
        mode: 模式 - "rag", "sql", "hybrid"
        user_role: 用户角色
    """
    for tool in build_tools(mode, user_role):
        registry.register_local_tool(tool, access_groups=[])


__all__ = [
    "build_tools",
    "SearchArticlesTool",
    "FinanceChartTool",
    "EmployeeQueryTool",
    "register_tools",
]
