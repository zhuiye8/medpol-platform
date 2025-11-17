"""简单语言检测封装。"""

from __future__ import annotations

try:  # pragma: no cover - 可选依赖
    from langdetect import DetectorFactory, detect, LangDetectException

    DetectorFactory.seed = 0  # 结果更稳定
    _LANGDETECT_AVAILABLE = True
except Exception:  # pragma: no cover
    _LANGDETECT_AVAILABLE = False


def detect_language(text: str | None) -> str:
    if not text or len(text.strip()) < 20:
        return "unknown"
    if not _LANGDETECT_AVAILABLE:
        return "unknown"
    try:
        lang = detect(text)
        return (lang or "unknown").lower()
    except LangDetectException:
        return "unknown"
