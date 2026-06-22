"""Shared admin gate for internal operator write routes.

In dev (`settings.debug=True`) anyone passes. In prod we require
`X-Admin-Token` matching `NORAD_ADMIN_TOKEN`. Fail-closed when the token
is not configured.
"""
from __future__ import annotations

from fastapi import Header, HTTPException, status

from app.core.config import get_settings


def require_admin(x_admin_token: str | None = Header(default=None)) -> None:
    settings = get_settings()
    if settings.debug:
        return
    expected = settings.admin_token
    if not expected:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="admin_token not configured",
        )
    if x_admin_token != expected:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="admin token required",
        )
