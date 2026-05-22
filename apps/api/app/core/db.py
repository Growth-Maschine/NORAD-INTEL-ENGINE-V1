"""Async SQLAlchemy engine + session factory pointed at Supabase Postgres.

Notes on the connection:
- We connect through Supabase's **transaction pooler** (port 6543). pgbouncer
  in transaction mode does not preserve prepared statements across pool
  clients, so we must:
    1. Disable asyncpg's own prepared-statement cache.
    2. Give every prepared statement a unique name so reused backend
       connections never see a name collision (asyncpg's default names are
       sequential `__asyncpg_stmt_N__` which DO collide under pgbouncer).
- `poolclass=NullPool` is used because the upstream pooler already pools.
"""
from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import NullPool

from app.core.config import get_settings


class Base(DeclarativeBase):
    """SQLAlchemy declarative base. Models inherit from this."""


_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def get_engine() -> AsyncEngine:
    global _engine
    if _engine is None:
        settings = get_settings()
        if not settings.database_url_async:
            raise RuntimeError("SUPABASE_DATABASE_URL is not configured")
        _engine = create_async_engine(
            settings.database_url_async,
            echo=False,
            future=True,
            poolclass=NullPool,
            connect_args={
                # required for Supabase transaction-mode pooler
                "statement_cache_size": 0,
                "prepared_statement_cache_size": 0,
                # Unique name per prepared statement → avoids pgbouncer
                # collisions when backend connections are reused.
                "prepared_statement_name_func": lambda: f"__asyncpg_{uuid.uuid4()}__",
            },
        )
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(
            bind=get_engine(),
            expire_on_commit=False,
            class_=AsyncSession,
        )
    return _session_factory


async def get_session() -> AsyncSession:
    """FastAPI dependency — yields an async session per request."""
    factory = get_session_factory()
    async with factory() as session:
        yield session
