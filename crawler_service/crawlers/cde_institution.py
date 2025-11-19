"""CDE - 中心制度 列表爬虫."""

from __future__ import annotations

from datetime import datetime
from typing import Dict, List
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from common.domain import ArticleCategory
from ..base import BaseCrawler, CrawlResult
from ..registry import registry


class CDEInstitutionCrawler(BaseCrawler):
    """采集 CDE 网站中心制度栏目."""

    name = "cde_institution"
    label = "CDE 中心制度"
    source_name = "药审中心(CDE)"
    category = ArticleCategory.INSTITUTION
    start_urls = ["https://www.cde.org.cn/main/policy/listpage/369ac7cfeb67c6000c33f85e6f374044"]

    def __init__(self, config: Dict | None = None) -> None:
        super().__init__(config)
        meta = self.config.meta
        self.list_url = meta.get("list_url") or self.start_urls[0]
        self.max_items = int(meta.get("max_items", 50))
        self._client.headers.setdefault(
            "User-Agent",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0 Safari/537.36",
        )

    def crawl(self) -> List[CrawlResult]:
        html = self._fetch_listing_html()
        entries = self._extract_entries(html)
        selected = entries[: self.max_items]
        results: List[CrawlResult] = []
        for entry in selected:
            try:
                results.append(self._build_result(entry))
            except Exception as exc:  # pylint: disable=broad-except
                self.logger.warning("解析中心制度失败 url=%s err=%s", entry["url"], exc)
        self.logger.info("中心制度采集 %s 条记录", len(results))
        return results

    def _fetch_listing_html(self) -> str:
        response = self.request("GET", self.list_url)
        response.encoding = response.charset_encoding or "utf-8"
        return response.text

    def _extract_entries(self, html: str) -> List[Dict[str, str]]:
        soup = BeautifulSoup(html, "html.parser")
        entries: List[Dict[str, str]] = []
        for li in soup.select("div#contentlist ul li"):
            anchor = li.find("a")
            if not anchor:
                continue
            href = anchor.get("href")
            if not href:
                continue
            title = anchor.get_text(strip=True)
            date_span = li.find("span")
            publish_date = date_span.get_text(strip=True) if date_span else ""
            url = urljoin(self.list_url, href)
            entries.append(
                {
                    "title": title,
                    "url": url,
                    "publish_date": publish_date,
                    "article_id": self._extract_article_id(url),
                }
            )
        return entries

    def _build_result(self, entry: Dict[str, str]) -> CrawlResult:
        detail_html = self._fetch_article_html(entry["url"])
        soup = BeautifulSoup(detail_html, "html.parser")
        content = soup.select_one("div#content")
        if not content:
            content = soup.body
        content_html = content.decode_contents() if content else f"<p>{entry['title']}</p>"
        publish_time = self._parse_publish_time(entry["publish_date"])
        metadata = {
            "article_id": entry["article_id"],
            "category": self.category.value,
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
    def _extract_article_id(url: str) -> str:
        slug = url.rstrip("/").split("/")[-1]
        return slug.rsplit(".", 1)[0]

    @staticmethod
    def _parse_publish_time(value: str | None) -> datetime:
        if not value:
            return datetime.utcnow()
        try:
            return datetime.strptime(value, "%Y-%m-%d")
        except ValueError:
            return datetime.utcnow()


registry.register(CDEInstitutionCrawler)
