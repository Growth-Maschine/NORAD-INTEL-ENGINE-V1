"""Async Redis client (used for cache, pubsub, and the arq job queue)."""
from __future__ import annotations

from redis.asyncio import Redis, from_url

from app.core.config import get_settings

_client: Redis | None = None


def get_redis() -> Redis:
    """Return a singleton async Redis client.

    Accepts both `redis://` and `rediss://` (TLS — Upstash uses TLS).
    """
    global _client
    if _client is None:
        settings = get_settings()
        if not settings.redis_url:
            raise RuntimeError("REDIS_URL is not configured")
        _client = from_url(
            settings.redis_url,
            encoding="utf-8",
            decode_responses=True,
        )
    return _client
