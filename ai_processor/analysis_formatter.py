"""Format and normalize AI analysis outputs."""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, Tuple


logger = logging.getLogger("ai_processor.analysis")


def _strip_code_fences(text: str) -> str:
    stripped = text.strip()
    if "```" not in stripped:
        return stripped
    parts = stripped.split("```")
    for part in parts:
        candidate = part.strip()
        if not candidate:
            continue
        if candidate.lower().startswith("json"):
            candidate = candidate.split("\n", 1)[1] if "\n" in candidate else ""
            candidate = candidate.strip()
        if candidate:
            return candidate
    return stripped


def format_analysis_content(content: str) -> Tuple[Dict[str, Any], bool]:
    """
    将 LLM 输出整理为 {content, is_positive_policy}。
    返回 (result, structured)；structured=False 时 result 仅包含 raw_text。
    """

    raw = content.strip()
    cleaned = _strip_code_fences(raw)
    try:
        data = json.loads(cleaned)
        if not isinstance(data, dict):
            raise ValueError("analysis output is not dict")
        result = {
            "content": data.get("content") or raw,
            "is_positive_policy": data.get("is_positive_policy"),
        }
        return result, True
    except Exception as exc:  # pylint: disable=broad-except
        logger.warning("解析 AI 解读失败，返回原始文本: %s", exc)
        return {
            "content": raw,
            "is_positive_policy": None,
        }, False
