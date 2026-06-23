"""M2M: organization ↔ web_discovery_cluster."""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models._base import _utcnow


class OrganizationCluster(Base):
    __tablename__ = "organization_clusters"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        primary_key=True,
    )
    cluster_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("web_discovery_clusters.id", ondelete="CASCADE"),
        primary_key=True,
        index=True,
    )
    assigned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        default=_utcnow,
    )
    assigned_by: Mapped[str] = mapped_column(String(255), nullable=False, default="admin")

    __table_args__ = (
        CheckConstraint(
            "char_length(assigned_by) > 0",
            name="ck_organization_clusters_assigned_by_nonempty",
        ),
    )
