"""`trend_articles` table — one row per article surfaced by a discovery run.

Lifecycle:
- `discovered`  : URL returned from Exa search (title + dek + date known)
- `ranked`      : Claude Haiku assigned a relevance_score (Stage 3)
- `read`        : Full body fetched via Exa /contents (Stage 4)
- `extracted`   : Claude Sonnet pulled out companies + summary (Stage 5)
- `dismissed`   : user (or filter) dropped it
- `researched`  : user clicked Research; at least one research run spawned

`extracted_companies` is a JSONB array of `{name, excerpt, hint_url?}` rows
populated at the `extracted` stage. Each entry can later become a research
run (recorded in `research_run_ids`).
"""
from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import (
    CheckConstraint,
    Date,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models._base import TimestampsMixin, UUIDPrimaryKey

ARTICLE_STATUSES = (
    "discovered",
    "ranked",
    "read",
    "extracted",
    "dismissed",
    "researched",
)


class TrendArticle(Base, UUIDPrimaryKey, TimestampsMixin):
    __tablename__ = "trend_articles"

    # Source identity
    url: Mapped[str] = mapped_column(Text, nullable=False, unique=True, index=True)
    source: Mapped[str] = mapped_column(String(32), nullable=False, default="trendhunter")
    category: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    subcategory: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # Article content (filled progressively)
    title: Mapped[str | None] = mapped_column(Text, nullable=True)
    dek: Mapped[str | None] = mapped_column(Text, nullable=True)
    body_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    published_date: Mapped[Any] = mapped_column(Date, nullable=True, index=True)
    image_url: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Outbound URLs found inside the article (worth deep-reading on click)
    reference_urls: Mapped[list[str]] = mapped_column(
        ARRAY(Text), nullable=False, default=list
    )

    # Stage 3 ranking output
    relevance_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    relevance_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Stage 5 extraction output: list of {name, excerpt, hint_url?}
    extracted_companies: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, nullable=False, default=list
    )

    # Lifecycle status
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="discovered", index=True
    )

    # Run linkage
    discovery_run_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("runs.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    # Each company researched from this article gets a research run; we track
    # the spawn list here for traceability.
    research_run_ids: Mapped[list[uuid.UUID]] = mapped_column(
        ARRAY(UUID(as_uuid=True)), nullable=False, default=list
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('discovered','ranked','read','extracted','dismissed','researched')",
            name="ck_trend_articles_status",
        ),
        CheckConstraint(
            "relevance_score IS NULL OR (relevance_score >= 0 AND relevance_score <= 100)",
            name="ck_trend_articles_relevance_range",
        ),
        Index("ix_trend_articles_status_pubdate", "status", "published_date"),
        Index("ix_trend_articles_category_pubdate", "category", "published_date"),
    )
