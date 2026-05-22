"""`run_events` table — append-only timeline of events per run.

Powers the live SSE stream that drives the right-rail "Discovery Feed" on
the Today page. Every engine call, stage transition, and significant log
gets a row here. Cheap writes, cheap reads (single composite index).
"""
from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models._base import TimestampsMixin, UUIDPrimaryKey

# Event kinds — kept as plain strings so we can add new ones without migrations.
EVENT_KINDS = (
    "run_started",
    "run_completed",
    "run_failed",
    "stage_started",
    "stage_completed",
    "engine_call",
    "article_discovered",
    "article_ranked",
    "article_read",
    "article_extracted",
    "company_extracted",
    "synthesis_started",
    "synthesis_completed",
    "log",
)


class RunEvent(Base, UUIDPrimaryKey, TimestampsMixin):
    __tablename__ = "run_events"

    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    kind: Mapped[str] = mapped_column(String(48), nullable=False, index=True)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    level: Mapped[str] = mapped_column(String(16), nullable=False, default="info")
    meta: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)

    __table_args__ = (
        Index("ix_run_events_run_created", "run_id", "created_at"),
    )
