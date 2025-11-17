"""药渡云-前沿动态爬虫，实现 `/zixun/more` 接口采集。"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Dict, List

from common.domain import ArticleCategory
from ..base import BaseCrawler, CrawlResult
from ..registry import registry


class PharnexFrontierCrawler(BaseCrawler):
    """药渡云 - 前沿动态栏目."""

    name = "pharnex_frontier"
    label = "前沿动态"
    source_name = "药渡云"
    category = ArticleCategory.FRONTIER
    description = "药渡云前沿动态栏目"
    start_urls: List[str] = []

    API_ENDPOINT = "https://www.pharnexcloud.com/zixun/more"

    def __init__(self, config: Dict | None = None) -> None:
        super().__init__(config)
        meta = self.config.meta
        self.category_slug = meta.get("category_slug", "shiye")
        self.abbreviation = meta.get("abbreviation", "qy")
        self.page_size = int(meta.get("page_size", 10))
        self.max_pages = int(meta.get("max_pages", 3))
        # 默认补充浏览器 UA，避免被判定为机器人
        default_headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0 Safari/537.36"
            ),
            "Accept": "application/json, text/plain, */*",
            "Referer": f"https://www.pharnexcloud.com/zixun/{self.category_slug}/{self.abbreviation}",
        }
        self._client.headers.update(default_headers)

    def crawl(self) -> List[CrawlResult]:
        """分页请求 `/zixun/more` 并解析文章。"""

        results: List[CrawlResult] = []
        for page in range(1, self.max_pages + 1):
            params = {
                "page": page,
                "pageSize": self.page_size,
                "category": self.category_slug,
                "abbreviation": self.abbreviation,
            }
            response = self.request("GET", self.API_ENDPOINT, params=params)
            payload = response.json()
            articles = payload.get("data") or []
            if not articles:
                self.logger.info("第 %s 页无数据，结束", page)
                break
            for article in articles:
                try:
                    results.append(self._build_result(article))
                except Exception as exc:  # pylint: disable=broad-except
                    self.logger.warning(
                        "解析文章失败 id=%s err=%s", article.get("id"), exc
                    )
            last_page = (payload.get("meta") or {}).get("last_page")
            if last_page and page >= last_page:
                break
        self.logger.info("共采集 %s 篇文章", len(results))
        return results

    def _build_result(self, article: Dict) -> CrawlResult:
        publish_time = self._parse_publish_time(article)
        content_html = self._merge_modules(article)
        source_url = article.get("url") or f"https://www.pharnexcloud.com/zixun/zcsp_{article.get('id')}"
        metadata = {
            "abstract": article.get("abstract") or "",
            "tags": [
                tag.get("name")
                for tag in article.get("tags", [])
                if tag.get("name")
            ],
            "category": self.category.value,
            "raw_category": article.get("categories"),
            "article_id": article.get("id"),
            "author": article.get("author") or article.get("original") or "药渡云",
        }
        return CrawlResult(
            title=(article.get("title") or "").strip(),
            source_url=source_url,
            content_html=content_html,
            publish_time=publish_time,
            raw_content=json.dumps(article, ensure_ascii=False),
            metadata=metadata,
        )

    def _merge_modules(self, article: Dict) -> str:
        """将模块化正文拼接为完整 HTML."""

        modules = article.get("modules") or []
        bodies = [module.get("body", "") for module in modules if module.get("body")]
        if not bodies and article.get("body"):
            bodies = [article["body"]]
        if not bodies and article.get("abstract"):
            bodies = [f"<p>{article['abstract']}</p>"]
        return "\n".join(bodies)

    def _parse_publish_time(self, article: Dict) -> datetime:
        """按照优先级解析发布时间，失败则返回当前时间。"""

        for field in ("released_at", "created_at", "updated_at"):
            value = article.get(field)
            if not value:
                continue
            try:
                return datetime.strptime(value, "%Y-%m-%d %H:%M:%S")
            except ValueError:
                continue
        return datetime.utcnow()


registry.register(PharnexFrontierCrawler)
