"""Formatter service：清洗、去重、入库，并在入库后自动推送 AI 任务。"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Dict, Optional
from urllib.parse import urlparse

from celery import Celery

from common.domain import Article, RawArticle, ArticleCategory
from common.utils.env import load_env
from common.persistence.database import get_session_factory, session_scope
from common.persistence import models as orm_models
from common.persistence.repository import ArticleRepository, SourceRepository
from .utils import apply_field_mapping, clean_html, normalize_text
from .language import detect_language
from datetime import datetime, timedelta

# finance sync / embeddings
from common.finance_sync.fetcher import FinanceDataFetcherError
from common.finance_sync.service import FinanceDataSyncError, FinanceDataSyncService
from ai_chat.vanna.vectorstore import add_documents
from scripts.index_articles import _chunk_text, chunk_articles

load_env()

# AI 任务（入库后立即入队）
try:
    from ai_processor.worker import (
        process_summary,
        process_translation,
        process_analysis,
        process_title_translation,
    )

    AI_TASKS_AVAILABLE = True
except Exception as exc:  # pragma: no cover - AI worker 未就绪时的兜底
    process_summary = None  # type: ignore
    process_translation = None  # type: ignore
    process_analysis = None  # type: ignore
    process_title_translation = None  # type: ignore
    AI_TASKS_AVAILABLE = False
    print(f"[formatter] AI 任务加载失败: {exc}")


# 预加载 .env，确保 Celery/数据库配置就绪
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
FORMATTER_QUEUE = os.getenv("FORMATTER_QUEUE", "formatter")
STATE_PATH = Path(os.getenv("FORMATTER_SEEN_PATH", "sample_data/state/formatter_seen.json"))
STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
DATABASE_URL = os.getenv("DATABASE_URL")

SESSION_FACTORY = None
if DATABASE_URL:
    try:
        SESSION_FACTORY = get_session_factory()
    except Exception as exc:  # pragma: no cover - 初始化失败仅提示
        print(f"[formatter] init session factory failed: {exc}")
        SESSION_FACTORY = None

celery_app = Celery(
    "formatter_service",
    broker=REDIS_URL,
    backend=REDIS_URL,
)
celery_app.conf.task_default_queue = FORMATTER_QUEUE


class FormatterDeduper:
    """基于内容哈希的去重器。"""

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
        self.path.write_text(json.dumps(sorted(self.hashes), ensure_ascii=False), encoding="utf-8")

    def is_duplicate(self, content_hash: str) -> bool:
        return content_hash in self.hashes

    def mark(self, content_hash: str) -> None:
        self.hashes.add(content_hash)
        self._save()


DEDUPER = FormatterDeduper(STATE_PATH)


def _is_project_apply(content: str, title: str) -> bool:
    """判断是否属于项目申报类，基于关键词粗判。"""

    text = (title + " " + content).lower()
    keywords = ["申报", "项目", "指南", "遴选", "公告", "资金", "补助", "绩效", "指引"]
    return any(k in text for k in keywords)


def _infer_status(raw: RawArticle) -> Optional[str]:
    """根据分类和元数据推断状态/子分类。"""

    if raw.status:
        return raw.status
    meta_status = raw.metadata.get("status")
    if meta_status:
        return str(meta_status)
    if raw.category == ArticleCategory.PROJECT_APPLY:
        return "pending"
    return None


def _to_article(raw: RawArticle) -> Article:
    """将 RawArticle 转为标准 Article。"""

    cleaned_html = clean_html(raw.content_html)
    soup_text = normalize_text(clean_html(raw.content_html))
    mapped = apply_field_mapping(raw.model_dump())
    tags = mapped.get("tags") or []
    summary = mapped.get("summary")
    content_source = mapped.get("content_source") or raw.content_source
    original_language = (mapped.get("original_source_language") or "").lower()
    if not original_language:
        _, detected_lang, _ = detect_language(soup_text)
        original_language = detected_lang

    return Article(
        id=raw.article_id,
        source_id=raw.source_id or f"src_{raw.source_name}",
        title=raw.title,
        translated_title=None,
        content_html=cleaned_html,
        content_text=soup_text,
        publish_time=raw.publish_time or raw.crawl_time,
        source_name=raw.source_name,
        source_url=raw.source_url,
        category=raw.category,
        status=_infer_status(raw),
        tags=tags,
        crawl_time=raw.crawl_time,
        content_source=content_source,
        summary=summary,
        ai_analysis=None,
        translated_content=None,
        translated_content_html=None,
        original_source_language=original_language or "unknown",
        is_positive_policy=None,
    )


def _enqueue_ai_tasks(article_id: str) -> None:
    """将摘要/正文翻译/标题翻译/分析任务入队。"""

    if not AI_TASKS_AVAILABLE or SESSION_FACTORY is None:
        return
    process_summary.delay(article_id)
    process_translation.delay(article_id)
    process_title_translation.delay(article_id)
    process_analysis.delay(article_id)


def _enqueue_ai_if_exists(article_id: str) -> None:
    """仅在文章已存在数据库时入队 AI，避免重复内容漏跑 AI。"""

    if not (AI_TASKS_AVAILABLE and SESSION_FACTORY):
        return
    with session_scope(SESSION_FACTORY) as session:
        repo = ArticleRepository(session)
        if not repo.get_by_id(article_id):
            return
    _enqueue_ai_tasks(article_id)


def process_raw_article(raw_article: Dict) -> Dict:
    """
    核心处理逻辑，可作为 Celery 任务或脚本复用。
    返回结构:
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
        _enqueue_ai_if_exists(article.id)
        return {
            "skipped": True,
            "reason": "duplicate",
            "article_id": article.id,
        }

    DEDUPER.mark(content_hash)
    _persist_article(article)
    _enqueue_ai_tasks(article.id)
    return {
        "skipped": False,
        "article": article.model_dump(mode="json"),
        "article_id": article.id,
    }


@celery_app.task(name="formatter_service.normalize_article", queue=FORMATTER_QUEUE)
def normalize_article(raw_article: dict) -> dict:
    """Celery 任务：清洗并入库。"""

    return process_raw_article(raw_article)


# --------- Admin-triggered tasks: finance sync & embeddings index ---------


def _parse_month(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    value = value.strip()
    if len(value) == 7:
        value = f"{value}-01"
    datetime.strptime(value, "%Y-%m-%d")
    return value


@celery_app.task(name="formatter.finance_sync", queue=FORMATTER_QUEUE)
def task_finance_sync(month: Optional[str] = None, dry_run: bool = False) -> dict:
    """Trigger finance data sync (optionally single month)."""

    try:
        keep_date = _parse_month(month)
        service = FinanceDataSyncService()
        stats = service.sync(keep_date=keep_date, dry_run=dry_run)
        return {"status": "ok", **stats}
    except (FinanceDataFetcherError, FinanceDataSyncError, ValueError) as exc:
        return {"status": "error", "error": str(exc)}
    except Exception as exc:  # pragma: no cover - unexpected
        return {"status": "error", "error": str(exc)}


def _select_articles_for_index(
    session,
    article_ids: Optional[list[str]] = None,
    days: Optional[int] = None,
    limit: Optional[int] = None,
):
    if article_ids:
        return (
            session.query(orm_models.ArticleORM)
            .filter(orm_models.ArticleORM.id.in_(article_ids))
            .all()
        )
    if days:
        cutoff = datetime.utcnow() - timedelta(days=days)
        q = session.query(orm_models.ArticleORM).filter(orm_models.ArticleORM.publish_time >= cutoff)
        if limit:
            q = q.limit(limit)
        return q.all()
    repo = ArticleRepository(session)
    return repo.list_recent(limit=limit or 1000)


@celery_app.task(name="formatter.embeddings_index", queue=FORMATTER_QUEUE)
def task_embeddings_index(
    article_ids: Optional[list[str]] = None,
    all_articles: bool = False,
    days: Optional[int] = None,
    limit: Optional[int] = None,
    force: bool = False,
) -> dict:
    """Trigger embeddings indexing for articles.

    Args:
        article_ids: Specific article IDs to index.
        all_articles: If True, index all articles.
        days: Only index articles from last N days.
        limit: Max number of articles to index.
        force: If True, re-index existing articles. If False, skip already indexed.
    """

    try:
        session_factory = get_session_factory()
        with session_scope(session_factory) as session:
            if all_articles:
                articles = session.query(orm_models.ArticleORM).all()
            else:
                articles = _select_articles_for_index(session, article_ids=article_ids, days=days, limit=limit)
        docs = chunk_articles(articles)
        added = add_documents(docs, force=force)
        return {"status": "ok", "articles": len(articles), "chunks_indexed": added, "force": force}
    except Exception as exc:  # pragma: no cover - unexpected
        return {"status": "error", "error": str(exc)}


def _persist_article(article: Article) -> None:
    """将 Article 写入数据库（需要 DATABASE_URL）。"""

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
                translated_title=article.translated_title,
                content_html=article.content_html,
                content_text=article.content_text,
                publish_time=article.publish_time,
                source_name=article.source_name,
                source_url=str(article.source_url),
                category=article.category,
                status=article.status,
                tags=article.tags,
                crawl_time=article.crawl_time,
                content_source=article.content_source,
                summary=article.summary,
                ai_analysis=None,
                translated_content=None,
                translated_content_html=article.translated_content_html,
                original_source_language=article.original_source_language,
                is_positive_policy=article.is_positive_policy,
            )
            article_repo.add(new_article)


def _apply_article(target: orm_models.ArticleORM, article: Article) -> None:
    """更新已有记录的字段。"""

    target.title = article.title
    target.translated_title = article.translated_title
    target.content_html = article.content_html
    target.content_text = article.content_text
    target.publish_time = article.publish_time
    target.source_name = article.source_name
    target.source_url = str(article.source_url)
    target.category = article.category
    target.status = article.status
    target.tags = article.tags
    target.crawl_time = article.crawl_time
    target.content_source = article.content_source
    target.summary = article.summary
    target.ai_analysis = article.ai_analysis
    target.translated_content = article.translated_content
    target.translated_content_html = article.translated_content_html
    target.original_source_language = article.original_source_language
    target.is_positive_policy = article.is_positive_policy


def _derive_base_url(url: str) -> str:
    parsed = urlparse(str(url))
    return f"{parsed.scheme}://{parsed.netloc}" if parsed.scheme else str(url)
