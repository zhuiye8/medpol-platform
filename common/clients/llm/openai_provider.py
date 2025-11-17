"""OpenAI Provider 实现，负责和官方/代理 API 通讯。"""

from __future__ import annotations

import time
from typing import Optional

import httpx

from .base import LLMProvider, LLMRequest, LLMResponse


class OpenAIProvider(LLMProvider):
    """封装 OpenAI Chat Completions 接口。"""

    name = "openai"

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.openai.com/v1",
        default_model: str = "gpt-4o-mini",
        timeout: float = 30,
    ) -> None:
        self._api_key = api_key
        self._default_model = default_model
        self._client = httpx.Client(
            base_url=base_url,
            timeout=timeout,
            headers={"Authorization": f"Bearer {api_key}"},
        )

    def invoke(self, request: LLMRequest) -> LLMResponse:
        """构造标准 Chat Completions 请求并返回统一响应。"""

        messages = [
            {
                "role": "system",
                "content": request.meta.get(
                    "system_prompt", "你是一名医药政策分析助手，请准确输出。"
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
                "temperature": request.meta.get("temperature", 0.2),
            },
        )
        elapsed = int((time.perf_counter() - start) * 1000)
        response.raise_for_status()
        data = response.json()
        choice = data["choices"][0]["message"]["content"]
        usage = data.get("usage", {})
        return LLMResponse(
            content=choice,
            provider=self.name,
            model=model,
            tokens=usage.get("total_tokens"),
            latency_ms=elapsed,
        )

    def close(self) -> None:
        """释放 HTTP 连接资源。"""

        self._client.close()

    def __del__(self) -> None:  # pragma: no cover - 防御性释放
        try:
            self.close()
        except Exception:
            pass
