"""国家医保局 - 政策与动态（bidding: policy_updates）。"""

from __future__ import annotations

from datetime import datetime
from typing import Dict, List

from bs4 import BeautifulSoup

from common.domain import ArticleCategory
from ..base import BaseCrawler, CrawlResult
from ..registry import registry
from ..playwright_runner import fetch_html


class NhsaPolicyUpdatesCrawler(BaseCrawler):
    """医保招标 - 政策与动态。"""

    name = "nhsa_policy_updates"
    label = "医保招标-政策与动态"
    category = ArticleCategory.BIDDING
    start_url = "https://www.nhsa.gov.cn/col/col147/index.html"

    def __init__(self, config: Dict | None = None) -> None:
        super().__init__(config)
        meta = self.config.meta
        self.list_url = meta.get("list_url") or self.start_url
        self.max_pages = int(meta.get("max_pages", 1))
        self.page_size = int(meta.get("page_size", 20))
        # 增强的请求头配置
        self._client.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Accept-Encoding": "gzip, deflate",
            "Referer": "https://www.nhsa.gov.cn/",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
        })

    def crawl(self) -> List[CrawlResult]:
        entries = self._fetch_entries()
        results: List[CrawlResult] = []
        for entry in entries:
            try:
                results.append(self._build_result(entry))
            except Exception as exc:  # pylint: disable=broad-except
                self.logger.warning("解析政策与动态失败 url=%s err=%s", entry["url"], exc)
        self.logger.info("政策与动态采集 %s 条记录", len(results))
        return results

    def _fetch_entries(self) -> List[Dict[str, str]]:
        """简易分页，列表页为 col147 的分页接口."""
        all_entries: List[Dict[str, str]] = []

        for page in range(1, self.max_pages + 1):
            # 构造分页URL
            if page == 1:
                url = self.list_url
            else:
                # 第2页是 index_0.html, 第3页是 index_1.html
                url = self.list_url.replace("index.html", f"index_{page-1}.html")

            self.logger.info("获取医保局政策列表第 %d 页: %s", page, url)

            html = ""
            # 优先使用Playwright渲染（因为内容是JavaScript动态加载）
            try:
                extra_headers = {
                    "Referer": "https://www.nhsa.gov.cn/",
                }
                html = fetch_html(url, wait_selector="a[href*='art']", wait_time=8.0, extra_headers=extra_headers)
                self.logger.info("Playwright成功渲染，HTML长度: %d", len(html))
            except Exception as exc:
                self.logger.warning("Playwright渲染失败: %s，尝试HTTP降级", exc)
                # 降级：使用HTTP请求
                try:
                    response = self.request("GET", url)
                    html = response.text
                    self.logger.info("HTTP请求成功，HTML长度: %d", len(html))
                except Exception as http_exc:
                    self.logger.error("HTTP请求也失败 (page=%d): %s", page, http_exc)
                    continue

            if not html or len(html) < 500:
                self.logger.warning("第 %d 页HTML内容过短，跳过", page)
                continue

            soup = BeautifulSoup(html, "html.parser")

            # 尝试多个选择器（按优先级）
            selectors = [
                "div.dfyb-con ul li",  # Playwright渲染后的正确选择器
                "div.dfyb-con li",  # 简化版
                "div#contentlist ul li",  # HTTP备选1
                "div.list-content ul li",  # HTTP备选2
                "ul.list li",  # HTTP备选3
                "div[id*='content'] li",  # 通配符
            ]

            items = []
            for selector in selectors:
                items = soup.select(selector)
                if items:
                    self.logger.info("使用选择器 '%s' 找到 %d 个列表项", selector, len(items))
                    break

            if not items:
                self.logger.warning("第 %d 页未找到列表项，尝试的选择器: %s", page, selectors)
                continue

            # 解析列表项
            for li in items:
                a = li.find("a", href=True)
                if not a:
                    continue

                title = a.get_text(strip=True)
                href = a["href"]
                if not title or not href:
                    continue

                # 提取日期（可能在span或其他标签中）
                date_span = li.find("span") or li.find("td") or li.find("div", class_="date")
                publish_date = date_span.get_text(strip=True) if date_span else ""

                all_entries.append({
                    "title": title,
                    "url": self._make_absolute(href),
                    "publish_date": publish_date,
                })

            self.logger.info("第 %d 页采集到 %d 条记录，累计 %d 条", page, len(items), len(all_entries))

            if len(all_entries) >= self.page_size:
                break

        return all_entries[: self.page_size]

    def _build_result(self, entry: Dict[str, str]) -> CrawlResult:
        try:
            response = self.request("GET", entry["url"])
            detail_html = response.text
            self.logger.debug("详情页HTML长度: %d", len(detail_html))
        except Exception as exc:
            self.logger.error("获取详情页失败 url=%s: %s", entry["url"], exc)
            # 降级：使用标题作为内容
            content_html = f"<p>{entry['title']}</p>"
            publish_time = self._parse_publish_time(entry.get("publish_date"))
            return CrawlResult(
                title=entry["title"],
                source_url=entry["url"],
                content_html=content_html,
                publish_time=publish_time,
                metadata={"status": "policy_updates", "error": "fetch_failed"},
            )

        soup = BeautifulSoup(detail_html, "html.parser")

        # 尝试多个详情页选择器（按优先级）
        content_selectors = [
            "div#zoom",  # 当前选择器1
            "div.TRS_Editor",  # 当前选择器2
            "div#content",  # 当前选择器3
            "div.article-content",  # 备选1
            "div.main-content",  # 备选2
            "div.content",  # 备选3
            "div.article",  # 备选4
            "div[class*='content']",  # 通配符
        ]

        content = None
        used_selector = None
        for selector in content_selectors:
            content = soup.select_one(selector)
            if content:
                used_selector = selector
                break

        # 最后兜底：使用body
        if not content:
            content = soup.body
            used_selector = "body"

        if content:
            content_html = content.decode_contents()
            self.logger.debug("使用选择器 '%s' 提取内容，长度: %d", used_selector, len(content_html))
        else:
            content_html = f"<p>{entry['title']}</p>"
            self.logger.warning("未找到详情内容，使用标题作为内容")

        publish_time = self._parse_publish_time(entry.get("publish_date"))
        metadata = {
            "status": "policy_updates",
            "content_selector": used_selector,
        }

        return CrawlResult(
            title=entry["title"],
            source_url=entry["url"],
            content_html=content_html,
            publish_time=publish_time,
            metadata=metadata,
        )

    @staticmethod
    def _make_absolute(href: str) -> str:
        if href.startswith("http"):
            return href
        return "https://www.nhsa.gov.cn" + href

    @staticmethod
    def _parse_publish_time(value: str | None) -> datetime:
        if not value:
            return datetime.utcnow()
        for fmt in ("%Y-%m-%d", "%Y.%m.%d"):
            try:
                return datetime.strptime(value, fmt)
            except ValueError:
                continue
        return datetime.utcnow()


registry.register(NhsaPolicyUpdatesCrawler)
