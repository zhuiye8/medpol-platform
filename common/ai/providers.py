"""LLM Provider 工厂"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import List, Optional

from openai import OpenAI

from common.utils.config import get_settings

logger = logging.getLogger(__name__)


class AIProviderError(RuntimeError):
    """LLM Provider 异常"""


@dataclass
class ProviderClient:
    client: OpenAI
    model: str


class AIProviderFactory:
    """根据配置创建 OpenAI / DeepSeek 客户端"""

    def __init__(self) -> None:
        self.settings = get_settings()

    def get_client(self, purpose: str = "chat") -> ProviderClient:
        providers = self._preferred_providers()
        last_error: Optional[str] = None

        for provider in providers:
            try:
                return self._build_client(provider, purpose=purpose)
            except AIProviderError as exc:  # pragma: no cover
                logger.warning("AI Provider %s 不可用: %s", provider, exc)
                last_error = str(exc)
                continue

        raise AIProviderError(last_error or "未配置可用的 AI Provider")

    def _preferred_providers(self) -> List[str]:
        prefs: List[str] = []
        if self.settings.ai_primary:
            prefs.append(self.settings.ai_primary)
        if self.settings.ai_fallback and self.settings.ai_fallback not in prefs:
            prefs.append(self.settings.ai_fallback)
        return prefs or ["openai"]

    def _build_client(self, provider: str, purpose: str) -> ProviderClient:
        provider = provider.lower()
        if provider == "deepseek":
            api_key = self.settings.deepseek_api_key
            if not api_key:
                raise AIProviderError("未配置 DEEPSEEK_API_KEY")
            base_url = self.settings.deepseek_base_url or "https://api.deepseek.com/v1"
            model = self._select_model(
                purpose=purpose,
                primary=self.settings.deepseek_model or "deepseek-chat",
                router_override=self.settings.ai_router_model,
            )
            client = OpenAI(api_key=api_key, base_url=base_url)
            return ProviderClient(client=client, model=model)

        # 默认 openai / openrouter
        api_key = self.settings.openai_api_key
        if not api_key:
            raise AIProviderError("未配置 OPENAI_API_KEY")
        base_url = self.settings.openai_base_url or "https://api.openai.com/v1"
        model = self._select_model(
            purpose=purpose,
            primary=self.settings.ai_chat_model or self.settings.openai_model,
            router_override=self.settings.ai_router_model,
        )
        client = OpenAI(api_key=api_key, base_url=base_url)
        return ProviderClient(client=client, model=model)

    def _select_model(self, *, purpose: str, primary: Optional[str], router_override: Optional[str]) -> str:
        if purpose == "router" and router_override:
            return router_override
        if not primary:
            raise AIProviderError("未配置可用模型")
        return primary


__all__ = ["AIProviderFactory", "AIProviderError", "ProviderClient"]
