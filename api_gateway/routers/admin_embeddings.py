"""Embeddings admin APIs: stats, article list, index trigger."""

from __future__ import annotations

from typing import Optional, List

from fastapi import APIRouter, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from celery.result import AsyncResult

from formatter_service.worker import celery_app, FORMATTER_QUEUE

from common.persistence.database import get_session_factory, session_scope
from common.persistence.models import ArticleEmbeddingORM, ArticleORM
from common.utils.env import load_env

router = APIRouter()


class EmbeddingIndexRequest(BaseModel):
    """Request body for triggering embedding indexing."""
    article_ids: Optional[List[str]] = None
    all: bool = False
    force: bool = False  # True: 覆盖已存在的, False: 跳过已存在的


load_env()


def _get_session():
    return get_session_factory()


@router.get("/embeddings/stats")
def embeddings_stats():
    factory = _get_session()
    with session_scope(factory) as session:
        total_articles = session.scalar(select(func.count()).select_from(ArticleORM)) or 0
        embedded_articles = (
            session.query(ArticleEmbeddingORM.article_id).distinct().count()
        )
        total_chunks = session.scalar(select(func.count()).select_from(ArticleEmbeddingORM)) or 0
    return {
        "code": 0,
        "message": "ok",
        "data": {
            "total_articles": total_articles,
            "embedded_articles": embedded_articles,
            "total_chunks": total_chunks,
        },
    }


@router.get("/embeddings/articles")
def embeddings_articles(
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    factory = _get_session()
    with session_scope(factory) as session:
        # 获取总数
        total = session.scalar(select(func.count()).select_from(ArticleORM)) or 0
        # 分页查询
        rows = (
            session.query(ArticleORM)
            .order_by(ArticleORM.publish_time.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )
        embedded_ids = {
            rid
            for (rid,) in session.query(ArticleEmbeddingORM.article_id)
            .distinct()
            .all()
        }
    data = []
    for art in rows:
        data.append(
            {
                "id": art.id,
                "title": art.title,
                "category": art.category.value if hasattr(art.category, "value") else art.category,
                "publish_time": art.publish_time,
                "source_name": art.source_name,
                "embedded": art.id in embedded_ids,
            }
        )
    return {"code": 0, "message": "ok", "data": {"items": data, "total": total}}


@router.get("/embeddings/articles/{article_id}")
def embeddings_article_detail(article_id: str):
    factory = _get_session()
    with session_scope(factory) as session:
        chunks = (
            session.query(ArticleEmbeddingORM)
            .filter(ArticleEmbeddingORM.article_id == article_id)
            .order_by(ArticleEmbeddingORM.chunk_index.asc())
            .all()
        )
    data = [
        {
            "chunk_index": c.chunk_index,
            "chunk_text": c.chunk_text,
            "model_name": c.model_name,
        }
        for c in chunks
    ]
    return {"code": 0, "message": "ok", "data": data}


@router.post("/embeddings/index")
def embeddings_index(req: EmbeddingIndexRequest):
    """Trigger embedding indexing via Celery."""

    task = celery_app.send_task(
        "formatter.embeddings_index",
        kwargs={
            "article_ids": req.article_ids,
            "all_articles": req.all,
            "force": req.force,
        },
        queue=FORMATTER_QUEUE,
    )
    return {"code": 0, "message": "index triggered", "data": {"task_id": task.id, "force": req.force}}


@router.get("/tasks/{task_id}")
def embeddings_task_status(task_id: str):
    res = AsyncResult(task_id, app=celery_app)
    return {
        "code": 0,
        "message": "ok",
        "data": {"task_id": task_id, "state": res.state, "result": res.result if res.ready() else None},
    }
