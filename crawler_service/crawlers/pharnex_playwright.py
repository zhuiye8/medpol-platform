"""药渡云-前沿动态（Playwright 版本）。"""

from __future__ import annotations

from datetime import datetime
from typing import List

from bs4 import BeautifulSoup
from common.domain import ArticleCategory

from ..base import BaseCrawler, CrawlResult
from ..playwright_runner import fetch_html
from ..registry import registry


class PharnexPlaywrightCrawler(BaseCrawler):
    """使用 Playwright 渲染页面以获取内容。"""

    name = "pharnex_frontier_playwright"
    label = "前沿动态（渲染）"
    category = ArticleCategory.FRONTIER
    source_name = "药渡云前沿动态（渲染）"

    def crawl(self) -> List[CrawlResult]:
        results: List[CrawlResult] = []
        max_pages = int(self.config.meta.get("max_pages", 1))
        page_size = int(self.config.meta.get("page_size", 10))
        category_slug = self.config.meta.get("category_slug", "shiye")
        abbreviation = self.config.meta.get("abbreviation", "qy")

        for page in range(1, max_pages + 1):
            url = f"https://www.pharnexcloud.com/zixun/{category_slug}/{abbreviation}?page={page}"
            try:
                html = fetch_html(url, wait_selector=".panel-list", wait_time=2.0)
                parsed = self.parse_rendered(html)
                if not parsed:
                    break
                results.extend(parsed[:page_size])
            except Exception as exc:  # pylint: disable=broad-except
                self.logger.warning("Playwright 抓取失败 page=%s err=%s", page, exc)
                break
        return results

    def parse_rendered(self, html: str) -> List[CrawlResult]:
        soup = BeautifulSoup(html, "html.parser")
        items = soup.select(".panel-list .panel-item")
        results: List[CrawlResult] = []
        for item in items:
            title_tag = item.select_one(".title")
            link = title_tag.find("a") if title_tag else None
            title = link.get_text(strip=True) if link else "未命名"
            href = link["href"] if link and link.has_attr("href") else ""
            summary_tag = item.select_one(".desc") or item.select_one(".summary")
            summary = summary_tag.get_text(strip=True) if summary_tag else ""
            date_tag = item.select_one(".date")
            publish_time = None
            if date_tag:
                try:
                    publish_time = datetime.strptime(date_tag.get_text(strip=True), "%Y-%m-%d")
                except ValueError:
                    publish_time = datetime.utcnow()
            metadata = {
                "abstract": summary,
                "tags": [tag.get_text(strip=True) for tag in item.select(".tag") if tag.get_text(strip=True)],
                "category": self.category.value,
            }
            results.append(
                CrawlResult(
                    title=title,
                    source_url=f"https://www.pharnexcloud.com{href}",
                    content_html=str(item),
                    publish_time=publish_time,
                    raw_content=str(item),
                    metadata=metadata,
                )
            )
        return results


registry.register(PharnexPlaywrightCrawler)
