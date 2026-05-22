"""Engine wiring smoke tests.

`GET /health/engines`        — shallow: reports which API keys are configured
`GET /health/engines/ping`   — deep:    fires a tiny live call to each vendor
                                       (~$0.00001 — safe to ping in dev)

The `deep=true` path costs real money (tiny — sub-cent — but real) and so is
**gated**:

- In dev/local (`settings.debug=True`) it's always allowed.
- In any other environment it requires an `X-Admin-Token` header that matches
  `NORAD_ADMIN_TOKEN` from the environment. Without that env var set, deep
  pings are refused outright in non-debug builds.

This stops the public deploy URL from being trivially abused to burn vendor
credits.
"""
from __future__ import annotations

import asyncio
import os

from fastapi import APIRouter, Header, HTTPException, Query

from app.core.config import get_settings
from app.engines import get_claude_client, get_exa_client, get_parallel_client

router = APIRouter(tags=["engines"])


@router.get("/health/engines")
def engines_config() -> dict:
    """Report which engine credentials are present (no live calls)."""
    s = get_settings()
    return {
        "status": "ok",
        "engines": {
            "exa":      {"configured": bool(s.exa_api_key)},
            "anthropic":{"configured": bool(s.anthropic_api_key)},
            "parallel": {"configured": bool(s.parallel_api_key)},
        },
    }


def _admin_gate(deep: bool, admin_token: str | None) -> None:
    """Raise 403 if deep=true is not authorized in this environment."""
    if not deep:
        return
    s = get_settings()
    if s.debug:
        return  # dev: always allowed
    expected = os.getenv("NORAD_ADMIN_TOKEN", "")
    if not expected:
        raise HTTPException(
            status_code=403,
            detail="deep=true is disabled in production (NORAD_ADMIN_TOKEN not set)",
        )
    if not admin_token or admin_token != expected:
        raise HTTPException(
            status_code=403,
            detail="deep=true requires a valid X-Admin-Token header",
        )


@router.get("/health/engines/ping")
async def engines_ping(
    deep: bool = Query(False, description="Hit live endpoints (~$0.00001 total)"),
    x_admin_token: str | None = Header(default=None),
) -> dict:
    """Verify each engine answers. With `deep=true`, fires a real call.

    Without `deep`, only checks credentials — same as `/health/engines`.
    """
    _admin_gate(deep, x_admin_token)

    s = get_settings()
    if not deep:
        return {
            "status": "ok",
            "engines": {
                "exa":      {"ok": bool(s.exa_api_key), "configured": bool(s.exa_api_key)},
                "anthropic":{"ok": bool(s.anthropic_api_key), "configured": bool(s.anthropic_api_key)},
                "parallel": {"ok": bool(s.parallel_api_key), "configured": bool(s.parallel_api_key)},
            },
            "note": "Use ?deep=true to hit live endpoints (admin-gated in prod).",
        }

    async def _safe(coro):
        try:
            return await coro
        except Exception as exc:
            return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}

    exa, claude, parallel = await asyncio.gather(
        _safe(get_exa_client().smoke_check()) if s.exa_api_key else _noop("exa"),
        _safe(get_claude_client().smoke_check()) if s.anthropic_api_key else _noop("anthropic"),
        _safe(get_parallel_client().smoke_check()) if s.parallel_api_key else _noop("parallel"),
    )

    overall = "ok" if all(r.get("ok") for r in (exa, claude, parallel)) else "degraded"
    return {
        "status": overall,
        "engines": {"exa": exa, "anthropic": claude, "parallel": parallel},
    }


async def _noop(vendor: str) -> dict:
    return {"ok": False, "vendor": vendor, "error": "api_key_not_configured"}
