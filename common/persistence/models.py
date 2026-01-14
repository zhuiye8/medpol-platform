"""SQLAlchemy ORM models."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from pgvector.sqlalchemy import Vector

from common.domain import ArticleCategory


ArticleCategoryEnum = SAEnum(
    ArticleCategory,
    name="article_category",
    values_callable=lambda enum_cls: [member.value for member in enum_cls],
)


class Base(DeclarativeBase):
    """ORM base."""


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow
    )


class SourceORM(TimestampMixin, Base):
    """Source."""

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
    """Normalized article."""

    __tablename__ = "articles"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    source_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("sources.id", ondelete="CASCADE"),
    )
    title: Mapped[str] = mapped_column(String(512))
    translated_title: Mapped[Optional[str]] = mapped_column(String(512))
    content_html: Mapped[str] = mapped_column(Text)
    content_text: Mapped[str] = mapped_column(Text)
    publish_time: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    source_name: Mapped[str] = mapped_column(String(128))
    source_url: Mapped[str] = mapped_column(String(512))
    category: Mapped[ArticleCategory] = mapped_column(ArticleCategoryEnum, nullable=False)
    status: Mapped[Optional[str]] = mapped_column(String(64))
    tags: Mapped[list] = mapped_column(JSON, default=list)
    crawl_time: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    content_source: Mapped[str] = mapped_column(String(32))
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    ai_analysis: Mapped[Optional[dict]] = mapped_column(JSON(none_as_null=True), nullable=True)
    translated_content: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    translated_content_html: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    original_source_language: Mapped[Optional[str]] = mapped_column(String(16))
    is_positive_policy: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)

    source: Mapped["SourceORM"] = relationship(back_populates="articles")
    ai_results: Mapped[List["AIResultORM"]] = relationship(
        back_populates="article", cascade="all, delete-orphan"
    )


Index(
    "idx_articles_search",
    ArticleORM.title,
    ArticleORM.translated_title,
    ArticleORM.content_text,
)  # 多字段搜索索引
Index("idx_articles_category", ArticleORM.category)
Index("idx_articles_status", ArticleORM.status)


class AIResultORM(TimestampMixin, Base):
    """AI result."""

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
    """Crawler job config."""

    __tablename__ = "crawler_jobs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(128))
    crawler_name: Mapped[str] = mapped_column(String(128))
    source_id: Mapped[str] = mapped_column(String(36), ForeignKey("sources.id"))
    job_type: Mapped[str] = mapped_column(String(16))
    schedule_cron: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    interval_minutes: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    retry_config: Mapped[dict] = mapped_column(JSON, default=dict)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    next_run_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    last_run_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    last_status: Mapped[Optional[str]] = mapped_column(String(16))

    source: Mapped["SourceORM"] = relationship()
    runs: Mapped[List["CrawlerJobRunORM"]] = relationship(
        back_populates="job", cascade="all, delete-orphan"
    )


class CrawlerJobRunORM(Base):
    """Crawler job execution."""

    __tablename__ = "crawler_job_runs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    job_id: Mapped[str] = mapped_column(String(64), ForeignKey("crawler_jobs.id"))
    status: Mapped[str] = mapped_column(String(16))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    executed_crawler: Mapped[str] = mapped_column(String(128))
    params_snapshot: Mapped[dict] = mapped_column(JSON, default=dict)
    result_count: Mapped[int] = mapped_column(Integer, default=0)
    duration_ms: Mapped[Optional[int]] = mapped_column(Integer, default=0)
    retry_attempts: Mapped[Optional[int]] = mapped_column(Integer, default=0)
    error_type: Mapped[Optional[str]] = mapped_column(String(32))
    pipeline_run_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    log_path: Mapped[Optional[str]] = mapped_column(String(255))
    error_message: Mapped[Optional[str]] = mapped_column(Text)

    job: Mapped["CrawlerJobORM"] = relationship(back_populates="runs")


class CrawlerPipelineRunORM(Base):
    """Pipeline run summary."""

    __tablename__ = "crawler_pipeline_runs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    run_type: Mapped[str] = mapped_column(String(16))  # quick/full/job/manual_retry
    status: Mapped[str] = mapped_column(String(16))
    total_crawlers: Mapped[int] = mapped_column(Integer, default=0)
    successful_crawlers: Mapped[int] = mapped_column(Integer, default=0)
    failed_crawlers: Mapped[int] = mapped_column(Integer, default=0)
    total_articles: Mapped[int] = mapped_column(Integer, default=0)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    error_message: Mapped[Optional[str]] = mapped_column(Text)

    details: Mapped[List["CrawlerPipelineRunDetailORM"]] = relationship(
        back_populates="run", cascade="all, delete-orphan"
    )


class CrawlerPipelineRunDetailORM(Base):
    """Pipeline run detail per crawler."""

    __tablename__ = "crawler_pipeline_run_details"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    run_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("crawler_pipeline_runs.id", ondelete="CASCADE")
    )
    crawler_name: Mapped[str] = mapped_column(String(128))
    source_id: Mapped[Optional[str]] = mapped_column(String(36))
    status: Mapped[str] = mapped_column(String(16))
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    duration_ms: Mapped[Optional[int]] = mapped_column(Integer, default=0)
    attempt_number: Mapped[Optional[int]] = mapped_column(Integer, default=0)
    max_attempts: Mapped[Optional[int]] = mapped_column(Integer, default=0)
    result_count: Mapped[int] = mapped_column(Integer, default=0)
    error_type: Mapped[Optional[str]] = mapped_column(String(32))
    error_message: Mapped[Optional[str]] = mapped_column(Text)
    log_path: Mapped[Optional[str]] = mapped_column(String(255))
    config_snapshot: Mapped[Optional[dict]] = mapped_column(JSON, default=dict)

    run: Mapped["CrawlerPipelineRunORM"] = relationship(back_populates="details")


class FinanceSyncLogORM(TimestampMixin, Base):
    """Finance sync log."""

    __tablename__ = "finance_sync_logs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    source: Mapped[str] = mapped_column(String(32), default="finance_api")
    mode: Mapped[str] = mapped_column(String(32), default="full")
    status: Mapped[str] = mapped_column(String(16), default="pending")
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    fetched_count: Mapped[int] = mapped_column(Integer, default=0)
    inserted_count: Mapped[int] = mapped_column(Integer, default=0)
    updated_count: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[Optional[str]] = mapped_column(Text)

    records: Mapped[List["FinanceRecordORM"]] = relationship(
        back_populates="sync_log", cascade="all, delete-orphan"
    )


class FinanceRecordORM(TimestampMixin, Base):
    """Finance record."""

    __tablename__ = "finance_records"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    sync_log_id: Mapped[Optional[str]] = mapped_column(
        String(64), ForeignKey("finance_sync_logs.id", ondelete="SET NULL")
    )
    keep_date: Mapped[date] = mapped_column(Date(), nullable=False)
    type_no: Mapped[str] = mapped_column(String(8), nullable=False)
    type_name: Mapped[Optional[str]] = mapped_column(String(64))
    company_no: Mapped[str] = mapped_column(String(64), nullable=False)
    company_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    company_name: Mapped[Optional[str]] = mapped_column(String(128))
    high_company_no: Mapped[Optional[str]] = mapped_column(String(64))
    level: Mapped[Optional[str]] = mapped_column(String(16))
    current_amount: Mapped[Optional[Decimal]] = mapped_column(Numeric(20, 4))
    last_year_amount: Mapped[Optional[Decimal]] = mapped_column(Numeric(20, 4))
    last_year_total_amount: Mapped[Optional[Decimal]] = mapped_column(Numeric(20, 4))
    this_year_total_amount: Mapped[Optional[Decimal]] = mapped_column(Numeric(20, 4))
    add_amount: Mapped[Optional[Decimal]] = mapped_column(Numeric(20, 4))
    add_rate: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 4))
    year_add_amount: Mapped[Optional[Decimal]] = mapped_column(Numeric(20, 4))
    year_add_rate: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 4))
    raw_payload: Mapped[dict] = mapped_column(JSON, default=dict)

    sync_log: Mapped[Optional["FinanceSyncLogORM"]] = relationship(back_populates="records")


class ArticleEmbeddingORM(TimestampMixin, Base):
    """Article embeddings for RAG."""

    __tablename__ = "article_embeddings"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    article_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("articles.id", ondelete="CASCADE"),
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    chunk_text: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[list[float]] = mapped_column(Vector(1024))
    model_name: Mapped[str] = mapped_column(String(64), nullable=False)

    article: Mapped["ArticleORM"] = relationship()


# ============================================================
# 用户认证相关模型
# ============================================================


class RoleORM(TimestampMixin, Base):
    """Role for RBAC."""

    __tablename__ = "roles"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String(256))
    permissions: Mapped[dict] = mapped_column(JSON, default=dict)

    users: Mapped[List["UserORM"]] = relationship(
        secondary="user_roles", back_populates="roles"
    )


class UserORM(TimestampMixin, Base):
    """User account."""

    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(256), nullable=False)
    display_name: Mapped[Optional[str]] = mapped_column(String(128))
    email: Mapped[Optional[str]] = mapped_column(String(128))
    company_no: Mapped[Optional[str]] = mapped_column(String(32))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    roles: Mapped[List["RoleORM"]] = relationship(
        secondary="user_roles", back_populates="users"
    )

    @property
    def role_names(self) -> List[str]:
        """Get list of role names."""
        return [role.name for role in self.roles]

    @property
    def primary_role(self) -> Optional[str]:
        """Get primary (first) role name."""
        return self.roles[0].name if self.roles else None


class UserRoleORM(Base):
    """User-Role association table."""

    __tablename__ = "user_roles"

    user_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    role_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow
    )


# ============================================================
# 员工信息模型
# ============================================================


class EmployeeORM(TimestampMixin, Base):
    """Employee information."""

    __tablename__ = "employees"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    company_no: Mapped[str] = mapped_column(String(32), nullable=False)
    company_name: Mapped[Optional[str]] = mapped_column(String(128))
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    gender: Mapped[Optional[str]] = mapped_column(String(8))
    id_number: Mapped[Optional[str]] = mapped_column(String(32))  # 敏感字段
    phone: Mapped[Optional[str]] = mapped_column(String(32))  # 敏感字段
    department: Mapped[Optional[str]] = mapped_column(String(128))
    position: Mapped[Optional[str]] = mapped_column(String(128))
    employee_level: Mapped[Optional[str]] = mapped_column(String(32))
    is_contract: Mapped[Optional[bool]] = mapped_column(Boolean)
    highest_education: Mapped[Optional[str]] = mapped_column(String(32))
    graduate_school: Mapped[Optional[str]] = mapped_column(String(128))
    major: Mapped[Optional[str]] = mapped_column(String(128))
    political_status: Mapped[Optional[str]] = mapped_column(String(32))
    professional_title: Mapped[Optional[str]] = mapped_column(String(64))
    skill_level: Mapped[Optional[str]] = mapped_column(String(32))
    hire_date: Mapped[Optional[date]] = mapped_column(Date)
    raw_data: Mapped[dict] = mapped_column(JSON, default=dict)
