"""事件名称与载荷结构定义。"""

from enum import Enum


class EventTopic(str, Enum):
    """统一事件主题。"""

    RAW_ARTICLE = "raw_article"
    NEEDS_AI = "needs_ai"
    DISTRIBUTION_EVENT = "distribution_event"
    METRICS = "metrics"


class EventHeader:
    """事件头信息常量。"""

    CORRELATION_ID = "x-correlation-id"
    RETRY_COUNT = "x-retry-count"
