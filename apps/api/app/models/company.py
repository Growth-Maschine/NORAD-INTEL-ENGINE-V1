"""`companies` table — the canonical company record (one per company)."""
from __future__ import annotations

import uuid

from sqlalchemy import CheckConstraint, ForeignKey, ForeignKeyConstraint, Index, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models._base import TimestampsMixin, UUIDPrimaryKey

COMPANY_ORIGINS = ("web_discovery", "research")


class Company(Base, UUIDPrimaryKey, TimestampsMixin):
    """One row per real-world company, or one Web Discovery mention per article.

    Deep Research creates/updates rows with ``origin='research'``.
    Web Discovery Sonnet enrich creates rows with ``origin='web_discovery'`` and
    ``source_article_id`` pointing at the ingested article.

    ``canonical_card_id`` points at the latest *accepted* ``cards`` row — the one
    the UI shows by default. The FK is **composite** against
    ``cards(id, company_id)`` so the canonical card is guaranteed to belong to
    *this* company.
    """

    __tablename__ = "companies"

    domain: Mapped[str | None] = mapped_column(
        String(255), nullable=True, index=True
    )
    company_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    legal_entity_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    website: Mapped[str | None] = mapped_column(Text, nullable=True)
    logo_url: Mapped[str | None] = mapped_column(Text, nullable=True)

    industry: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    category: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    headquarters_country: Mapped[str | None] = mapped_column(String(64), nullable=True)

    canonical_card_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )

    origin: Mapped[str] = mapped_column(
        String(32), nullable=False, default="research", index=True
    )
    source_article_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("articles.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    discovery_role: Mapped[str | None] = mapped_column(String(64), nullable=True)
    discovery_context: Mapped[str | None] = mapped_column(Text, nullable=True)
    normalized_name: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)

    __table_args__ = (
        Index("ix_companies_industry_category", "industry", "category"),
        CheckConstraint(
            "origin IN ('web_discovery', 'research')",
            name="ck_companies_origin",
        ),
        ForeignKeyConstraint(
            ["canonical_card_id", "id"],
            ["cards.id", "cards.company_id"],
            ondelete="SET NULL",
            name="fk_companies_canonical_card",
            use_alter=True,
        ),
    )
