"""pgvector persistence and search for article embeddings."""

from __future__ import annotations

import uuid
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


def add_documents(docs: List[Dict]) -> int:
    """Insert documents into article_embeddings."""

    if not docs:
        return 0
    inserted = 0
    with _connect() as conn, conn.cursor() as cur:
        for item in docs:
            text = item.get("text", "")
            meta = item.get("metadata", {}) or {}
            article_id = meta.get("article_id")
            chunk_index = meta.get("chunk_index", 0)
            if not text or not article_id:
                continue
            embedding = get_embedding(text)
            cur.execute(
                """
                INSERT INTO article_embeddings (id, article_id, chunk_index, chunk_text, embedding, model_name)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (id) DO NOTHING
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
        results.append(
            {
                "text": record.pop("chunk_text", ""),
                "metadata": record,
                "score": record.get("score"),
            }
        )
    return results


__all__ = ["add_documents", "similarity_search"]
