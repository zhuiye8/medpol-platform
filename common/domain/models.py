"""Domain data models shared across modules."""

from enum import Enum
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field, HttpUrl


class ArticleCategory(str, Enum):
    """Article categories."""

    FRONTIER = "frontier"
    FDA_POLICY = "fda_policy"
    EMA_POLICY = "ema_policy"
    PMDA_POLICY = "pmda_policy"
    BIDDING = "bidding"
    LAWS = "laws"
    INSTITUTION = "institution"
    PROJECT_APPLY = "project_apply"
    CDE_TREND = "cde_trend"
    INDUSTRY_TREND = "industry_trend"


class RawArticle(BaseModel):
    """Raw article payload."""

    article_id: str = Field(..., description="原始记录 ID，通常为 UUID")
    source_id: str = Field("", description="来源 ID，便于溯源")
    source_name: str = Field(..., description="来源展示名称")
    category: ArticleCategory = Field(..., description="业务分类")
    title: str = Field(..., description="原标题")
    content_html: str = Field(..., description="原始 HTML 内容")
    source_url: HttpUrl = Field(..., description="原文链接")
    publish_time: Optional[datetime] = Field(None, description="原文发布时间")
    crawl_time: datetime = Field(..., description="采集时间")
    content_source: str = Field("web_page", description="具体渠道，如 web_page/wechat")
    status: Optional[str] = Field(None, description="子分类/状态，用于筛选")
    metadata: dict = Field(default_factory=dict, description="附加元信息（标签等）")


class Source(BaseModel):
    """Data source config."""

    id: str = Field(..., description="来源主键，UUID")
    name: str = Field(..., description="来源展示名称")
    label: str = Field(..., description="来源标签，用于分类或过滤")
    base_url: HttpUrl = Field(..., description="来源根域名，便于监控与跳转")
    category: ArticleCategory = Field(..., description="来源所属类别，例：fda_policy")
    is_active: bool = Field(True, description="是否启用")
    crawl_frequency_minutes: int = Field(60, description="建议采集频率")
    meta: dict = Field(default_factory=dict, description="额外配置信息，如代理、凭证")


class Article(BaseModel):
    """Normalized article/policy data."""

    id: str = Field(..., description="UUID 主键")
    source_id: str = Field(..., description="来源 ID")
    title: str = Field(..., description="文章标题")
    translated_title: Optional[str] = Field(None, description="翻译后的标题")
    content_html: str = Field(..., description="结构化 HTML 内容")
    content_text: str = Field(..., description="纯文本内容，便于搜索")
    publish_time: datetime = Field(..., description="原文发布时间")
    source_name: str = Field(..., description="来源名称，冗余展示")
    source_url: HttpUrl = Field(..., description="原文链接")
    category: ArticleCategory = Field(..., description="业务分类，如 fda_policy")
    status: Optional[str] = Field(None, description="子分类/状态，统一筛选键")
    tags: List[str] = Field(default_factory=list, description="标签列表")
    crawl_time: datetime = Field(..., description="采集时间")
    content_source: str = Field(..., description="内容来源渠道，如 web_page/wechat")
    summary: Optional[str] = Field(None, description="AI 生成摘要")
    ai_analysis: Optional[dict] = Field(None, description="AI 专业解读：content + is_positive_policy")
    translated_content: Optional[str] = Field(None, description="翻译后纯文本")
    translated_content_html: Optional[str] = Field(None, description="翻译后的 HTML")
    original_source_language: Optional[str] = Field(None, description="原文语言代码")
    is_positive_policy: Optional[bool] = Field(None, description="是否利好政策（同步 ai_analysis）")


class AIResult(BaseModel):
    """AI result record."""

    id: str = Field(..., description="UUID 主键")
    article_id: str = Field(..., description="关联的文档 UUID")
    task_type: str = Field(..., description="任务类型：summary/translation/analysis")
    provider: str = Field(..., description="模型提供方，例：openai/deepseek")
    model: str = Field(..., description="模型名称")
    output: str = Field(..., description="AI 输出内容（可能是 JSON 字符串）")
    latency_ms: int = Field(..., description="耗时，毫秒")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="生成时间")
    metadata: dict = Field(default_factory=dict, description="额外上下文信息")


class DistributionEvent(BaseModel):
    """Envelope for distribution."""

    article: Article
    ai_results: List[AIResult] = Field(default_factory=list)
    targets: List[str] = Field(
        default_factory=list, description="需要投递的渠道标识，如 webhook/email"
    )
    delivery_id: str = Field(..., description="该次分发的唯一 ID")


class CrawlerTask(BaseModel):
    """Crawler task description."""

    source_id: str = Field(..., description="来源 ID")
    crawler_name: str = Field(..., description="对应的爬虫类名")
    schedule_id: str = Field(..., description="调度唯一标识")
    priority: int = Field(3, description="优先级，数字越小优先级越高")
    retry_count: int = Field(0, description="已重试次数")
    payload: dict = Field(default_factory=dict, description="自定义参数")


class ErrorEnvelope(BaseModel):
    """Error envelope."""

    code: int = Field(..., description="错误码")
    msg: str = Field(..., description="错误描述")
    detail: Optional[str] = Field(None, description="额外细节")


class CrawlerJob(BaseModel):
    """Scheduler job config."""

    id: str
    name: str
    crawler_name: str
    source_id: str
    job_type: str = Field(..., description="scheduled / one_off")
    schedule_cron: Optional[str] = Field(None, description="Cron 表达式")
    interval_minutes: Optional[int] = Field(None, description="间隔分钟数")
    payload: dict = Field(default_factory=dict, description="运行参数，如 meta/limit")
    retry_config: dict = Field(default_factory=dict, description="爬虫级重试与请求重试配置")
    enabled: bool = True
    next_run_at: Optional[datetime] = None
    last_run_at: Optional[datetime] = None
    last_status: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class CrawlerJobRun(BaseModel):
    """Scheduler job execution record."""

    id: str
    job_id: str
    status: str
    started_at: datetime
    finished_at: Optional[datetime] = None
    executed_crawler: str
    params_snapshot: dict = Field(default_factory=dict)
    result_count: int = 0
    duration_ms: Optional[int] = 0
    retry_attempts: Optional[int] = 0
    error_type: Optional[str] = None
    pipeline_run_id: Optional[str] = None
    log_path: Optional[str] = None
    error_message: Optional[str] = None


class CrawlerPipelineRun(BaseModel):
    """Pipeline run summary."""

    id: str
    run_type: str
    status: str
    total_crawlers: int = 0
    successful_crawlers: int = 0
    failed_crawlers: int = 0
    total_articles: int = 0
    started_at: datetime
    finished_at: Optional[datetime] = None
    error_message: Optional[str] = None


class CrawlerPipelineRunDetail(BaseModel):
    """Pipeline run detail per crawler."""

    id: str
    run_id: str
    crawler_name: str
    source_id: Optional[str] = None
    status: str
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    duration_ms: Optional[int] = 0
    attempt_number: Optional[int] = 0
    max_attempts: Optional[int] = 0
    result_count: int = 0
    error_type: Optional[str] = None
    error_message: Optional[str] = None
    log_path: Optional[str] = None
    config_snapshot: dict = Field(default_factory=dict)
