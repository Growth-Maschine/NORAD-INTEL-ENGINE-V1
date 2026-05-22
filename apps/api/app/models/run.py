"""`runs` table — one row per research request."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models._base import TimestampsMixin, UUIDPrimaryKey

# Status values (kept as plain strings — easier to evolve than PG enums).
RUN_STATUSES = (
    "queued",
    "researching",  # engines running
    "synthesizing",  # Claude composing the card
    "completed",
    "failed",
    "cancelled",
)


class Run(Base, UUIDPrimaryKey, TimestampsMixin):
    __tablename__ = "runs"

    # The user's input. Free-form query for v1; later: trend-hunter article URL.
    query: Mapped[str] = mapped_column(Text, nullable=False)
    source_kind: Mapped[str] = mapped_column(String(32), default="user_query")
    # Idempotency: if a caller passes the same key for the same query, we return
    # the existing run instead of enqueuing a duplicate. Nullable so manual /
    # ad-hoc runs don't need one.
    idempotency_key: Mapped[str | None] = mapped_column(
        String(64), nullable=True, unique=True, index=True
    )
    # e.g. "user_query" | "trendhunter_article" | "manual" — keep flexible

    status: Mapped[str] = mapped_column(String(32), default="queued", index=True)
    progress_pct: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Per-run engine config (which engines, processor tier, effort, etc.).
    engines: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict
    )
    # Raw engine outputs (kept for debugging + audit). Stripped after N days
    # in a future job — for v1, retain.
    engine_outputs: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict
    )

    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Filled when the run resolves to a known company.
    company_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("companies.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    card_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("cards.id", ondelete="SET NULL"),
        nullable=True,
    )

    __table_args__ = (
        Index("ix_runs_status_created", "status", "created_at"),
        CheckConstraint(
            "progress_pct >= 0 AND progress_pct <= 100",
            name="ck_runs_progress_pct_range",
        ),
    )
