"""Конфигурация приложения (pydantic-settings + переменные окружения)."""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Все настройки читаются из переменных окружения или .env."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- LLM (OpenAI-совместимый) ---
    openai_api_key: str = Field(..., alias="OPENAI_API_KEY")
    openai_base_url: str = Field(..., alias="OPENAI_BASE_URL")
    openai_model: str = Field(..., alias="OPENAI_MODEL")

    # --- Redis ---
    redis_url: str = Field("redis://localhost:6379/0", alias="REDIS_URL")

    # --- MCP-сервер CBR ---
    mcp_cbr_command: str = Field("atomno-mcp-cbr-rates", alias="MCP_CBR_COMMAND")
    mcp_cbr_args: list[str] = Field(default_factory=list, alias="MCP_CBR_ARGS")

    # --- Кэш и сессии ---
    cache_ttl_seconds: int = Field(3600, alias="CACHE_TTL_SECONDS", ge=1)
    session_ttl_seconds: int = Field(86400, alias="SESSION_TTL_SECONDS", ge=1)

    # --- HTTP-приложение ---
    app_host: str = Field("0.0.0.0", alias="APP_HOST")
    app_port: int = Field(8000, alias="APP_PORT", ge=1, le=65535)
    log_level: str = Field("INFO", alias="LOG_LEVEL")

    @field_validator("mcp_cbr_args", mode="before")
    @classmethod
    def _split_args(cls, value: object) -> object:
        """Позволяет задавать MCP_CBR_ARGS через запятую в .env (например, '--flag,value')."""
        if isinstance(value, str):
            return [chunk.strip() for chunk in value.split(",") if chunk.strip()]
        return value

    @field_validator("log_level")
    @classmethod
    def _normalize_log_level(cls, value: str) -> str:
        normalized = value.upper()
        if normalized not in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}:
            msg = f"Unsupported log level: {value}"
            raise ValueError(msg)
        return normalized


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Singleton-доступ к настройкам (читаются один раз)."""
    return Settings()  # type: ignore[call-arg]
