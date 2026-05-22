"""Exa client — search + contents extraction.

Used in two places in NORAD:
1. **Discovery funnel** — `search()` to find candidate TrendHunter articles
   filtered by domain + date range, then `get_contents()` on top-N to read
   full bodies + outbound URLs.
2. **Research engine** — targeted per-block `search()` calls to gather
   sources for each Company Card block (funding, leadership, financials, …).

The Exa Python SDK (`exa-py`) is synchronous; we wrap calls in
`asyncio.to_thread` so the async FastAPI app doesn't block its event loop.

Every call is logged to the `engine_calls` table via `_log_call` for cost
visibility — see `apps/api/app/engines/_pricing.py` for unit prices.
"""
from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from datetime import date
from typing import Any

from exa_py import Exa

from app.core.config import get_settings
from app.engines._pricing import exa_cost_usd

logger = logging.getLogger(__name__)


# ── Result types (decoupled from the SDK's shape so we control our API) ─────


@dataclass(slots=True)
class ExaSearchResult:
    url: str
    title: str | None
    snippet: str | None
    published_date: str | None  # YYYY-MM-DD when known
    score: float | None
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ExaContent:
    url: str
    title: str | None
    text: str
    outbound_links: list[str]
    published_date: str | None
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ExaCallStats:
    """Per-call cost + latency metadata. Persisted to engine_calls."""

    operation: str
    units: int
    cost_usd: float
    latency_ms: float
    status: str
    error: str | None = None


# ── Client ──────────────────────────────────────────────────────────────────


class ExaClient:
    """Async-friendly wrapper around the synchronous exa-py SDK."""

    def __init__(self, api_key: str):
        if not api_key:
            raise RuntimeError("EXA_API_KEY is not configured")
        self._sdk = Exa(api_key=api_key)

    # ── Search ──────────────────────────────────────────────────────────────

    async def search(
        self,
        query: str,
        *,
        include_domains: list[str] | None = None,
        exclude_domains: list[str] | None = None,
        start_published_date: date | str | None = None,
        end_published_date: date | str | None = None,
        num_results: int = 20,
        category: str | None = None,
        search_type: str = "auto",
        deep_model: str | None = None,
    ) -> tuple[list[ExaSearchResult], ExaCallStats]:
        """Run an Exa search. Returns (results, stats).

        `search_type` is one of: auto | fast | neural | keyword | deep.
        When `search_type="deep"`, `deep_model` selects the deep-research
        reasoning model (deep-lite | deep | deep-reasoning). Ignored otherwise.
        """
        kwargs: dict[str, Any] = {"num_results": num_results, "type": search_type}
        # NOTE: the current `exa-py` SDK does not expose a `deep_model` kwarg
        # on .search(). We keep the parameter in our public signature (and in
        # ResearchConfig) so the UI/API can persist user intent today; wire it
        # through once Exa's SDK ships the option. `type="deep"` alone is what
        # actually activates deep research at the moment.
        _ = deep_model  # intentionally unused until SDK supports it
        if include_domains:
            kwargs["include_domains"] = include_domains
        if exclude_domains:
            kwargs["exclude_domains"] = exclude_domains
        if start_published_date:
            kwargs["start_published_date"] = _isoformat(start_published_date)
        if end_published_date:
            kwargs["end_published_date"] = _isoformat(end_published_date)
        if category:
            kwargs["category"] = category

        t0 = time.perf_counter()
        try:
            # Hard wall-clock cap so a hung Exa SDK call can't freeze Stage 2
            # (Exa's deep-search can take 30-60s normally; 120s is a generous
            # ceiling that still guarantees the pipeline returns).
            raw = await asyncio.wait_for(
                asyncio.to_thread(self._sdk.search, query, **kwargs),
                timeout=120.0,
            )
            results = [_to_search_result(item) for item in (raw.results or [])]
            stats = ExaCallStats(
                operation="search",
                units=1,
                cost_usd=exa_cost_usd("search"),
                latency_ms=_ms_since(t0),
                status="ok",
            )
            return results, stats
        except asyncio.TimeoutError:
            logger.warning("Exa search hard-timeout after 120s for query=%r", query)
            return [], ExaCallStats(
                operation="search",
                units=1,
                cost_usd=0.0,
                latency_ms=_ms_since(t0),
                status="timeout",
                error="exa_search hard_timeout after 120s",
            )
        except Exception as exc:
            logger.exception("Exa search failed: %s", exc)
            return [], ExaCallStats(
                operation="search",
                units=1,
                cost_usd=exa_cost_usd("search"),
                latency_ms=_ms_since(t0),
                status="error",
                error=f"{type(exc).__name__}: {exc}",
            )

    # ── Get Contents ────────────────────────────────────────────────────────

    async def get_contents(
        self,
        urls: list[str],
        *,
        livecrawl: str = "fallback",
        text: bool = True,
        extract_links: bool = True,
    ) -> tuple[list[ExaContent], ExaCallStats]:
        """Fetch full text + outbound links for one or many URLs.

        NOTE: `livecrawl="always"` errors on TrendHunter (anti-bot blocks
        fresh crawls). `"fallback"` tries live then falls back to Exa's
        cache, which holds TH content — the only mode that returns bodies
        for our pipeline.
        """
        if not urls:
            return [], ExaCallStats(
                operation="get_contents",
                units=0,
                cost_usd=0.0,
                latency_ms=0.0,
                status="ok",
            )

        kwargs: dict[str, Any] = {
            "livecrawl": livecrawl,
            "text": text,
        }
        # `extras` is the exa-py 1.x parameter for outbound link extraction
        if extract_links:
            kwargs["extras"] = {"links": 25}

        t0 = time.perf_counter()
        try:
            # Hard wall-clock cap — get_contents can be slow with livecrawl,
            # but 90s is plenty for any realistic URL batch we send.
            raw = await asyncio.wait_for(
                asyncio.to_thread(self._sdk.get_contents, urls, **kwargs),
                timeout=90.0,
            )
            results = [_to_content(item) for item in (raw.results or [])]
            stats = ExaCallStats(
                operation="get_contents",
                units=len(urls),
                cost_usd=exa_cost_usd("get_contents", len(urls)),
                latency_ms=_ms_since(t0),
                status="ok",
            )
            return results, stats
        except asyncio.TimeoutError:
            logger.warning(
                "Exa get_contents hard-timeout after 90s for %d urls", len(urls),
            )
            return [], ExaCallStats(
                operation="get_contents",
                units=len(urls),
                cost_usd=0.0,
                latency_ms=_ms_since(t0),
                status="timeout",
                error=f"exa_get_contents hard_timeout after 90s ({len(urls)} urls)",
            )
        except Exception as exc:
            logger.exception("Exa get_contents failed: %s", exc)
            return [], ExaCallStats(
                operation="get_contents",
                units=len(urls),
                cost_usd=exa_cost_usd("get_contents", len(urls)),
                latency_ms=_ms_since(t0),
                status="error",
                error=f"{type(exc).__name__}: {exc}",
            )

    # ── Smoke probe (no credits burned beyond 1 search) ─────────────────────

    async def smoke_check(self) -> dict[str, Any]:
        """Tiny live call. Used by /health/engines."""
        t0 = time.perf_counter()
        try:
            await asyncio.to_thread(
                self._sdk.search, "trendhunter functional beverages", num_results=1
            )
            return {
                "ok": True,
                "latency_ms": _ms_since(t0),
                "vendor": "exa",
            }
        except Exception as exc:
            return {
                "ok": False,
                "latency_ms": _ms_since(t0),
                "error": f"{type(exc).__name__}: {exc}",
                "vendor": "exa",
            }


# ── Helpers ─────────────────────────────────────────────────────────────────


def _isoformat(d: date | str) -> str:
    return d.isoformat() if isinstance(d, date) else d


def _ms_since(t0: float) -> float:
    return round((time.perf_counter() - t0) * 1000, 1)


def _to_search_result(item: Any) -> ExaSearchResult:
    return ExaSearchResult(
        url=getattr(item, "url", ""),
        title=getattr(item, "title", None),
        snippet=getattr(item, "text", None) or getattr(item, "snippet", None),
        published_date=getattr(item, "published_date", None),
        score=getattr(item, "score", None),
    )


def _to_content(item: Any) -> ExaContent:
    extras = getattr(item, "extras", {}) or {}
    links = extras.get("links") if isinstance(extras, dict) else None
    return ExaContent(
        url=getattr(item, "url", ""),
        title=getattr(item, "title", None),
        text=getattr(item, "text", "") or "",
        outbound_links=list(links or []),
        published_date=getattr(item, "published_date", None),
    )


# ── Singleton accessor ──────────────────────────────────────────────────────

_client: ExaClient | None = None


def get_exa_client() -> ExaClient:
    global _client
    if _client is None:
        settings = get_settings()
        _client = ExaClient(api_key=settings.exa_api_key)
    return _client
