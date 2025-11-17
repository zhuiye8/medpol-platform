"""EMA What's New 爬虫。"""

from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Optional
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from common.domain import ArticleCategory
from ..base import BaseCrawler, CrawlResult
from ..registry import registry


class EmaWhatsNewCrawler(BaseCrawler):
    """解析 EMA What's New 列表，抓取详情正文。"""

    name = "ema_whats_new"
    label = "EMA What's New"
    source_name = "EMA"
    category = ArticleCategory.EMA_POLICY
    start_urls = [
        "https://www.ema.europa.eu/en/news-events/whats-new",
    ]

    def __init__(self, config: Optional[Dict] = None) -> None:
        super().__init__(config)
        self.list_url = self.config.start_urls[0] if self.config.start_urls else self.start_urls[0]
        meta = self.config.meta
        self.max_pages = int(meta.get("max_pages", 2))
        self.max_items = int(meta.get("max_items", 30))
        self.detail_selector = meta.get("detail_selector") or "main article"
        self._client.headers.setdefault(
            "User-Agent",
            (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/125.0 Safari/537.36"
            ),
        )

    def crawl(self) -> List[CrawlResult]:
        results: List[CrawlResult] = []
        for page in range(self.max_pages):
            if self.max_items and len(results) >= self.max_items:
                break
            params = {"page": page} if page > 0 else None
            response = self.request("GET", self.list_url, params=params)
            soup = BeautifulSoup(response.text, "html.parser")
            rows = soup.select("#ema-search-results tr.col")
            if not rows:
                self.logger.info("第 %s 页无数据，终止", page)
                break
            for row in rows:
                if self.max_items and len(results) >= self.max_items:
                    break
                try:
                    crawl_result = self._parse_row(row)
                except SkipRow:
                    continue
                except Exception as exc:  # pylint: disable=broad-except
                    self.logger.warning("解析 EMA 条目失败 err=%s", exc)
                    continue
                results.append(crawl_result)
        self.logger.info("EMA What's New 共采集 %s 条", len(results))
        return results

    def _parse_row(self, row) -> CrawlResult:
        cols = row.find_all("td")
        if len(cols) < 2:
            raise SkipRow()
        date_text = cols[0].get_text(strip=True)
        publish_time = self._parse_date(date_text)
        title_block = cols[1]
        link = title_block.find("a")
        if not link or not link.get("href"):
            raise SkipRow()
        href = link.get("href")
        if href.lower().endswith(".pdf"):
            raise SkipRow()
        detail_url = urljoin(self.list_url, href)
        title = link.get_text(strip=True)
        content_type = title_block.select_one(".content-type strong")
        substance = title_block.select_one(".metadata")
        status_col = cols[2] if len(cols) > 2 else None
        status = (
            status_col.get_text(strip=True)
            if status_col and status_col.get_text(strip=True)
            else ""
        )
        detail_html, raw_html = self._fetch_detail(detail_url)
        metadata = {
            "content_type": content_type.get_text(strip=True) if content_type else "",
            "substance": substance.get_text(strip=True) if substance else "",
            "status": status,
        }
        return CrawlResult(
            title=title,
            source_url=detail_url,
            content_html=detail_html,
            publish_time=publish_time,
            raw_content=raw_html,
            metadata=metadata,
        )

    def _parse_date(self, text: str) -> Optional[datetime]:
        for fmt in ("%d/%m/%Y", "%d-%m-%Y"):
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


class SkipRow(Exception):
    """用于跳过无效行。"""


registry.register(EmaWhatsNewCrawler)
