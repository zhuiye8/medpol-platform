"""API response schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Generic, List, Literal, Optional, TypeVar

from pydantic import BaseModel, Field
from common.domain import ArticleCategory


class AIAnalysisData(BaseModel):
    content: Optional[str] = None
    is_positive_policy: Optional[bool] = None


class ArticleItem(BaseModel):
    id: str
    title: str
    translated_title: Optional[str] = None
    summary: Optional[str] = None
    publish_time: datetime
    source_name: str
    category: ArticleCategory
    status: Optional[str] = None
    tags: List[str]
    source_url: str
    is_positive_policy: Optional[bool] = None


class ArticleListData(BaseModel):
    items: List[ArticleItem]
    page: int
    page_size: int
    total: int
    stats: Optional[Dict[str, Any]] = None


class LogLine(BaseModel):
    idx: int
    content: str


class LogListData(BaseModel):
    lines: List[LogLine]
    total: int
    truncated: bool


T = TypeVar("T")


class Envelope(BaseModel, Generic[T]):
    code: int
    msg: str
    data: T


class CrawlerMeta(BaseModel):
    name: str
    label: str
    description: Optional[str] = None
    category: Optional[str] = None


class CrawlerJobPayload(BaseModel):
    meta: Dict[str, Any] = Field(default_factory=dict)
    limit: Optional[int] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None


class CrawlerJobBase(BaseModel):
    name: str
    task_type: Literal["crawler", "finance_sync", "embeddings_index"] = "crawler"
    crawler_name: Optional[str] = None  # Required only for crawler tasks
    source_id: Optional[str] = None  # Required only for crawler tasks
    job_type: Literal["scheduled", "one_off"]
    schedule_cron: Optional[str] = None
    interval_minutes: Optional[int] = None
    payload: CrawlerJobPayload = Field(default_factory=CrawlerJobPayload)
    retry_config: Dict[str, Any] = Field(default_factory=dict)
    enabled: bool = True


class CrawlerJobCreate(CrawlerJobBase):
    pass


class CrawlerJobUpdate(BaseModel):
    name: Optional[str] = None
    task_type: Optional[Literal["crawler", "finance_sync", "embeddings_index"]] = None
    crawler_name: Optional[str] = None
    source_id: Optional[str] = None
    job_type: Optional[Literal["scheduled", "one_off"]] = None
    schedule_cron: Optional[str] = None
    interval_minutes: Optional[int] = None
    payload: Optional[CrawlerJobPayload] = None
    retry_config: Optional[Dict[str, Any]] = None
    enabled: Optional[bool] = None


class CrawlerJobItem(BaseModel):
    id: str
    name: str
    task_type: str = "crawler"
    crawler_name: Optional[str] = None
    source_id: Optional[str] = None
    job_type: str
    schedule_cron: Optional[str]
    interval_minutes: Optional[int]
    payload: CrawlerJobPayload
    retry_config: Dict[str, Any]
    enabled: bool
    next_run_at: Optional[datetime]
    last_run_at: Optional[datetime]
    last_status: Optional[str]


class CrawlerJobListData(BaseModel):
    items: List[CrawlerJobItem]


class RunJobRequest(BaseModel):
    payload_override: Optional[Dict[str, Any]] = None


class CrawlerJobRunItem(BaseModel):
    id: str
    status: str
    started_at: datetime
    finished_at: Optional[datetime]
    executed_crawler: str
    result_count: int
    duration_ms: Optional[int] = None
    retry_attempts: Optional[int] = None
    error_type: Optional[str] = None
    pipeline_run_id: Optional[str] = None
    log_path: Optional[str]
    error_message: Optional[str]


class CrawlerJobRunListData(BaseModel):
    items: List[CrawlerJobRunItem]


class PipelineRunData(BaseModel):
    run_id: Optional[str] = None
    crawled: int
    outbox_files: int
    outbox_processed: int
    outbox_skipped: int
    ai_summary_pending: int
    ai_summary_enqueued: int
    ai_translation_pending: int
    ai_translation_enqueued: int
    ai_analysis_pending: int
    ai_analysis_enqueued: int
    details: List["PipelineRunDetailItem"] = Field(default_factory=list)


class PipelineRunDetailItem(BaseModel):
    id: Optional[str] = None
    crawler_name: str
    source_id: Optional[str] = None
    status: str
    result_count: int
    duration_ms: Optional[int] = None
    attempt_number: Optional[int] = None
    max_attempts: Optional[int] = None
    error_type: Optional[str] = None
    error_message: Optional[str] = None
    log_path: Optional[str] = None


class PipelineRunItem(BaseModel):
    id: str
    run_type: str
    status: str
    total_crawlers: int
    successful_crawlers: int
    failed_crawlers: int
    total_articles: int
    started_at: datetime
    finished_at: Optional[datetime] = None
    error_message: Optional[str] = None
    details: List[PipelineRunDetailItem] = Field(default_factory=list)


class PipelineRunListData(BaseModel):
    items: List[PipelineRunItem]
    total: int


class CeleryStatus(BaseModel):
    running: bool
    detail: str


class ProxyConfig(BaseModel):
    """代理配置"""
    proxy_mode: Literal["auto", "always", "never"] = "auto"
    proxy_url: Optional[str] = None
    proxy_needed: Optional[bool] = None
    proxy_last_used: Optional[bool] = None


class SourceProxyItem(BaseModel):
    """来源代理状态"""
    source_id: str
    source_name: str
    crawler_name: Optional[str] = None
    proxy_mode: str = "auto"
    proxy_url: Optional[str] = None
    proxy_needed: Optional[bool] = None
    proxy_last_used: Optional[bool] = None


class SourceProxyListData(BaseModel):
    """来源代理状态列表"""
    items: List[SourceProxyItem]


class UpdateProxyConfigRequest(BaseModel):
    """更新代理配置请求"""
    proxy_mode: Optional[Literal["auto", "always", "never"]] = None
    proxy_url: Optional[str] = None


class ResetResultData(BaseModel):
    truncated_tables: List[str]
    cleared_dirs: List[str]
    dedupe_reset: bool
    redis_cleared: bool


class AIResultItem(BaseModel):
    id: str
    task_type: str
    provider: str
    model: str
    output: str
    created_at: datetime


class ArticleDetailData(BaseModel):
    id: str
    title: str
    translated_title: Optional[str]
    content_html: str
    translated_content: Optional[str]
    translated_content_html: Optional[str]
    ai_analysis: Optional[AIAnalysisData]
    summary: Optional[str]
    publish_time: datetime
    source_name: str
    source_url: str
    category: ArticleCategory
    status: Optional[str]
    original_source_language: Optional[str]
    is_positive_policy: Optional[bool]
    ai_results: List[AIResultItem]
