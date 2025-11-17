"""大模型 Provider 路由器，支持主备与任务级别选择。"""

from __future__ import annotations

from typing import Dict, Optional

from .base import LLMProvider, LLMRequest, LLMResponse


class ProviderRouter:
    """根据配置挑选合适的 Provider，并在失败时回退。"""

    def __init__(self, primary: str, fallback: Optional[str] = None) -> None:
        self._registry: Dict[str, LLMProvider] = {}
        self._primary = primary
        self._fallback = fallback

    def register(self, provider: LLMProvider) -> None:
        """注册 Provider，名称使用实现类的 name 属性。"""

        self._registry[provider.name] = provider

    def invoke(self, request: LLMRequest) -> LLMResponse:
        """
        根据请求信息挑选 Provider。
        规则：
        1. 若 meta 中指定 provider，则优先使用。
        2. 否则按 primary → fallback 顺序尝试。
        """

        preferred = request.meta.get("provider")
        if preferred:
            provider = self._registry.get(preferred)
            if not provider:
                raise ValueError(f"未注册 provider: {preferred}")
            return provider.invoke(request)

        provider = self._registry.get(self._primary)
        if not provider:
            if self._fallback:
                fallback_provider = self._registry.get(self._fallback)
                if fallback_provider:
                    return fallback_provider.invoke(request)
            raise ValueError(f"未注册主 provider: {self._primary}")

        try:
            return provider.invoke(request)
        except Exception:
            if not self._fallback:
                raise
            backup = self._registry.get(self._fallback)
            if not backup:
                raise
            return backup.invoke(request)

    def close(self) -> None:
        """关闭所有 Provider，释放资源。"""

        for provider in self._registry.values():
            close = getattr(provider, "close", None)
            if callable(close):
                close()
