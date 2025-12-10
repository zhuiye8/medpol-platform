"""Settings loader with .env support."""

from functools import lru_cache
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Platform configuration."""

    database_url: str = Field(..., validation_alias="DATABASE_URL")
    redis_url: str = Field(..., validation_alias="REDIS_URL")

    # --- AI 分析（摘要翻译/分析）---
    ai_analysis_provider: Optional[str] = Field(default=None, validation_alias="AI_ANALYSIS_PROVIDER")
    ai_analysis_model: Optional[str] = Field(default=None, validation_alias="AI_ANALYSIS_MODEL")
    ai_analysis_fallback_provider: Optional[str] = Field(default=None, validation_alias="AI_ANALYSIS_FALLBACK_PROVIDER")
    ai_analysis_fallback_model: Optional[str] = Field(default=None, validation_alias="AI_ANALYSIS_FALLBACK_MODEL")

    # --- AI 对话 ---
    ai_chat_provider: Optional[str] = Field(default=None, validation_alias="AI_CHAT_PROVIDER")
    ai_chat_model: Optional[str] = Field(default=None, validation_alias="AI_CHAT_MODEL")
    ai_chat_fallback_provider: Optional[str] = Field(default=None, validation_alias="AI_CHAT_FALLBACK_PROVIDER")
    ai_chat_fallback_model: Optional[str] = Field(default=None, validation_alias="AI_CHAT_FALLBACK_MODEL")

    openai_api_key: Optional[str] = Field(default=None, validation_alias="OPENAI_API_KEY")
    openai_base_url: str = Field(default="https://api.openai.com/v1", validation_alias="OPENAI_BASE_URL")
    openai_model: str = Field(default="gpt-4o-mini", validation_alias="OPENAI_MODEL")

    deepseek_api_key: Optional[str] = Field(default=None, validation_alias="DEEPSEEK_API_KEY")
    deepseek_base_url: str = Field(default="https://api.deepseek.com/v1", validation_alias="DEEPSEEK_BASE_URL")
    deepseek_beta_url: str = Field(default="https://api.deepseek.com/beta", validation_alias="DEEPSEEK_BETA_URL")
    deepseek_model: str = Field(default="deepseek-chat", validation_alias="DEEPSEEK_MODEL")

    ollama_base_url: str = Field(default="http://localhost:11434", validation_alias="OLLAMA_BASE_URL")
    ollama_chat_model: Optional[str] = Field(default=None, validation_alias="OLLAMA_CHAT_MODEL")
    ollama_analysis_model: Optional[str] = Field(default=None, validation_alias="OLLAMA_ANALYSIS_MODEL")

    ai_primary: str = Field(default="ollama", validation_alias="AI_PRIMARY")
    ai_fallback: Optional[str] = Field(default=None, validation_alias="AI_FALLBACK")
    ai_strict_mode: bool = Field(default=False, validation_alias="AI_STRICT_MODE")
    ai_json_fallback: bool = Field(default=True, validation_alias="AI_JSON_FALLBACK")
    ai_router_model: Optional[str] = Field(default=None, validation_alias="AI_ROUTER_MODEL")

    # --- RAG / 向量检索 ---
    ollama_embedding_model: str = Field(default="bge-m3", validation_alias="OLLAMA_EMBEDDING_MODEL")
    pgvector_collection_name: str = Field(default="medpol_articles", validation_alias="PGVECTOR_COLLECTION_NAME")
    pgvector_embedding_dimension: int = Field(default=1024, validation_alias="PGVECTOR_EMBEDDING_DIMENSION")

    # --- 对话记忆 ---
    memory_window: int = Field(default=30, validation_alias="MEMORY_WINDOW")
    memory_ttl_minutes: int = Field(default=4320, validation_alias="MEMORY_TTL_MINUTES")  # 3 days

    # --- 可观测性（可选） ---
    langfuse_enabled: bool = Field(default=False, validation_alias="LANGFUSE_ENABLED")
    langfuse_public_key: Optional[str] = Field(default=None, validation_alias="LANGFUSE_PUBLIC_KEY")
    langfuse_secret_key: Optional[str] = Field(default=None, validation_alias="LANGFUSE_SECRET_KEY")
    langfuse_host: str = Field(default="http://localhost:3000", validation_alias="LANGFUSE_HOST")

    finance_api_base_url: str = Field(default="http://ailianhuan.xyz:8333", validation_alias="FINANCE_API_BASE_URL")
    finance_api_timeout: float = Field(default=30.0, validation_alias="FINANCE_API_TIMEOUT")
    finance_data_endpoint: str = Field(
        default="http://ailianhuan.xyz:8333/financeDate/dataList",
        validation_alias="FINANCE_DATA_ENDPOINT",
    )

    # --- 嵌入式聊天认证 ---
    embed_auth_token: Optional[str] = Field(default=None, validation_alias="EMBED_AUTH_TOKEN")

    model_config = SettingsConfigDict(
        case_sensitive=False,
        env_file=".env",
        env_file_encoding="utf-8",
        extra="allow",
    )


@lru_cache
def get_settings() -> Settings:
    """Return cached settings instance."""

    return Settings()
