"""`sources` table — denormalized for fast attribution lookup.

Cross-company drift is prevented by a **composite FK** against
`cards(id, company_id)` — same pattern as `signals`.
"""
from __future__ import annotations

import uuid

from sqlalchemy import (
    Date,
    Float,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models._base import TimestampsMixin, UUIDPrimaryKey


class Source(Base, UUIDPrimaryKey, TimestampsMixin):
    __tablename__ = "sources"

    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    card_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        index=True,
    )
    local_id: Mapped[int] = mapped_column(nullable=False)  # the int referenced inside the card

    url: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str | None] = mapped_column(Text, nullable=True)
    type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    trust_tier: Mapped[str | None] = mapped_column(String(2), nullable=True)
    date_published: Mapped[str | None] = mapped_column(Date, nullable=True)
    date_found: Mapped[str | None] = mapped_column(Date, nullable=True)
    last_checked: Mapped[str | None] = mapped_column(Date, nullable=True)
    snippet: Mapped[str | None] = mapped_column(Text, nullable=True)
    freshness_score: Mapped[float | None] = mapped_column(Float, nullable=True)

    __table_args__ = (
        ForeignKeyConstraint(
            ["card_id", "company_id"],
            ["cards.id", "cards.company_id"],
            ondelete="CASCADE",
            name="fk_sources_card_company",
        ),
        Index("ix_sources_card_local", "card_id", "local_id"),
    )
