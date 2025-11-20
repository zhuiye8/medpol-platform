"""Playwright 渲染工具。"""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from typing import Optional


def ensure_playwright():
    try:
        from playwright.async_api import async_playwright  # noqa: F401
    except ImportError as exc:
        raise RuntimeError(
            "未安装 Playwright，请运行 `pip install playwright` 并执行 `playwright install chromium`"
        ) from exc


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
            ]
        )
        try:
            yield browser
        finally:
            await browser.close()


async def _fetch_html_async(url: str, wait_selector: Optional[str], wait_time: float) -> str:
    async with _launch_browser() as browser:
        # 创建新页面并设置浏览器标识
        page = await browser.new_page(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1920, "height": 1080}
        )

        # 设置额外的请求头
        await page.set_extra_http_headers({
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        })

        # 移除 webdriver 标志
        await page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
        """)

        # 访问页面
        await page.goto(url, wait_until="networkidle", timeout=30000)

        # 等待选择器
        if wait_selector:
            try:
                await page.wait_for_selector(wait_selector, timeout=wait_time * 1000)
            except Exception as e:
                # 记录等待失败，但继续执行
                import logging
                logging.getLogger("crawler.playwright").warning(
                    f"等待选择器 {wait_selector} 超时: {e}"
                )

        # 额外等待确保内容加载
        await page.wait_for_timeout(wait_time * 1000)

        # 获取页面内容
        content = await page.content()
        await page.close()
        return content


def fetch_html(url: str, wait_selector: Optional[str] = None, wait_time: float = 2.0) -> str:
    """获取渲染后的 HTML。"""

    ensure_playwright()
    return asyncio.run(_fetch_html_async(url, wait_selector, wait_time))
