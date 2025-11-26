"""Tavily 网络搜索工具 - OpenAI Function Calling 集成"""

from __future__ import annotations

import logging
from typing import Dict, List, Optional

from tavily import TavilyClient

logger = logging.getLogger(__name__)

# Tavily 客户端全局单例
_tavily_client: Optional[TavilyClient] = None


def get_tavily_client() -> TavilyClient:
    """获取 Tavily 客户端单例"""
    global _tavily_client
    if _tavily_client is None:
        from common.utils.config import get_settings
        settings = get_settings()
        api_key = settings.tavily_api_key
        if not api_key:
            raise ValueError("TAVILY_API_KEY 未配置，请在 .env 文件中设置")
        _tavily_client = TavilyClient(api_key=api_key)
        logger.info("Tavily 客户端初始化成功")
    return _tavily_client


# ============ 域名白名单配置 ============

# 核心域名白名单（来自项目爬虫）
ALL_DOMAINS = [
    "pharnexcloud.com",    # 药渡云 - 前沿动态
    "cde.org.cn",          # CDE - 法规/制度/受理
    "nhsa.gov.cn",         # 国家医保局 - 政策/招标
    "nmpa.gov.cn",         # 国家药监局 - 监管要闻
    "fda.gov",             # FDA - 美国政策
    "ema.europa.eu",       # EMA - 欧洲政策
    "pmda.go.jp",          # PMDA - 日本政策
]

# 分类到域名的映射（优化搜索精准度）
CATEGORY_DOMAIN_MAP = {
    "cde": ["cde.org.cn"],                              # CDE 专属
    "nhsa": ["nhsa.gov.cn"],                            # 医保局专属
    "nmpa": ["nmpa.gov.cn"],                            # 药监局专属
    "industry": ["pharnexcloud.com"],                   # 行业动态
    "fda": ["fda.gov"],                                 # FDA 专属
    "ema": ["ema.europa.eu"],                           # EMA 专属
    "pmda": ["pmda.go.jp"],                             # PMDA 专属
    "multiple": ["cde.org.cn", "nhsa.gov.cn", "nmpa.gov.cn"],  # 跨机构（国内）
    "unknown": ALL_DOMAINS,                             # 未知分类，全域名搜索
}


def get_domains_for_category(category: str | None) -> list[str]:
    """根据业务分类获取推荐的搜索域名

    Args:
        category: 业务分类（cde/nhsa/nmpa/industry/fda/ema/pmda/multiple/unknown）

    Returns:
        推荐的域名列表，如果未指定分类则返回全部域名
    """
    if not category:
        return ALL_DOMAINS
    return CATEGORY_DOMAIN_MAP.get(category, ALL_DOMAINS)


# ============ OpenAI Function Calling 工具定义 ============

KNOWLEDGE_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_medical_policy",
            "description": (
                "搜索医药政策、法规、新闻、公告等权威内容。"
                "搜索范围包括：CDE（法规/制度/受理品种）、国家医保局（政策/招标）、"
                "国家药监局（监管要闻）、药渡云（行业动态）、FDA/EMA/PMDA（国际标准）。"
                "适用场景：政策查询、法规解读、审批动态、行业新闻、申报指导、合规分析。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "搜索关键词或问题（建议使用具体、专业的医药术语，如'CDE创新药审评政策'）"
                    },
                    "search_depth": {
                        "type": "string",
                        "enum": ["basic", "advanced"],
                        "description": (
                            "搜索深度。basic=基础搜索（快速，5条结果，1 credit）；"
                            "advanced=深度搜索（详细，10条结果，2 credits）。默认 basic。"
                        ),
                        "default": "basic"
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "最大返回结果数（1-10），默认 5",
                        "default": 5,
                        "minimum": 1,
                        "maximum": 10
                    },
                    "include_domains": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": (
                            "指定搜索的域名白名单（可选）。"
                            "可选值：cde.org.cn, nhsa.gov.cn, nmpa.gov.cn, pharnexcloud.com, "
                            "fda.gov, ema.europa.eu, pmda.go.jp。"
                            "留空则搜索所有权威域名。"
                        )
                    }
                },
                "required": ["query"]
            }
        }
    }
]


# ============ 工具执行函数 ============

def search_medical_policy(
    query: str,
    search_depth: str = "basic",
    max_results: int = 5,
    include_domains: Optional[List[str]] = None,
    category: Optional[str] = None
) -> Dict:
    """
    使用 Tavily 搜索医药政策与行业动态

    Args:
        query: 搜索关键词或问题
        search_depth: 搜索深度（basic 或 advanced）
        max_results: 最大返回结果数（1-10）
        include_domains: 指定域名白名单（None=使用默认）
        category: 业务分类（cde/nhsa/nmpa/industry/fda/ema/pmda/multiple/unknown），用于自动推荐域名

    Returns:
        {
            "results": [
                {
                    "title": "标题",
                    "url": "链接",
                    "content": "内容摘要",
                    "score": 0.95  # 相关性评分
                }
            ],
            "query": "原始查询",
            "answer": "Tavily 生成的综合答案摘要",
            "domains_searched": ["实际搜索的域名列表"],
            "category_used": "使用的分类"
        }
    """
    # 确定域名白名单：优先级为 用户指定 > 分类推荐 > 全部域名
    if include_domains:
        domains = include_domains
    elif category:
        domains = get_domains_for_category(category)
        logger.info("根据分类 %s 推荐域名: %s", category, domains)
    else:
        domains = ALL_DOMAINS

    logger.info(
        "Tavily 搜索调用: query=%s depth=%s max=%d category=%s domains=%d个",
        query, search_depth, max_results, category, len(domains)
    )

    try:
        client = get_tavily_client()

        # 调用 Tavily API
        response = client.search(
            query=query,
            search_depth=search_depth,
            max_results=max_results,
            include_domains=domains,
            include_answer=True,  # 让 Tavily 生成答案摘要
        )

        # 格式化结果
        results = []
        for item in response.get("results", []):
            results.append({
                "title": item.get("title", ""),
                "url": item.get("url", ""),
                "content": item.get("content", ""),
                "score": item.get("score", 0.0)
            })

        logger.info("Tavily 搜索成功: 返回 %d 条结果", len(results))

        return {
            "results": results,
            "query": query,
            "answer": response.get("answer", ""),  # Tavily 生成的综合摘要
            "domains_searched": domains,
            "category_used": category
        }

    except Exception as exc:
        logger.error("Tavily 搜索失败: %s", exc, exc_info=True)
        return {
            "error": f"搜索失败: {str(exc)}",
            "results": [],
            "query": query
        }


def execute_knowledge_tool(tool_name: str, arguments: Dict) -> Dict:
    """知识库工具统一执行入口（供 ai_chat.py 调用）"""
    logger.info("执行知识库工具: %s", tool_name)

    if tool_name == "search_medical_policy":
        return search_medical_policy(**arguments)

    raise ValueError(f"未知的知识库工具: {tool_name}")


__all__ = [
    "KNOWLEDGE_TOOLS",
    "execute_knowledge_tool",
    "search_medical_policy",
    "ALL_DOMAINS",
]
