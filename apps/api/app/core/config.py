"""Application settings.

Centralized config loaded from environment variables with sensible defaults
for local development. Production must set values explicitly.

Reads `.env` from the current working directory (the api app root).
Same code path works in Replit (env injected at runtime) and on VS Code
(values pulled from `apps/api/.env`).
"""
from functools import lru_cache
from pathlib import Path
from typing import List

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Resolve .env relative to this file (apps/api/app/core/config.py → apps/api/.env)
# so the app works whether launched from apps/api or the repo root.
_API_ROOT = Path(__file__).resolve().parents[2]
_ENV_FILE = _API_ROOT / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(_ENV_FILE),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── app
    app_name: str = "NORAD API"
    app_version: str = "0.1.0"
    environment: str = Field(default="development")
    debug: bool = Field(default=True)

    # Shared bearer for admin-only write routes (e.g. PUT /api/settings/*).
    # When unset in non-debug mode the routes return 503 — fail-closed.
    admin_token: str = Field(default="")

    # ── server
    host: str = "0.0.0.0"
    port: int = 8000

    # ── cors
    cors_origins: List[str] = Field(
        default=[
            "http://localhost:5000",
            "http://127.0.0.1:5000",
        ]
    )

    # ── research engines + LLM
    parallel_api_key: str = Field(default="")
    exa_api_key: str = Field(default="")
    anthropic_api_key: str = Field(default="")

    # ── supabase
    supabase_url: str = Field(default="")
    supabase_project_ref: str = Field(default="")
    supabase_publishable_key: str = Field(default="")
    supabase_secret_key: str = Field(default="")
    supabase_jwt_secret: str = Field(default="")

    # ── postgres (supabase)
    # Prefixed `supabase_` so they don't collide with Replit's auto-injected
    # DATABASE_URL (which points at the built-in Helium dev DB).
    #
    # Three URLs, used by different code paths:
    #   _url        : transaction pooler (port 6543, IPv4)  → app runtime
    #   _url_pool   : SESSION  pooler   (port 5432, IPv4)  → ad-hoc DDL on Replit
    #                 (Supabase Dashboard → Connect → "Session pooler")
    #   _url_direct : direct connection (port 5432, IPv6)  → ad-hoc DDL on local
    #                 dev machines that have IPv6 routing
    # Schema is managed by running SQL directly against Supabase (no Alembic).
    # For DDL from Replit shells use `_url_pool`; from local dev use `_url_direct`.
    supabase_database_url: str = Field(default="")
    supabase_database_url_pool: str = Field(default="")
    supabase_database_url_direct: str = Field(default="")

    # ── redis (upstash or self-hosted)
    redis_url: str = Field(default="")
    upstash_redis_rest_url: str = Field(default="")
    upstash_redis_rest_token: str = Field(default="")

    @property
    def database_url_async(self) -> str:
        """Return the DB URL with the asyncpg driver scheme.

        asyncpg requires `postgresql+asyncpg://` for SQLAlchemy's async engine.
        Accepts `postgresql://` or `postgres://` as input.
        """
        url = self.supabase_database_url
        if not url:
            return ""
        if url.startswith("postgresql+asyncpg://"):
            return url
        if url.startswith("postgresql://"):
            return "postgresql+asyncpg://" + url[len("postgresql://"):]
        if url.startswith("postgres://"):
            return "postgresql+asyncpg://" + url[len("postgres://"):]
        return url


@lru_cache
def get_settings() -> Settings:
    return Settings()
