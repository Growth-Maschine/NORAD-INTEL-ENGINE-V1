"""`card_profile_parameters` — one row per must-have profile completeness param."""
from __future__ import annotations

import uuid

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models._base import TimestampsMixin, UUIDPrimaryKey

COVERAGE_STATUSES = ("verified", "uncertain", "missing")
FIELD_CONFIDENCES = ("confirmed", "estimated", "inferred", "unknown")


class CardProfileParameter(Base, UUIDPrimaryKey, TimestampsMixin):
    """Materialized must-have parameter for a ``CompanyCardV1``.

    Filled at card persist time from the canonical NORAD profile-completeness
    catalog (49 parameters). API consumers read this table instead of recomputing
    coverage from ``cards.card`` JSONB.
    """

    __tablename__ = "card_profile_parameters"

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

    param_key: Mapped[str] = mapped_column(String(64), nullable=False)
    group_name: Mapped[str] = mapped_column(String(64), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False)
    label: Mapped[str] = mapped_column(String(128), nullable=False)

    value: Mapped[dict | list | str | int | float | bool | None] = mapped_column(
        JSONB, nullable=True
    )
    confidence: Mapped[str] = mapped_column(String(16), default="unknown")
    basis: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_refs: Mapped[list] = mapped_column(JSONB, default=list)
    coverage_status: Mapped[str] = mapped_column(String(16), nullable=False)

    __table_args__ = (
        ForeignKeyConstraint(
            ["card_id", "company_id"],
            ["cards.id", "cards.company_id"],
            ondelete="CASCADE",
            name="fk_card_profile_parameters_card_company",
        ),
        UniqueConstraint("card_id", "param_key", name="uq_card_profile_parameters_card_param"),
        Index("ix_card_profile_parameters_card_group", "card_id", "group_name", "sort_order"),
        Index("ix_card_profile_parameters_coverage", "card_id", "coverage_status"),
        CheckConstraint(
            "confidence IN ('confirmed', 'estimated', 'inferred', 'unknown')",
            name="ck_card_profile_parameters_confidence",
        ),
        CheckConstraint(
            "coverage_status IN ('verified', 'uncertain', 'missing')",
            name="ck_card_profile_parameters_coverage_status",
        ),
    )
