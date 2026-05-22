"""`app_kv` table — generic singleton-key/value store for app-level config.

We don't want to scatter scalar config across many tables. `app_kv` is a tiny
key→jsonb store used for things that are global to the install:

    key="research_config"  →  {parallel: {...}, exa: {...}}

Read paths cache the row in memory with a short TTL (see services/settings.py).
"""
from __future__ import annotations

from typing import Any

from sqlalchemy import String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models._base import TimestampsMixin


class AppKV(Base, TimestampsMixin):
    __tablename__ = "app_kv"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
