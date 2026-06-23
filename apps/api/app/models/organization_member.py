"""Analyst users belonging to an organization."""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models._base import TimestampsMixin, UUIDPrimaryKey


class OrganizationMember(Base, UUIDPrimaryKey, TimestampsMixin):
    __tablename__ = "organization_members"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    email: Mapped[str] = mapped_column(String(320), nullable=False)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(32), nullable=False, default="staff")
    team: Mapped[str | None] = mapped_column(String(120), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")
    joined_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    deactivated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    created_by: Mapped[str] = mapped_column(String(255), nullable=False, default="admin")
    updated_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    deactivated_by: Mapped[str | None] = mapped_column(String(255), nullable=True)

    __table_args__ = (
        UniqueConstraint("organization_id", "email", name="uq_organization_members_org_email"),
        CheckConstraint(
            "char_length(email) > 0",
            name="ck_organization_members_email_nonempty",
        ),
        CheckConstraint(
            "char_length(display_name) > 0",
            name="ck_organization_members_display_name_nonempty",
        ),
        CheckConstraint(
            "role IN ('staff', 'manager')",
            name="ck_organization_members_role_enum",
        ),
        CheckConstraint(
            "status IN ('active', 'deactivated')",
            name="ck_organization_members_status_enum",
        ),
        CheckConstraint(
            "char_length(created_by) > 0",
            name="ck_organization_members_created_by_nonempty",
        ),
        Index("ix_organization_members_org_status", "organization_id", "status"),
    )
