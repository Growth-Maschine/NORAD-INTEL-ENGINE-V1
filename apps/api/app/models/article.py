"""`articles` table — consolidated news items ingested from Web Discovery runs."""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models._base import TimestampsMixin, UUIDPrimaryKey


class Article(Base, UUIDPrimaryKey, TimestampsMixin):
    __tablename__ = "articles"

    url: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    body_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ingested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    cluster_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("web_discovery_clusters.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    query_run_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("runs.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    source_query_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("web_discovery_queries.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    category_tag: Mapped[str | None] = mapped_column(String(80), nullable=True)
    priority_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    mentioned_companies: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    source_metadata: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active", index=True)

    __table_args__ = (
        CheckConstraint("char_length(title) > 0", name="ck_articles_title_nonempty"),
        CheckConstraint(
            "status IN ('active', 'dismissed', 'archived')",
            name="ck_articles_status_enum",
        ),
        CheckConstraint(
            "priority_score IS NULL OR (priority_score >= 0 AND priority_score <= 100)",
            name="ck_articles_priority_score_range",
        ),
        CheckConstraint(
            "jsonb_typeof(mentioned_companies) = 'array'",
            name="ck_articles_mentioned_companies_array",
        ),
        CheckConstraint(
            "jsonb_typeof(source_metadata) = 'object'",
            name="ck_articles_source_metadata_object",
        ),
        Index("ix_articles_published_at", "published_at"),
        Index("ix_articles_ingested_at", "ingested_at"),
        Index("ix_articles_status_ingested", "status", "ingested_at"),
    )
