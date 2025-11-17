"""SQLAlchemy ORM 模型定义。"""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from common.domain import ArticleCategory


ArticleCategoryEnum = SAEnum(
    ArticleCategory,
    name="article_category",
    values_callable=lambda enum_cls: [member.value for member in enum_cls],
)


class Base(DeclarativeBase):
    """所有 ORM 的基类。"""


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow
    )


class SourceORM(TimestampMixin, Base):
    """数据来源表。"""

    __tablename__ = "sources"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(128), unique=True)
    label: Mapped[Optional[str]] = mapped_column(String(64))
    base_url: Mapped[str] = mapped_column(String(255))
    category: Mapped[ArticleCategory] = mapped_column(ArticleCategoryEnum, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    meta: Mapped[dict] = mapped_column(JSON, default=dict)

    articles: Mapped[List["ArticleORM"]] = relationship(
        back_populates="source", cascade="all, delete-orphan"
    )


class ArticleORM(TimestampMixin, Base):
    """规范化后的文章。"""

    __tablename__ = "articles"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    source_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("sources.id", ondelete="CASCADE"),
    )
    title: Mapped[str] = mapped_column(String(512))
    content_html: Mapped[str] = mapped_column(Text)
    content_text: Mapped[str] = mapped_column(Text)
    publish_time: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    source_name: Mapped[str] = mapped_column(String(128))
    source_url: Mapped[str] = mapped_column(String(512))
    category: Mapped[ArticleCategory] = mapped_column(ArticleCategoryEnum, nullable=False)
    tags: Mapped[list] = mapped_column(JSON, default=list)
    crawl_time: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    content_source: Mapped[str] = mapped_column(String(32))
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    ai_analysis: Mapped[Optional[dict]] = mapped_column(JSON(none_as_null=True), nullable=True)
    translated_content: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    translated_content_html: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    original_source_language: Mapped[Optional[str]] = mapped_column(String(16))

    source: Mapped["SourceORM"] = relationship(back_populates="articles")
    ai_results: Mapped[List["AIResultORM"]] = relationship(
        back_populates="article", cascade="all, delete-orphan"
    )


class AIResultORM(TimestampMixin, Base):
    """AI 处理结果。"""

    __tablename__ = "ai_results"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    article_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("articles.id", ondelete="CASCADE")
    )
    task_type: Mapped[str] = mapped_column(String(32))
    provider: Mapped[str] = mapped_column(String(32))
    model: Mapped[str] = mapped_column(String(64))
    output: Mapped[str] = mapped_column(Text)
    latency_ms: Mapped[int] = mapped_column(Integer)

    article: Mapped["ArticleORM"] = relationship(back_populates="ai_results")


class CrawlerJobORM(TimestampMixin, Base):
    """调度任务配置。"""

    __tablename__ = "crawler_jobs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(128))
    crawler_name: Mapped[str] = mapped_column(String(128))
    source_id: Mapped[str] = mapped_column(String(36), ForeignKey("sources.id"))
    job_type: Mapped[str] = mapped_column(String(16))
    schedule_cron: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    interval_minutes: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    next_run_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    last_run_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    last_status: Mapped[Optional[str]] = mapped_column(String(16))

    source: Mapped["SourceORM"] = relationship()
    runs: Mapped[List["CrawlerJobRunORM"]] = relationship(
        back_populates="job", cascade="all, delete-orphan"
    )


class CrawlerJobRunORM(Base):
    """调度任务执行记录。"""

    __tablename__ = "crawler_job_runs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    job_id: Mapped[str] = mapped_column(String(64), ForeignKey("crawler_jobs.id"))
    status: Mapped[str] = mapped_column(String(16))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    executed_crawler: Mapped[str] = mapped_column(String(128))
    params_snapshot: Mapped[dict] = mapped_column(JSON, default=dict)
    result_count: Mapped[int] = mapped_column(Integer, default=0)
    log_path: Mapped[Optional[str]] = mapped_column(String(255))
    error_message: Mapped[Optional[str]] = mapped_column(Text)

    job: Mapped["CrawlerJobORM"] = relationship(back_populates="runs")
