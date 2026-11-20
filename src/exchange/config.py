from __future__ import annotations

from functools import lru_cache

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    server_port: int = Field(default=8080, ge=1, le=65535)
    log_level: str = "INFO"

    exchange_provider_url: str | None = None
    exchange_provider_api_key: SecretStr | None = None
    exchange_provider_requires_api_key: bool = False
    exchange_provider_version: str = Field(default="v1", min_length=1, max_length=32)
    exchange_provider_timeout_seconds: float = Field(default=2.0, gt=0, le=30)
    exchange_provider_retries: int = Field(default=1, ge=0, le=3)
    exchange_provider_max_concurrency: int = Field(default=20, ge=1, le=1000)
    exchange_provider_spread_bps: float = Field(default=0.0, ge=0, le=1000)

    cache_redis_url: str = "redis://redis:6379/0"
    cache_enabled: bool = False
    cache_ttl_seconds: int = Field(default=60, ge=1, le=3600)

    jwt_secret: SecretStr = Field(min_length=32)
    jwt_issuer: str | None = None
    jwt_audience: str | None = None

    @field_validator("log_level")
    @classmethod
    def normalize_log_level(cls, value: str) -> str:
        level = value.upper()
        allowed = {"CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"}
        if level not in allowed:
            raise ValueError(f"LOG_LEVEL must be one of {sorted(allowed)}")
        return level

    @field_validator("exchange_provider_url")
    @classmethod
    def normalize_provider_url(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip().rstrip("/")
        if not normalized:
            return None
        if not normalized.startswith(("http://", "https://")):
            raise ValueError("EXCHANGE_PROVIDER_URL must be an http(s) URL")
        return normalized

    @field_validator("jwt_issuer", "jwt_audience", mode="before")
    @classmethod
    def blank_to_none(cls, value: object) -> object:
        if isinstance(value, str) and not value.strip():
            return None
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
