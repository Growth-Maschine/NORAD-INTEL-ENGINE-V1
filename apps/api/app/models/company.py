"""`companies` table — the canonical company record (one per company)."""
from __future__ import annotations

import uuid

from sqlalchemy import ForeignKeyConstraint, Index, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models._base import TimestampsMixin, UUIDPrimaryKey


class Company(Base, UUIDPrimaryKey, TimestampsMixin):
    """One row per real-world company.

    `canonical_card_id` points at the latest *accepted* `cards` row — the one
    the UI shows by default. The FK is **composite** against
    `cards(id, company_id)` so the canonical card is guaranteed to belong to
    *this* company. Without this, a stray write could point a company at a
    card owned by another company.
    """

    __tablename__ = "companies"

    # Lowercased apex domain — primary identity for dedupe.
    # Uniqueness enforced by `ix_companies_domain` (unique index in migration).
    domain: Mapped[str | None] = mapped_column(
        String(255), nullable=True, index=True
    )
    company_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    legal_entity_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    website: Mapped[str | None] = mapped_column(Text, nullable=True)
    logo_url: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Denormalized for fast list/sort. Kept in sync with the canonical card.
    industry: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    category: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    headquarters_country: Mapped[str | None] = mapped_column(String(64), nullable=True)

    canonical_card_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )

    __table_args__ = (
        Index("ix_companies_industry_category", "industry", "category"),
        # Composite FK: (canonical_card_id, id) → cards(id, company_id)
        # Guarantees the canonical card belongs to *this* company.
        # `use_alter=True` lets the migration add it after cards exists.
        ForeignKeyConstraint(
            ["canonical_card_id", "id"],
            ["cards.id", "cards.company_id"],
            ondelete="SET NULL",
            name="fk_companies_canonical_card",
            use_alter=True,
        ),
    )
