"""Helper for writing `run_events` rows + JSONL pipeline tail.

Kept tiny + sync-friendly so any service / job can fire-and-forget an
event without worrying about transaction state. Each call opens its own
short-lived session, commits, and exits — the SSE poller picks it up on
the next tick.

Every emit() also tees to the structured JSONL pipeline log
(`apps/api/logs/pipeline.jsonl`) so you can `tail -f` the whole pipeline
across both research + discovery without joining tables.

Pipeline tagging:
    Each pipeline (research / discovery) sets a contextvar at entry; emit()
    reads it so events land tagged with the right pipeline in the JSONL.

For tight inner loops (e.g. per-article events inside the funnel), prefer
`emit_many` which writes a batch in one transaction.
"""
from __future__ import annotations

import contextvars
import logging
import uuid
from typing import Any

from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession

from app.core.db import get_session_factory
from app.core.pipeline_log import log_event as _pipeline_log_event
from app.models.run_event import RunEvent

logger = logging.getLogger(__name__)


# ── Pipeline context ────────────────────────────────────────────────────────

_pipeline_ctx: contextvars.ContextVar[str] = contextvars.ContextVar(
    "norad_pipeline", default="research"
)


def set_pipeline(name: str) -> None:
    """Tag the current async context with the active pipeline ('research' or
    'discovery'). Read by emit() to label JSONL events. Idempotent."""
    _pipeline_ctx.set(name)


def current_pipeline() -> str:
    return _pipeline_ctx.get()


# ── Emit ─────────────────────────────────────────────────────────────────────


async def emit(
    run_id: uuid.UUID,
    kind: str,
    message: str,
    *,
    level: str = "info",
    meta: dict[str, Any] | None = None,
    session_factory: async_sessionmaker[AsyncSession] | None = None,
) -> None:
    """Append a single event for `run_id`. Never raises (logs on failure).

    Side-effect: also tees to the JSONL pipeline log.
    """
    pipeline = _pipeline_ctx.get()
    stage = (meta or {}).get("stage") if isinstance(meta, dict) else None
    _pipeline_log_event(
        pipeline=pipeline,
        kind=kind,
        message=message,
        run_id=run_id,
        stage=stage if isinstance(stage, int) else None,
        level=level,
        meta=meta,
    )
    factory = session_factory or get_session_factory()
    try:
        async with factory() as session:
            session.add(
                RunEvent(
                    run_id=run_id,
                    kind=kind,
                    message=message,
                    level=level,
                    meta=meta or {},
                )
            )
            await session.commit()
    except Exception as exc:  # pragma: no cover — observability path
        logger.warning("failed to emit run_event run_id=%s kind=%s: %s", run_id, kind, exc)


async def emit_with_session(
    session: AsyncSession,
    run_id: uuid.UUID,
    kind: str,
    message: str,
    *,
    level: str = "info",
    meta: dict[str, Any] | None = None,
) -> None:
    """Emit using an existing session — caller commits."""
    pipeline = _pipeline_ctx.get()
    stage = (meta or {}).get("stage") if isinstance(meta, dict) else None
    _pipeline_log_event(
        pipeline=pipeline,
        kind=kind,
        message=message,
        run_id=run_id,
        stage=stage if isinstance(stage, int) else None,
        level=level,
        meta=meta,
    )
    session.add(
        RunEvent(
            run_id=run_id,
            kind=kind,
            message=message,
            level=level,
            meta=meta or {},
        )
    )
