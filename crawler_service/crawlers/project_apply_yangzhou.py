"""扬州科技/工信公告栏 - 项目申报爬虫，后续由 Formatter + LLM 过滤非申报信息."""

from __future__ import annotations

from datetime import datetime
from typing import Dict, List
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from common.domain import ArticleCategory
from ..base import BaseCrawler, CrawlResult
from ..registry import registry


class YangzhouProjectApplyCrawler(BaseCrawler):
    """扬州科技局/工信局公告栏，抓取后交给后续过滤."""

    name = "project_apply_yangzhou"
    label = "扬州项目申报"
    source_name = "扬州公告栏"
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
        self._client.headers.setdefault(
            "User-Agent",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0 Safari/537.36",
        )

    def crawl(self) -> List[CrawlResult]:
        results: List[CrawlResult] = []
        for list_url in self.list_urls:
            html = self._fetch_listing_html(list_url)
            entries = self._extract_entries(html, list_url)
            for entry in entries[: self.max_items]:
                try:
                    results.append(self._build_result(entry))
                except Exception as exc:  # pylint: disable=broad-except
                    self.logger.warning("解析项目公告失败 url=%s err=%s", entry["url"], exc)
        self.logger.info("扬州项目申报采集 %s 条记录", len(results))
        return results

    def _fetch_listing_html(self, list_url: str) -> str:
        response = self.request("GET", list_url)
        response.encoding = response.charset_encoding or "utf-8"
        return response.text

    def _extract_entries(self, html: str, list_url: str) -> List[Dict[str, str]]:
        soup = BeautifulSoup(html, "html.parser")
        entries: List[Dict[str, str]] = []
        for li in soup.select("div#page div.list ul li"):
            anchor = li.find("a")
            if not anchor:
                continue
            href = anchor.get("href")
            if not href:
                continue
            title = anchor.get_text(strip=True)
            date_span = li.find("span")
            publish_date = date_span.get_text(strip=True) if date_span else ""
            url = urljoin(list_url, href)
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
        content = soup.select_one("div.TRS_Editor") or soup.select_one("div#zoom") or soup.body
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


registry.register(YangzhouProjectApplyCrawler)
