"""FDA 新增指南列表爬虫，抓取 HTML 表格并获取详情正文。"""

from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Optional
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from common.domain import ArticleCategory
from ..base import BaseCrawler, CrawlResult
from ..registry import registry


class FDAGuidanceCrawler(BaseCrawler):
    """解析 https://www.fda.gov/drugs/.../newly-added-guidance-documents"""

    name = "fda_guidance"
    label = "FDA 新增指南"
    source_name = "FDA"
    category = ArticleCategory.FDA_POLICY
    description = "获取 FDA 新增指南列表及正文"
    start_urls = [
        "https://www.fda.gov/drugs/guidances-drugs/newly-added-guidance-documents"
    ]

    def __init__(self, config: Optional[Dict] = None) -> None:
        super().__init__(config)
        self.list_url = self.config.start_urls[0] if self.config.start_urls else self.start_urls[0]
        meta = self.config.meta
        self.max_items = int(meta.get("max_items", 30))
        self.detail_selector = meta.get("detail_selector") or "article#main-content"
        # FDA 站点需常规浏览器 UA，避免被 WAF 拦截
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
        table = soup.find("table")
        if not table:
            self.logger.warning("页面未找到指南表格")
            return []
        rows = table.find_all("tr")
        results: List[CrawlResult] = []
        for row in rows[1:]:  # 跳过表头
            if self.max_items and len(results) >= self.max_items:
                break
            try:
                parsed = self._parse_row(row)
                if parsed:
                    results.append(parsed)
            except Exception as exc:  # pylint: disable=broad-except
                self.logger.warning("解析行失败 err=%s", exc)
        self.logger.info("FDA 指南采集完成，共 %s 条", len(results))
        return results

    def _parse_row(self, row) -> Optional[CrawlResult]:
        cols = row.find_all("td")
        if len(cols) < 4:
            return None
        topic = cols[0].get_text(strip=True)
        link_tag = cols[1].find("a")
        title = link_tag.get_text(strip=True) if link_tag else cols[1].get_text(strip=True)
        href = link_tag.get("href") if link_tag else ""
        detail_url = urljoin(self.list_url, href)
        status = cols[2].get_text(strip=True)
        date_text = cols[3].get_text(strip=True)
        publish_time = self._parse_date(date_text)

        detail_html, raw_html = self._fetch_detail(detail_url)
        metadata = {
            "topic": topic,
            "status": status,
            "detail_url": detail_url,
        }
        return CrawlResult(
            title=title,
            source_url=detail_url,
            content_html=detail_html,
            publish_time=publish_time,
            raw_content=raw_html,
            metadata=metadata,
        )

    def _parse_date(self, date_text: str) -> Optional[datetime]:
        for fmt in ("%m/%d/%Y", "%B %d, %Y"):
            try:
                return datetime.strptime(date_text, fmt)
            except ValueError:
                continue
        self.logger.debug("无法解析日期：%s", date_text)
        return None

    def _fetch_detail(self, url: str) -> tuple[str, str]:
        response = self.request("GET", url)
        soup = BeautifulSoup(response.text, "html.parser")
        detail = soup.select_one(self.detail_selector)
        if not detail:
            # 回退 body 内容
            body = soup.body
            html = body.decode_contents() if body else response.text
        else:
            html = detail.decode_contents()
        return html, response.text


registry.register(FDAGuidanceCrawler)
