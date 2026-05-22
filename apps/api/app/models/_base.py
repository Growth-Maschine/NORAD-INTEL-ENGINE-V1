"""Shared mixins and type helpers for SQLAlchemy models."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, declared_attr, mapped_column


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class UUIDPrimaryKey:
    """Mixin: UUID v4 primary key column."""

    @declared_attr
    def id(cls) -> Mapped[uuid.UUID]:  # type: ignore[override]
        return mapped_column(
            UUID(as_uuid=True),
            primary_key=True,
            default=uuid.uuid4,
        )


class TimestampsMixin:
    """Mixin: created_at / updated_at, both timezone-aware."""

    @declared_attr
    def created_at(cls) -> Mapped[datetime]:  # type: ignore[override]
        return mapped_column(
            DateTime(timezone=True),
            nullable=False,
            server_default=func.now(),
            default=_utcnow,
        )

    @declared_attr
    def updated_at(cls) -> Mapped[datetime]:  # type: ignore[override]
        return mapped_column(
            DateTime(timezone=True),
            nullable=False,
            server_default=func.now(),
            onupdate=_utcnow,
            default=_utcnow,
        )
