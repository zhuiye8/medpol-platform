"""本地回退 Provider：无 Key 时使用简单规则生成结果。"""

from __future__ import annotations

import time

from .base import LLMProvider, LLMRequest, LLMResponse


class MockProvider(LLMProvider):
    """基于简单截断/模板的 mock。"""

    name = "mock"

    def __init__(self, suffix: str = "...") -> None:
        self.suffix = suffix

    def invoke(self, request: LLMRequest) -> LLMResponse:
        start = time.perf_counter()
        text = request.prompt.strip().splitlines()[-1]
        content = text[:160] + self.suffix
        elapsed = int((time.perf_counter() - start) * 1000)
        return LLMResponse(
            content=content,
            provider=self.name,
            model="mock-1",
            latency_ms=elapsed,
            tokens=len(content),
        )
