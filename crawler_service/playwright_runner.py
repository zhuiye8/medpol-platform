"""Playwright 渲染工具。"""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from typing import Optional

# 尝试导入 playwright-stealth
try:
    from playwright_stealth import stealth_async
    STEALTH_AVAILABLE = True
except ImportError:
    STEALTH_AVAILABLE = False


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


async def _fetch_html_async(url: str, wait_selector: Optional[str], wait_time: float, extra_headers: Optional[dict] = None, cookies: Optional[list] = None) -> str:
    async with _launch_browser() as browser:
        # 创建新页面并设置浏览器标识
        page = await browser.new_page(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1920, "height": 1080}
        )

        # 应用 Stealth 模式（如果可用）
        if STEALTH_AVAILABLE:
            import logging
            logging.getLogger("crawler.playwright").info("启用 Playwright Stealth 模式")
            await stealth_async(page)

        # 注入Cookie（如果提供）
        if cookies:
            import logging
            logging.getLogger("crawler.playwright").info(f"注入 {len(cookies)} 个 Cookie")
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

        # 合并用户自定义的Headers
        if extra_headers:
            headers.update(extra_headers)

        await page.set_extra_http_headers(headers)

        # 增强的反检测脚本
        await page.add_init_script("""
            // 移除 webdriver 标志
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });

            // 伪造 plugins
            Object.defineProperty(navigator, 'plugins', {
                get: () => [1, 2, 3, 4, 5]
            });

            // 伪造 languages
            Object.defineProperty(navigator, 'languages', {
                get: () => ['zh-CN', 'zh', 'en-US', 'en']
            });

            // 伪造 platform
            Object.defineProperty(navigator, 'platform', {
                get: () => 'Win32'
            });

            // 添加 chrome 对象
            window.chrome = {
                runtime: {},
                loadTimes: function() {},
                csi: function() {},
                app: {}
            };

            // 伪造 permissions
            const originalQuery = window.navigator.permissions.query;
            window.navigator.permissions.query = (parameters) => (
                parameters.name === 'notifications' ?
                    Promise.resolve({ state: Notification.permission }) :
                    originalQuery(parameters)
            );

            // 覆盖 toString 方法
            Object.defineProperty(navigator.webdriver, 'toString', {
                value: () => 'undefined'
            });
        """)

        # 访问页面
        await page.goto(url, wait_until="domcontentloaded", timeout=30000)

        # 模拟真实用户行为：随机鼠标移动和滚动
        await page.mouse.move(100, 100)
        await page.wait_for_timeout(500)
        await page.mouse.move(200, 300)
        await page.wait_for_timeout(300)

        # 等待页面完全加载
        await page.wait_for_load_state("networkidle", timeout=15000)

        # 模拟滚动页面
        await page.evaluate("window.scrollTo(0, document.body.scrollHeight / 2)")
        await page.wait_for_timeout(500)
        await page.evaluate("window.scrollTo(0, 0)")

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
