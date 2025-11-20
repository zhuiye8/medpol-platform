"""初始化来源配置：与当前爬虫目录一致的全量配置。"""

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
        print(f"[ok] 写入示例来源：{label}")
    except IntegrityError:
        session.rollback()
        print(f"[skip] {label} 已存在，跳过")


def main() -> None:
    session_factory = get_session_factory()
    with session_scope(session_factory) as session:
        # 前沿动态
        _insert(
            session,
            models.SourceORM(
                id="src_pharnex_frontier",
                name="药渡前沿",
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
                        "page_size": 5,
                    },
                },
            ),
            "药渡前沿",
        )

        # CDE/医保局
        _insert(
            session,
            models.SourceORM(
                id="src_nhsa_cde",
                name="国家医保局 - 政策与动态",
                label="CDE 动态",
                base_url="https://www.nhsa.gov.cn",
                category=ArticleCategory.CDE_TREND,
                is_active=True,
                meta={
                    "crawler_name": "nhsa_cde",
                    "crawler_meta": {
                        "max_pages": 1,
                        "page_size": 20,
                        "list_url": "https://www.nhsa.gov.cn/col/col147/index.html",
                    },
                },
            ),
            "国家医保局 - CDE 动态",
        )

        _insert(
            session,
            models.SourceORM(
                id="src_nhsa_bidding_national",
                name="国家医保局 - 国家集采",
                label="国家集采",
                base_url="https://www.nhsa.gov.cn",
                category=ArticleCategory.BIDDING,
                is_active=True,
                meta={
                    "crawler_name": "nhsa_bidding",
                    "crawler_meta": {
                        "max_pages": 1,
                        "page_size": 20,
                        "list_url": "https://www.nhsa.gov.cn/col/col187/index.html",
                        "source_label": "国家组织集中采购",
                    },
                },
            ),
            "国家医保局 - 国家集采",
        )

        _insert(
            session,
            models.SourceORM(
                id="src_nhsa_bidding_provincial",
                name="国家医保局 - 省级集采",
                label="省级集采",
                base_url="https://www.nhsa.gov.cn",
                category=ArticleCategory.BIDDING,
                is_active=True,
                meta={
                    "crawler_name": "nhsa_bidding",
                    "crawler_meta": {
                        "max_pages": 1,
                        "page_size": 20,
                        "list_url": "https://www.nhsa.gov.cn/col/col186/index.html",
                        "source_label": "省级集中采购",
                    },
                },
            ),
            "国家医保局 - 省级集采",
        )

        _insert(
            session,
            models.SourceORM(
                id="src_nhsa_industry",
                name="国家医保局 - 地方工作动态",
                label="行业动态",
                base_url="https://www.nhsa.gov.cn",
                category=ArticleCategory.INDUSTRY_TREND,
                is_active=True,
                meta={
                    "crawler_name": "nhsa_industry",
                    "crawler_meta": {
                        "max_pages": 1,
                        "page_size": 20,
                        "list_url": "https://www.nhsa.gov.cn/col/col193/index.html",
                    },
                },
            ),
            "国家医保局 - 行业动态",
        )

        # CDE 法规/制度
        _insert(
            session,
            models.SourceORM(
                id="src_cde_law",
                name="CDE 法律法规",
                label="法律法规",
                base_url="https://www.cde.org.cn",
                category=ArticleCategory.LAWS,
                is_active=True,
                meta={
                    "crawler_name": "cde_law",
                    "crawler_meta": {
                        "max_items": 50,
                        "list_url": "https://www.cde.org.cn/main/policy/listpage/9f9c74c73e0f8f56a8bfbc646055026d",
                    },
                },
            ),
            "CDE 法律法规",
        )

        _insert(
            session,
            models.SourceORM(
                id="src_cde_institution",
                name="CDE 中心制度",
                label="中心制度",
                base_url="https://www.cde.org.cn",
                category=ArticleCategory.INSTITUTION,
                is_active=True,
                meta={
                    "crawler_name": "cde_institution",
                    "crawler_meta": {
                        "max_items": 50,
                        "list_url": "https://www.cde.org.cn/main/policy/listpage/369ac7cfeb67c6000c33f85e6f374044",
                    },
                },
            ),
            "CDE 中心制度",
        )

        # 扬州项目申报
        _insert(
            session,
            models.SourceORM(
                id="src_project_apply_yangzhou",
                name="扬州项目申报",
                label="项目申报",
                base_url="https://kjj.yangzhou.gov.cn",
                category=ArticleCategory.PROJECT_APPLY,
                is_active=True,
                meta={
                    "crawler_name": "project_apply_yangzhou",
                    "crawler_meta": {
                        "max_items": 50,
                        "list_urls": [
                            "https://kjj.yangzhou.gov.cn/zfxxgk/fdzdgknr/tzgg/index.html",
                            "https://gxj.yangzhou.gov.cn/zfxxgk/fdzdgknr/tzgg/index.html",
                        ],
                    },
                },
            ),
            "扬州项目申报",
        )

        # 海外监管
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
                name="FDA 新闻",
                label="FDA 新闻",
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
            "FDA 新闻",
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

    print("[done] 示例来源写入完毕")


if __name__ == "__main__":
    main()
