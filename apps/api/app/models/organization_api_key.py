"""Org-scoped integration API keys for analyst frontends."""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models._base import UUIDPrimaryKey, _utcnow


class OrganizationApiKey(Base, UUIDPrimaryKey):
    __tablename__ = "organization_api_keys"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False, default="default")
    key_prefix: Mapped[str] = mapped_column(String(24), nullable=False)
    key_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utcnow,
    )
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        CheckConstraint(
            "char_length(key_prefix) > 0",
            name="ck_organization_api_keys_prefix_nonempty",
        ),
        CheckConstraint(
            "char_length(key_hash) = 64",
            name="ck_organization_api_keys_hash_nonempty",
        ),
        Index(
            "ix_organization_api_keys_org_active",
            "organization_id",
            postgresql_where="revoked_at IS NULL AND is_active = TRUE",
        ),
    )
