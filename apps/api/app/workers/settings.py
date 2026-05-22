"""arq WorkerSettings — entrypoint for the background worker process.

Started by a separate Replit workflow (or `arq` CLI locally). Connects to
the same Redis instance used by the FastAPI app for cache + pubsub.

`redis_settings` MUST be a `RedisSettings` instance (not a function or
staticmethod) — arq reads the attribute directly via `getattr`, and a
staticmethod descriptor would be passed in as-is, exploding at runtime.
"""
from __future__ import annotations

import logging
from typing import Any

from arq.connections import RedisSettings

from app.core.config import get_settings
from app.workers.jobs.discovery import run_discovery
from app.workers.jobs.research import run_research

logger = logging.getLogger(__name__)


def _build_redis_settings() -> RedisSettings:
    settings = get_settings()
    if not settings.redis_url:
        raise RuntimeError("REDIS_URL is not configured — worker cannot start")
    return RedisSettings.from_dsn(settings.redis_url)


async def _on_startup(ctx: dict[str, Any]) -> None:
    logger.info("arq worker starting")


async def _on_shutdown(ctx: dict[str, Any]) -> None:
    logger.info("arq worker shutting down")


class WorkerSettings:
    """Loaded by `arq` CLI — see https://arq-docs.helpmanual.io/.

    Class attributes are read at worker boot via `getattr`. `redis_settings`
    is evaluated at import time so any misconfig surfaces immediately.
    """

    functions = [run_discovery, run_research]
    redis_settings = _build_redis_settings()
    on_startup = _on_startup
    on_shutdown = _on_shutdown
    job_timeout = 900  # 15 min — research can be slow
    max_jobs = 4
    keep_result = 3600  # keep job results 1h
