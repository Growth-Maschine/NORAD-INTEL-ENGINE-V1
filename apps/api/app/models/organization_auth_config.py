"""Per-organization SSO / security policy config (schema-first; wiring deferred)."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models._base import _utcnow


class OrganizationAuthConfig(Base):
    __tablename__ = "organization_auth_config"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        primary_key=True,
    )
    mfa_enforced: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    sso_only: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    ip_allowlist_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    scim_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    ip_allowlist: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    sso_provider: Mapped[str | None] = mapped_column(String(64), nullable=True)
    sso_config: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    updated_by: Mapped[str | None] = mapped_column(String(255), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        default=_utcnow,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=_utcnow,
        default=_utcnow,
    )

    __table_args__ = (
        CheckConstraint(
            "jsonb_typeof(ip_allowlist) = 'array'",
            name="ck_organization_auth_config_ip_allowlist_array",
        ),
    )
