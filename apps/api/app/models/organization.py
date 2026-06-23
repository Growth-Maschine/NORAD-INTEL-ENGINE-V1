"""Organization tenant — top-level customer boundary for analyst access."""
from __future__ import annotations

from sqlalchemy import CheckConstraint, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models._base import TimestampsMixin, UUIDPrimaryKey

ORGANIZATION_STATUSES = ("active", "suspended")
MEMBER_ROLES = ("staff", "manager")
MEMBER_STATUSES = ("active", "deactivated")
INVITE_STATUSES = ("pending", "accepted", "expired", "cancelled")

ACTIVE_RUN_STATUSES = ("queued", "researching", "synthesizing")


class Organization(Base, UUIDPrimaryKey, TimestampsMixin):
    __tablename__ = "organizations"

    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    domain: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active", index=True)
    created_by: Mapped[str] = mapped_column(String(255), nullable=False, default="admin")
    updated_by: Mapped[str | None] = mapped_column(String(255), nullable=True)

    __table_args__ = (
        CheckConstraint("char_length(name) > 0", name="ck_organizations_name_nonempty"),
        CheckConstraint("char_length(domain) > 0", name="ck_organizations_domain_nonempty"),
        CheckConstraint(
            "status IN ('active', 'suspended')",
            name="ck_organizations_status_enum",
        ),
        CheckConstraint(
            "char_length(created_by) > 0",
            name="ck_organizations_created_by_nonempty",
        ),
    )
