"""初始化示例来源配置。"""

from __future__ import annotations

import sys
from pathlib import Path

from sqlalchemy.exc import IntegrityError

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from common.persistence.database import get_session_factory, session_scope  # noqa: E402
from common.persistence import models  # noqa: E402
from common.domain import ArticleCategory  # noqa: E402


def _insert(session, source: models.SourceORM, label: str) -> None:
    """安全写入来源，若存在则跳过。"""

    session.add(source)
    try:
        session.flush()
        print(f"✅ 已写入示例来源：{label}")
    except IntegrityError:
        session.rollback()
        print(f"ℹ️ {label} 已存在，跳过")


def main() -> None:
    session_factory = get_session_factory()
    with session_scope(session_factory) as session:
        _insert(
            session,
            models.SourceORM(
                id="src_pharnex_frontier",
                name="药渡云前沿动态",
                label="前沿动态",
                base_url="https://www.pharnexcloud.com",
                category=ArticleCategory.FRONTIER,
                is_active=True,
                meta={
                    "crawler_name": "pharnex_frontier",
                    "crawler_meta": {
                        "category_slug": "shiye",
                        "abbreviation": "qy",
                        "max_pages": 1,
                        "page_size": 10,
                    },
                },
            ),
            "药渡云前沿动态（API）",
        )

        _insert(
            session,
            models.SourceORM(
                id="src_pharnex_frontier_playwright",
                name="药渡云前沿动态（渲染）",
                label="前沿动态渲染",
                base_url="https://www.pharnexcloud.com",
                category=ArticleCategory.FRONTIER,
                is_active=True,
                meta={
                    "crawler_name": "pharnex_frontier_playwright",
                    "crawler_meta": {
                        "category_slug": "shiye",
                        "abbreviation": "qy",
                        "max_pages": 1,
                        "page_size": 5,
                    },
                },
            ),
            "药渡云前沿动态（渲染）",
        )

        _insert(
            session,
            models.SourceORM(
                id="src_nhsa_domestic",
                name="国家医疗保障局",
                label="国内政策与动态",
                base_url="https://www.nhsa.gov.cn",
                category=ArticleCategory.DOMESTIC_POLICY,
                is_active=True,
                meta={
                    "crawler_name": "nhsa_domestic",
                    "crawler_meta": {
                        "max_pages": 1,
                        "page_size": 20,
                        "list_url": "https://www.nhsa.gov.cn/col/col147/index.html",
                    },
                },
            ),
            "国家医疗保障局",
        )

        _insert(
            session,
            models.SourceORM(
                id="src_fda_guidance",
                name="FDA 新增指南",
                label="FDA 指南",
                base_url="https://www.fda.gov",
                category=ArticleCategory.FDA_POLICY,
                is_active=True,
                meta={
                    "crawler_name": "fda_guidance",
                    "crawler_meta": {
                        "max_items": 30,
                    },
                },
            ),
            "FDA 新增指南",
        )

        _insert(
            session,
            models.SourceORM(
                id="src_fda_press",
                name="FDA 新闻稿",
                label="FDA 新闻稿",
                base_url="https://www.fda.gov",
                category=ArticleCategory.FDA_POLICY,
                is_active=True,
                meta={
                    "crawler_name": "fda_press",
                    "crawler_meta": {
                        "max_pages": 3,
                        "max_items": 30,
                    },
                },
            ),
            "FDA 新闻稿",
        )

        _insert(
            session,
            models.SourceORM(
                id="src_ema_whats_new",
                name="EMA What's New",
                label="EMA 政策动态",
                base_url="https://www.ema.europa.eu",
                category=ArticleCategory.EMA_POLICY,
                is_active=True,
                meta={
                    "crawler_name": "ema_whats_new",
                    "crawler_meta": {
                        "max_pages": 2,
                        "max_items": 30,
                    },
                },
            ),
            "EMA What's New",
        )

        _insert(
            session,
            models.SourceORM(
                id="src_pmda_whats_new",
                name="PMDA What's New",
                label="PMDA 政策动态",
                base_url="https://www.pmda.go.jp",
                category=ArticleCategory.PMDA_POLICY,
                is_active=True,
                meta={
                    "crawler_name": "pmda_whats_new",
                    "crawler_meta": {
                        "max_items": 30,
                    },
                },
            ),
            "PMDA What's New",
        )


if __name__ == "__main__":
    main()
