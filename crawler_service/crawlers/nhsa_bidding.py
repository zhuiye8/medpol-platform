"""国家医保局 - 采购/集采/政策类爬虫。"""

from __future__ import annotations

from datetime import datetime
from typing import Dict, List
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from common.domain import ArticleCategory
from ..base import BaseCrawler, CrawlResult
from ..registry import registry


class NHSABiddingCrawler(BaseCrawler):
    """采集医保局网站的采购/集采通知，带子分类 status。"""

    name = "nhsa_bidding"
    label = "国家医保局-采购"
    source_name = "国家医保局"
    category = ArticleCategory.BIDDING
    start_urls = [
        # 默认使用国家组织集采栏目 col187
        "https://www.nhsa.gov.cn/col/col187/index.html",
    ]

    def __init__(self, config: Dict | None = None) -> None:
        super().__init__(config)
        meta = self.config.meta
        self.list_url = meta.get("list_url") or self.start_urls[0]
        self.page_size = int(meta.get("page_size", 20))
        self.max_pages = int(meta.get("max_pages", 1))
        self.source_label = meta.get("source_label") or "国家组织集采"
        # status: policy_updates / national_tenders / provincial_tenders
        self.status = meta.get("status")
        if not self.status:
            if "col187" in self.list_url:
                self.status = "national_tenders"
            elif "col186" in self.list_url:
                self.status = "provincial_tenders"
            else:
                self.status = "policy_updates"
        self._client.headers.setdefault(
            "User-Agent",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0 Safari/537.36",
        )

    def crawl(self) -> List[CrawlResult]:
        html = self._fetch_listing_html()
        entries = self._extract_entries(html)
        limit = self.page_size * self.max_pages if self.max_pages > 0 else len(entries)
        selected = entries[:limit]
        results: List[CrawlResult] = []
        for entry in selected:
            try:
                results.append(self._build_result(entry))
            except Exception as exc:  # pylint: disable=broad-except
                self.logger.warning("采集招采失败 url=%s err=%s", entry["url"], exc)
        self.logger.info("招采采集 %s 条记录", len(results))
        return results

    def _fetch_listing_html(self) -> str:
        response = self.request("GET", self.list_url)
        response.encoding = response.charset_encoding or "utf-8"
        return response.text

    def _extract_entries(self, html: str) -> List[Dict[str, str]]:
        soup = BeautifulSoup(html, "html.parser")
        entries: List[Dict[str, str]] = []
        seen: set[str] = set()
        for script in soup.find_all("script", attrs={"type": "text/xml"}):
            xml = BeautifulSoup(script.string or "", "xml")
            for record in xml.find_all("record"):
                fragment = record.string
                if not fragment:
                    continue
                frag_soup = BeautifulSoup(fragment, "html.parser")
                li = frag_soup.find("li")
                if not li:
                    continue
                anchor = li.find("a")
                span = li.find("span")
                if not anchor or not span:
                    continue
                href = anchor.get("href")
                if not href:
                    continue
                url = urljoin(self.list_url, href)
                if url in seen:
                    continue
                seen.add(url)
                entries.append(
                    {
                        "title": anchor.get_text(strip=True),
                        "url": url,
                        "publish_date": span.get_text(strip=True),
                        "article_id": self._extract_article_id(url),
                    }
                )
        return entries

    def _build_result(self, entry: Dict[str, str]) -> CrawlResult:
        detail_html = self._fetch_article_html(entry["url"])
        soup = BeautifulSoup(detail_html, "html.parser")
        content = soup.select_one("div#zoom") or soup.select_one("div.atricle") or soup.body
        content_html = content.decode_contents() if content else f"<p>{entry['title']}</p>"
        publish_time = self._parse_publish_time(entry["publish_date"])
        metadata = {
            "article_id": entry["article_id"],
            "category": self.category.value,
            "source_label": self.source_label,
            "status": self.status,
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


registry.register(NHSABiddingCrawler)
