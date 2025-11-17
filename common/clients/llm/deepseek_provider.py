"""DeepSeek Provider，实现与 DeepSeek API 的对接。"""

from __future__ import annotations

import time
from typing import Optional

import httpx

from .base import LLMProvider, LLMRequest, LLMResponse


class DeepSeekProvider(LLMProvider):
    """封装 DeepSeek Chat 完整流程。"""

    name = "deepseek"

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.deepseek.com/v1",
        default_model: str = "deepseek-chat",
        timeout: float = 45,
    ) -> None:
        self._client = httpx.Client(
            base_url=base_url,
            timeout=timeout,
            headers={"Authorization": f"Bearer {api_key}"},
        )
        self._default_model = default_model

    def invoke(self, request: LLMRequest) -> LLMResponse:
        """构造 DeepSeek 请求，返回统一响应。"""

        messages = [
            {
                "role": "system",
                "content": request.meta.get(
                    "system_prompt", "你是一名严谨的医药政策翻译与分析助手。"
                ),
            },
            {"role": "user", "content": request.prompt},
        ]
        model = request.meta.get("model") or self._default_model
        start = time.perf_counter()
        response = self._client.post(
            "/chat/completions",
            json={
                "model": model,
                "messages": messages,
                "temperature": request.meta.get("temperature", 0.15),
            },
        )
        elapsed = int((time.perf_counter() - start) * 1000)
        response.raise_for_status()
        data = response.json()
        content = data["choices"][0]["message"]["content"]
        usage = data.get("usage", {})
        return LLMResponse(
            content=content,
            provider=self.name,
            model=model,
            tokens=usage.get("total_tokens"),
            latency_ms=elapsed,
        )

    def close(self) -> None:
        """释放 HTTP 会话资源。"""

        self._client.close()

    def __del__(self) -> None:  # pragma: no cover - 防御性释放
        try:
            self.close()
        except Exception:
            pass
