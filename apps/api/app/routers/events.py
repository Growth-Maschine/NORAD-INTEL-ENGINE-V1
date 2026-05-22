"""Server-Sent Events stream of `run_events` for the Today right-rail feed.

Reads `run_events` rows for a given run and streams new ones as they appear.
For v1 we poll the DB every 1s with **short-lived sessions per poll** — the
generator never holds an AsyncSession across `await asyncio.sleep`, so we
don't pin a pgbouncer-mode connection for the lifetime of the stream.

Pagination uses a keyset cursor `(created_at, id)` to guarantee no event is
dropped even when multiple rows share the same `created_at`.

Endpoints:
    GET /api/events/runs/:run_id           → text/event-stream
    GET /api/events/runs/:run_id/recent    → JSON fallback (newest-first)
"""
from __future__ import annotations

import asyncio
import json
import uuid as uuid_lib
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from starlette.responses import StreamingResponse

from app.core.db import get_session, get_session_factory
from app.models.run_event import RunEvent

router = APIRouter(prefix="/api/events", tags=["events"])

POLL_INTERVAL_S = 1.0
STREAM_MAX_S = 300.0  # 5 min keep-alive ceiling
BATCH_LIMIT = 200


def _serialize(event: RunEvent) -> str:
    payload = {
        "id": str(event.id),
        "run_id": str(event.run_id),
        "kind": event.kind,
        "message": event.message,
        "level": event.level,
        "meta": event.meta,
        "created_at": event.created_at.isoformat(),
    }
    return f"data: {json.dumps(payload)}\n\n"


async def _event_stream(
    run_id: UUID,
    session_factory: async_sessionmaker[AsyncSession],
):
    """Stream events for a run.

    Uses keyset cursor (created_at, id) so concurrent inserts sharing the
    same created_at can't be skipped. Opens a fresh session per poll so we
    never hold a DB connection across `await asyncio.sleep`.
    """
    cursor_created_at: datetime = datetime.now(timezone.utc)
    cursor_id: UUID = uuid_lib.UUID(int=0)  # zero UUID = "all ids > this"

    yield ": stream open\n\n"
    loop = asyncio.get_event_loop()
    started = loop.time()

    while True:
        if loop.time() - started > STREAM_MAX_S:
            yield ": stream timeout\n\n"
            return

        # Short-lived session per poll. NEVER held across sleep.
        async with session_factory() as session:
            stmt = (
                select(RunEvent)
                .where(
                    RunEvent.run_id == run_id,
                    or_(
                        RunEvent.created_at > cursor_created_at,
                        and_(
                            RunEvent.created_at == cursor_created_at,
                            RunEvent.id > cursor_id,
                        ),
                    ),
                )
                .order_by(RunEvent.created_at.asc(), RunEvent.id.asc())
                .limit(BATCH_LIMIT)
            )
            rows = (await session.execute(stmt)).scalars().all()

        for row in rows:
            cursor_created_at = row.created_at
            cursor_id = row.id
            yield _serialize(row)

        # Heartbeat comment every poll keeps proxies from closing the connection.
        if not rows:
            yield ": keep-alive\n\n"

        await asyncio.sleep(POLL_INTERVAL_S)


@router.get("/runs/{run_id}")
async def stream_run_events(run_id: UUID) -> StreamingResponse:
    """SSE stream of events for a single run."""
    factory = get_session_factory()
    return StreamingResponse(
        _event_stream(run_id, factory),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # disable nginx buffering
            "Connection": "keep-alive",
        },
    )


@router.get("/runs/{run_id}/recent")
async def list_recent_events(
    run_id: UUID,
    limit: int = 50,
    session: AsyncSession = Depends(get_session),
) -> list[dict]:
    """Non-streaming fallback: most recent N events for a run (newest last)."""
    if limit < 1 or limit > 500:
        raise HTTPException(400, "limit must be 1..500")
    stmt = (
        select(RunEvent)
        .where(RunEvent.run_id == run_id)
        .order_by(RunEvent.created_at.desc(), RunEvent.id.desc())
        .limit(limit)
    )
    result = await session.execute(stmt)
    rows = list(reversed(result.scalars().all()))
    return [
        {
            "id": str(r.id),
            "run_id": str(r.run_id),
            "kind": r.kind,
            "message": r.message,
            "level": r.level,
            "meta": r.meta,
            "created_at": r.created_at.isoformat(),
        }
        for r in rows
    ]
