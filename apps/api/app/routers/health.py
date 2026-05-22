"""Health and readiness probes.

- `/health`  — app is up, returns build info
- `/ready`   — liveness probe (no dependency checks)
- `/health/db` — checks Postgres + Redis connectivity (use to verify wiring)
"""
from __future__ import annotations

import asyncio
import time

from fastapi import APIRouter
from sqlalchemy import text

from app.core.config import get_settings
from app.core.db import get_engine
from app.core.redis_client import get_redis

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict:
    s = get_settings()
    return {
        "status": "ok",
        "app": s.app_name,
        "version": s.app_version,
        "environment": s.environment,
    }


@router.get("/ready")
def ready() -> dict:
    return {"status": "ready"}


def _error_payload(exc: Exception, t0: float) -> dict:
    """Build a dependency-check error payload.

    Raw exception messages can leak hostnames/usernames, so we expose detail
    only in debug mode. Server-side we always log the full error.
    """
    settings = get_settings()
    payload = {
        "ok": False,
        "latency_ms": round((time.perf_counter() - t0) * 1000, 1),
    }
    if settings.debug:
        payload["error"] = f"{type(exc).__name__}: {exc}"
    else:
        payload["error"] = type(exc).__name__
    return payload


async def _check_postgres() -> dict:
    t0 = time.perf_counter()
    try:
        engine = get_engine()
        async with engine.connect() as conn:
            result = await conn.execute(text("SELECT 1"))
            value = result.scalar_one()
        return {
            "ok": value == 1,
            "latency_ms": round((time.perf_counter() - t0) * 1000, 1),
        }
    except Exception as exc:
        return _error_payload(exc, t0)


async def _check_redis() -> dict:
    t0 = time.perf_counter()
    try:
        client = get_redis()
        pong = await client.ping()
        return {
            "ok": bool(pong),
            "latency_ms": round((time.perf_counter() - t0) * 1000, 1),
        }
    except Exception as exc:
        return _error_payload(exc, t0)


@router.get("/health/db")
async def health_db() -> dict:
    """Verify Postgres + Redis connectivity. Used for wiring smoke-tests."""
    postgres, redis_ = await asyncio.gather(_check_postgres(), _check_redis())
    overall = "ok" if postgres["ok"] and redis_["ok"] else "degraded"
    return {
        "status": overall,
        "postgres": postgres,
        "redis": redis_,
    }
