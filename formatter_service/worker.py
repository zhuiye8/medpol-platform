"""格式化服务：原始数据清洗、校验、去重，并可作为 Celery Worker 使用。"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Dict, Optional
from urllib.parse import urlparse

from celery import Celery

from common.domain import Article, RawArticle, ArticleCategory
from common.persistence.database import get_session_factory, session_scope
from common.persistence import models as orm_models
from common.persistence.repository import ArticleRepository, SourceRepository
from .utils import apply_field_mapping, clean_html, normalize_text
from .language import detect_language


REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
FORMATTER_QUEUE = os.getenv("FORMATTER_QUEUE", "formatter")
STATE_PATH = Path(os.getenv("FORMATTER_SEEN_PATH", "sample_data/state/formatter_seen.json"))
STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
DATABASE_URL = os.getenv("DATABASE_URL")

SESSION_FACTORY = None
if DATABASE_URL:
    try:
        SESSION_FACTORY = get_session_factory()
    except Exception as exc:  # pragma: no cover - 初始化失败时，仅记录
        print(f"[formatter] init session factory failed: {exc}")
        SESSION_FACTORY = None

celery_app = Celery(
    "formatter_service",
    broker=REDIS_URL,
    backend=REDIS_URL,
)
celery_app.conf.task_default_queue = FORMATTER_QUEUE


class FormatterDeduper:
    """简易内容去重器，按正文哈希去重。"""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.hashes = self._load()

    def _load(self) -> set[str]:
        if not self.path.exists():
            return set()
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            return set(data)
        except Exception:
            return set()

    def _save(self) -> None:
        self.path.write_text(json.dumps(sorted(self.hashes)), encoding="utf-8")

    def is_duplicate(self, content_hash: str) -> bool:
        return content_hash in self.hashes

    def mark(self, content_hash: str) -> None:
        self.hashes.add(content_hash)
        self._save()


DEDUPER = FormatterDeduper(STATE_PATH)


def _is_project_apply(content: str, title: str) -> bool:
    """判断是否为项目申报类信息，关键词优先，兜底使用大模型判断。"""

    text = (title + " " + content).lower()
    keywords = ["申报", "项目", "征集", "遴选", "扶持", "资金", "奖励", "认定", "指南"]
    if any(k in text for k in keywords):
        return True
    return False


def _to_article(raw: RawArticle) -> Article:
    """将原始载荷转换为标准 Article。"""

    cleaned_html = clean_html(raw.content_html)
    soup_text = normalize_text(clean_html(raw.content_html))
    mapped = apply_field_mapping(raw.model_dump())
    tags = mapped.get("tags") or []
    summary = mapped.get("summary")
    content_source = mapped.get("content_source") or raw.content_source
    original_language = (mapped.get("original_source_language") or "").lower()
    if not original_language:
        original_language = detect_language(soup_text)

    return Article(
        id=raw.article_id,
        source_id=raw.source_id or f"src_{raw.source_name}",
        title=raw.title,
        content_html=cleaned_html,
        content_text=soup_text,
        publish_time=raw.publish_time or raw.crawl_time,
        source_name=raw.source_name,
        source_url=raw.source_url,
        category=raw.category,
        tags=tags,
        crawl_time=raw.crawl_time,
        content_source=content_source,
        summary=summary,
        ai_analysis=None,
        translated_content=None,
        translated_content_html=None,
        original_source_language=original_language or "unknown",
        apply_status="pending" if raw.category == ArticleCategory.PROJECT_APPLY else None,
        is_positive_policy=None,
    )


def process_raw_article(raw_article: Dict) -> Dict:
    """
    核心处理逻辑，可被 Celery 或离线脚本复用。
    返回结构：
        {
            "skipped": bool,
            "reason": Optional[str],
            "article_id": str,
            "article": Optional[dict]
        }
    """

    raw = RawArticle(**raw_article)
    if not raw.title or not raw.content_html:
        return {
            "skipped": True,
            "reason": "missing_required_field",
            "article_id": raw.article_id,
        }

    article = _to_article(raw)
    if article.category == ArticleCategory.PROJECT_APPLY:
        keep = _is_project_apply(article.content_text, article.title)
        if not keep:
            return {
                "skipped": True,
                "reason": "not_project_apply",
                "article_id": raw.article_id,
            }
    content_hash = hashlib.sha256(article.content_text.encode("utf-8")).hexdigest()
    if DEDUPER.is_duplicate(content_hash):
        return {
            "skipped": True,
            "reason": "duplicate",
            "article_id": article.id,
        }

    DEDUPER.mark(content_hash)
    _persist_article(article)
    return {
        "skipped": False,
        "article": article.model_dump(mode="json"),
        "article_id": article.id,
    }


@celery_app.task(name="formatter_service.normalize_article", queue=FORMATTER_QUEUE)
def normalize_article(raw_article: dict) -> dict:
    """Celery 任务入口。"""

    return process_raw_article(raw_article)


def _persist_article(article: Article) -> None:
    """将 Article 写入数据库（若配置了 DATABASE_URL）。"""

    if SESSION_FACTORY is None:
        return

    with session_scope(SESSION_FACTORY) as session:
        source_repo = SourceRepository(session)
        article_repo = ArticleRepository(session)

        source = source_repo.get_by_id(article.source_id)
        if not source:
            base_url = _derive_base_url(article.source_url)
            source = orm_models.SourceORM(
                id=article.source_id,
                name=article.source_name,
                label=article.source_name,
                base_url=base_url,
                category=article.category,
                is_active=True,
                meta={},
            )
            source_repo.add(source)

        existing = article_repo.get_by_id(article.id)
        if existing:
            _apply_article(existing, article)
        else:
            new_article = orm_models.ArticleORM(
                id=article.id,
                source_id=article.source_id,
                title=article.title,
                content_html=article.content_html,
                content_text=article.content_text,
                publish_time=article.publish_time,
                source_name=article.source_name,
                source_url=str(article.source_url),
                category=article.category,
                tags=article.tags,
                crawl_time=article.crawl_time,
                content_source=article.content_source,
                summary=article.summary,
                ai_analysis=None,
                translated_content=None,
                translated_content_html=article.translated_content_html,
                original_source_language=article.original_source_language,
                apply_status=article.apply_status,
                is_positive_policy=article.is_positive_policy,
            )
            article_repo.add(new_article)


def _apply_article(target: orm_models.ArticleORM, article: Article) -> None:
    """更新已存在的文章记录。"""

    target.title = article.title
    target.content_html = article.content_html
    target.content_text = article.content_text
    target.publish_time = article.publish_time
    target.source_name = article.source_name
    target.source_url = str(article.source_url)
    target.category = article.category
    target.tags = article.tags
    target.crawl_time = article.crawl_time
    target.content_source = article.content_source
    target.summary = article.summary
    target.ai_analysis = article.ai_analysis
    target.translated_content = article.translated_content
    target.translated_content_html = article.translated_content_html
    target.original_source_language = article.original_source_language
    target.apply_status = article.apply_status
    target.is_positive_policy = article.is_positive_policy


def _derive_base_url(url: str) -> str:
    parsed = urlparse(str(url))
    return f"{parsed.scheme}://{parsed.netloc}" if parsed.scheme else str(url)
