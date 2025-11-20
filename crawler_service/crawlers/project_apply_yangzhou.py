"""扬州项目申报爬虫，通过 JS 渲染后的列表提取公告。"""

from __future__ import annotations

from datetime import datetime
from typing import Dict, List
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from common.domain import ArticleCategory
from ..base import BaseCrawler, CrawlResult
from ..registry import registry


class YangzhouProjectApplyCrawler(BaseCrawler):
    """采集扬州科技局/工信局公告，用于项目申报任务。"""

    name = "project_apply_yangzhou"
    label = "扬州项目申报"
    source_name = "扬州公告"
    category = ArticleCategory.PROJECT_APPLY
    start_urls = [
        "https://kjj.yangzhou.gov.cn/zfxxgk/fdzdgknr/tzgg/index.html",
        "https://gxj.yangzhou.gov.cn/zfxxgk/fdzdgknr/tzgg/index.html",
    ]

    def __init__(self, config: Dict | None = None) -> None:
        super().__init__(config)
        meta = self.config.meta
        self.list_urls = meta.get("list_urls") or self.start_urls
        self.max_items = int(meta.get("max_items", 50))
        self.status = meta.get("status") or "pending"
        self._client.headers.setdefault(
            "User-Agent",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0 Safari/537.36",
        )

    def crawl(self) -> List[CrawlResult]:
        results: List[CrawlResult] = []
        for list_url in self.list_urls:
            html = self._render_listing_html(list_url)
            entries = self._extract_entries(html, list_url)
            for entry in entries[: self.max_items]:
                try:
                    results.append(self._build_result(entry))
                except Exception as exc:  # pylint: disable=broad-except
                    self.logger.warning("采集扬州项目失败 url=%s err=%s", entry["url"], exc)
        self.logger.info("扬州项目申报采集 %s 条记录", len(results))
        return results

    def _render_listing_html(self, list_url: str) -> str:
        """使用 Playwright 渲染列表页，拿到真实公告。"""

        from playwright.sync_api import sync_playwright  # noqa: WPS433 (runtime import)

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(list_url, wait_until="networkidle", timeout=20000)
            page.wait_for_timeout(2000)
            html = page.content()
            browser.close()
            return html

    def _extract_entries(self, html: str, list_url: str) -> List[Dict[str, str]]:
        soup = BeautifulSoup(html, "html.parser")
        entries: List[Dict[str, str]] = []
        for block in soup.select("div.xxgk-list"):
            for a in block.select("a[href]"):
                href = a.get("href", "")
                if not href or href.startswith("javascript"):
                    continue
                title = a.get_text(strip=True)
                if not title:
                    continue
                url = urljoin(list_url, href)
                li = a.find_parent("li")
                publish_date = ""
                if li:
                    span = li.find("span")
                    if span:
                        publish_date = span.get_text(strip=True)
                entries.append(
                    {
                        "title": title,
                        "url": url,
                        "publish_date": publish_date,
                    }
                )
        return entries

    def _build_result(self, entry: Dict[str, str]) -> CrawlResult:
        detail_html = self._fetch_article_html(entry["url"])
        soup = BeautifulSoup(detail_html, "html.parser")
        content = soup.select_one("div.article") or soup.select_one("div.zw") or soup.body
        content_html = content.decode_contents() if content else f"<p>{entry['title']}</p>"
        publish_time = self._parse_publish_time(entry.get("publish_date"))
        metadata = {
            "category": self.category.value,
            "status": self.status,
            "source_name": self.source_name,
        }
        return CrawlResult(
            title=entry["title"],
            source_url=entry["url"],
            content_html=content_html,
            publish_time=publish_time,
            metadata=metadata,
        )

    def _fetch_article_html(self, url: str) -> str:
        response = self.request("GET", url)
        response.encoding = response.charset_encoding or "utf-8"
        return response.text

    @staticmethod
    def _parse_publish_time(value: str | None) -> datetime:
        if not value:
            return datetime.utcnow()
        for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y.%m.%d"):
            try:
                return datetime.strptime(value, fmt)
            except ValueError:
                continue
        return datetime.utcnow()


registry.register(YangzhouProjectApplyCrawler)
