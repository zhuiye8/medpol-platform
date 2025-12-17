"""通用爬虫基类，负责统一的请求、重试与结果结构。"""

from __future__ import annotations

import logging
import random
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

import httpx
from common.domain import ArticleCategory


logger = logging.getLogger("crawler.base")


@dataclass
class CrawlResult:
    """单条抓取结果的标准结构。"""

    title: str
    source_url: str
    content_html: str
    publish_time: Optional[datetime] = None
    raw_content: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> Dict[str, Any]:
        """转换为可序列化字典，方便下游透传。"""

        return {
            "title": self.title,
            "source_url": self.source_url,
            "content_html": self.content_html,
            "publish_time": self.publish_time.isoformat()
            if self.publish_time
            else None,
            "raw_content": self.raw_content,
            "metadata": self.metadata,
        }


@dataclass
class CrawlStats:
    """爬虫执行统计信息。"""

    total_fetched: int = 0  # 从网站获取的原始数量
    total_parsed: int = 0  # 成功解析的数量
    errors: List[str] = field(default_factory=list)  # 错误信息列表

    @property
    def has_errors(self) -> bool:
        """是否有错误发生。"""
        return len(self.errors) > 0

    def add_error(self, msg: str) -> None:
        """添加错误信息。"""
        self.errors.append(msg)


@dataclass
class CrawlerConfig:
    """运行时配置，可由数据库或 YAML 注入。"""

    source_id: str = ""
    start_urls: List[str] = field(default_factory=list)
    headers: Dict[str, str] = field(default_factory=dict)
    proxy: Optional[str] = None
    timeout: float = 20.0
    max_retries: int = 3
    retry_sleep: float = 2.0
    request_interval: float = 0.5
    meta: Dict[str, Any] = field(default_factory=dict)
    # 代理自动切换配置
    proxy_mode: str = "auto"  # auto | always | never
    fallback_proxy: Optional[str] = None  # 备用代理地址

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CrawlerConfig":
        """从字典构建配置，提供合理默认值。"""
        meta = dict(data.get("meta", {}))
        return cls(
            source_id=data.get("source_id", ""),
            start_urls=list(data.get("start_urls", [])),
            headers=dict(data.get("headers", {})),
            proxy=data.get("proxy") or data.get("proxies"),
            timeout=float(data.get("timeout", 20.0)),
            max_retries=int(data.get("max_retries", 3)),
            retry_sleep=float(data.get("retry_sleep", 2.0)),
            request_interval=float(data.get("request_interval", 0.5)),
            meta=meta,
            proxy_mode=meta.get("proxy_mode", "auto"),
            fallback_proxy=meta.get("fallback_proxy") or data.get("fallback_proxy"),
        )


class CrawlError(Exception):
    """统一的爬虫异常，方便上游捕获。"""


class ProxyTimeoutError(CrawlError):
    """连接超时错误，可能需要代理。"""


class BaseCrawler:
    """
    所有采集器的基类。

    - 负责请求、重试、节流
    - 定义 prepare -> crawl -> post_process 生命周期
    - 统一日志输出
    """

    name: str = "base"
    label: str = "base"
    category: ArticleCategory = ArticleCategory.FRONTIER
    description: str = "基础爬虫"
    start_urls: List[str] = []

    # 全局默认代理地址（可通过环境变量配置）
    DEFAULT_PROXY = "http://127.0.0.1:7897"

    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None:
        raw_config = CrawlerConfig.from_dict(config or {})
        if not raw_config.start_urls:
            raw_config.start_urls = list(self.start_urls)
        self.config = raw_config
        self.logger = logging.getLogger(f"crawler.{self.name}")
        # 代理状态追踪
        self._proxy_used = False  # 当前是否使用代理
        self._proxy_needed = None  # 本次运行是否需要代理（运行后更新）
        self._init_client(use_proxy=self._should_use_proxy_initially())

    def _should_use_proxy_initially(self) -> bool:
        """判断初始是否使用代理。"""
        mode = self.config.proxy_mode
        if mode == "always":
            return True
        if mode == "never":
            return False
        # auto 模式：检查 meta 中的历史记录
        return self.config.meta.get("proxy_needed", False)

    def _get_proxy_url(self) -> Optional[str]:
        """获取代理URL。"""
        return (
            self.config.proxy
            or self.config.fallback_proxy
            or self.config.meta.get("proxy_url")
            or self.DEFAULT_PROXY
        )

    def _init_client(self, use_proxy: bool = False) -> None:
        """初始化或重新初始化 HTTP 客户端。"""
        if hasattr(self, "_client") and self._client:
            try:
                self._client.close()
            except Exception:
                pass
        self._proxy_used = use_proxy
        proxy = self._get_proxy_url() if use_proxy else None
        self._client = httpx.Client(
            timeout=self.config.timeout,
            headers=self.config.headers,
            proxy=proxy,
            follow_redirects=True,
        )
        if use_proxy:
            self.logger.info("已启用代理: %s", proxy)

    # -------- 生命周期方法 --------
    def prepare(self) -> None:
        """子类可覆盖的初始化钩子，例如登录或注入 Cookie。"""

    def crawl(self) -> List[CrawlResult]:
        """默认遍历 start_urls，子类可完全覆盖。"""

        results: List[CrawlResult] = []
        for url in self.config.start_urls:
            self.logger.debug("开始抓取: %s", url)
            try:
                response = self.request("GET", url)
                parsed = self.parse(response)
                results.extend(parsed)
            except Exception as exc:  # pylint: disable=broad-except
                self.logger.exception("抓取失败 url=%s err=%s", url, exc)
            finally:
                self._throttle()
        return results

    def post_process(self, results: List[CrawlResult]) -> List[CrawlResult]:
        """统一输出清洗钩子，默认直接返回。"""

        return results

    def run(self) -> List[CrawlResult]:
        """调度入口：prepare -> crawl -> post_process。"""

        self.logger.info("启动爬虫: %s", self.name)
        self.prepare()
        results = self.crawl()
        cleaned = self.post_process(results)
        return cleaned

    # -------- 子类需要实现的方法 --------
    def parse(self, response: httpx.Response) -> List[CrawlResult]:  # pragma: no cover
        """解析响应生成 CrawlResult，留待子类实现。"""

        raise NotImplementedError("子类必须实现 parse 方法")

    # -------- 辅助方法 --------
    def request(
        self,
        method: str,
        url: str,
        *,
        params: Optional[Dict[str, Any]] = None,
        data: Optional[Any] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> httpx.Response:
        """统一的请求封装，内置重试与指数退避，支持代理自动切换。"""

        last_exc: Optional[Exception] = None
        proxy_switched = False

        for attempt in range(1, self.config.max_retries + 1):
            try:
                merged_headers = {**self.config.headers, **(headers or {})}
                response = self._client.request(
                    method=method,
                    url=url,
                    params=params,
                    data=data,
                    headers=merged_headers,
                )
                response.raise_for_status()
                # 请求成功，记录代理状态
                if self._proxy_needed is None:
                    self._proxy_needed = self._proxy_used
                return response
            except (httpx.TimeoutException, httpx.ConnectError) as exc:
                last_exc = exc
                is_timeout = isinstance(exc, httpx.TimeoutException)
                is_connect_error = isinstance(exc, httpx.ConnectError)
                self.logger.warning(
                    "请求失败(%s/%s) url=%s err=%s (timeout=%s, connect_error=%s)",
                    attempt,
                    self.config.max_retries,
                    url,
                    exc,
                    is_timeout,
                    is_connect_error,
                )
                # auto 模式下，超时/连接错误时尝试切换代理
                if self.config.proxy_mode == "auto" and not proxy_switched:
                    if not self._proxy_used:
                        self.logger.info("检测到连接问题，尝试启用代理...")
                        self._init_client(use_proxy=True)
                        proxy_switched = True
                        continue  # 不计入重试次数
                    elif self._proxy_used:
                        self.logger.info("代理模式下连接失败，尝试直连...")
                        self._init_client(use_proxy=False)
                        proxy_switched = True
                        continue
                if attempt < self.config.max_retries:
                    sleep_time = self.config.retry_sleep * attempt
                    time.sleep(sleep_time)
            except Exception as exc:  # pylint: disable=broad-except
                last_exc = exc
                self.logger.warning(
                    "请求失败(%s/%s) url=%s err=%s",
                    attempt,
                    self.config.max_retries,
                    url,
                    exc,
                )
                if attempt < self.config.max_retries:
                    sleep_time = self.config.retry_sleep * attempt
                    time.sleep(sleep_time)

        # 记录最终代理状态
        self._proxy_needed = self._proxy_used
        raise CrawlError(f"请求失败 url={url}") from last_exc

    def _throttle(self) -> None:
        """简单的节流控制，带随机抖动降低识别率。"""

        interval = self.config.request_interval
        if interval <= 0:
            return
        jitter = random.uniform(0, interval / 5)
        time.sleep(interval + jitter)

    def get_proxy_status(self) -> Dict[str, Any]:
        """获取代理使用状态，供上层保存到数据库。"""
        return {
            "proxy_mode": self.config.proxy_mode,
            "proxy_used": self._proxy_used,
            "proxy_needed": self._proxy_needed,
            "proxy_url": self._get_proxy_url() if self._proxy_used else None,
        }

    def close(self) -> None:
        """释放 HTTP 连接。"""

        self._client.close()

    def __enter__(self) -> "BaseCrawler":  # pragma: no cover
        return self

    def __exit__(self, exc_type, exc, tb) -> None:  # pragma: no cover
        self.close()

    def __del__(self) -> None:  # pragma: no cover
        try:
            self.close()
        except Exception:  # pragma: no cover - 防御性
            pass
