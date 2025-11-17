"""领域数据模型定义，所有模块共享统一结构。"""

from enum import Enum
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field, HttpUrl


class ArticleCategory(str, Enum):
    """文章分类枚举，统一所有模块使用的业务标签。"""

    FRONTIER = "frontier"  # 前沿动态
    FDA_POLICY = "fda_policy"
    EMA_POLICY = "ema_policy"
    PMDA_POLICY = "pmda_policy"
    PROJECT_APPLY = "project_apply"
    DOMESTIC_POLICY = "domestic_policy"  # 国内政策与动态


class RawArticle(BaseModel):
    """原始爬取的文章载荷，用于传递给格式化模块。"""

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
    metadata: dict = Field(default_factory=dict, description="附加元信息（标签、摘要等）")


class Source(BaseModel):
    """数据来源配置，例如 FDA 官网、行业协会等。"""

    id: str = Field(..., description="来源主键，UUID")
    name: str = Field(..., description="来源展示名称")
    label: str = Field(..., description="来源标签，用于分类或过滤")
    base_url: HttpUrl = Field(..., description="来源根域名，便于监控与跳转")
    category: ArticleCategory = Field(..., description="来源所属类别，例：fda_policy")
    is_active: bool = Field(True, description="是否启用")
    crawl_frequency_minutes: int = Field(
        60, description="建议的采集频率，便于动态调度"
    )
    meta: dict = Field(default_factory=dict, description="额外配置信息，如代理、凭证")


class Article(BaseModel):
    """标准化后的文章/政策信息。"""

    id: str = Field(..., description="UUID 主键")
    source_id: str = Field(..., description="来源 ID")
    title: str = Field(..., description="文章标题")
    content_html: str = Field(..., description="结构化 HTML 内容")
    content_text: str = Field(..., description="纯文本内容，便于搜索")
    publish_time: datetime = Field(..., description="原文发布时间")
    source_name: str = Field(..., description="来源名称，冗余展示")
    source_url: HttpUrl = Field(..., description="原文链接")
    category: ArticleCategory = Field(..., description="业务分类，如 fda_policy")
    tags: List[str] = Field(default_factory=list, description="标签列表")
    crawl_time: datetime = Field(..., description="采集时间")
    content_source: str = Field(..., description="内容来源渠道，如 web_page/wechat")
    summary: Optional[str] = Field(None, description="AI 生成摘要")
    ai_analysis: Optional[dict] = Field(None, description="AI 专业解读结构化结果")
    translated_content: Optional[str] = Field(None, description="翻译后纯文本")
    translated_content_html: Optional[str] = Field(None, description="翻译后的 HTML")
    original_source_language: Optional[str] = Field(None, description="原文语言代码")


class AIResult(BaseModel):
    """AI 模块生成的结果记录。"""

    id: str = Field(..., description="UUID 主键")
    article_id: str = Field(..., description="关联的文章 UUID")
    task_type: str = Field(..., description="任务类型：summary/translation/analysis")
    provider: str = Field(..., description="模型提供方，例：openai/deepseek")
    model: str = Field(..., description="模型名称")
    output: str = Field(..., description="AI 输出内容（可为 JSON 字符串）")
    latency_ms: int = Field(..., description="耗时，毫秒")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="生成时间")
    metadata: dict = Field(default_factory=dict, description="额外上下文信息")


class DistributionEvent(BaseModel):
    """用于分发的数据载体。"""

    article: Article
    ai_results: List[AIResult] = Field(default_factory=list)
    targets: List[str] = Field(
        default_factory=list, description="需要投递的渠道标识，如 webhook/email"
    )
    delivery_id: str = Field(..., description="该次分发的唯一 ID")


class CrawlerTask(BaseModel):
    """爬虫调度任务描述。"""

    source_id: str = Field(..., description="来源 ID")
    crawler_name: str = Field(..., description="对应的爬虫类名")
    schedule_id: str = Field(..., description="调度唯一标识")
    priority: int = Field(3, description="优先级，数字越小优先级越高")
    retry_count: int = Field(0, description="已重试次数")
    payload: dict = Field(default_factory=dict, description="自定义参数")


class ErrorEnvelope(BaseModel):
    """统一错误返回结构。"""

    code: int = Field(..., description="错误码")
    msg: str = Field(..., description="错误描述")
    detail: Optional[str] = Field(None, description="额外细节")


class CrawlerJob(BaseModel):
    """调度任务配置。"""

    id: str
    name: str
    crawler_name: str
    source_id: str
    job_type: str = Field(..., description="scheduled / one_off")
    schedule_cron: Optional[str] = Field(None, description="Cron 表达式")
    interval_minutes: Optional[int] = Field(None, description="间隔分钟数")
    payload: dict = Field(default_factory=dict, description="运行参数，如 meta/limit")
    enabled: bool = True
    next_run_at: Optional[datetime] = None
    last_run_at: Optional[datetime] = None
    last_status: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class CrawlerJobRun(BaseModel):
    """调度任务执行记录。"""

    id: str
    job_id: str
    status: str
    started_at: datetime
    finished_at: Optional[datetime] = None
    executed_crawler: str
    params_snapshot: dict = Field(default_factory=dict)
    result_count: int = 0
    log_path: Optional[str] = None
    error_message: Optional[str] = None
