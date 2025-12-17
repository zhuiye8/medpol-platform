"""Lightweight repository helpers for core data access."""

from __future__ import annotations

from datetime import datetime
from typing import Iterable, List, Optional

from sqlalchemy import func, select, case, or_
from sqlalchemy.orm import Session
from common.domain import ArticleCategory

from . import models


class SourceRepository:
    """Source access helpers."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def get_by_id(self, source_id: str) -> Optional[models.SourceORM]:
        return self.session.get(models.SourceORM, source_id)

    def get_by_name(self, name: str) -> Optional[models.SourceORM]:
        stmt = select(models.SourceORM).where(models.SourceORM.name == name)
        return self.session.scalars(stmt).first()

    def list_active(self) -> List[models.SourceORM]:
        stmt = select(models.SourceORM).where(models.SourceORM.is_active.is_(True))
        return list(self.session.scalars(stmt))

    def list_all(self) -> List[models.SourceORM]:
        stmt = select(models.SourceORM).order_by(models.SourceORM.name)
        return list(self.session.scalars(stmt))

    def add(self, source: models.SourceORM) -> None:
        self.session.add(source)

    def get_by_crawler_name(self, crawler_name: str) -> Optional[models.SourceORM]:
        stmt = select(models.SourceORM).where(
            models.SourceORM.meta["crawler_name"].as_string() == crawler_name  # type: ignore[index]
        )
        return self.session.scalars(stmt).first()

    def get_or_create_default(
        self,
        *,
        crawler_name: str,
        category: str,
        label: str,
        base_url: str | None = None,
    ) -> models.SourceORM:
        # 先通过 ID 查找
        expected_id = f"src_{crawler_name}"
        existing = self.get_by_id(expected_id)
        if existing:
            return existing
        # 再通过 meta.crawler_name 查找
        existing = self.get_by_crawler_name(crawler_name)
        if existing:
            return existing
        # 都没找到，创建新的
        source = models.SourceORM(
            id=expected_id,
            name=f"{label}",
            label=label,
            base_url=base_url if base_url is not None else f"https://{crawler_name}.example.com",
            category=category,
            is_active=True,
            meta={"crawler_name": crawler_name},
        )
        self.session.add(source)
        self.session.flush()
        return source


class ArticleRepository:
    """Article access helpers."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def get_by_id(self, article_id: str) -> Optional[models.ArticleORM]:
        return self.session.get(models.ArticleORM, article_id)

    def list_recent(
        self,
        *,
        limit: int = 20,
        category: Optional[ArticleCategory] = None,
    ) -> List[models.ArticleORM]:
        stmt = select(models.ArticleORM).order_by(models.ArticleORM.publish_time.desc())
        if category:
            db_value = category.value if isinstance(category, ArticleCategory) else category
            stmt = stmt.where(models.ArticleORM.category == db_value)
        stmt = stmt.limit(limit)
        return list(self.session.scalars(stmt))

    def paginate(
        self,
        *,
        page: int = 1,
        page_size: int = 20,
        category: Optional[ArticleCategory] = None,
        status: Optional[str] = None,
        q: Optional[str] = None,
    ) -> tuple[List[models.ArticleORM], int]:
        stmt = select(models.ArticleORM).order_by(models.ArticleORM.publish_time.desc())
        if category:
            db_value = category.value if isinstance(category, ArticleCategory) else category
            stmt = stmt.where(models.ArticleORM.category == db_value)
        if status:
            stmt = stmt.where(models.ArticleORM.status == status)
        if q:
            pattern = f"%{q}%"
            stmt = stmt.where(
                or_(
                    models.ArticleORM.title.ilike(pattern),
                    models.ArticleORM.translated_title.ilike(pattern),
                    models.ArticleORM.content_text.ilike(pattern),
                )
            )
        total = self.session.scalar(select(func.count()).select_from(stmt.subquery()))
        stmt = stmt.offset((page - 1) * page_size).limit(page_size)
        return list(self.session.scalars(stmt)), int(total or 0)

    def list_without_summary(self, limit: int | None = 10) -> List[models.ArticleORM]:
        stmt = (
            select(models.ArticleORM)
            .where(models.ArticleORM.summary.is_(None))
            .order_by(models.ArticleORM.publish_time.desc())
        )
        if limit:
            stmt = stmt.limit(limit)
        return list(self.session.scalars(stmt))

    def list_without_translation(self, limit: int | None = 10) -> List[models.ArticleORM]:
        stmt = (
            select(models.ArticleORM)
            .where(
                models.ArticleORM.translated_content_html.is_(None),
                models.ArticleORM.original_source_language.is_not(None),
                models.ArticleORM.original_source_language != "zh",
            )
            .order_by(models.ArticleORM.publish_time.desc())
        )
        if limit:
            stmt = stmt.limit(limit)
        return list(self.session.scalars(stmt))

    def list_without_title_translation(self, limit: int | None = 10) -> List[models.ArticleORM]:
        stmt = (
            select(models.ArticleORM)
            .where(models.ArticleORM.translated_title.is_(None))
            .order_by(models.ArticleORM.publish_time.desc())
        )
        if limit:
            stmt = stmt.limit(limit)
        return list(self.session.scalars(stmt))

    def list_without_analysis(self, limit: int | None = 10) -> List[models.ArticleORM]:
        stmt = (
            select(models.ArticleORM)
            .where(models.ArticleORM.ai_analysis.is_(None))
            .order_by(models.ArticleORM.publish_time.desc())
        )
        if limit:
            stmt = stmt.limit(limit)
        return list(self.session.scalars(stmt))

    def count_by_category(self, category: ArticleCategory) -> int:
        db_value = category.value if isinstance(category, ArticleCategory) else category
        stmt = select(func.count()).select_from(models.ArticleORM).where(
            models.ArticleORM.category == db_value
        )
        return int(self.session.scalar(stmt) or 0)

    def count_year_category(self, category: ArticleCategory, year: int) -> int:
        db_value = category.value if isinstance(category, ArticleCategory) else category
        stmt = (
            select(func.count())
            .select_from(models.ArticleORM)
            .where(
                models.ArticleORM.category == db_value,
                func.extract("year", models.ArticleORM.publish_time) == year,
            )
        )
        return int(self.session.scalar(stmt) or 0)

    def count_positive_policy(self, category: ArticleCategory) -> int:
        db_value = category.value if isinstance(category, ArticleCategory) else category
        stmt = (
            select(func.count())
            .select_from(models.ArticleORM)
            .where(
                models.ArticleORM.category == db_value,
                models.ArticleORM.is_positive_policy.is_(True),
            )
        )
        return int(self.session.scalar(stmt) or 0)

    def count_project_apply_stats(self, year: int) -> dict:
        year_case = case(
            (func.extract("year", models.ArticleORM.publish_time) == year, 1),
            else_=0,
        )
        base = (
            select(
                models.ArticleORM.status,
                func.count().label("cnt"),
                func.sum(year_case).label("year_cnt"),
            )
            .where(models.ArticleORM.category == ArticleCategory.PROJECT_APPLY.value)
            .group_by(models.ArticleORM.status)
        )
        rows = list(self.session.execute(base))
        result = {
            "pending_total": 0,
            "submitted_total": 0,
            "pending_year": 0,
            "submitted_year": 0,
        }
        for status_value, cnt, year_cnt in rows:
            if status_value == "pending":
                result["pending_total"] = int(cnt or 0)
                result["pending_year"] = int(year_cnt or 0)
            elif status_value == "submitted":
                result["submitted_total"] = int(cnt or 0)
                result["submitted_year"] = int(year_cnt or 0)
        return result

    def add(self, article: models.ArticleORM) -> None:
        self.session.add(article)

    def bulk_add(self, articles: Iterable[models.ArticleORM]) -> None:
        self.session.add_all(list(articles))

    def update_summary(self, article_id: str, summary: str) -> None:
        article = self.get_by_id(article_id)
        if article:
            article.summary = summary

    def get_existing_urls(self, urls: List[str]) -> set[str]:
        """批量检查哪些 source_url 已存在于数据库中。"""
        if not urls:
            return set()
        stmt = select(models.ArticleORM.source_url).where(
            models.ArticleORM.source_url.in_(urls)
        )
        return set(self.session.scalars(stmt))


class AIResultRepository:
    """AI result access helpers."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, result: models.AIResultORM) -> None:
        self.session.add(result)

    def list_by_article(self, article_id: str) -> List[models.AIResultORM]:
        stmt = select(models.AIResultORM).where(models.AIResultORM.article_id == article_id)
        return list(self.session.scalars(stmt))

    def latest_by_article_task(self, article_id: str, task_type: str) -> Optional[models.AIResultORM]:
        stmt = (
            select(models.AIResultORM)
            .where(
                models.AIResultORM.article_id == article_id,
                models.AIResultORM.task_type == task_type,
            )
            .order_by(models.AIResultORM.created_at.desc())
            .limit(1)
        )
        return self.session.scalars(stmt).first()


class CrawlerJobRepository:
    """Crawler job access helpers."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def list(self, enabled: Optional[bool] = None) -> List[models.CrawlerJobORM]:
        stmt = select(models.CrawlerJobORM).order_by(models.CrawlerJobORM.created_at.desc())
        if enabled is not None:
            stmt = stmt.where(models.CrawlerJobORM.enabled.is_(enabled))
        return list(self.session.scalars(stmt))

    def list_due_jobs(self, now: datetime) -> List[models.CrawlerJobORM]:
        stmt = (
            select(models.CrawlerJobORM)
            .where(
                models.CrawlerJobORM.enabled.is_(True),
                models.CrawlerJobORM.job_type == "scheduled",
                models.CrawlerJobORM.next_run_at.is_not(None),
                models.CrawlerJobORM.next_run_at <= now,
            )
            .order_by(models.CrawlerJobORM.next_run_at.asc())
        )
        return list(self.session.scalars(stmt))

    def get(self, job_id: str) -> Optional[models.CrawlerJobORM]:
        return self.session.get(models.CrawlerJobORM, job_id)

    def add(self, job: models.CrawlerJobORM) -> None:
        self.session.add(job)

    def delete(self, job: models.CrawlerJobORM) -> None:
        self.session.delete(job)

    def create_run(self, run: models.CrawlerJobRunORM) -> None:
        self.session.add(run)

    def list_runs(self, job_id: str, limit: int = 50) -> List[models.CrawlerJobRunORM]:
        stmt = (
            select(models.CrawlerJobRunORM)
            .where(models.CrawlerJobRunORM.job_id == job_id)
            .order_by(models.CrawlerJobRunORM.started_at.desc())
            .limit(limit)
        )
        return list(self.session.scalars(stmt))

    def list_pending_runs(self) -> List[models.CrawlerJobRunORM]:
        stmt = select(models.CrawlerJobRunORM).where(models.CrawlerJobRunORM.status == "pending")
        return list(self.session.scalars(stmt))

    def get_run(self, run_id: str) -> Optional[models.CrawlerJobRunORM]:
        return self.session.get(models.CrawlerJobRunORM, run_id)


class PipelineRunRepository:
    """Pipeline run access helpers."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def add_run(self, run: models.CrawlerPipelineRunORM) -> None:
        self.session.add(run)

    def add_detail(self, detail: models.CrawlerPipelineRunDetailORM) -> None:
        self.session.add(detail)

    def get_run(self, run_id: str) -> Optional[models.CrawlerPipelineRunORM]:
        return self.session.get(models.CrawlerPipelineRunORM, run_id)

    def list_runs(
        self,
        limit: int = 50,
        offset: int = 0,
        run_type: str | None = None,
        status: str | None = None,
    ) -> List[models.CrawlerPipelineRunORM]:
        stmt = select(models.CrawlerPipelineRunORM).order_by(models.CrawlerPipelineRunORM.started_at.desc())
        if run_type:
            stmt = stmt.where(models.CrawlerPipelineRunORM.run_type == run_type)
        if status:
            stmt = stmt.where(models.CrawlerPipelineRunORM.status == status)
        stmt = stmt.offset(offset).limit(limit)
        return list(self.session.scalars(stmt))

    def count_runs(self, run_type: str | None = None, status: str | None = None) -> int:
        stmt = select(func.count()).select_from(models.CrawlerPipelineRunORM)
        if run_type:
            stmt = stmt.where(models.CrawlerPipelineRunORM.run_type == run_type)
        if status:
            stmt = stmt.where(models.CrawlerPipelineRunORM.status == status)
        return int(self.session.scalar(stmt) or 0)

    def list_details(self, run_id: str) -> List[models.CrawlerPipelineRunDetailORM]:
        stmt = (
            select(models.CrawlerPipelineRunDetailORM)
            .where(models.CrawlerPipelineRunDetailORM.run_id == run_id)
            .order_by(models.CrawlerPipelineRunDetailORM.started_at.desc())
        )
        return list(self.session.scalars(stmt))

    def get_detail(self, detail_id: str) -> Optional[models.CrawlerPipelineRunDetailORM]:
        return self.session.get(models.CrawlerPipelineRunDetailORM, detail_id)


class FinanceRecordRepository:
    """Finance record access."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def get(self, record_id: str) -> Optional[models.FinanceRecordORM]:
        return self.session.get(models.FinanceRecordORM, record_id)

    def add(self, record: models.FinanceRecordORM) -> None:
        self.session.add(record)


class FinanceSyncLogRepository:
    """Finance sync log access."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def get(self, log_id: str) -> Optional[models.FinanceSyncLogORM]:
        return self.session.get(models.FinanceSyncLogORM, log_id)

    def add(self, log: models.FinanceSyncLogORM) -> None:
        self.session.add(log)
