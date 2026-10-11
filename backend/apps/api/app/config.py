"""Application configuration using Pydantic Settings."""

import json
from functools import lru_cache
from typing import Any

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central configuration for Enterprise RAG API."""

    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Environment
    APP_ENV: str = "development"
    LOG_LEVEL: str = "INFO"
    DEBUG: bool = False

    # Server
    API_HOST: str = "0.0.0.0"  # noqa: S104 — overridden by .env in all environments
    API_PORT: int = 8000
    CORS_ORIGINS: list[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def parse_cors_origins(cls, v: Any) -> list[str]:
        if isinstance(v, str):
            v = v.strip()
            if v.startswith("[") and v.endswith("]"):
                try:
                    return json.loads(v)
                except (json.JSONDecodeError, TypeError):
                    # Malformed JSON list — fall through to comma-split parsing
                    pass
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        if isinstance(v, list):
            return v
        return ["http://localhost:3000"]

    # Database
    DATABASE_URL: str = "sqlite+aiosqlite:///./enterprise_rag_dev.db"
    DATABASE_URL_SYNC: str = "sqlite:///./enterprise_rag_dev.db"

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # Qdrant
    QDRANT_URL: str = "http://localhost:6333"
    QDRANT_API_KEY: str | None = None

    # Security & Auth
    JWT_SECRET: str = "default_development_secret_do_not_use_in_production_min_32_bytes"  # noqa: S105 — must be overridden via JWT_SECRET env var
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # LLM Providers (Rule 4: secrets in env vars only)
    LLM_PROVIDER: str = "groq"  # groq | openrouter | ollama
    LLM_MODEL: str = "openai/gpt-oss-120b"
    GROQ_API_KEY: str | None = None
    OPENROUTER_API_KEY: str | None = None
    OLLAMA_BASE_URL: str = "http://localhost:11434"

    # LLM safety limits (Rule 15: timeouts + cost-DOS prevention)
    LLM_TIMEOUT_SECONDS: int = 60
    LLM_MAX_TOKENS: int = 1024
    LLM_RATE_LIMIT_PER_MINUTE: int = 10  # per-user, per query endpoint

    # Agentic RAG limits (Phase 11)
    AGENT_MAX_RETRIEVAL_ATTEMPTS: int = 3
    AGENT_MAX_TOOL_CALLS: int = 10

    # SSE streaming limits (Risk 3 mitigation)
    SSE_MAX_CONCURRENT_STREAMS_PER_USER: int = 3


@lru_cache
def get_settings() -> Settings:
    """Return cached settings instance."""
    return Settings()
