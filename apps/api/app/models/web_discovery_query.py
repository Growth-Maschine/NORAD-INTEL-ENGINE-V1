"""`web_discovery_queries` table — Exa query configs nested under web clusters."""
from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy import Boolean, CheckConstraint, Date, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models._base import TimestampsMixin, UUIDPrimaryKey


class WebDiscoveryQuery(Base, UUIDPrimaryKey, TimestampsMixin):
    __tablename__ = "web_discovery_queries"

    cluster_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("web_discovery_clusters.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    label: Mapped[str] = mapped_column(String(160), nullable=False)
    search_query: Mapped[str] = mapped_column(Text, nullable=False)
    search_type: Mapped[str] = mapped_column(String(32), nullable=False, default="auto")
    num_results: Mapped[int] = mapped_column(Integer, nullable=False, default=10)

    content_highlights: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    content_text: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    content_summary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    structured_outputs: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    highlights_max_chars: Mapped[int | None] = mapped_column(Integer, nullable=True)
    highlights_guiding_query: Mapped[str | None] = mapped_column(Text, nullable=True)
    text_max_chars: Mapped[int | None] = mapped_column(Integer, nullable=True)
    text_main_content_only: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    summary_max_chars: Mapped[int | None] = mapped_column(Integer, nullable=True)
    system_prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    output_schema: Mapped[dict | None] = mapped_column(JSONB(none_as_null=True), nullable=True)

    livecrawl_timeout_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=10000)
    max_age_hours: Mapped[int | None] = mapped_column(Integer, nullable=True)
    subpages: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    extra_links: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    extra_image_links: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    subpage_target_keywords: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)

    category: Mapped[str | None] = mapped_column(String(80), nullable=True)
    user_location: Mapped[str | None] = mapped_column(String(8), nullable=True)
    include_domains: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    exclude_domains: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    published_after: Mapped[date | None] = mapped_column(Date, nullable=True)
    published_before: Mapped[date | None] = mapped_column(Date, nullable=True)
    crawled_after: Mapped[date | None] = mapped_column(Date, nullable=True)
    crawled_before: Mapped[date | None] = mapped_column(Date, nullable=True)
    content_moderation: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    stream_response: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    additional_queries: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)

    __table_args__ = (
        CheckConstraint("char_length(label) > 0", name="ck_web_discovery_queries_label_nonempty"),
        CheckConstraint(
            "char_length(search_query) > 0", name="ck_web_discovery_queries_search_query_nonempty"
        ),
        CheckConstraint(
            "search_type IN ('auto', 'fast', 'deep', 'deep-lite', 'deep-reasoning', 'instant')",
            name="ck_web_discovery_queries_search_type_enum",
        ),
        CheckConstraint("num_results >= 1 AND num_results <= 100", name="ck_web_discovery_queries_num_results_range"),
        CheckConstraint(
            "highlights_max_chars IS NULL OR highlights_max_chars >= 0",
            name="ck_web_discovery_queries_highlights_max_chars_nonnegative",
        ),
        CheckConstraint(
            "text_max_chars IS NULL OR text_max_chars >= 0",
            name="ck_web_discovery_queries_text_max_chars_nonnegative",
        ),
        CheckConstraint(
            "summary_max_chars IS NULL OR summary_max_chars >= 0",
            name="ck_web_discovery_queries_summary_max_chars_nonnegative",
        ),
        CheckConstraint(
            "output_schema IS NULL OR jsonb_typeof(output_schema) IN ('object', 'null')",
            name="ck_web_discovery_queries_output_schema_object",
        ),
        CheckConstraint("livecrawl_timeout_ms >= 0", name="ck_web_discovery_queries_livecrawl_timeout_nonnegative"),
        CheckConstraint("subpages >= 0", name="ck_web_discovery_queries_subpages_nonnegative"),
        CheckConstraint("extra_links >= 0", name="ck_web_discovery_queries_extra_links_nonnegative"),
        CheckConstraint(
            "extra_image_links >= 0", name="ck_web_discovery_queries_extra_image_links_nonnegative"
        ),
        CheckConstraint("max_age_hours IS NULL OR max_age_hours >= -1", name="ck_web_discovery_queries_max_age_valid"),
        CheckConstraint(
            "jsonb_typeof(subpage_target_keywords) = 'array'",
            name="ck_web_discovery_queries_subpage_target_keywords_array",
        ),
        CheckConstraint(
            "jsonb_typeof(include_domains) = 'array'",
            name="ck_web_discovery_queries_include_domains_array",
        ),
        CheckConstraint(
            "jsonb_typeof(exclude_domains) = 'array'",
            name="ck_web_discovery_queries_exclude_domains_array",
        ),
        CheckConstraint(
            "jsonb_typeof(additional_queries) = 'array'",
            name="ck_web_discovery_queries_additional_queries_array",
        ),
        Index("ix_web_discovery_queries_cluster_created", "cluster_id", "created_at"),
    )
