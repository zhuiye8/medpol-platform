"""爬虫注册中心，负责热插拔管理。"""

from __future__ import annotations

from typing import Dict, Type

from .base import BaseCrawler


class CrawlerRegistry:
    """维护爬虫映射，便于按名称实例化。"""

    def __init__(self) -> None:
        self._registry: Dict[str, Type[BaseCrawler]] = {}

    def register(self, crawler_cls: Type[BaseCrawler]) -> None:
        """按类的 name 属性登记，若重复会覆盖。"""

        self._registry[crawler_cls.name] = crawler_cls

    def create(self, name: str, config: Dict) -> BaseCrawler:
        """根据名称实例化爬虫."""

        crawler_cls = self._registry.get(name)
        if not crawler_cls:
            raise KeyError(f"未注册爬虫：{name}")
        return crawler_cls(config)

    def available(self) -> Dict[str, Type[BaseCrawler]]:
        """返回当前所有可用爬虫."""

        return dict(self._registry)


registry = CrawlerRegistry()
