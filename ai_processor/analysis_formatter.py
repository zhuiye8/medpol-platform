"""AI 分析结果的格式化与兜底逻辑。"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Tuple


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


def _ensure_list(value: Any) -> List[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


def format_analysis_content(content: str) -> Tuple[Dict[str, Any], bool]:
    """
    对 LLM 输出进行格式化：
    - 成功时返回结构化 dict（含 key_points/risks/actions）
    - 若解析失败，返回带 raw_text 的兜底结构
    """

    raw = content.strip()
    cleaned = _strip_code_fences(raw)
    try:
        data = json.loads(cleaned)
        if not isinstance(data, dict):
            raise ValueError("analysis output is not dict")
        normalized = {
            "structured": True,
            "key_points": _ensure_list(data.get("key_points")),
            "risks": _ensure_list(data.get("risks")),
            "actions": _ensure_list(data.get("actions")),
        }
        if not any(normalized[key] for key in ("key_points", "risks", "actions")):
            raise ValueError("empty analysis data")
        return normalized, True
    except Exception as exc:  # pylint: disable=broad-except
        logger.warning("解析 AI 分析失败，将保存原始文本：%s", exc)
        return {
            "structured": False,
            "raw_text": raw,
        }, False
