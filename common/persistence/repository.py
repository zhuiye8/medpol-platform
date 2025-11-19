"""简单的仓储封装，供服务层调用。"""

from __future__ import annotations

from datetime import datetime
from typing import Iterable, List, Optional

from sqlalchemy import func, select, case
from sqlalchemy.orm import Session
from common.domain import ArticleCategory

from . import models


class SourceRepository:
    """来源数据访问。"""

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

    def add(self, source: models.SourceORM) -> None:
        self.session.add(source)


class ArticleRepository:
    """文章数据访问。"""

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
    ) -> tuple[List[models.ArticleORM], int]:
        stmt = select(models.ArticleORM).order_by(models.ArticleORM.publish_time.desc())
        if category:
            db_value = category.value if isinstance(category, ArticleCategory) else category
            stmt = stmt.where(models.ArticleORM.category == db_value)
        total = self.session.scalar(
            select(func.count()).select_from(stmt.subquery())  # type: ignore[arg-type]
        )
        stmt = stmt.offset((page - 1) * page_size).limit(page_size)
        return list(self.session.scalars(stmt)), int(total or 0)

    def list_without_summary(self, limit: int = 10) -> List[models.ArticleORM]:
        stmt = (
            select(models.ArticleORM)
            .where(models.ArticleORM.summary.is_(None))
            .order_by(models.ArticleORM.publish_time.desc())
            .limit(limit)
        )
        return list(self.session.scalars(stmt))

    def list_without_translation(self, limit: int = 10) -> List[models.ArticleORM]:
        stmt = (
            select(models.ArticleORM)
            .where(
                models.ArticleORM.translated_content_html.is_(None),
                models.ArticleORM.original_source_language.is_not(None),
                models.ArticleORM.original_source_language != "zh",
            )
            .order_by(models.ArticleORM.publish_time.desc())
            .limit(limit)
        )
        return list(self.session.scalars(stmt))

    def list_without_analysis(self, limit: int = 10) -> List[models.ArticleORM]:
        stmt = (
            select(models.ArticleORM)
            .where(models.ArticleORM.ai_analysis.is_(None))
            .order_by(models.ArticleORM.publish_time.desc())
            .limit(limit)
        )
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
                models.ArticleORM.apply_status,
                func.count().label("cnt"),
                func.sum(year_case).label("year_cnt"),
            )
            .where(models.ArticleORM.category == ArticleCategory.PROJECT_APPLY.value)
            .group_by(models.ArticleORM.apply_status)
        )
        rows = list(self.session.execute(base))
        result = {
            "pending_total": 0,
            "submitted_total": 0,
            "pending_year": 0,
            "submitted_year": 0,
        }
        for status, cnt, year_cnt in rows:
            if status == "pending":
                result["pending_total"] = int(cnt or 0)
                result["pending_year"] = int(year_cnt or 0)
            elif status == "submitted":
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


class AIResultRepository:
    """AI 结果数据访问。"""

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
    """调度任务仓储。"""

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


class FinanceRecordRepository:
    """财务数据仓储"""

    def __init__(self, session: Session) -> None:
        self.session = session

    def get(self, record_id: str) -> Optional[models.FinanceRecordORM]:
        return self.session.get(models.FinanceRecordORM, record_id)

    def add(self, record: models.FinanceRecordORM) -> None:
        self.session.add(record)


class FinanceSyncLogRepository:
    """财务同步日志仓储"""

    def __init__(self, session: Session) -> None:
        self.session = session

    def get(self, log_id: str) -> Optional[models.FinanceSyncLogORM]:
        return self.session.get(models.FinanceSyncLogORM, log_id)

    def add(self, log: models.FinanceSyncLogORM) -> None:
        self.session.add(log)
