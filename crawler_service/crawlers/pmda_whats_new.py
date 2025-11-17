"""PMDA What's New 爬虫。"""

from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Optional
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from common.domain import ArticleCategory
from ..base import BaseCrawler, CrawlResult
from ..registry import registry


class PMDAWhatsNewCrawler(BaseCrawler):
    """解析 PMDA What's New 列表，抓取详情正文。"""

    name = "pmda_whats_new"
    label = "PMDA What's New"
    source_name = "PMDA"
    category = ArticleCategory.PMDA_POLICY
    start_urls = [
        "https://www.pmda.go.jp/english/0006.html",
    ]

    def __init__(self, config: Optional[Dict] = None) -> None:
        super().__init__(config)
        self.list_url = self.config.start_urls[0] if self.config.start_urls else self.start_urls[0]
        meta = self.config.meta
        self.max_items = int(meta.get("max_items", 30))
        self.detail_selector = meta.get("detail_selector") or "main"
        self._client.headers.setdefault(
            "User-Agent",
            (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/125.0 Safari/537.36"
            ),
        )

    def crawl(self) -> List[CrawlResult]:
        response = self.request("GET", self.list_url)
        soup = BeautifulSoup(response.text, "html.parser")
        items = soup.select("ul.list__news li a")
        results: List[CrawlResult] = []
        for anchor in items:
            if self.max_items and len(results) >= self.max_items:
                break
            try:
                results.append(self._build_result(anchor))
            except Exception as exc:  # pylint: disable=broad-except
                self.logger.warning("解析 PMDA 条目失败 err=%s", exc)
        self.logger.info("PMDA What's New 共采集 %s 条", len(results))
        return results

    def _build_result(self, anchor) -> CrawlResult:
        detail_url = urljoin(self.list_url, anchor.get("href", ""))
        if not detail_url:
            raise ValueError("missing url")
        title = (anchor.select_one("p.title") or anchor).get_text(strip=True)
        category = anchor.select_one("p.category")
        status = anchor.select_one("p.status")
        date_text = (anchor.select_one("p.date") or anchor).get_text(strip=True)
        publish_time = self._parse_date(date_text)
        detail_html, raw = self._fetch_detail(detail_url)
        metadata = {
            "category_label": category.get_text(strip=True) if category else "",
            "status": status.get_text(strip=True) if status else "",
        }
        return CrawlResult(
            title=title,
            source_url=detail_url,
            content_html=detail_html,
            publish_time=publish_time,
            raw_content=raw,
            metadata=metadata,
        )

    def _parse_date(self, text: str) -> Optional[datetime]:
        for fmt in ("%B %d, %Y",):
            try:
                return datetime.strptime(text, fmt)
            except ValueError:
                continue
        return None

    def _fetch_detail(self, url: str) -> tuple[str, str]:
        response = self.request("GET", url)
        soup = BeautifulSoup(response.text, "html.parser")
        node = soup.select_one(self.detail_selector)
        if not node:
            body = soup.body
            html = body.decode_contents() if body else response.text
        else:
            html = node.decode_contents()
        return html, response.text


registry.register(PMDAWhatsNewCrawler)
