"""pgvector persistence and search for article embeddings."""

from __future__ import annotations

import uuid
from collections import defaultdict
from datetime import date, datetime
from typing import Dict, List

import psycopg
from sqlalchemy.engine.url import make_url
from pgvector.psycopg import register_vector, Vector

from ai_chat.vanna.embeddings import get_embedding
from common.utils.config import get_settings

_settings = get_settings()


def _normalized_db_url() -> str:
    """Strip SQLAlchemy driver suffix for psycopg."""

    url_obj = make_url(_settings.database_url)
    if "+" in url_obj.drivername:
        url_obj = url_obj.set(drivername=url_obj.drivername.split("+")[0])
    return url_obj.render_as_string(hide_password=False)


def _connect():
    conn = psycopg.connect(_normalized_db_url())
    register_vector(conn)
    return conn


def add_documents(docs: List[Dict], force: bool = False) -> int:
    """Insert documents into article_embeddings.

    Args:
        docs: List of documents with text and metadata.
        force: If True, delete existing embeddings for articles before inserting.
               If False, skip articles that already have embeddings.

    Returns:
        Number of chunks inserted.
    """

    if not docs:
        return 0

    # 按 article_id 分组
    by_article: Dict[str, List[Dict]] = defaultdict(list)
    for item in docs:
        article_id = item.get("metadata", {}).get("article_id")
        if article_id:
            by_article[article_id].append(item)

    if not by_article:
        return 0

    inserted = 0
    with _connect() as conn:
        # 跳过模式：先查询已存在的 article_id
        existing_ids: set = set()
        if not force:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT DISTINCT article_id FROM article_embeddings WHERE article_id = ANY(%s)",
                    (list(by_article.keys()),),
                )
                existing_ids = {row[0] for row in cur.fetchall()}

        # 逐篇文章处理，每篇 commit 一次
        for article_id, chunks in by_article.items():
            # 跳过模式：如果文章已存在则跳过
            if not force and article_id in existing_ids:
                continue

            with conn.cursor() as cur:
                if force:
                    # 强制模式：先删除这篇文章的旧切片
                    cur.execute(
                        "DELETE FROM article_embeddings WHERE article_id = %s",
                        (article_id,),
                    )

                for item in chunks:
                    text = item.get("text", "")
                    meta = item.get("metadata", {}) or {}
                    chunk_index = meta.get("chunk_index", 0)
                    if not text:
                        continue

                    embedding = get_embedding(text)
                    cur.execute(
                        """
                        INSERT INTO article_embeddings (id, article_id, chunk_index, chunk_text, embedding, model_name)
                        VALUES (%s, %s, %s, %s, %s, %s)
                        ON CONFLICT (article_id, chunk_index) DO UPDATE SET
                            chunk_text = EXCLUDED.chunk_text,
                            embedding = EXCLUDED.embedding,
                            model_name = EXCLUDED.model_name,
                            updated_at = NOW()
                        """,
                        (
                            str(uuid.uuid4()),
                            article_id,
                            int(chunk_index),
                            text,
                            Vector(embedding),
                            _settings.ollama_embedding_model,
                        ),
                    )
                    inserted += 1

            # 每篇文章处理完 commit 一次
            conn.commit()

    return inserted


def similarity_search(query: str, top_k: int = 5) -> List[Dict]:
    """Return top-k similar chunks with metadata."""

    embedding = get_embedding(query)
    with _connect() as conn, conn.cursor() as cur:
        vec = Vector(embedding)
        cur.execute(
            """
            SELECT
                ae.chunk_text,
                ae.chunk_index,
                ae.article_id,
                a.title,
                a.source_name,
                a.publish_time,
                1 - (ae.embedding <=> %s) AS score
            FROM article_embeddings ae
            JOIN articles a ON a.id = ae.article_id
            ORDER BY ae.embedding <=> %s
            LIMIT %s
            """,
            (vec, vec, top_k),
        )
        rows = cur.fetchall()
        cols = [desc.name for desc in cur.description]
    results: List[Dict] = []
    for row in rows:
        record = dict(zip(cols, row))
        # 转换 datetime 为 ISO 字符串，避免 JSON 序列化错误
        for key, value in record.items():
            if isinstance(value, (datetime, date)):
                record[key] = value.isoformat()
        results.append(
            {
                "text": record.pop("chunk_text", ""),
                "metadata": record,
                "score": record.get("score"),
            }
        )
    return results


__all__ = ["add_documents", "similarity_search"]
