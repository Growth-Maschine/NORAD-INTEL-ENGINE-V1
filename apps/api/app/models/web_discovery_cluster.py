"""`web_discovery_clusters` table — separate cluster system for Web Discovery."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models._base import TimestampsMixin, UUIDPrimaryKey


class WebDiscoveryCluster(Base, UUIDPrimaryKey, TimestampsMixin):
    __tablename__ = "web_discovery_clusters"

    name: Mapped[str] = mapped_column(String(140), nullable=False)
    slug: Mapped[str] = mapped_column(String(160), nullable=False, unique=True, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    priority: Mapped[str] = mapped_column(String(32), nullable=False, default="P2 Daily Intelligence")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)

    include_keywords: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    exclude_keywords: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    geography_focus: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    source_preferences: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    signal_priorities: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)

    query_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    signal_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        CheckConstraint("char_length(name) > 0", name="ck_web_discovery_clusters_name_nonempty"),
        CheckConstraint("char_length(slug) > 0", name="ck_web_discovery_clusters_slug_nonempty"),
        CheckConstraint(
            "priority IN ('P1 Critical', 'P2 Daily Intelligence', 'P3 Weekly Monitoring')",
            name="ck_web_discovery_clusters_priority_enum",
        ),
        CheckConstraint(
            "jsonb_typeof(include_keywords) = 'array'",
            name="ck_web_discovery_clusters_include_keywords_array",
        ),
        CheckConstraint(
            "jsonb_typeof(exclude_keywords) = 'array'",
            name="ck_web_discovery_clusters_exclude_keywords_array",
        ),
        CheckConstraint(
            "jsonb_typeof(geography_focus) = 'array'",
            name="ck_web_discovery_clusters_geography_focus_array",
        ),
        CheckConstraint(
            "jsonb_typeof(source_preferences) = 'array'",
            name="ck_web_discovery_clusters_source_preferences_array",
        ),
        CheckConstraint(
            "jsonb_typeof(signal_priorities) = 'array'",
            name="ck_web_discovery_clusters_signal_priorities_array",
        ),
        CheckConstraint("query_count >= 0", name="ck_web_discovery_clusters_query_count_nonnegative"),
        CheckConstraint("signal_count >= 0", name="ck_web_discovery_clusters_signal_count_nonnegative"),
        Index("ix_web_discovery_clusters_priority", "priority"),
        Index("ix_web_discovery_clusters_last_run_at", "last_run_at"),
    )
