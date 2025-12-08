"""LLM Provider 工厂，支持 OpenAI / DeepSeek / Ollama."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import List, Optional

import httpx
from openai import OpenAI

from common.utils.config import get_settings

logger = logging.getLogger(__name__)


class AIProviderError(RuntimeError):
    """LLM Provider 异常"""


@dataclass
class ProviderClient:
    client: any
    model: str
    provider_name: str
    supports_strict_mode: bool


class _OllamaChatCompletions:
    """Minimal shim to mimic OpenAI chat.completions.create for Ollama."""

    def __init__(self, base_url: str) -> None:
        self.base_url = base_url.rstrip("/")

    def create(self, model: str, messages: list, temperature: float = 0.3, **kwargs):
        payload = {"model": model, "messages": messages, "stream": False, "options": {"temperature": temperature}}
        resp = httpx.post(f"{self.base_url}/api/chat", json=payload, timeout=60)
        resp.raise_for_status()
        data = resp.json()
        content = data.get("message", {}).get("content", "") if isinstance(data, dict) else ""
        return type(
            "OllamaResp",
            (),
            {
                "choices": [type("Choice", (), {"message": type("Msg", (), {"content": content})()})()],
                "usage": None,
            },
        )


class _OllamaClient:
    def __init__(self, base_url: str) -> None:
        self.chat = type("ChatNamespace", (), {"completions": _OllamaChatCompletions(base_url)})()


class AIProviderFactory:
    """根据配置创建 OpenAI / DeepSeek / Ollama 客户端"""

    def __init__(self) -> None:
        self.settings = get_settings()

    def get_client(self, purpose: str = "analysis") -> ProviderClient:
        providers = self._preferred_providers(purpose)
        last_error: Optional[str] = None
        for provider in providers:
            try:
                return self._build_client(provider, purpose=purpose)
            except AIProviderError as exc:  # pragma: no cover
                logger.warning("AI Provider %s 不可用: %s", provider, exc)
                last_error = str(exc)
                continue
        raise AIProviderError(last_error or "未配置可用的 AI Provider")

    def _preferred_providers(self, purpose: str) -> List[str]:
        prefs: List[str] = []
        if purpose == "chat":
            primary = self.settings.ai_chat_provider or self.settings.ai_primary
            fallback = self.settings.ai_chat_fallback_provider or self.settings.ai_fallback
        else:
            primary = self.settings.ai_analysis_provider or self.settings.ai_primary
            fallback = self.settings.ai_analysis_fallback_provider or self.settings.ai_fallback
        if primary:
            prefs.append(primary)
        if fallback and fallback not in prefs:
            prefs.append(fallback)
        return prefs or ["ollama"]

    def _build_client(self, provider: str, purpose: str) -> ProviderClient:
        provider = provider.lower()
        if provider == "ollama":
            model = self._select_model(provider="ollama", purpose=purpose)
            client = _OllamaClient(self.settings.ollama_base_url)
            return ProviderClient(client=client, model=model, provider_name="ollama", supports_strict_mode=False)

        if provider == "deepseek":
            api_key = self.settings.deepseek_api_key
            if not api_key:
                raise AIProviderError("未配置 DEEPSEEK_API_KEY")
            base_url = (
                self.settings.deepseek_beta_url
                if self.settings.ai_strict_mode
                else self.settings.deepseek_base_url or "https://api.deepseek.com/v1"
            )
            model = self._select_model(provider="deepseek", purpose=purpose)
            client = OpenAI(api_key=api_key, base_url=base_url)
            return ProviderClient(
                client=client,
                model=model,
                provider_name="deepseek",
                supports_strict_mode=bool(self.settings.ai_strict_mode),
            )

        # 默认 openai / openrouter
        api_key = self.settings.openai_api_key
        if not api_key:
            raise AIProviderError("未配置 OPENAI_API_KEY")
        base_url = self.settings.openai_base_url or "https://api.openai.com/v1"
        model = self._select_model(provider="openai", purpose=purpose)
        client = OpenAI(api_key=api_key, base_url=base_url)
        return ProviderClient(client=client, model=model, provider_name="openai", supports_strict_mode=True)

    def _select_model(self, *, provider: str, purpose: str) -> str:
        if purpose == "router" and self.settings.ai_router_model:
            return self.settings.ai_router_model

        if provider == "deepseek":
            if purpose == "chat":
                return (
                    self.settings.ai_chat_model
                    or self.settings.ai_chat_fallback_model
                    or self.settings.deepseek_model
                    or "deepseek-chat"
                )
            return (
                self.settings.ai_analysis_model
                or self.settings.ai_analysis_fallback_model
                or self.settings.deepseek_model
                or "deepseek-chat"
            )

        if provider == "ollama":
            if purpose == "chat":
                return self.settings.ollama_chat_model or self.settings.ai_chat_model or "llama3"
            return self.settings.ollama_analysis_model or self.settings.ai_analysis_model or "llama3"

        # 默认 openai / openrouter
        if purpose == "chat":
            return (
                self.settings.ai_chat_model
                or self.settings.ai_chat_fallback_model
                or self.settings.openai_model
            )

        return (
            self.settings.ai_analysis_model
            or self.settings.ai_analysis_fallback_model
            or self.settings.openai_model
        )

    def build_response_format(
        self,
        schema: dict,
        *,
        name: str,
        strict: bool = True,
        provider: Optional[str] = None,
        purpose: str = "analysis",
    ):
        default_provider = (
            self.settings.ai_analysis_provider if purpose != "chat" else self.settings.ai_chat_provider
        )
        target_provider = (provider or default_provider or self.settings.ai_primary or "ollama").lower()
        if strict and target_provider == "openai":
            return {"type": "json_schema", "json_schema": {"name": name, "strict": True, "schema": schema}}
        if strict and target_provider == "deepseek" and self.settings.ai_strict_mode:
            return {"type": "json_schema", "json_schema": {"name": name, "strict": True, "schema": schema}}
        return {"type": "json_object"}


__all__ = ["AIProviderFactory", "AIProviderError", "ProviderClient"]
