"""简单调度器：运行注册的爬虫并推送到 formatter。"""

from __future__ import annotations

import logging
from typing import Dict, List, Optional

import os
import pkgutil
from importlib import import_module
from typing import List

from sqlalchemy.orm import Session

from common.domain import RawArticle
from common.persistence.database import get_session_factory, session_scope

from .config_loader import CrawlerRuntimeConfig, iter_configs
from .dispatcher import FormatterPublisher, dispatch_results
from .registry import registry


logger = logging.getLogger("crawler.scheduler")
publisher = FormatterPublisher()
DEFAULT_CONFIGS = [
    CrawlerRuntimeConfig(
        source_id="pharnex_frontier",
        source_name="药渡云",
        crawler_name="pharnex_frontier",
        meta={"category_slug": "shiye", "abbreviation": "qy", "max_pages": 1, "page_size": 5},
    ),
    CrawlerRuntimeConfig(
        source_id="pharnex_frontier_playwright",
        source_name="药渡云渲染",
        crawler_name="pharnex_frontier_playwright",
        meta={"category_slug": "shiye", "abbreviation": "qy", "max_pages": 1, "page_size": 5},
    ),
    CrawlerRuntimeConfig(
        source_id="src_nhsa_domestic",
        source_name="国家医疗保障局",
        crawler_name="nhsa_domestic",
        meta={"max_pages": 1, "page_size": 20},
    ),
    CrawlerRuntimeConfig(
        source_id="src_fda_guidance",
        source_name="FDA 新增指南",
        crawler_name="fda_guidance",
        meta={"max_items": 20},
    ),
    CrawlerRuntimeConfig(
        source_id="src_fda_press",
        source_name="FDA 新闻稿",
        crawler_name="fda_press",
        meta={"max_pages": 2, "max_items": 20},
    ),
    CrawlerRuntimeConfig(
        source_id="src_ema_whats_new",
        source_name="EMA What's New",
        crawler_name="ema_whats_new",
        meta={"max_pages": 1, "max_items": 20},
    ),
    CrawlerRuntimeConfig(
        source_id="src_pmda_whats_new",
        source_name="PMDA What's New",
        crawler_name="pmda_whats_new",
        meta={"max_items": 20},
    ),
]


def _load_crawlers() -> None:
    """自动导入 crawlers 包下的所有模块，确保完成注册。"""

    import crawler_service.crawlers  # pylint: disable=import-outside-toplevel

    package = crawler_service.crawlers
    prefix = package.__name__ + "."
    for _, module_name, _ in pkgutil.iter_modules(package.__path__, prefix):
        import_module(module_name)


def list_available_crawlers() -> List[Dict[str, str]]:
    """返回全部已注册爬虫的元信息。"""

    _load_crawlers()
    items: List[Dict[str, str]] = []
    for name, crawler_cls in registry.available().items():
        category = getattr(crawler_cls, "category", "")
        category_value = getattr(category, "value", category)
        items.append(
            {
                "name": name,
                "label": getattr(crawler_cls, "label", name),
                "description": getattr(crawler_cls, "description", ""),
                "category": category_value,
            }
        )
    return items


def run_crawler(crawler_name: str, config: Optional[Dict] = None) -> List[RawArticle]:
    """运行指定爬虫，将结果推送到 formatter，并返回 RawArticle 列表。"""

    _load_crawlers()
    crawler = registry.create(crawler_name, config or {})
    results = crawler.run()
    articles = dispatch_results(crawler, results, publisher)
    logger.info("Crawler=%s 推送 %s 条记录", crawler_name, len(articles))
    return articles


def run_crawler_config(runtime_config: CrawlerRuntimeConfig) -> List[RawArticle]:
    """根据来源配置运行爬虫。"""

    crawler_config = {
        "source_id": runtime_config.source_id,
        "meta": runtime_config.meta,
    }
    crawler = registry.create(runtime_config.crawler_name, crawler_config)
    setattr(crawler, "source_name", runtime_config.source_name)
    results = crawler.run()
    articles = dispatch_results(crawler, results, publisher)
    logger.info(
        "Source=%s Crawler=%s 推送 %s 条记录",
        runtime_config.source_name,
        runtime_config.crawler_name,
        len(articles),
    )
    return articles


def run_active_crawlers(session: Session | None = None) -> int:
    """运行所有可用配置，返回总条数。"""

    _load_crawlers()
    configs = iter_configs(session=session, fallback=DEFAULT_CONFIGS)
    total = 0
    for cfg in configs:
        articles = run_crawler_config(cfg)
        total += len(articles)
    return total


if __name__ == "__main__":
    database_url = os.getenv("DATABASE_URL")
    if database_url:
        session_factory = get_session_factory()
        with session_scope(session_factory) as session:
            total = run_active_crawlers(session=session)
    else:
        total = run_active_crawlers()
    print(f"已采集 {total} 条文章")
