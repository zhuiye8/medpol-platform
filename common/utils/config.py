"""Settings loader with .env support."""

from functools import lru_cache
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Platform configuration."""

    database_url: str = Field(..., validation_alias="DATABASE_URL")
    redis_url: str = Field(..., validation_alias="REDIS_URL")

    openai_api_key: Optional[str] = Field(default=None, validation_alias="OPENAI_API_KEY")
    openai_base_url: str = Field(default="https://api.openai.com/v1", validation_alias="OPENAI_BASE_URL")
    openai_model: str = Field(default="gpt-4o-mini", validation_alias="OPENAI_MODEL")

    deepseek_api_key: Optional[str] = Field(default=None, validation_alias="DEEPSEEK_API_KEY")
    deepseek_base_url: str = Field(default="https://api.deepseek.com/v1", validation_alias="DEEPSEEK_BASE_URL")
    deepseek_model: str = Field(default="deepseek-chat", validation_alias="DEEPSEEK_MODEL")

    ai_primary: str = Field(default="openai", validation_alias="AI_PRIMARY")
    ai_fallback: Optional[str] = Field(default="deepseek", validation_alias="AI_FALLBACK")

    finance_api_base_url: str = Field(default="http://ailianhuan.xyz:8333", validation_alias="FINANCE_API_BASE_URL")
    finance_api_timeout: float = Field(default=30.0, validation_alias="FINANCE_API_TIMEOUT")
    finance_data_endpoint: str = Field(
        default="http://ailianhuan.xyz:8333/financeDate/dataList",
        validation_alias="FINANCE_DATA_ENDPOINT",
    )

    ai_chat_model: str = Field(default="gpt-4", validation_alias="AI_CHAT_MODEL")
    ai_router_model: Optional[str] = Field(default=None, validation_alias="AI_ROUTER_MODEL")

    tavily_api_key: Optional[str] = Field(default=None, validation_alias="TAVILY_API_KEY")

    memory_ttl_minutes: int = Field(default=60, validation_alias="MEMORY_TTL_MINUTES")
    memory_window: int = Field(default=6, validation_alias="MEMORY_WINDOW")
    memory_summary_threshold: int = Field(default=10, validation_alias="MEMORY_SUMMARY_THRESHOLD")
    memory_summary_model: Optional[str] = Field(default=None, validation_alias="MEMORY_SUMMARY_MODEL")
    memory_enable_stagea_cache: bool = Field(default=False, validation_alias="MEMORY_ENABLE_STAGEA_CACHE")

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
