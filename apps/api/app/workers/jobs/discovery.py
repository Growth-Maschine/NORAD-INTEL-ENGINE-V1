"""Discovery funnel arq job — wraps `services.discovery.execute_discovery`.

The actual funnel logic lives in `app/services/discovery.py` so it can be
invoked from either the arq worker OR an in-process `asyncio.create_task`
(useful while the worker workflow isn't running yet).
"""
from __future__ import annotations

import logging
import uuid
from datetime import date
from typing import Any

from app.services.discovery import DiscoveryParams, execute_discovery

logger = logging.getLogger(__name__)


def _parse_date(s: str | None) -> date | None:
    if not s:
        return None
    try:
        return date.fromisoformat(s[:10])
    except Exception:
        return None


async def run_discovery(
    ctx: dict[str, Any],
    run_id: str,
    *,
    category: str,
    date_from: str | None = None,
    date_to: str | None = None,
    keyword: str | None = None,
    max_articles: int = 15,
) -> dict[str, Any]:
    """arq entrypoint. Returns a result dict; full state is in the DB."""
    params = DiscoveryParams(
        category=category,
        keyword=keyword,
        date_from=_parse_date(date_from),
        date_to=_parse_date(date_to),
        max_articles=max_articles,
    )
    result = await execute_discovery(uuid.UUID(run_id), params)
    return {
        "run_id": str(result.run_id),
        "status": result.status,
        "candidates_found": result.candidates_found,
        "new_articles": result.new_articles,
        "ranked": result.ranked,
        "read": result.read,
        "extracted": result.extracted,
        "cost_usd": result.cost_usd,
        "elapsed_s": result.elapsed_s,
        "error": result.error,
    }
