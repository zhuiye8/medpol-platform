"""FDA 新闻稿（Press Announcements）爬虫。"""

from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Optional
from urllib.parse import urljoin

from bs4 import BeautifulSoup, NavigableString

from common.domain import ArticleCategory
from ..base import BaseCrawler, CrawlResult
from ..registry import registry


class FDAPressAnnouncementsCrawler(BaseCrawler):
    """抓取 FDA 新闻稿列表与详情正文。"""

    name = "fda_press"
    label = "FDA 新闻稿"
    source_name = "FDA"
    category = ArticleCategory.FDA_POLICY
    start_urls = [
        "https://www.fda.gov/news-events/fda-newsroom/press-announcements",
    ]

    def __init__(self, config: Optional[Dict] = None) -> None:
        super().__init__(config)
        self.list_url = self.config.start_urls[0] if self.config.start_urls else self.start_urls[0]
        meta = self.config.meta
        self.max_pages = int(meta.get("max_pages", 3))
        self.max_items = int(meta.get("max_items", 30))
        self.detail_selector = meta.get("detail_selector") or "article#main-content"
        self._client.headers.setdefault(
            "User-Agent",
            (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/125.0 Safari/537.36"
            ),
        )

    def crawl(self) -> List[CrawlResult]:
        total: List[CrawlResult] = []
        for page in range(self.max_pages):
            if self.max_items and len(total) >= self.max_items:
                break
            page_url = self._build_page_url(page)
            response = self.request("GET", page_url)
            soup = BeautifulSoup(response.text, "html.parser")
            items = self._extract_list_items(soup)
            if not items:
                self.logger.info("第 %s 页无数据，停止", page)
                break
            for item in items:
                if self.max_items and len(total) >= self.max_items:
                    break
                try:
                    total.append(self._build_result(item))
                except Exception as exc:  # pylint: disable=broad-except
                    self.logger.warning("解析新闻稿失败 err=%s", exc)
            if len(items) == 0:
                break
        self.logger.info("FDA 新闻稿采集完成，共 %s 条", len(total))
        return total

    def _build_page_url(self, page: int) -> str:
        if page <= 0:
            return self.list_url
        return f"{self.list_url}?page={page}"

    def _extract_list_items(self, soup: BeautifulSoup) -> List[Dict]:
        container = soup.select_one("div.view-press-announcements")
        if not container:
            container = soup  # fallback
        entries: List[Dict] = []
        for title_div in container.select("div.views-field-title a"):
            href = title_div.get("href")
            if not href:
                continue
            time_tag = title_div.find("time")
            publish_time = self._parse_datetime(time_tag)
            title = self._extract_title(title_div, time_tag)
            entries.append(
                {
                    "title": title,
                    "url": urljoin(self.list_url, href),
                    "publish_time": publish_time,
                }
            )
        return entries

    def _extract_title(self, anchor, time_tag) -> str:
        if not time_tag:
            return anchor.get_text(strip=True)
        chunks: List[str] = []
        for sibling in time_tag.next_siblings:
            if isinstance(sibling, NavigableString):
                text = str(sibling).strip()
                if text:
                    chunks.append(text)
            else:
                text = str(sibling.get_text(" ", strip=True))
                if text:
                    chunks.append(text)
        title = " ".join(chunks).strip(" -\u2013")
        return title or anchor.get_text(strip=True)

    def _parse_datetime(self, time_tag) -> Optional[datetime]:
        if not time_tag:
            return None
        iso = time_tag.get("datetime")
        if iso:
            try:
                return datetime.fromisoformat(iso.replace("Z", "+00:00"))
            except ValueError:
                pass
        text = time_tag.get_text(strip=True)
        for fmt in ("%B %d, %Y", "%b %d, %Y"):
            try:
                return datetime.strptime(text, fmt)
            except ValueError:
                continue
        return None

    def _build_result(self, item: Dict) -> CrawlResult:
        detail_html, raw = self._fetch_detail(item["url"])
        metadata = {
            "section": "Press Announcements",
        }
        return CrawlResult(
            title=item["title"],
            source_url=item["url"],
            content_html=detail_html,
            publish_time=item["publish_time"],
            raw_content=raw,
            metadata=metadata,
        )

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


registry.register(FDAPressAnnouncementsCrawler)
