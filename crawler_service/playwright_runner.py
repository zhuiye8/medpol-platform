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
        browser = await p.chromium.launch(headless=headless)
        try:
            yield browser
        finally:
            await browser.close()


async def _fetch_html_async(url: str, wait_selector: Optional[str], wait_time: float) -> str:
    async with _launch_browser() as browser:
        page = await browser.new_page()
        await page.goto(url, wait_until="networkidle")
        if wait_selector:
            try:
                await page.wait_for_selector(wait_selector, timeout=wait_time * 1000)
            except Exception:
                pass
        await page.wait_for_timeout(wait_time * 1000)
        content = await page.content()
        await page.close()
        return content


def fetch_html(url: str, wait_selector: Optional[str] = None, wait_time: float = 2.0) -> str:
    """获取渲染后的 HTML。"""

    ensure_playwright()
    return asyncio.run(_fetch_html_async(url, wait_selector, wait_time))
