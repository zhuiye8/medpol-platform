"""Tool registry based on Vanna Tool API."""

from __future__ import annotations

import json
from datetime import date, datetime
from typing import Dict, List, Optional


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


class SearchArgs(BaseModel):
    query: str = Field(description="检索问题或关键词")
    top_k: int = Field(default=5, ge=1, le=20, description="返回片段数量")


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
        summary = []
        for item in results[:3]:
            meta = item.get("metadata") or {}
            title = meta.get("title") or "[未命名]"
            summary.append(f"- {title}")
        llm_text = (
            "已检索到相关片段，请基于这些内容回答用户问题。\n"
            f"摘要：\n{chr(10).join(summary) if summary else '未找到相关内容'}\n"
            "详细结果(JSON)：\n" + json.dumps(results, ensure_ascii=False, default=_json_serial)[:2000]
        )
        return ToolResult(success=True, result_for_llm=llm_text, metadata={"results": results})


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

    if mode == "sql":
        tools.append(sql_tool)
    elif mode == "rag":
        tools.append(search_tool)
    else:  # hybrid 默认都带上
        tools.extend([sql_tool, search_tool])
    return tools


def register_tools(registry: ToolRegistry, mode: str) -> None:
    for tool in build_tools(mode):
        registry.register_local_tool(tool, access_groups=[])

    # 可选：注册可视化工具，需搭配 run_sql 生成的 CSV 文件
    # from vanna.tools.visualize_data import VisualizeDataTool
    # registry.register_local_tool(VisualizeDataTool(), access_groups=[])


__all__ = ["build_tools", "SearchArticlesTool", "register_tools"]
