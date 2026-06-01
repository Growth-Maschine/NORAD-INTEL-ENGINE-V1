"""`discovery_clusters` table — user-managed keyword clusters for Discovery."""
from __future__ import annotations

from typing import Any

from sqlalchemy import Boolean, CheckConstraint, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models._base import TimestampsMixin, UUIDPrimaryKey


class DiscoveryCluster(Base, UUIDPrimaryKey, TimestampsMixin):
    __tablename__ = "discovery_clusters"

    name: Mapped[str] = mapped_column(String(120), nullable=False)
    slug: Mapped[str] = mapped_column(String(120), nullable=False, unique=True, index=True)
    group_name: Mapped[str] = mapped_column(String(120), nullable=False, default="Custom")
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    keywords: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    is_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0, index=True)

    __table_args__ = (
        CheckConstraint("char_length(name) > 0", name="ck_discovery_clusters_name_nonempty"),
        CheckConstraint("char_length(slug) > 0", name="ck_discovery_clusters_slug_nonempty"),
        CheckConstraint("jsonb_typeof(keywords) = 'array'", name="ck_discovery_clusters_keywords_array"),
        CheckConstraint("sort_order >= 0", name="ck_discovery_clusters_sort_order_nonnegative"),
        Index("ix_discovery_clusters_group_sort", "group_name", "sort_order"),
    )
