"""简单语言检测封装（返回结构化结果）。"""

from __future__ import annotations
from typing import Tuple

try:  # pragma: no cover - 可选依赖
    from langdetect import DetectorFactory, detect, LangDetectException

    DetectorFactory.seed = 0  # 结果更稳定
    _LANGDETECT_AVAILABLE = True
except Exception:  # pragma: no cover
    _LANGDETECT_AVAILABLE = False


def detect_language(text: str | None) -> Tuple[bool, str, float]:
    """
    返回 (is_chinese, detected_language, confidence)。
    - is_chinese: 是否主要为中文/CJK
    - detected_language: 语言代码（小写，unknown 兜底）
    - confidence: 0-1 置信度（langdetect 未提供，使用经验值）
    """

    if not text or len(text.strip()) < 20:
        return False, "unknown", 0.2
    if not _LANGDETECT_AVAILABLE:
        return False, "unknown", 0.2
    try:
        lang = (detect(text) or "unknown").lower()
        is_chinese = lang.startswith("zh")
        # langdetect 没有直接给出置信度，这里根据是否命中以及文本长度给一个近似值
        confidence = 0.8 if lang != "unknown" else 0.3
        return is_chinese, lang, confidence
    except LangDetectException:
        return False, "unknown", 0.2
