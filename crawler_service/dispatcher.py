"""将 CrawlResult 转换为 RawArticle 并推送到消息队列。"""

from __future__ import annotations

import json
import logging
import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import List

from celery import Celery

from common.domain import RawArticle, ArticleCategory

from .base import BaseCrawler, CrawlResult


logger = logging.getLogger("crawler.dispatcher")
REDIS_URL = os.getenv("REDIS_URL")
FORMATTER_QUEUE = os.getenv("FORMATTER_QUEUE", "formatter")

celery_app = None
if REDIS_URL:
    celery_app = Celery(
        "crawler_dispatcher",
        broker=REDIS_URL,
        backend=REDIS_URL,
    )


class RawArticleBuilder:
    """负责将 CrawlResult 转换为 RawArticle。"""

    def __init__(self, crawler: BaseCrawler) -> None:
        self.crawler = crawler

    def build(self, result: CrawlResult) -> RawArticle:
        metadata = result.metadata or {}
        article_id = metadata.get("article_id")
        if article_id is not None:
            article_id = str(article_id)
        else:
            article_id = str(uuid.uuid4())
        source_id_value = metadata.get("source_id") or self.crawler.config.source_id or ""
        source_id = str(source_id_value)
        source_name = metadata.get("source_name") or getattr(
            self.crawler, "source_name", self.crawler.label
        )
        category = self._resolve_category(metadata.get("category"))
        content_source = metadata.get("content_source", "web_page")
        crawl_time = metadata.get("crawl_time")
        if crawl_time and isinstance(crawl_time, str):
            try:
                crawl_time = datetime.fromisoformat(crawl_time)
            except ValueError:
                crawl_time = None
        crawl_time = crawl_time or datetime.utcnow()

        return RawArticle(
            article_id=article_id,
            source_id=source_id,
            source_name=source_name,
            category=category,
            title=result.title,
            content_html=result.content_html,
            source_url=result.source_url,
            publish_time=result.publish_time,
            crawl_time=crawl_time,
            content_source=content_source,
            metadata=metadata,
        )

    def _resolve_category(self, value) -> ArticleCategory:
        """从 metadata 或 crawler 默认解析分类为合法枚举。"""

        if isinstance(value, ArticleCategory):
            return value
        if isinstance(value, str) and value:
            try:
                return ArticleCategory(value.lower())
            except ValueError as exc:
                raise ValueError(f"不支持的分类: {value}") from exc
        return self.crawler.category


class FormatterPublisher:
    """向 formatter_service 发布任务，失败时写入本地。"""

    def __init__(self) -> None:
        self._celery = celery_app
        self._fallback_dir = Path("sample_data/outbox")
        self._fallback_dir.mkdir(parents=True, exist_ok=True)

    def publish(self, article: RawArticle) -> None:
        payload = article.model_dump(mode="json")
        if self._celery:
            try:
                self._celery.send_task(
                    "formatter_service.normalize_article",
                    args=[payload],
                    queue=FORMATTER_QUEUE,
                )
                return
            except Exception as exc:  # pylint: disable=broad-except
                logger.warning("Celery 发送失败，写入本地队列: %s", exc)
        self._write_fallback(payload)

    def _write_fallback(self, payload: dict) -> None:
        file_path = self._fallback_dir / f"raw_{payload['article_id']}.json"
        with file_path.open("w", encoding="utf-8") as fh:
            json.dump(payload, fh, ensure_ascii=False, indent=2)


def dispatch_results(
    crawler: BaseCrawler, results: List[CrawlResult], publisher: FormatterPublisher
) -> List[RawArticle]:
    """辅助函数：将结果批量转换并发布。"""

    builder = RawArticleBuilder(crawler)
    articles: List[RawArticle] = []
    for result in results:
        raw_article = builder.build(result)
        publisher.publish(raw_article)
        articles.append(raw_article)
    return articles
