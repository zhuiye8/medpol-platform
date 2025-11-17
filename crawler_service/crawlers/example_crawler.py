"""示例爬虫，演示如何基于 BaseCrawler 实现采集逻辑。"""

from __future__ import annotations

from datetime import datetime
from typing import List

from bs4 import BeautifulSoup

from ..base import BaseCrawler, CrawlResult
from ..registry import registry


class ExampleCrawler(BaseCrawler):
    """示例实现：抓取公开网页标题。"""

    name = "example_policy"
    label = "demo"
    start_urls = ["https://example.com"]

    def parse(self, response) -> List[CrawlResult]:
        """解析页面标题并构造标准结果。"""

        soup = BeautifulSoup(response.text, "html.parser")
        title_tag = soup.find("title")
        title = title_tag.text.strip() if title_tag else "示例站点"
        result = CrawlResult(
            title=title,
            source_url=str(response.url),
            content_html=response.text,
            raw_content=response.text,
            metadata={
                "source_id": self.config.source_id,
                "fetched_at": datetime.utcnow().isoformat(),
            },
        )
        return [result]


registry.register(ExampleCrawler)
