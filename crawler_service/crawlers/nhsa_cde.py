"""国家医保局 - CDE 动态（CDE 官网新闻，status=operations 固定）"""

from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Optional

from playwright.sync_api import sync_playwright

from common.domain import ArticleCategory
from ..base import BaseCrawler, CrawlResult
from ..registry import registry


class NHSACDECrawler(BaseCrawler):
    """直接抓取 CDE 官网接口 /news/getWorkList，固定 status=operations。"""

    name = "nhsa_cde"
    label = "国家医保局-CDE 动态"
    source_name = "国家医保局"
    category = ArticleCategory.CDE_TREND
    list_url = "https://www.cde.org.cn/main/news/listpage/3cc45b396497b598341ce3af000490e5"
    api_url = "https://www.cde.org.cn/news/getWorkList"

    def __init__(self, config: Dict | None = None) -> None:
        super().__init__(config)
        meta = self.config.meta
        self.max_items = int(meta.get("max_items", 20))
        self.status = "operations"
        self.remote_cdp = meta.get("remote_cdp_url")

    def crawl(self) -> List[CrawlResult]:
        records = self._fetch_records()
        results: List[CrawlResult] = []
        for rec in records[: self.max_items]:
            try:
                results.append(self._build_result(rec))
            except Exception as exc:  # pylint: disable=broad-except
                self.logger.warning("CDE 动态解析失败 id=%s err=%s", rec.get("newsIdCode"), exc)
        self.logger.info("CDE 动态采集 %s 条记录", len(results))
        return results

    def _fetch_records(self) -> List[dict]:
        """通过 Playwright 监听接口响应获取 JSON 数据。"""

        def capture_with(browser) -> List[dict]:
            target_body: Optional[bytes] = None

            def _on_resp(resp):
                nonlocal target_body
                if target_body is None and "getWorkList" in resp.url:
                    try:
                        target_body = resp.body()
                    except Exception:
                        target_body = None

            context = browser.contexts[0] if browser.contexts else browser.new_context(
                user_agent=self._client.headers.get(
                    "User-Agent",
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36",
                ),
                locale="zh-CN",
                extra_http_headers={"Referer": "https://www.cde.org.cn/"},
            )
            page = context.new_page()
            page.on("response", _on_resp)
            page.goto(self.list_url, wait_until="domcontentloaded", timeout=20000)
            try:
                page.wait_for_load_state("networkidle", timeout=8000)
            except Exception:
                pass
            page.wait_for_timeout(2000)
            page.close()
            if target_body:
                try:
                    import json

                    txt = target_body.decode("utf-8", errors="replace")
                    data = json.loads(txt)
                    return data.get("data", {}).get("records", []) or []
                except Exception as exc:  # pylint: disable=broad-except
                    self.logger.warning("解析接口 JSON 失败: %s", exc)
            return []

        if self.remote_cdp:
            with sync_playwright() as p:
                browser = p.chromium.connect_over_cdp(self.remote_cdp)
                records = capture_with(browser)
                browser.close()
                return records

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            records = capture_with(browser)
            browser.close()
            return records

    def _build_result(self, rec: dict) -> CrawlResult:
        title = rec.get("title") or "CDE 动态"
        publish_date = rec.get("publishDate") or ""
        content = rec.get("content") or title
        news_id = rec.get("newsIdCode") or ""
        # 构造一个可点击的伪 URL，避免判重冲突
        source_url = f"{self.list_url}#newsId={news_id}" if news_id else self.list_url
        publish_time = self._parse_publish_time(publish_date)
        return CrawlResult(
            title=title,
            source_url=source_url,
            content_html=f"<p>{content}</p>",
            publish_time=publish_time,
            metadata={"status": self.status, "news_id": news_id},
        )

    @staticmethod
    def _parse_publish_time(value: str | None) -> datetime:
        if not value:
            return datetime.utcnow()
        for fmt in ("%Y-%m-%d", "%Y.%m.%d", "%Y.%m %d", "%Y%m%d"):
            try:
                return datetime.strptime(value, fmt)
            except ValueError:
                continue
        return datetime.utcnow()


registry.register(NHSACDECrawler)
