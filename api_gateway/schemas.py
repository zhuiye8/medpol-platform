"""API 响应 Schema。"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Generic, List, Literal, Optional, TypeVar

from pydantic import BaseModel, Field
from common.domain import ArticleCategory


class ArticleItem(BaseModel):
    id: str
    title: str
    summary: Optional[str] = None
    publish_time: datetime
    source_name: str
    category: ArticleCategory
    tags: List[str]
    source_url: str
    apply_status: Optional[str] = None
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
    crawler_name: str
    source_id: str
    job_type: Literal["scheduled", "one_off"]
    schedule_cron: Optional[str] = None
    interval_minutes: Optional[int] = None
    payload: CrawlerJobPayload = Field(default_factory=CrawlerJobPayload)
    enabled: bool = True


class CrawlerJobCreate(CrawlerJobBase):
    pass


class CrawlerJobUpdate(BaseModel):
    name: Optional[str] = None
    crawler_name: Optional[str] = None
    source_id: Optional[str] = None
    job_type: Optional[Literal["scheduled", "one_off"]] = None
    schedule_cron: Optional[str] = None
    interval_minutes: Optional[int] = None
    payload: Optional[CrawlerJobPayload] = None
    enabled: Optional[bool] = None


class CrawlerJobItem(BaseModel):
    id: str
    name: str
    crawler_name: str
    source_id: str
    job_type: str
    schedule_cron: Optional[str]
    interval_minutes: Optional[int]
    payload: CrawlerJobPayload
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
    log_path: Optional[str]
    error_message: Optional[str]


class CrawlerJobRunListData(BaseModel):
    items: List[CrawlerJobRunItem]


class PipelineRunData(BaseModel):
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


class CeleryStatus(BaseModel):
    running: bool
    detail: str


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
    content_html: str
    translated_content: Optional[str]
    translated_content_html: Optional[str]
    ai_analysis: Optional[dict]
    summary: Optional[str]
    publish_time: datetime
    source_name: str
    original_source_language: Optional[str]
    apply_status: Optional[str] = None
    is_positive_policy: Optional[bool] = None
    ai_results: List[AIResultItem]
