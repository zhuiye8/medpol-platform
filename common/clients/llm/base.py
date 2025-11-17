"""大模型 Provider 抽象，统一 OpenAI / DeepSeek / 自研接口。"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass
class LLMRequest:
    """描述一次 AI 调用的请求."""

    prompt: str
    task_type: str  # summary / translation / analysis
    meta: Dict[str, Any]


@dataclass
class LLMResponse:
    """统一封装模型输出."""

    content: str
    provider: str
    model: str
    tokens: Optional[int] = None
    latency_ms: Optional[int] = None


class LLMProvider(ABC):
    """所有 Provider 必须实现的接口."""

    name: str

    @abstractmethod
    def invoke(self, request: LLMRequest) -> LLMResponse:  # pragma: no cover - 接口定义
        """执行模型调用，返回统一结构。"""

