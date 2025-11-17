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

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CrawlerConfig":
        """从字典构建配置，提供合理默认值。"""

        return cls(
            source_id=data.get("source_id", ""),
            start_urls=list(data.get("start_urls", [])),
            headers=dict(data.get("headers", {})),
            proxy=data.get("proxy") or data.get("proxies"),
            timeout=float(data.get("timeout", 20.0)),
            max_retries=int(data.get("max_retries", 3)),
            retry_sleep=float(data.get("retry_sleep", 2.0)),
            request_interval=float(data.get("request_interval", 0.5)),
            meta=dict(data.get("meta", {})),
        )


class CrawlError(Exception):
    """统一的爬虫异常，方便上游捕获。"""


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

    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None:
        raw_config = CrawlerConfig.from_dict(config or {})
        if not raw_config.start_urls:
            raw_config.start_urls = list(self.start_urls)
        self.config = raw_config
        self.logger = logging.getLogger(f"crawler.{self.name}")
        self._client = httpx.Client(
            timeout=self.config.timeout,
            headers=self.config.headers,
            proxy=self.config.proxy,
            follow_redirects=True,
        )

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
        """统一的请求封装，内置重试与指数退避。"""

        last_exc: Optional[Exception] = None
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
                return response
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
        raise CrawlError(f"请求失败 url={url}") from last_exc

    def _throttle(self) -> None:
        """简单的节流控制，带随机抖动降低识别率。"""

        interval = self.config.request_interval
        if interval <= 0:
            return
        jitter = random.uniform(0, interval / 5)
        time.sleep(interval + jitter)

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
