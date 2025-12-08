"""Factory to create Vanna LLM services for chat/analysis."""

from __future__ import annotations

from vanna.core.llm import LlmService
from vanna.integrations.ollama import OllamaLlmService
from vanna.integrations.openai import OpenAILlmService

from common.utils.config import get_settings

_settings = get_settings()


def build_llm_service() -> LlmService:
    """
    Create an LLM service based on configuration.

    Providers:
    - ollama: local Ollama API
    - openai: OpenAI 兼容接口
    - deepseek: 走 OpenAI 兼容（base_url+key）
    """

    provider = (_settings.ai_chat_provider or _settings.ai_primary or "ollama").lower()
    model = (
        _settings.ai_chat_model
        or _settings.ollama_chat_model
        or _settings.openai_model
        or "gpt-4o-mini"
    )

    if provider == "ollama":
        return OllamaLlmService(model=model, host=_settings.ollama_base_url)

    if provider in {"openai", "deepseek"}:
        api_key = _settings.openai_api_key or _settings.deepseek_api_key
        base_url = (
            _settings.openai_base_url
            if provider == "openai"
            else _settings.deepseek_beta_url if _settings.ai_strict_mode else _settings.deepseek_base_url
        )
        return OpenAILlmService(model=model, api_key=api_key, base_url=base_url)

    # Fallback to OpenAI compatible
    return OpenAILlmService(model=model, api_key=_settings.openai_api_key, base_url=_settings.openai_base_url)


__all__ = ["build_llm_service"]
