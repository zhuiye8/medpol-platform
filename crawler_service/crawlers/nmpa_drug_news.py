"""国家药监局 - 药品监管要闻（industry_trend，无子分类）"""

from __future__ import annotations

import re
import time
from datetime import datetime, timedelta
from http.cookies import SimpleCookie
from typing import Dict, Iterable, List, Optional, Tuple
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

from common.domain import ArticleCategory
from ..base import BaseCrawler, CrawlResult
from ..registry import registry

# 详情页路径形如 /yaowen/ypjgyw/<subdir>/20251118172544130.html（可能带 ../）
DETAIL_RE = re.compile(r"yaowen/ypjgyw/.+/\d+\.html", re.IGNORECASE)

try:
    from curl_cffi import requests as cffi_requests  # type: ignore

    HAVE_CURL_CFFI = True
except Exception:  # pragma: no cover - optional
    HAVE_CURL_CFFI = False

try:
    from playwright.sync_api import sync_playwright  # type: ignore

    HAVE_PLAYWRIGHT = True
except Exception:  # pragma: no cover - optional
    HAVE_PLAYWRIGHT = False


class NMPADrugNewsCrawler(BaseCrawler):
    """采集 NMPA 药品监管要闻（industry_trend，无子分类）"""

    name = "nmpa_drug_news"
    label = "NMPA 药品监管要闻"
    source_name = "国家药监局"
    category = ArticleCategory.INDUSTRY_TREND
    start_urls = [
        "https://www.nmpa.gov.cn/yaowen/ypjgyw/index.html",
    ]

    MAX_PAGES = 50
    TIME_BOUND_DAYS = 120
    REQUEST_TIMEOUT = 20

    def __init__(self, config: Dict | None = None) -> None:
        super().__init__(config)
        meta = self.config.meta
        self.list_urls = meta.get("list_urls") or self.start_urls
        self.max_pages = int(meta.get("max_pages", self.MAX_PAGES))
        self.page_size = int(meta.get("page_size", 20))
        self.time_bound_days = int(meta.get("time_bound_days", self.TIME_BOUND_DAYS))
        self.custom_cookies = self._parse_cookies(meta.get("cookies") or meta.get("cookie"))
        self.remote_cdp = meta.get("remote_cdp_url") or None

    def crawl(self) -> List[CrawlResult]:
        results: List[CrawlResult] = []
        time_bound = datetime.utcnow() - timedelta(days=self.time_bound_days)

        for base_url in self.list_urls:
            seen = set()
            for page_url in self._iter_pages(base_url):
                html = self._get_html(page_url, referer=self._parent_ref(base_url), wait_selector="div.list ul li")
                if not html:
                    break
                items = self._parse_list(html, page_url)
                if not items:
                    break

                stop_time = False
                for url, title_guess, pub_guess in items:
                    if url in seen:
                        continue
                    seen.add(url)
                    if pub_guess and pub_guess < time_bound:
                        stop_time = True
                        continue
                    detail_html = self._get_html(url, referer=page_url, wait_selector="div.TRS_Editor,div#zoom,div.article-content")
                    if not detail_html:
                        self.logger.warning("详情抓取失败 %s", url)
                        continue
                    try:
                        results.append(self._parse_detail(detail_html, url, pub_guess, title_guess))
                    except Exception as exc:  # pylint: disable=broad-except
                        self.logger.warning("详情解析失败 %s err=%s", url, exc)
                    if len(results) >= self.page_size:
                        stop_time = True
                        break
                    time.sleep(0.8)  # 降速以降低 412 风险
                if stop_time:
                    break

        self.logger.info("药品监管要闻采集 %s 条记录", len(results))
        return results

    # ---- HTTP helpers ----
    def _get_html(self, url: str, referer: Optional[str] = None, wait_selector: Optional[str] = None) -> Optional[str]:
        # 自动检测本地 CDP 服务
        if not self.remote_cdp:
            from ..playwright_runner import _get_cdp_ws_url
            auto_cdp = _get_cdp_ws_url()
            if auto_cdp:
                self.remote_cdp = auto_cdp
                self.logger.info("自动检测到本地 CDP: %s", auto_cdp[:50])

        # 0) 复用远程已登录浏览器（CDP）
        if HAVE_PLAYWRIGHT and self.remote_cdp:
            try:
                with sync_playwright() as p:
                    browser = p.chromium.connect_over_cdp(self.remote_cdp)
                    context = browser.contexts[0] if browser.contexts else browser.new_context()
                    page = context.new_page()

                    # 预热：先访问首页获取 cookie，避免 412
                    page.goto("https://www.nmpa.gov.cn/", wait_until="domcontentloaded", timeout=30000)
                    page.wait_for_timeout(2000)

                    body_bytes: Optional[bytes] = None

                    def _on_resp(resp):
                        nonlocal body_bytes
                        if body_bytes is None and resp.url.startswith(url):
                            try:
                                body_bytes = resp.body()
                            except Exception:
                                body_bytes = None

                    page.on("response", _on_resp)
                    resp = page.goto(url, wait_until="domcontentloaded", timeout=30000)
                    if resp and resp.status != 200:
                        self.logger.warning("CDP 目标状态码 %s，等待 JS 渲染", resp.status)
                    try:
                        page.wait_for_load_state("networkidle", timeout=15000)
                    except Exception:
                        pass
                    # NMPA 网站需要额外等待 JS 渲染
                    page.wait_for_timeout(3000)
                    if wait_selector:
                        try:
                            page.wait_for_selector(wait_selector, timeout=10000)
                        except Exception:
                            pass

                    html = None
                    if body_bytes and len(body_bytes) > 500:
                        html = self._decode_body(body_bytes)
                    if not html or len(html) < 500:
                        html = page.content()

                    page.close()
                    browser.close()  # 关闭连接，不关浏览器
                    if html and len(html) > 200:
                        return html
            except Exception as exc:  # pylint: disable=broad-except
                self.logger.warning("CDP 获取失败 url=%s err=%s", url, exc)

        # 1) Playwright 自启浏览器
        if HAVE_PLAYWRIGHT:
            try:
                with sync_playwright() as p:
                    browser = p.chromium.launch(
                        headless=True,
                        args=["--disable-blink-features=AutomationControlled", "--no-sandbox"],
                    )
                    context = browser.new_context(
                        user_agent=(
                            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                            "AppleWebKit/537.36 (KHTML, like Gecko) "
                            "Chrome/120.0.0.0 Safari/537.36"
                        ),
                        locale="zh-CN",
                        extra_http_headers=self._browser_like_headers(referer),
                    )
                    if self.custom_cookies:
                        cookie_objs = [
                            {"name": k, "value": v, "domain": ".nmpa.gov.cn", "path": "/"}
                            for k, v in self.custom_cookies.items()
                        ]
                        context.add_cookies(cookie_objs)
                    page = context.new_page()
                    # 预热：访问首页获取 cookie，等待足够时间
                    page.goto("https://www.nmpa.gov.cn/", wait_until="domcontentloaded", timeout=30000)
                    time.sleep(2)
                    # 访问目标页
                    page.goto(url, wait_until="domcontentloaded", timeout=30000)
                    try:
                        page.wait_for_load_state("networkidle", timeout=15000)
                    except Exception:
                        pass
                    time.sleep(2)  # NMPA 需要额外等待 JS 渲染
                    if wait_selector:
                        try:
                            page.wait_for_selector(wait_selector, timeout=5000)
                        except Exception:
                            pass
                    html = page.content()
                    context.close()
                    browser.close()
                    if html and len(html) > 500:
                        return html
            except Exception as exc:  # pylint: disable=broad-except
                self.logger.warning("Playwright 获取失败 url=%s err=%s", url, exc)

        # 2) curl_cffi Chrome 拟态
        if HAVE_CURL_CFFI:
            try:
                sess = getattr(self, "_cffi_sess", None)
                if not sess:
                    sess = cffi_requests.Session()
                    sess.impersonate = "chrome120"
                    self._cffi_sess = sess
                    if self.custom_cookies:
                        for k, v in self.custom_cookies.items():
                            sess.cookies.set(k, v, domain=".nmpa.gov.cn")
                    sess.get("https://www.nmpa.gov.cn/", headers=self._browser_like_headers(None), timeout=self.REQUEST_TIMEOUT)
                resp = sess.get(url, headers=self._browser_like_headers(referer), timeout=self.REQUEST_TIMEOUT)
                if resp.status_code == 200 and resp.text:
                    return resp.text
                if resp.status_code == 412:
                    self.logger.warning("curl_cffi 返回 412 url=%s", url)
            except Exception as exc:  # pylint: disable=broad-except
                self.logger.warning("curl_cffi 获取失败 url=%s err=%s", url, exc)

        # 3) httpx 兜底
        try:
            client = getattr(self, "_httpx_client", None)
            if not client:
                client = httpx.Client(
                    http2=True,
                    headers=self._basic_headers(),
                    follow_redirects=True,
                    timeout=self.REQUEST_TIMEOUT,
                )
                self._httpx_client = client
                if self.custom_cookies:
                    client.cookies.update(self.custom_cookies)
                try:
                    client.get("https://www.nmpa.gov.cn/", headers={"Referer": "https://www.nmpa.gov.cn/"})
                except Exception:
                    pass
            resp = client.get(url, headers={"Referer": referer or "https://www.nmpa.gov.cn/"})
            if resp.status_code == 200 and resp.text:
                return resp.text
        except Exception as exc:  # pylint: disable=broad-except
            self.logger.warning("httpx 获取失败 url=%s err=%s", url, exc)
        return None

    def _basic_headers(self) -> dict:
        return {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
            "Connection": "keep-alive",
        }

    def _browser_like_headers(self, referer: Optional[str]) -> dict:
        headers = {
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Site": "same-origin",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Dest": "document",
            "sec-ch-ua": '"Chromium";v="120", "Not=A?Brand";v="99"',
            "sec-ch-ua-platform": '"Windows"',
            "sec-ch-ua-mobile": "?0",
        }
        if referer:
            headers["Referer"] = referer
        return headers

    # ---- Parsing ----
    def _iter_pages(self, base_index: str):
        if base_index.endswith("index.html"):
            yield base_index
        else:
            yield urljoin(base_index.rstrip("/") + "/", "index.html")
        for i in range(1, self.max_pages):
            yield base_index.replace("index.html", f"index_{i}.html")

    def _parse_list(self, html: str, base_url: str) -> List[Tuple[str, Optional[str], Optional[datetime]]]:
        soup = BeautifulSoup(html, "html.parser")
        results: List[Tuple[str, Optional[str], Optional[datetime]]] = []
        for a in soup.select("a[href]"):
            href = a.get("href") or ""
            if not DETAIL_RE.search(href):
                continue
            abs_url = self._normalize_url(urljoin(base_url, href))
            title = a.get("title") or a.get_text(" ", strip=True) or None
            publish_time = self._extract_date_from_list_item(a)
            results.append((abs_url, title, publish_time))
        seen = set()
        unique: List[Tuple[str, Optional[str], Optional[datetime]]] = []
        for item in results:
            if item[0] in seen:
                continue
            seen.add(item[0])
            unique.append(item)
        return unique

    def _parse_detail(
        self,
        html: str,
        url: str,
        publish_time: Optional[datetime],
        title_guess: Optional[str],
    ) -> CrawlResult:
        soup = BeautifulSoup(html, "html.parser")
        title_node = self._pick_first(soup, ["h1.title", "div.title h1", "h1", "div.xl_tit h2"])
        title = title_node.get_text(strip=True) if title_node else (title_guess or "国家药监局要闻")

        meta_node = self._pick_first(soup, ["div.info", "div.title > span", "div.xl_tit > p", "div.source", "div.pubTime"])
        pub_text = meta_node.get_text(" ", strip=True) if meta_node else ""
        if not publish_time:
            publish_time = self._parse_date(pub_text)

        content_node = self._pick_first(
            soup,
            [
                "div.TRS_Editor",
                "div#zoom",
                "div.article-content",
                "div.conTxt",
                "div#detailContent",
                "div.content",
                "div.article",
                "div.wenzhang",
            ],
        )
        content_node = content_node or soup.body or soup
        for tag in content_node.find_all(["script", "style", "iframe"]):
            tag.decompose()
        content_html = str(content_node)

        raw_content = content_node.get_text("\n", strip=True)
        attachments: List[str] = []
        for a in content_node.select("a[href]"):
            href = a.get("href") or ""
            if re.search(r"\.(pdf|docx?|xlsx?|zip)$", href, re.I):
                attachments.append(urljoin(url, href))

        metadata = {
            "source_id": self.config.source_id,
            "fetched_at": datetime.utcnow().isoformat(),
            "publish_time": publish_time.isoformat() if publish_time else None,
            "attachments": attachments,
        }
        return CrawlResult(
            title=title,
            source_url=url,
            content_html=content_html,
            publish_time=publish_time or datetime.utcnow(),
            raw_content=raw_content,
            metadata=metadata,
        )

    @staticmethod
    def _pick_first(soup: BeautifulSoup, selectors: Iterable[str]):
        for css in selectors:
            node = soup.select_one(css)
            if node:
                return node
        return None

    @staticmethod
    def _normalize_url(url: str) -> str:
        u = urlparse(url)
        if not u.scheme:
            url = urljoin("https://www.nmpa.gov.cn/", url.lstrip("/"))
        return url.replace("/directory/web/nmpa/", "/")

    @staticmethod
    def _parent_ref(url: str) -> str:
        if url.endswith("index.html"):
            return url.rsplit("/", 1)[0] + "/"
        return "https://www.nmpa.gov.cn/"

    @staticmethod
    def _parse_date(value: str | None) -> Optional[datetime]:
        if not value:
            return None
        for fmt in ("%Y-%m-%d", "%Y/%m/%d"):
            try:
                return datetime.strptime(value.strip(), fmt)
            except ValueError:
                continue
        m = re.search(r"(20\d{2}-\d{1,2}-\d{1,2})", value or "")
        if m:
            try:
                return datetime.strptime(m.group(1), "%Y-%m-%d")
            except ValueError:
                return None
        return None

    @staticmethod
    def _extract_date_from_list_item(a_tag) -> Optional[datetime]:
        li = a_tag.find_parent("li")
        if li:
            for node in li.select("span, em, i"):
                text = node.get_text(" ", strip=True)
                m = re.search(r"\d{4}[-/.]\d{1,2}[-/.]\d{1,2}", text)
                if m:
                    try:
                        cleaned = re.sub(r"[./]", "-", m.group(0))
                        return datetime.strptime(cleaned, "%Y-%m-%d")
                    except ValueError:
                        continue
        href = a_tag.get("href") or ""
        m = re.search(r"/(\d{8})\d*\.html$", href)
        if m:
            try:
                return datetime.strptime(m.group(1), "%Y%m%d")
            except ValueError:
                return None
        return None

    @staticmethod
    def _parse_cookies(raw: Optional[str]) -> Dict[str, str]:
        if not raw or not isinstance(raw, str):
            return {}
        jar = SimpleCookie()
        jar.load(raw)
        return {k: morsel.value for k, morsel in jar.items()}

    @staticmethod
    def _decode_body(body: bytes) -> Optional[str]:
        if not body:
            return None

        def _is_clean(txt: str) -> bool:
            bad = txt.count("\ufffd")
            return bad == 0 or bad / max(len(txt), 1) < 0.01

        try:
            txt = body.decode("utf-8")
            if _is_clean(txt):
                return txt
        except Exception:
            txt = None

        for enc in ("gb18030", "gbk"):
            try:
                txt2 = body.decode(enc)
                if _is_clean(txt2):
                    return txt2
            except Exception:
                continue

        try:
            return body.decode("utf-8", errors="replace")
        except Exception:
            return None


registry.register(NMPADrugNewsCrawler)
