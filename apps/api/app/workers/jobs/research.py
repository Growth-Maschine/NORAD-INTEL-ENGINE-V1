"""Research engine job — full Company Card pipeline for one company.

Fires on user click of "Research" on an article card. Steps:
1. Build ResearchInput from `trend_articles` row + company hint
2. Spawn Parallel + Exa-deep IN PARALLEL (asyncio.gather)
3. Hand both outputs to Claude Sonnet synthesizer
4. Validate against CompanyCardV1, save card/signals/sources, mark run complete

The synthesizer logic lands in Phase C Step 3 — this file is the wired stub.
"""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


async def run_research(
    ctx: dict[str, Any],
    run_id: str,
    *,
    company_name: str,
    trend_article_id: str | None = None,
) -> dict[str, Any]:
    """Run the main research engine. STUB — real implementation lands next."""
    logger.info(
        "run_research stub invoked run_id=%s company=%s article=%s",
        run_id,
        company_name,
        trend_article_id,
    )
    return {
        "run_id": run_id,
        "status": "stub",
        "note": "research engine logic ships with Claude synthesizer (Phase C Step 3)",
    }
