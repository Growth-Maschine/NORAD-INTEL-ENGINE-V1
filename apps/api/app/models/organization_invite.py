"""Pending analyst user invitations."""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models._base import TimestampsMixin, UUIDPrimaryKey


class OrganizationInvite(Base, UUIDPrimaryKey, TimestampsMixin):
    __tablename__ = "organization_invites"

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
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    invited_by: Mapped[str] = mapped_column(String(255), nullable=False, default="admin")

    __table_args__ = (
        CheckConstraint(
            "char_length(email) > 0",
            name="ck_organization_invites_email_nonempty",
        ),
        CheckConstraint(
            "char_length(display_name) > 0",
            name="ck_organization_invites_display_name_nonempty",
        ),
        CheckConstraint(
            "role IN ('staff', 'manager')",
            name="ck_organization_invites_role_enum",
        ),
        CheckConstraint(
            "status IN ('pending', 'accepted', 'expired', 'cancelled')",
            name="ck_organization_invites_status_enum",
        ),
        CheckConstraint(
            "char_length(token_hash) = 64",
            name="ck_organization_invites_token_hash_len",
        ),
        CheckConstraint(
            "char_length(invited_by) > 0",
            name="ck_organization_invites_invited_by_nonempty",
        ),
        Index("ix_organization_invites_org_status", "organization_id", "status"),
    )
