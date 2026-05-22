"""`signals` table — denormalized for fast timeline + filtering.

Cross-company drift is prevented by a **composite FK** against
`cards(id, company_id)`. Without it, a signal could end up referencing a
`card_id` belonging to a different company than `company_id`.
"""
from __future__ import annotations

import uuid

from sqlalchemy import (
    CheckConstraint,
    Date,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models._base import TimestampsMixin, UUIDPrimaryKey


class Signal(Base, UUIDPrimaryKey, TimestampsMixin):
    __tablename__ = "signals"

    # Plain UUID columns — the composite FK below enforces both at once,
    # plus a single-col FK on company_id for cascade-on-company-delete.
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

    # type: growth | fundraising | acquisition | partnership | risk | strategic
    type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    subtype: Mapped[str | None] = mapped_column(String(64), nullable=True)
    headline: Mapped[str] = mapped_column(Text, nullable=False)
    evidence: Mapped[str | None] = mapped_column(Text, nullable=True)
    weight: Mapped[int] = mapped_column(Integer, default=5)  # 1-10
    signal_date: Mapped[str | None] = mapped_column(Date, nullable=True)
    source_refs: Mapped[list] = mapped_column(JSONB, default=list)  # [source.id, ...]

    __table_args__ = (
        ForeignKeyConstraint(
            ["card_id", "company_id"],
            ["cards.id", "cards.company_id"],
            ondelete="CASCADE",
            name="fk_signals_card_company",
        ),
        Index("ix_signals_company_date", "company_id", "signal_date"),
        Index("ix_signals_type_weight", "type", "weight"),
        CheckConstraint("weight BETWEEN 1 AND 10", name="ck_signals_weight_range"),
    )
