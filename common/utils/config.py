"""统一配置加载，兼容 .env 与环境变量。"""

from functools import lru_cache
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """平台级配置项。"""

    database_url: str = Field(..., env="DATABASE_URL")
    redis_url: str = Field(..., env="REDIS_URL")

    openai_api_key: Optional[str] = Field(None, env="OPENAI_API_KEY")
    openai_base_url: str = Field("https://api.openai.com/v1", env="OPENAI_BASE_URL")
    openai_model: str = Field("gpt-4o-mini", env="OPENAI_MODEL")

    deepseek_api_key: Optional[str] = Field(None, env="DEEPSEEK_API_KEY")
    deepseek_base_url: str = Field("https://api.deepseek.com/v1", env="DEEPSEEK_BASE_URL")
    deepseek_model: str = Field("deepseek-chat", env="DEEPSEEK_MODEL")

    ai_primary: str = Field("openai", env="AI_PRIMARY")
    ai_fallback: Optional[str] = Field("deepseek", env="AI_FALLBACK")

    # 财务API配置
    finance_api_base_url: str = Field("http://ailianhuan.xyz:8333", env="FINANCE_API_BASE_URL")
    finance_api_timeout: float = Field(30.0, env="FINANCE_API_TIMEOUT")
    finance_data_endpoint: str = Field(
        "http://ailianhuan.xyz:8333/financeDate/dataList",
        env="FINANCE_DATA_ENDPOINT",
    )

    # AI对话配置
    ai_chat_model: str = Field("gpt-4", env="AI_CHAT_MODEL")
    ai_chat_max_history: int = Field(10, env="AI_CHAT_MAX_HISTORY")

    model_config = SettingsConfigDict(
        case_sensitive=False,
        env_file=".env",
        env_file_encoding="utf-8",
        extra="allow",
    )


@lru_cache
def get_settings() -> Settings:
    """懒加载配置，避免重复读取。"""

    return Settings()
