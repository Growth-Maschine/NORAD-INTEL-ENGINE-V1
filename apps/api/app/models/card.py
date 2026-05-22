"""`cards` table — the canonical `CompanyCardV1` JSON store."""
from __future__ import annotations

import uuid

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models._base import TimestampsMixin, UUIDPrimaryKey

# Review status values
CARD_REVIEW_STATUSES = ("draft", "accepted", "rejected", "archived")


class Card(Base, UUIDPrimaryKey, TimestampsMixin):
    """Stores one full `CompanyCardV1` document.

    `card` jsonb holds the verbatim Pydantic dump. The denormalized score
    columns make list-sorting + filtering fast without parsing the JSON.

    The `UniqueConstraint(id, company_id)` lets other tables form a
    *composite* foreign key against `(card_id, company_id)` — that's how we
    prevent cross-company drift on signals/sources/canonical_card_id.
    """

    __tablename__ = "cards"

    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    run_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("runs.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    schema_version: Mapped[str] = mapped_column(String(16), default="1.0")
    card: Mapped[dict] = mapped_column(JSONB, nullable=False)

    # Denormalized 0-100 scores (mirror of card.scores.* for sortable lists).
    score_overall: Mapped[int | None] = mapped_column(Integer, nullable=True)
    score_growth: Mapped[int | None] = mapped_column(Integer, nullable=True)
    score_momentum: Mapped[int | None] = mapped_column(Integer, nullable=True)
    score_fundraising: Mapped[int | None] = mapped_column(Integer, nullable=True)
    score_acquisition: Mapped[int | None] = mapped_column(Integer, nullable=True)
    score_partnership_fit: Mapped[int | None] = mapped_column(Integer, nullable=True)
    score_strategic_fit: Mapped[int | None] = mapped_column(Integer, nullable=True)
    score_risk: Mapped[int | None] = mapped_column(Integer, nullable=True)

    review_status: Mapped[str] = mapped_column(String(16), default="draft", index=True)
    reviewer_notes: Mapped[str | None] = mapped_column(String, nullable=True)

    __table_args__ = (
        UniqueConstraint("id", "company_id", name="uq_cards_id_company"),
        Index("ix_cards_company_created", "company_id", "created_at"),
        Index("ix_cards_score_overall", "score_overall"),
        CheckConstraint(
            "score_overall IS NULL OR (score_overall BETWEEN 0 AND 100)",
            name="ck_cards_score_overall_range",
        ),
        CheckConstraint(
            "score_growth IS NULL OR (score_growth BETWEEN 0 AND 100)",
            name="ck_cards_score_growth_range",
        ),
        CheckConstraint(
            "score_momentum IS NULL OR (score_momentum BETWEEN 0 AND 100)",
            name="ck_cards_score_momentum_range",
        ),
        CheckConstraint(
            "score_fundraising IS NULL OR (score_fundraising BETWEEN 0 AND 100)",
            name="ck_cards_score_fundraising_range",
        ),
        CheckConstraint(
            "score_acquisition IS NULL OR (score_acquisition BETWEEN 0 AND 100)",
            name="ck_cards_score_acquisition_range",
        ),
        CheckConstraint(
            "score_partnership_fit IS NULL OR (score_partnership_fit BETWEEN 0 AND 100)",
            name="ck_cards_score_partnership_fit_range",
        ),
        CheckConstraint(
            "score_strategic_fit IS NULL OR (score_strategic_fit BETWEEN 0 AND 100)",
            name="ck_cards_score_strategic_fit_range",
        ),
        CheckConstraint(
            "score_risk IS NULL OR (score_risk BETWEEN 0 AND 100)",
            name="ck_cards_score_risk_range",
        ),
    )
