"""Embedding helpers using Ollama /api/embeddings."""

from __future__ import annotations

from typing import List

import httpx

from common.utils.config import get_settings

_settings = get_settings()


def get_embedding(text: str) -> List[float]:
    """Call Ollama embedding endpoint to get vector."""

    url = f"{_settings.ollama_base_url.rstrip('/')}/api/embeddings"
    with httpx.Client(timeout=30) as client:
        resp = client.post(url, json={"model": _settings.ollama_embedding_model, "prompt": text})
        resp.raise_for_status()
        data = resp.json()
    embedding = data.get("embedding")
    if not embedding:
        raise RuntimeError("未能从 Ollama 获取 embedding")
    return embedding


def embed_texts(texts: List[str]) -> List[List[float]]:
    return [get_embedding(t) for t in texts]


__all__ = ["get_embedding", "embed_texts"]
