"""从数据库或静态配置中加载爬虫运行参数。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List

from sqlalchemy.orm import Session

from common.persistence.repository import SourceRepository
from common.persistence import models


@dataclass
class CrawlerRuntimeConfig:
    source_id: str
    source_name: str
    crawler_name: str
    meta: Dict


def load_from_db(session: Session) -> List[CrawlerRuntimeConfig]:
    """读取所有 active sources，并过滤出包含 crawler_name 的源。"""

    repo = SourceRepository(session)
    configs: List[CrawlerRuntimeConfig] = []
    for source in repo.list_active():
        crawler_name = (source.meta or {}).get("crawler_name")
        if not crawler_name:
            continue
        configs.append(
            CrawlerRuntimeConfig(
                source_id=source.id,
                source_name=source.name,
                crawler_name=crawler_name,
                meta=(source.meta or {}).get("crawler_meta", {}),
            )
        )
    return configs


def iter_configs(
    session: Session | None = None,
    *,
    fallback: Iterable[CrawlerRuntimeConfig] | None = None,
) -> List[CrawlerRuntimeConfig]:
    """优先从数据库加载，若无则返回回退配置。"""

    if session:
        configs = load_from_db(session)
        if configs:
            return configs
    return list(fallback or [])
