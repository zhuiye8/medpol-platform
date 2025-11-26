"""简单调度器：运行注册的爬虫并推送到 formatter。"""

from __future__ import annotations

import logging
import os
import pkgutil
from importlib import import_module
from typing import Dict, List, Optional

from sqlalchemy.orm import Session

from common.domain import RawArticle
from common.persistence.database import get_session_factory, session_scope

from .config_loader import CrawlerRuntimeConfig, iter_configs
from .dispatcher import FormatterPublisher, dispatch_results
from .registry import registry


logger = logging.getLogger("crawler.scheduler")
publisher = FormatterPublisher()
DEFAULT_CONFIGS = [
    # 药渡前沿
    CrawlerRuntimeConfig(
        source_id="src_pharnex_frontier",
        source_name="药渡前沿",
        crawler_name="pharnex_frontier",
        meta={"category_slug": "shiye", "abbreviation": "qy", "max_pages": 1, "page_size": 5},
    ),
    # 医保局
    CrawlerRuntimeConfig(
        source_id="src_nhsa_policy_updates",
        source_name="国家医保局-政策与动态",
        crawler_name="nhsa_policy_updates",
        meta={
            "max_pages": 1,
            "page_size": 20,
            "list_url": "https://www.nhsa.gov.cn/col/col147/index.html",
        },
    ),
    CrawlerRuntimeConfig(
        source_id="src_nhsa_cde",
        source_name="国家医保局-CDE 动态",
        crawler_name="nhsa_cde",
        meta={
            "max_items": 20,
            "list_url": "https://www.cde.org.cn/main/news/listpage/3cc45b396497b598341ce3af000490e5",
            "status": "operations",
            "remote_cdp_url": os.getenv("NMPA_REMOTE_CDP_URL") or os.getenv("REMOTE_CDP_URL"),
        },
    ),
    CrawlerRuntimeConfig(
        source_id="src_nhsa_bidding_national",
        source_name="国家医保局-国家集采",
        crawler_name="nhsa_bidding",
        meta={
            "max_pages": 1,
            "page_size": 20,
            "list_url": "https://www.nhsa.gov.cn/col/col187/index.html",
            "source_label": "国家组织集中采购",
        },
    ),
    CrawlerRuntimeConfig(
        source_id="src_nhsa_bidding_provincial",
        source_name="国家医保局-省级集采",
        crawler_name="nhsa_bidding",
        meta={
            "max_pages": 1,
            "page_size": 20,
            "list_url": "https://www.nhsa.gov.cn/col/col186/index.html",
            "source_label": "省级集中采购",
        },
    ),
    # CDE 法规/制度/受理品种
    CrawlerRuntimeConfig(
        source_id="src_cde_law",
        source_name="CDE 法律法规",
        crawler_name="cde_law",
        meta={
            "max_items": 50,
            "list_url": "https://www.cde.org.cn/main/policy/listpage/9f9c74c73e0f8f56a8bfbc646055026d",
        },
    ),
    CrawlerRuntimeConfig(
        source_id="src_cde_institution",
        source_name="CDE 中心制度",
        crawler_name="cde_institution",
        meta={
            "max_items": 50,
            "list_url": "https://www.cde.org.cn/main/policy/listpage/369ac7cfeb67c6000c33f85e6f374044",
        },
    ),
    CrawlerRuntimeConfig(
        source_id="src_cde_accepted_products",
        source_name="CDE 受理品种信息",
        crawler_name="cde_accepted_products",
        meta={
            "max_items": 20,
            "list_url": "https://www.cde.org.cn/main/xxgk/listpage/9f9c74c73e0f8f56a8bfbc646055026d",
        },
    ),
    # 扬州项目申报
    CrawlerRuntimeConfig(
        source_id="src_project_apply_yangzhou",
        source_name="扬州项目申报",
        crawler_name="project_apply_yangzhou",
        meta={
            "max_items": 50,
            "list_urls": [
                "https://kjj.yangzhou.gov.cn/zfxxgk/fdzdgknr/tzgg/index.html",
                "https://gxj.yangzhou.gov.cn/zfxxgk/fdzdgknr/tzgg/index.html",
            ],
        },
    ),
    # 海外监管
    CrawlerRuntimeConfig(
        source_id="src_fda_guidance",
        source_name="FDA 新增指南",
        crawler_name="fda_guidance",
        meta={"max_items": 20},
    ),
    CrawlerRuntimeConfig(
        source_id="src_fda_press",
        source_name="FDA 新闻",
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
    # NMPA 药品监管要闻（行业动态-受理品种）
    CrawlerRuntimeConfig(
        source_id="src_nmpa_drug_news",
        source_name="NMPA 药品监管要闻",
        crawler_name="nmpa_drug_news",
        meta={
            "max_pages": 1,
            "page_size": 20,
            "list_url": "https://www.nmpa.gov.cn/yaowen/ypjgyw/index.html",
            "remote_cdp_url": os.getenv("NMPA_REMOTE_CDP_URL") or os.getenv("REMOTE_CDP_URL"),
        },
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


def _apply_quick_meta(meta: Dict) -> Dict:
    """快速检测模式下，强制每个爬虫最多抓 1 条，避免放量。"""

    new_meta = dict(meta or {})
    new_meta["page_size"] = 1
    new_meta["max_pages"] = 1
    new_meta["max_items"] = 1
    new_meta["max_records"] = 1
    return new_meta


def run_active_crawlers(session: Session | None = None, quick_mode: bool = False) -> int:
    """运行所有可用配置，返回总条数；单个爬虫失败时记录错误并继续。"""

    _load_crawlers()
    configs = iter_configs(session=session, fallback=DEFAULT_CONFIGS)
    total = 0
    for cfg in configs:
        runtime_cfg = cfg
        if quick_mode:
            runtime_cfg = CrawlerRuntimeConfig(
                source_id=cfg.source_id,
                source_name=cfg.source_name,
                crawler_name=cfg.crawler_name,
                meta=_apply_quick_meta(cfg.meta),
            )
        try:
            articles = run_crawler_config(runtime_cfg)
            total += len(articles)
        except KeyError as exc:
            logger.error("跳过未注册的爬虫: %s", exc)
            continue
        except Exception:  # pylint: disable=broad-except
            logger.exception("Crawler 运行失败，已跳过: %s", runtime_cfg.crawler_name)
            continue
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
