"""Diffbot Knowledge Graph client — Enhance API (and friends).

Third research engine in NORAD, sitting alongside Parallel + Exa. Where
Parallel returns an LLM-generated brief and Exa returns raw page text,
Diffbot returns a **pre-structured organization record** from a continuously-
crawled graph of ~5B orgs and 50B+ facts, with origin URLs attached to every
fact.

For Stage 2 of Research we use the **Enhance** endpoint:

    GET https://kg.diffbot.com/kg/v3/enhance
        ?token=<DIFFBOT_API_KEY>
        &type=Organization
        &name=<company name>
        &url=<domain hint>            # optional but dramatically boosts match

Auth: query-string `token` only — no bearer header. See
https://docs.diffbot.com/reference/authentication.

We talk to REST directly via httpx (Diffbot's Python SDKs are partial; the
shape is simple enough that a thin wrapper is cleaner than depending on a
third-party SDK). Same pattern as `parallel_client.py`.
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any

import httpx

from app.core.config import get_settings
from app.engines._pricing import diffbot_cost_usd

logger = logging.getLogger(__name__)

DIFFBOT_BASE_URL = "https://kg.diffbot.com"
DEFAULT_TIMEOUT_S = 30.0


# ── Types ───────────────────────────────────────────────────────────────────


@dataclass(slots=True)
class DiffbotEnhanceResponse:
    """Result of a single Enhance call.

    Status semantics follow the project-wide convention enforced by the
    `engine_calls.status` check constraint:

    - `ok`      — HTTP succeeded. Note: a 200 with `hits=0` is still `ok`;
                  the company simply isn't in the KG. Inspect `entity` /
                  `hits` to know whether real data came back.
    - `error`   — HTTP 4xx/5xx, parse failure, or auth error.
    - `timeout` — wall-clock hard cap tripped.
    """

    status: str
    score: float = 0.0          # Diffbot match confidence (0.0–1.0)
    esscore: float = 0.0        # raw ElasticSearch relevance
    entity: dict[str, Any] | None = None  # the full org record (~150 fields)
    hits: int = 0
    kg_version: str | None = None
    cost_usd: float = 0.0       # plan-bundled — always 0 today
    latency_ms: float = 0.0
    error: str | None = None
    # Echo of the params we sent. Persisted to engine_calls.request_payload.
    request_params: dict[str, Any] = field(default_factory=dict)
    # Raw response body (truncated downstream). Persisted to response_payload.
    response_body: dict[str, Any] = field(default_factory=dict)

    @property
    def succeeded(self) -> bool:
        """True iff Diffbot returned a usable entity record.

        Distinct from `status == 'ok'`: a successful HTTP call with zero hits
        is `status='ok'` but `succeeded=False` — easier for callers (the
        research pipeline) to gate the synthesizer prompt on.
        """
        return self.status == "ok" and self.entity is not None and self.hits > 0


# ── Client ──────────────────────────────────────────────────────────────────


class DiffbotClient:
    """Async httpx wrapper around the Diffbot KG REST API."""

    def __init__(self, api_key: str, base_url: str = DIFFBOT_BASE_URL):
        if not api_key:
            raise RuntimeError("DIFFBOT_API_KEY is not configured")
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")

    # ── Enhance ──────────────────────────────────────────────────────────────

    async def enhance_organization(
        self,
        *,
        name: str,
        url: str | None = None,
        location: str | None = None,
        size: int = 1,
        timeout_s: float = DEFAULT_TIMEOUT_S,
    ) -> DiffbotEnhanceResponse:
        """Look up an Organization by partial identifiers.

        `name` is required. Passing a `url` (the company's domain or
        homepage) sharpens the match dramatically — without it, name-only
        queries can collide on common company names. The research pipeline
        opportunistically derives a domain from Exa results when one isn't
        provided upfront, then re-fires Enhance with the better signal.

        `size` caps the number of candidates returned. We use 1 (best match)
        for the research pipeline; higher values cost proportionately more
        plan credits.

        Never raises — all failure modes are folded into a
        `DiffbotEnhanceResponse` so the caller can keep moving.
        """
        if not name or not name.strip():
            return DiffbotEnhanceResponse(
                status="error",
                error="enhance_organization called with empty name",
            )

        params: dict[str, Any] = {
            "token": self._api_key,
            "type": "Organization",
            "name": name.strip(),
            "size": size,
        }
        if url:
            params["url"] = url
        if location:
            params["location"] = location

        # Snapshot the request without the token — engine_calls is a JSONB
        # audit log; secrets must never land in it.
        req_snapshot = {k: v for k, v in params.items() if k != "token"}

        t0 = time.perf_counter()
        try:
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(
                    connect=10.0, read=timeout_s, write=10.0, pool=10.0,
                ),
            ) as client:
                resp = await client.get(
                    f"{self._base_url}/kg/v3/enhance",
                    params=params,
                    headers={"accept": "application/json"},
                )
        except httpx.TimeoutException as exc:
            return DiffbotEnhanceResponse(
                status="timeout",
                latency_ms=_ms_since(t0),
                error=f"enhance_timeout after {timeout_s}s: {type(exc).__name__}",
                request_params=req_snapshot,
            )
        except httpx.HTTPError as exc:
            return DiffbotEnhanceResponse(
                status="error",
                latency_ms=_ms_since(t0),
                error=f"http_error: {type(exc).__name__}: {exc}",
                request_params=req_snapshot,
            )

        latency_ms = _ms_since(t0)

        if resp.status_code != 200:
            body = ""
            try:
                body = resp.text[:400]
            except Exception:
                pass
            return DiffbotEnhanceResponse(
                status="error",
                latency_ms=latency_ms,
                error=f"http_{resp.status_code}: {body}",
                request_params=req_snapshot,
            )

        try:
            payload = resp.json()
        except (ValueError, TypeError) as exc:
            return DiffbotEnhanceResponse(
                status="error",
                latency_ms=latency_ms,
                error=f"json_decode_failed: {type(exc).__name__}: {exc}",
                request_params=req_snapshot,
            )

        data = payload.get("data") or []
        hits = int(payload.get("hits") or len(data))
        kg_version = payload.get("kgversion")

        if not data:
            return DiffbotEnhanceResponse(
                status="ok",
                hits=hits,
                kg_version=kg_version,
                cost_usd=diffbot_cost_usd("enhance"),
                latency_ms=latency_ms,
                request_params=req_snapshot,
                response_body=payload,
            )

        top = data[0] if isinstance(data, list) else {}
        return DiffbotEnhanceResponse(
            status="ok",
            score=float(top.get("score") or 0.0),
            esscore=float(top.get("esscore") or 0.0),
            entity=top.get("entity"),
            hits=hits,
            kg_version=kg_version,
            cost_usd=diffbot_cost_usd("enhance"),
            latency_ms=latency_ms,
            request_params=req_snapshot,
            response_body=payload,
        )

    # ── Smoke probe ──────────────────────────────────────────────────────────

    async def smoke_check(self) -> dict[str, Any]:
        """Verify auth + reachability with a single Enhance call.

        Uses Diffbot's own org ("Diffbot") so we always get a hit. Same
        return shape as the other engines' smoke_check methods.
        """
        t0 = time.perf_counter()
        try:
            resp = await self.enhance_organization(
                name="Diffbot",
                url="diffbot.com",
                timeout_s=15.0,
            )
            ok = resp.status == "ok" and resp.entity is not None
            return {
                "ok": ok,
                "latency_ms": _ms_since(t0),
                "vendor": "diffbot",
                "score": resp.score,
                **({"error": resp.error} if not ok else {}),
            }
        except Exception as exc:
            return {
                "ok": False,
                "latency_ms": _ms_since(t0),
                "error": f"{type(exc).__name__}: {exc}",
                "vendor": "diffbot",
            }


def _ms_since(t0: float) -> float:
    return round((time.perf_counter() - t0) * 1000, 1)


# ── Singleton accessor ──────────────────────────────────────────────────────

_client: DiffbotClient | None = None


def get_diffbot_client() -> DiffbotClient:
    global _client
    if _client is None:
        settings = get_settings()
        _client = DiffbotClient(api_key=settings.diffbot_api_key)
    return _client
