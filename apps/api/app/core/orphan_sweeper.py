"""On startup, mark any non-terminal `runs` row older than the cutoff as
`failed`.

Why: research runs live entirely in the FastAPI worker process — there is no
durable queue. If the worker dies (deploy, restart, OOM, crash) mid-pipeline,
the row stays in `queued` / `researching` / `synthesizing` forever, and the UI
keeps showing "1 running" against a dead run. Customers see "Profiling 55%"
that never advances. We sweep on every startup so a restart is self-healing.

This is intentionally conservative: only runs older than `cutoff_minutes` are
swept, so a healthy in-flight run is never killed by a slow startup.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession

logger = logging.getLogger(__name__)

_NON_TERMINAL = ("queued", "researching", "synthesizing", "persisting")
_DEFAULT_CUTOFF_MIN = 30


async def sweep_orphan_runs(
    factory: async_sessionmaker[AsyncSession],
    cutoff_minutes: int = _DEFAULT_CUTOFF_MIN,
) -> int:
    """Mark abandoned non-terminal runs as failed. Returns number of rows fixed."""
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=cutoff_minutes)
    async with factory() as s:
        result = await s.execute(
            text(
                """
                UPDATE runs
                SET status='failed',
                    completed_at=now(),
                    error=COALESCE(error,'')
                          || ' [orphan-sweeper: worker died mid-pipeline, '
                          || 'last status=' || status || ', '
                          || 'started_at=' || COALESCE(started_at::text,'null')
                          || ']'
                WHERE status = ANY(:non_terminal)
                  AND (started_at IS NULL OR started_at < :cutoff)
                  AND (completed_at IS NULL)
                RETURNING id, status
                """
            ),
            {"non_terminal": list(_NON_TERMINAL), "cutoff": cutoff},
        )
        rows = result.fetchall()
        await s.commit()
        n = len(rows)
        if n:
            logger.warning(
                "orphan_sweeper: marked %d abandoned run(s) as failed (cutoff=%dmin): %s",
                n,
                cutoff_minutes,
                ", ".join(str(r[0]) for r in rows),
            )
        else:
            logger.info("orphan_sweeper: no orphan runs (cutoff=%dmin)", cutoff_minutes)
        return n
