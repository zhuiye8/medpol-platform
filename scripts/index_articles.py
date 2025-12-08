"""Index articles into pgvector using Ollama embeddings (no LangChain)."""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import List

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ai_chat.vanna.vectorstore import add_documents
from common.persistence.database import get_session_factory, session_scope
from common.persistence.repository import ArticleRepository
from common.utils.config import get_settings
from common.utils.env import load_env


def _chunk_text(text: str, chunk_size: int = 800, overlap: int = 100) -> List[str]:
    """Simple sliding window chunker."""
    if not text:
        return []
    chunks = []
    start = 0
    length = len(text)
    while start < length:
        end = min(length, start + chunk_size)
        chunks.append(text[start:end])
        if end == length:
            break
        start = end - overlap
    return chunks


def chunk_articles(docs: List) -> List[dict]:
    chunks: List[dict] = []
    for art in docs:
        pieces = _chunk_text(art.content_text or "")
        for idx, piece in enumerate(pieces):
            chunks.append(
                {
                    "text": piece,
                    "metadata": {
                        "article_id": art.id,
                        "chunk_index": idx,
                        "title": art.title,
                        "category": art.category.value if hasattr(art.category, "value") else art.category,
                        "publish_time": art.publish_time.isoformat(),
                        "source_name": art.source_name,
                        "source_url": art.source_url,
                    },
                }
            )
    return chunks


def main(days: int | None = None, limit: int | None = None):
    load_env()
    settings = get_settings()
    session_factory = get_session_factory()
    with session_scope(session_factory) as session:
        repo = ArticleRepository(session)
        articles = repo.list_recent(limit=limit or 1000)
        if days:
            cutoff = datetime.utcnow() - timedelta(days=days)
            articles = [a for a in articles if a.publish_time >= cutoff]
    docs = chunk_articles(articles)
    added = add_documents(docs)
    print(f"Indexed {added} chunks to collection {settings.pgvector_collection_name}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Index articles into pgvector for RAG.")
    parser.add_argument("--days", type=int, default=None, help="Only index articles in last N days")
    parser.add_argument("--limit", type=int, default=None, help="Max articles to load")
    args = parser.parse_args()
    main(days=args.days, limit=args.limit)
