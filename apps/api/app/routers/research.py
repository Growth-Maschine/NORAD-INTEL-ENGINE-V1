"""Research API — runs the full Company-Card synthesis for one company.

Endpoints under `/api/research/*`:

    POST /runs                     — kick off a research run for a company
    GET  /runs/:id                 — poll run status (SSE is preferred)
    GET  /cards/:id                — fetch a finished CompanyCardV1 (full JSON)
    GET  /companies                — list known companies (by latest card)
    GET  /companies/:id            — one company + its canonical card + lists

Mirrors discovery.py's contracts: same admin gate, same in-flight admission cap,
same in-process `asyncio.create_task` fire-and-forget (an arq worker will swap
this out later without changing the API surface).
"""
from __future__ import annotations

import asyncio
import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.db import get_session
from app.models import Card, Company, Run, Signal, Source, TrendArticle
from app.services.research import ResearchParams, execute_research

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/research", tags=["research"])


# ── Admin gate (same as discovery) ───────────────────────────────────────────


def _require_admin_in_prod(x_admin_token: str | None) -> None:
    """Admin gate disabled — single-user tool, open in all environments."""
    return


# ── Schemas ──────────────────────────────────────────────────────────────────


class ResearchRunRequest(BaseModel):
    company_name: str = Field(..., min_length=1, max_length=200)
    domain_hint: str | None = Field(None, max_length=255)
    trend_article_id: uuid.UUID | None = None


class ResearchRunCreated(BaseModel):
    run_id: uuid.UUID
    status: str
    company_name: str
    sse_url: str
    poll_url: str


class RunStatus(BaseModel):
    id: uuid.UUID
    status: str
    progress_pct: int
    source_kind: str
    query: str
    engines: dict[str, Any]
    engine_outputs: dict[str, Any]
    started_at: datetime | None
    completed_at: datetime | None
    error: str | None
    created_at: datetime
    company_id: uuid.UUID | None
    card_id: uuid.UUID | None


class CardOut(BaseModel):
    id: uuid.UUID
    company_id: uuid.UUID
    run_id: uuid.UUID | None
    schema_version: str
    review_status: str
    score_overall: int | None
    score_growth: int | None
    score_momentum: int | None
    score_fundraising: int | None
    score_acquisition: int | None
    score_partnership_fit: int | None
    score_strategic_fit: int | None
    score_risk: int | None
    card: dict[str, Any]
    created_at: datetime


class CompanyOut(BaseModel):
    id: uuid.UUID
    company_name: str
    domain: str | None
    website: str | None
    logo_url: str | None
    industry: str | None
    category: str | None
    status: str | None
    headquarters_country: str | None
    canonical_card_id: uuid.UUID | None
    score_overall: int | None = None
    created_at: datetime


class CompanyDetail(BaseModel):
    company: CompanyOut
    card: CardOut | None
    signals: list[dict[str, Any]]
    sources: list[dict[str, Any]]


class CompanyFeedRow(BaseModel):
    """One row on the Companies command-center page.

    Represents *a company the user has fired a Profile research run at*. The
    user may have hit Profile before the run resolved to a canonical company
    (in which case `company_id` is still null and we bucket by `query`), or
    they may have re-researched the same company multiple times — we collapse
    those into one row and surface the latest run + a count.
    """
    bucket_key: str                # stable client key: company_id or "q:<query>"
    company_id: uuid.UUID | None
    company_name: str
    domain: str | None
    industry: str | None
    score_overall: int | None
    card_id: uuid.UUID | None
    latest_run: RunStatus
    run_count: int
    is_live: bool                  # any run in queued/researching/synthesizing


# ── POST /runs ───────────────────────────────────────────────────────────────


@router.post("/runs", response_model=ResearchRunCreated, status_code=202)
async def create_research_run(
    body: ResearchRunRequest,
    x_admin_token: str | None = Header(default=None),
    session: AsyncSession = Depends(get_session),
) -> ResearchRunCreated:
    _require_admin_in_prod(x_admin_token)

    # Admission control — keep concurrent paid runs bounded.
    in_flight = (
        await session.execute(
            select(Run).where(
                Run.source_kind == "research",
                Run.status.in_(["queued", "researching", "synthesizing"]),
            )
        )
    ).scalars().all()
    if len(in_flight) >= 5:
        raise HTTPException(
            429,
            f"too many research runs in flight ({len(in_flight)}); wait for them to finish.",
        )

    # Validate article id if provided
    if body.trend_article_id is not None:
        if await session.get(TrendArticle, body.trend_article_id) is None:
            raise HTTPException(404, "trend_article_id not found")

    run = Run(
        query=body.company_name,
        source_kind="research",
        status="queued",
        progress_pct=0,
        engines={
            "company_name": body.company_name,
            "domain_hint": body.domain_hint,
            "trend_article_id": str(body.trend_article_id) if body.trend_article_id else None,
        },
    )
    session.add(run)
    await session.commit()
    await session.refresh(run)

    # Pin run-id onto the article for the UI's "researched" badge.
    if body.trend_article_id is not None:
        article = await session.get(TrendArticle, body.trend_article_id)
        if article is not None:
            existing = list(article.research_run_ids or [])
            if run.id not in existing:
                existing.append(run.id)
                article.research_run_ids = existing
            if article.status not in ("researched",):
                article.status = "researched"
            await session.commit()

    params = ResearchParams(
        company_name=body.company_name,
        domain_hint=body.domain_hint,
        trend_article_id=body.trend_article_id,
    )
    asyncio.create_task(_safe_execute(run.id, params))

    return ResearchRunCreated(
        run_id=run.id,
        status="queued",
        company_name=body.company_name,
        sse_url=f"/api/events/runs/{run.id}",
        poll_url=f"/api/research/runs/{run.id}",
    )


async def _safe_execute(run_id: uuid.UUID, params: ResearchParams) -> None:
    try:
        await execute_research(run_id, params)
    except Exception:  # pragma: no cover — service logs/records internally
        logger.exception("execute_research crashed (run_id=%s)", run_id)


# ── GET /runs/:id ────────────────────────────────────────────────────────────


@router.get("/runs/{run_id}", response_model=RunStatus)
async def get_run(
    run_id: uuid.UUID, session: AsyncSession = Depends(get_session)
) -> RunStatus:
    run = await session.get(Run, run_id)
    if run is None:
        raise HTTPException(404, "run not found")
    return _run_to_status(run)


# ── POST /runs/:id/cancel ────────────────────────────────────────────────────


# Statuses we consider "in flight" and therefore cancellable. Anything in a
# terminal state is left alone (200 with no-op) so the frontend doesn't have
# to special-case races (e.g. the run completed in the half-second between
# the user clicking Cancel and the request landing).
_CANCELLABLE_STATUSES = {"queued", "researching", "synthesizing"}


@router.post("/runs/{run_id}/cancel", response_model=RunStatus)
async def cancel_research_run(
    run_id: uuid.UUID,
    x_admin_token: str | None = Header(default=None),
    session: AsyncSession = Depends(get_session),
) -> RunStatus:
    """Soft-cancel a research run. Marks status='cancelled' and completed_at=now.

    We can't kill the in-process asyncio task that's currently doing the work
    (no cancel token plumbed through Parallel/Exa/Claude calls), but flipping
    the DB row is enough for the UX: the frontend filters cancelled runs out
    of the Profile history list, and the orphan sweeper cleans up any stale
    artifacts in the background.
    """
    _require_admin_in_prod(x_admin_token)

    run = await session.get(Run, run_id)
    if run is None:
        raise HTTPException(404, "run not found")
    if run.source_kind != "research":
        raise HTTPException(400, "run is not a research run")

    # Idempotent: if it's already terminal, just return its current state.
    if run.status in _CANCELLABLE_STATUSES:
        run.status = "cancelled"
        run.completed_at = datetime.now(timezone.utc)
        run.error = run.error or "cancelled by user"
        await session.commit()
        await session.refresh(run)
        logger.info("research run %s cancelled by user", run_id)

    return _run_to_status(run)


# ── GET /cards/:id ───────────────────────────────────────────────────────────


@router.get("/cards/{card_id}", response_model=CardOut)
async def get_card(
    card_id: uuid.UUID, session: AsyncSession = Depends(get_session)
) -> CardOut:
    card = await session.get(Card, card_id)
    if card is None:
        raise HTTPException(404, "card not found")
    return _card_to_out(card)


# ── GET /companies ───────────────────────────────────────────────────────────


@router.get("/companies", response_model=list[CompanyOut])
async def list_companies(
    limit: int = Query(50, ge=1, le=200),
    session: AsyncSession = Depends(get_session),
) -> list[CompanyOut]:
    rows = (
        await session.execute(
            select(Company).order_by(Company.created_at.desc()).limit(limit)
        )
    ).scalars().all()
    # batch-load canonical card scores so the list view sorts well in the UI
    card_ids = [r.canonical_card_id for r in rows if r.canonical_card_id]
    scores: dict[uuid.UUID, int | None] = {}
    if card_ids:
        for c in (
            await session.execute(select(Card).where(Card.id.in_(card_ids)))
        ).scalars().all():
            scores[c.id] = c.score_overall
    return [_company_to_out(r, scores.get(r.canonical_card_id) if r.canonical_card_id else None) for r in rows]


# ── GET /feed ────────────────────────────────────────────────────────────────


@router.get("/feed", response_model=list[CompanyFeedRow])
async def company_feed(
    limit: int = Query(50, ge=1, le=200),
    session: AsyncSession = Depends(get_session),
) -> list[CompanyFeedRow]:
    """Command-center feed for the Companies page.

    Returns one row per company the user has profile-researched, with the
    latest run embedded. Sorted: any company with a live (in-flight) run
    floats to the top with `is_live=true`; the rest fall in by latest run
    recency. Companies with no research runs are excluded — they don't belong
    on this surface.

    Bucketing rule: prefer `Run.company_id`; for runs that haven't resolved
    yet (or failed before resolution), bucket by lower-cased `Run.query` so
    in-flight rows still surface immediately after the user hits Profile.
    """
    from sqlalchemy import func

    # Pull recent research runs — enough headroom to bucket and still respect
    # the caller's display limit.
    recency = func.coalesce(Run.started_at, Run.created_at)
    # NORAD is a single-user tool with sub-thousand total runs; pulling 20×
    # the display limit is well within budget and guards against the case
    # where a single company dominates recent run volume and pushes other
    # companies off the page.
    # Treat cancelled runs as if they never happened on this surface — the
    # user explicitly asked for them to disappear. A company that has *only*
    # cancelled runs (e.g. first-time profile that was cancelled before any
    # company/card row existed) drops off the list entirely; a company with
    # earlier completed runs keeps its row with the prior result as latest.
    runs: list[Run] = list(
        (
            await session.execute(
                select(Run)
                .where(Run.source_kind == "research")
                .where(Run.status != "cancelled")
                .order_by(recency.desc(), Run.id.desc())
                .limit(limit * 20)
            )
        ).scalars().all()
    )

    live_states = {"queued", "researching", "synthesizing"}

    buckets: dict[str, dict[str, Any]] = {}
    for r in runs:
        # Stable key across the unresolved→resolved transition: always prefer
        # the user-typed `query` (it doesn't change when `company_id` gets
        # populated mid-flight). Falling back to company_id only when the
        # query somehow got wiped. This keeps the client's expanded-row state
        # attached to the same bucket as the live Activity log keeps
        # streaming.
        q = (r.query or "").strip().lower()
        if q:
            key = f"q:{q}"
        elif r.company_id is not None:
            key = f"c:{r.company_id}"
        else:
            key = f"r:{r.id}"
        b = buckets.get(key)
        if b is None:
            buckets[key] = {
                "key": key,
                "company_id": r.company_id,
                "query": r.query,
                "latest": r,
                "count": 1,
                "is_live": r.status in live_states,
            }
        else:
            b["count"] += 1
            if r.status in live_states:
                b["is_live"] = True
                # Prefer a live run as the bucket's representative — the user
                # cares about *what's happening right now* for this company,
                # not the most recent finished one. Otherwise the row badges
                # "Profiling…" while showing a failed run's progress/timestamp.
                if b["latest"].status not in live_states:
                    b["latest"] = r
            # `runs` already ordered by recency desc, so first non-live hit
            # wins as latest within the non-live class.
            # If this run has a company_id and the bucket didn't, prefer it.
            if b["company_id"] is None and r.company_id is not None:
                b["company_id"] = r.company_id

    # Hydrate company + card data in batches.
    company_ids = [b["company_id"] for b in buckets.values() if b["company_id"]]
    companies: dict[uuid.UUID, Company] = {}
    if company_ids:
        for c in (
            await session.execute(select(Company).where(Company.id.in_(company_ids)))
        ).scalars().all():
            companies[c.id] = c

    card_ids = [
        c.canonical_card_id for c in companies.values() if c.canonical_card_id
    ]
    cards: dict[uuid.UUID, Card] = {}
    if card_ids:
        for c in (
            await session.execute(select(Card).where(Card.id.in_(card_ids)))
        ).scalars().all():
            cards[c.id] = c

    out: list[CompanyFeedRow] = []
    for b in buckets.values():
        cid: uuid.UUID | None = b["company_id"]
        company = companies.get(cid) if cid else None
        card = (
            cards.get(company.canonical_card_id)
            if company and company.canonical_card_id
            else None
        )
        latest = b["latest"]
        out.append(
            CompanyFeedRow(
                bucket_key=b["key"],
                company_id=cid,
                company_name=(company.company_name if company else (b["query"] or "?")),
                domain=(company.domain if company else None),
                industry=(company.industry if company else None),
                score_overall=(card.score_overall if card else None),
                card_id=(card.id if card else None),
                latest_run=_run_to_status(latest),
                run_count=b["count"],
                is_live=b["is_live"],
            )
        )

    # Sort: live runs first; then by latest run recency desc.
    def _sort_key(row: CompanyFeedRow) -> tuple[int, datetime]:
        when = row.latest_run.started_at or row.latest_run.created_at
        return (0 if row.is_live else 1, -when.timestamp() if when else 0)

    out.sort(key=_sort_key)
    return out[:limit]


# ── GET /companies/:id/runs ──────────────────────────────────────────────────


@router.get("/companies/{company_id}/runs", response_model=list[RunStatus])
async def list_company_research_runs(
    company_id: uuid.UUID,
    limit: int = Query(20, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
) -> list[RunStatus]:
    """Past research runs for a single company, newest first.

    Powers the "Profile history" surface on the company page so the user can
    see every time we've profiled this company and jump back into any of
    those runs (with their saved SSE log + card).
    """
    # Order by true recency: prefer started_at, fall back to created_at so
    # queued/just-spawned rows (started_at still null) sort to the top instead
    # of getting buried behind older completed runs. id is the deterministic
    # tie-breaker.
    from sqlalchemy import func

    recency = func.coalesce(Run.started_at, Run.created_at)
    rows = (
        await session.execute(
            select(Run)
            .where(
                Run.company_id == company_id,
                Run.source_kind == "research",
                # Hide cancelled runs from the company page — they're noise
                # once the user has dismissed them. Audit trail (engine_calls,
                # run_events) is preserved in the DB regardless.
                Run.status != "cancelled",
            )
            .order_by(recency.desc(), Run.id.desc())
            .limit(limit)
        )
    ).scalars().all()
    return [_run_to_status(r) for r in rows]


# ── GET /companies/:id ───────────────────────────────────────────────────────


@router.get("/companies/{company_id}", response_model=CompanyDetail)
async def get_company(
    company_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> CompanyDetail:
    company = await session.get(Company, company_id)
    if company is None:
        raise HTTPException(404, "company not found")
    card: Card | None = None
    if company.canonical_card_id:
        card = await session.get(Card, company.canonical_card_id)

    # Scope signals + sources to the *canonical* card so historical re-runs
    # don't pollute the detail view with mismatched citation ids.
    if card is not None:
        signals = (
            await session.execute(
                select(Signal).where(Signal.card_id == card.id)
                .order_by(Signal.signal_date.desc().nulls_last(), Signal.created_at.desc())
            )
        ).scalars().all()
        sources = (
            await session.execute(
                select(Source).where(Source.card_id == card.id)
                .order_by(Source.local_id.asc())
            )
        ).scalars().all()
    else:
        signals, sources = [], []

    return CompanyDetail(
        company=_company_to_out(company, card.score_overall if card else None),
        card=_card_to_out(card) if card else None,
        signals=[_signal_to_dict(s) for s in signals],
        sources=[_source_to_dict(s) for s in sources],
    )


# ── Helpers ──────────────────────────────────────────────────────────────────


def _run_to_status(r: Run) -> RunStatus:
    return RunStatus(
        id=r.id, status=r.status, progress_pct=r.progress_pct,
        source_kind=r.source_kind, query=r.query,
        engines=r.engines or {}, engine_outputs=r.engine_outputs or {},
        started_at=r.started_at, completed_at=r.completed_at, error=r.error,
        created_at=r.created_at, company_id=r.company_id, card_id=r.card_id,
    )


def _card_to_out(c: Card) -> CardOut:
    return CardOut(
        id=c.id, company_id=c.company_id, run_id=c.run_id,
        schema_version=c.schema_version, review_status=c.review_status,
        score_overall=c.score_overall, score_growth=c.score_growth,
        score_momentum=c.score_momentum, score_fundraising=c.score_fundraising,
        score_acquisition=c.score_acquisition, score_partnership_fit=c.score_partnership_fit,
        score_strategic_fit=c.score_strategic_fit, score_risk=c.score_risk,
        card=c.card or {}, created_at=c.created_at,
    )


def _company_to_out(c: Company, score_overall: int | None = None) -> CompanyOut:
    return CompanyOut(
        id=c.id, company_name=c.company_name, domain=c.domain,
        website=c.website, logo_url=c.logo_url, industry=c.industry,
        category=c.category, status=c.status,
        headquarters_country=c.headquarters_country,
        canonical_card_id=c.canonical_card_id,
        score_overall=score_overall, created_at=c.created_at,
    )


def _signal_to_dict(s: Signal) -> dict[str, Any]:
    return {
        "id": str(s.id),
        "type": s.type,
        "subtype": s.subtype,
        "headline": s.headline,
        "evidence": s.evidence,
        "weight": s.weight,
        "signal_date": s.signal_date.isoformat() if s.signal_date else None,
        "source_refs": s.source_refs or [],
    }


def _source_to_dict(s: Source) -> dict[str, Any]:
    return {
        "id": str(s.id),
        "local_id": s.local_id,
        "url": s.url,
        "title": s.title,
        "type": s.type,
        "trust_tier": s.trust_tier,
        "date_published": s.date_published.isoformat() if s.date_published else None,
        "snippet": s.snippet,
        "freshness_score": s.freshness_score,
    }
