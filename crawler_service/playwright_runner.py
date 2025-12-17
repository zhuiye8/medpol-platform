"""Playwright 渲染工具。"""

from __future__ import annotations

import asyncio
import logging
import os
from contextlib import asynccontextmanager
from typing import Optional

import httpx

# 尝试导入 playwright-stealth
try:
    from playwright_stealth import stealth_async
    STEALTH_AVAILABLE = True
except ImportError:
    STEALTH_AVAILABLE = False

logger = logging.getLogger("crawler.playwright")

# CDP 配置（优先使用远程 Chrome）
CDP_HTTP_URL = os.getenv("REMOTE_CDP_URL") or os.getenv("NMPA_REMOTE_CDP_URL") or "http://localhost:9222"


def _get_cdp_ws_url() -> Optional[str]:
    """从 CDP HTTP 端点获取 WebSocket URL。"""
    try:
        resp = httpx.get(f"{CDP_HTTP_URL}/json/version", timeout=3)
        if resp.status_code == 200:
            return resp.json().get("webSocketDebuggerUrl")
    except Exception:
        pass
    return None


def ensure_playwright():
    try:
        from playwright.async_api import async_playwright  # noqa: F401
    except ImportError as exc:
        raise RuntimeError(
            "未安装 Playwright，请运行 `pip install playwright` 并执行 `playwright install chromium`"
        ) from exc


@asynccontextmanager
async def _connect_cdp(ws_url: str):
    """连接到远程 CDP Chrome 实例。"""
    from playwright.async_api import async_playwright

    async with async_playwright() as p:
        browser = await p.chromium.connect_over_cdp(ws_url)
        try:
            yield browser
        finally:
            await browser.close()  # 关闭连接，不关闭浏览器


@asynccontextmanager
async def _launch_browser(headless: bool = True):
    from playwright.async_api import async_playwright

    async with async_playwright() as p:
        # 启动浏览器时添加反检测参数
        browser = await p.chromium.launch(
            headless=headless,
            args=[
                '--disable-blink-features=AutomationControlled',  # 禁用自动化检测
                '--no-sandbox',
                '--disable-dev-shm-usage',
                '--disable-web-security',  # 禁用Web安全策略
                '--disable-features=IsolateOrigins,site-per-process',  # 禁用站点隔离
                '--window-size=1920,1080',  # 设置窗口大小
                '--disable-gpu',  # 禁用GPU加速
                '--disable-setuid-sandbox',  # 禁用setuid沙箱
            ]
        )
        try:
            yield browser
        finally:
            await browser.close()


async def _fetch_with_browser(browser, url: str, wait_selector: Optional[str], wait_time: float, extra_headers: Optional[dict] = None, cookies: Optional[list] = None, use_cdp: bool = False) -> str:
    """使用浏览器获取页面内容的核心逻辑。"""
    # 获取或创建 context
    if use_cdp and browser.contexts:
        context = browser.contexts[0]
        page = await context.new_page()
    else:
        page = await browser.new_page(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1920, "height": 1080}
        )

    try:
        # 应用 Stealth 模式（如果可用，仅本地浏览器）
        if STEALTH_AVAILABLE and not use_cdp:
            logger.debug("启用 Playwright Stealth 模式")
            await stealth_async(page)

        # 注入Cookie（如果提供）
        if cookies:
            logger.debug(f"注入 {len(cookies)} 个 Cookie")
            await page.context.add_cookies(cookies)

        # 设置额外的请求头
        headers = {
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
            "Accept-Encoding": "gzip, deflate, br",
            "Cache-Control": "max-age=0",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
            "Upgrade-Insecure-Requests": "1",
        }
        if extra_headers:
            headers.update(extra_headers)
        await page.set_extra_http_headers(headers)

        # 访问页面
        await page.goto(url, wait_until="domcontentloaded", timeout=30000)

        # 等待页面完全加载
        try:
            await page.wait_for_load_state("networkidle", timeout=15000)
        except Exception:
            pass  # networkidle 超时不影响

        # 等待选择器
        if wait_selector:
            try:
                await page.wait_for_selector(wait_selector, timeout=wait_time * 1000)
            except Exception as e:
                logger.warning(f"等待选择器 {wait_selector} 超时: {e}")

        # 额外等待确保内容加载
        await page.wait_for_timeout(wait_time * 1000)

        # 获取页面内容
        content = await page.content()
        return content
    finally:
        await page.close()


async def _fetch_html_async(url: str, wait_selector: Optional[str], wait_time: float, extra_headers: Optional[dict] = None, cookies: Optional[list] = None) -> str:
    # 优先尝试 CDP 连接
    ws_url = _get_cdp_ws_url()
    if ws_url:
        try:
            logger.info(f"使用 CDP 连接获取: {url}")
            async with _connect_cdp(ws_url) as browser:
                return await _fetch_with_browser(browser, url, wait_selector, wait_time, extra_headers, cookies, use_cdp=True)
        except Exception as e:
            logger.warning(f"CDP 连接失败，回退到本地浏览器: {e}")

    # 回退到本地浏览器
    logger.info(f"使用本地 Playwright 获取: {url}")
    async with _launch_browser() as browser:
        return await _fetch_with_browser(browser, url, wait_selector, wait_time, extra_headers, cookies, use_cdp=False)


def fetch_html(url: str, wait_selector: Optional[str] = None, wait_time: float = 2.0, extra_headers: Optional[dict] = None, cookies: Optional[list] = None) -> str:
    """获取渲染后的 HTML。

    Args:
        url: 目标URL
        wait_selector: 等待的CSS选择器
        wait_time: 等待时间（秒）
        extra_headers: 额外的HTTP头（如 {"Referer": "https://..."} ）
        cookies: Cookie列表（格式：[{"name": "xxx", "value": "yyy", "domain": ".example.com", "path": "/"}]）

    Returns:
        渲染后的HTML内容
    """
    ensure_playwright()
    return asyncio.run(_fetch_html_async(url, wait_selector, wait_time, extra_headers, cookies))
