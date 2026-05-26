"""`engine_calls` table — per-call cost + latency audit log.

Every call to Exa / Claude / Parallel writes one row. Lets us see:
- exact $ cost per run (sum group by run_id)
- p50 / p95 latency per vendor (analytics on `latency_ms`)
- which calls failed and why (`status`, `error`)

Kept independent of `run_events` so cost analytics queries stay fast.
"""
from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import (
    CheckConstraint,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models._base import TimestampsMixin, UUIDPrimaryKey

VENDORS = ("exa", "anthropic", "parallel", "diffbot")
STATUSES = ("ok", "error", "timeout")


class EngineCall(Base, UUIDPrimaryKey, TimestampsMixin):
    __tablename__ = "engine_calls"

    run_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("runs.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    vendor: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    operation: Mapped[str] = mapped_column(String(64), nullable=False)
    model: Mapped[str | None] = mapped_column(String(64), nullable=True)
    processor: Mapped[str | None] = mapped_column(String(32), nullable=True)

    # Usage + cost
    units: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    input_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cost_usd: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    latency_ms: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    status: Mapped[str] = mapped_column(String(16), nullable=False, default="ok")
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    meta: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)

    # Full request + response payloads for post-hoc inspection. Truncated by
    # the logger helpers to keep row size sane (~100 KB cap per column).
    request_payload: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB, nullable=True
    )
    response_payload: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB, nullable=True
    )

    __table_args__ = (
        CheckConstraint(
            "vendor IN ('exa','anthropic','parallel','diffbot')",
            name="ck_engine_calls_vendor",
        ),
        CheckConstraint(
            "status IN ('ok','error','timeout')",
            name="ck_engine_calls_status",
        ),
        CheckConstraint("cost_usd >= 0", name="ck_engine_calls_cost_nonneg"),
        Index("ix_engine_calls_vendor_created", "vendor", "created_at"),
    )
