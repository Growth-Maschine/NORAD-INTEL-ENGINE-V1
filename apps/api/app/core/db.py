"""Async SQLAlchemy engine + session factory for GCP Cloud SQL Postgres."""
from __future__ import annotations

import ssl
import uuid
from pathlib import Path
from urllib.parse import urlparse

import certifi
from sqlalchemy.engine.url import make_url
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import NullPool

from app.core.config import get_settings

_API_ROOT = Path(__file__).resolve().parents[2]
_CLOUD_SQL_SERVER_CA = _API_ROOT / "certs" / "cloud-sql-server-ca.pem"


class Base(DeclarativeBase):
    """SQLAlchemy declarative base. Models inherit from this."""


_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None

# libpq/psql query params that asyncpg.connect() does not accept.
_LIBPQ_ONLY_QUERY_KEYS = frozenset({"sslmode", "sslcert", "sslkey", "sslrootcert", "sslcrl"})


def _uses_pgbouncer_transaction_pooler(url: str) -> bool:
    """Port 6543 transaction poolers disable asyncpg prepared-statement caching."""
    return ":6543" in url


def _ssl_required(url: str) -> bool:
    parsed = make_url(url)
    sslmode = parsed.query.get("sslmode", "")
    if sslmode in ("require", "verify-ca", "verify-full"):
        return True
    if parsed.query.get("ssl", "").lower() == "true":
        return True
    host = (urlparse(url).hostname or "").lower()
    return "sql.cloud.google.com" in host


def _asyncpg_url(url: str) -> str:
    """Drop libpq-only query params before handing the URL to asyncpg."""
    parsed = make_url(url)
    query = {k: v for k, v in parsed.query.items() if k not in _LIBPQ_ONLY_QUERY_KEYS}
    return parsed.set(query=query).render_as_string(hide_password=False)


def _ssl_context() -> ssl.SSLContext:
    """Cloud SQL public-IP certs are issued for the instance name, not the IP."""
    ctx = ssl.create_default_context(cafile=certifi.where())
    if _CLOUD_SQL_SERVER_CA.is_file():
        ctx.load_verify_locations(cafile=str(_CLOUD_SQL_SERVER_CA))
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_REQUIRED
    return ctx


def _asyncpg_connect_args(url: str) -> dict:
    args: dict = {}
    if _uses_pgbouncer_transaction_pooler(url):
        args.update(
            {
                "statement_cache_size": 0,
                "prepared_statement_cache_size": 0,
                "prepared_statement_name_func": lambda: f"__asyncpg_{uuid.uuid4()}__",
            }
        )
    if _ssl_required(url):
        args["ssl"] = _ssl_context()
    return args


def get_engine() -> AsyncEngine:
    global _engine
    if _engine is None:
        settings = get_settings()
        url = settings.database_url_async
        if not url:
            raise RuntimeError("GCP_DATABASE_URL is not configured")
        _engine = create_async_engine(
            _asyncpg_url(url),
            echo=False,
            future=True,
            poolclass=NullPool,
            connect_args=_asyncpg_connect_args(url),
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
