"""CDE - 中心制度 列表爬虫."""

from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from common.domain import ArticleCategory
from ..base import BaseCrawler, CrawlResult
from ..playwright_runner import fetch_html
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
        # 支持翻页采集
        all_entries = self._fetch_all_pages()

        # 限制采集数量
        selected = all_entries[: self.max_items]
        results: List[CrawlResult] = []
        for entry in selected:
            try:
                results.append(self._build_result(entry))
            except Exception as exc:  # pylint: disable=broad-except
                self.logger.warning("解析中心制度失败 url=%s err=%s", entry["url"], exc)
        self.logger.info("中心制度采集 %s 条记录", len(results))
        return results

    def _fetch_listing_html(self) -> str:
        """使用 HTTP 请求获取列表页（兜底方法，不推荐，已由 _fetch_all_pages 替代）."""
        self.logger.info("使用 HTTP 获取中心制度列表页: %s", self.list_url)
        try:
            response = self.request("GET", self.list_url)
            response.encoding = response.charset_encoding or "utf-8"
            html = response.text
            self.logger.info("HTTP 请求成功，HTML 长度: %d", len(html))
            return html
        except Exception as exc:
            self.logger.error("HTTP 请求失败: %s", exc)
            return ""

    def _fetch_all_pages(self) -> List[Dict[str, str]]:
        """使用Playwright翻页采集所有需要的条目."""
        from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

        all_entries: List[Dict[str, str]] = []
        page_num = 1

        self.logger.info("开始翻页采集，目标数量: %d", self.max_items)

        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=[
                    '--disable-blink-features=AutomationControlled',
                    '--no-sandbox',
                    '--disable-dev-shm-usage',
                ]
            )
            page = browser.new_page(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                viewport={"width": 1920, "height": 1080}
            )

            # 移除webdriver标志
            page.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                });
            """)

            try:
                # 访问第一页（只等待 domcontentloaded，不等待 networkidle）
                page.goto(self.list_url, wait_until="domcontentloaded", timeout=30000)
                # 等待页面内容加载
                page.wait_for_timeout(2000)
                # 尝试等待选择器，但允许失败
                try:
                    page.wait_for_selector("div.news_item", timeout=5000)
                except:
                    self.logger.warning("等待 div.news_item 超时，继续尝试")

                while len(all_entries) < self.max_items:
                    # 提取当前页的HTML
                    html = page.content()
                    entries = self._extract_entries(html)

                    self.logger.info(
                        "第 %d 页：提取 %d 条记录，累计 %d 条",
                        page_num, len(entries), len(all_entries) + len(entries)
                    )

                    all_entries.extend(entries)

                    # 如果已经足够，停止翻页
                    if len(all_entries) >= self.max_items:
                        break

                    # 检查是否有下一页
                    try:
                        next_button = page.locator('a.layui-laypage-next:not(.layui-disabled)')
                        if next_button.count() == 0:
                            self.logger.info("没有更多页面，停止翻页")
                            break

                        # 点击下一页
                        self.logger.info("点击下一页...")
                        next_button.click()

                        # 等待页面更新
                        page.wait_for_timeout(2000)  # 等待2秒让页面加载
                        # 尝试等待选择器，但允许失败
                        try:
                            page.wait_for_selector("div.news_item", timeout=5000)
                        except:
                            self.logger.warning("翻页后等待选择器超时，继续")

                        page_num += 1

                    except PlaywrightTimeout:
                        self.logger.warning("翻页超时，停止采集")
                        break
                    except Exception as exc:
                        self.logger.warning("翻页失败: %s，停止采集", exc)
                        break

            except Exception as exc:
                self.logger.error("翻页采集失败: %s", exc)
                # 如果Playwright失败，尝试回退到单页模式
                if not all_entries:
                    html = self._fetch_listing_html()
                    all_entries = self._extract_entries(html)

            finally:
                browser.close()

        self.logger.info("翻页采集完成，共获取 %d 条记录", len(all_entries))
        return all_entries

    def _extract_entries(self, html: str) -> List[Dict[str, str]]:
        soup = BeautifulSoup(html, "html.parser")
        entries: List[Dict[str, str]] = []
        news_items = soup.select("div.news_item")
        self.logger.info("找到 %d 个 news_item 元素", len(news_items))
        if news_items:
            for item in news_items:
                date_box = item.select_one(".news_date")
                spans = date_box.find_all("span") if date_box else []
                yymm = spans[0].get_text(strip=True) if len(spans) > 0 else ""
                day = spans[1].get_text(strip=True) if len(spans) > 1 else ""
                title_el = item.select_one(".news_content_title")
                href_el = item.find("a", href=True)
                href = href_el["href"] if href_el else ""
                title = title_el.get_text(strip=True) if title_el else ""
                if not href or not title:
                    self.logger.debug("跳过条目: title=%r href=%r", title, href)
                    continue
                url = urljoin(self.list_url, href)
                publish_date = f"{yymm}.{day}" if yymm and day else ""
                entries.append(
                    {
                        "title": title,
                        "url": url,
                        "publish_date": publish_date,
                        "article_id": self._extract_article_id(url),
                    }
                )
            return entries
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
        if entries:
            self.logger.info("从旧版结构解析出 %d 条中心制度", len(entries))
        else:
            self.logger.warning("未能从任何结构解析出中心制度条目")
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
        """获取文章详情页HTML，遇到反爬时使用Playwright."""
        self.logger.debug("获取详情页: %s", url)
        response = self.request("GET", url)
        response.encoding = response.charset_encoding or "utf-8"
        html = response.text

        self.logger.debug("详情页状态码: %d, HTML长度: %d", response.status_code, len(html))

        # 检测是否遇到反爬：202状态码或内容过短（<500字节）
        if response.status_code == 202 or len(html) < 500 or "_$" in html[:200]:
            self.logger.warning(
                "详情页疑似反爬拦截 (状态码=%d, 长度=%d)，使用 Playwright 重新获取",
                response.status_code, len(html)
            )
            try:
                html = fetch_html(url, wait_selector="div#content", wait_time=2.0)
                self.logger.info("Playwright 获取详情页成功，HTML长度: %d", len(html))
            except Exception as exc:
                self.logger.error("Playwright 获取详情页失败: %s", exc)
                # 如果Playwright也失败，返回原始HTML

        return html

    @staticmethod
    def _extract_article_id(url: str) -> str:
        slug = url.rstrip("/").split("/")[-1]
        return slug.rsplit(".", 1)[0]

    @staticmethod
    def _parse_publish_time(value: str | None) -> datetime:
        if not value:
            return datetime.utcnow()
        for fmt in ("%Y-%m-%d", "%Y.%m.%d", "%Y.%m %d"):
            try:
                return datetime.strptime(value, fmt)
            except ValueError:
                continue
        return datetime.utcnow()


registry.register(CDEInstitutionCrawler)
