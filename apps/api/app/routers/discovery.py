"""Discovery API.

Three groups of endpoints, all under `/api/discovery/*`:

- `POST /runs`                    — kick off a 5-stage discovery funnel.
- `GET  /runs/:id`                — poll run status (used as fallback by UI).
- `GET  /articles`                — list discovered articles with filters.
- `POST /articles/:id/dismiss`    — soft-hide an article from the Today feed.
- `GET  /clusters`                — grouped keyword clusters for Discovery.
- `POST /clusters`                — create a cluster.
- `PUT  /clusters/:id`            — edit a cluster.
- `DELETE /clusters/:id`          — delete a cluster.

The POST /runs endpoint kicks the funnel off **in-process** via
`asyncio.create_task` so we can demo end-to-end without an arq worker. Once
the worker workflow is running we'll switch to enqueueing into arq.
"""
from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import date, datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, Header, HTTPException, Query

from app.core.config import get_settings
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.models.discovery_cluster import DiscoveryCluster
from app.models.run import Run
from app.models.trend_article import TrendArticle
from app.services.discovery_clusters import ensure_seed_clusters, slugify
from app.services.discovery import DiscoveryParams, execute_discovery

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/discovery", tags=["discovery"])


def _require_admin_in_prod(x_admin_token: str | None) -> None:
    """Admin gate disabled — single-user tool, open in all environments."""
    return


# ── Request / response schemas ──────────────────────────────────────────────


class DiscoveryRunRequest(BaseModel):
    cluster_id: uuid.UUID = Field(..., description="Discovery cluster id")
    date_from: date | None = None
    date_to: date | None = None
    max_articles: int = Field(15, ge=1, le=30)


class DiscoveryRunCreated(BaseModel):
    run_id: uuid.UUID
    status: str
    cluster_id: uuid.UUID
    cluster_name: str
    sse_url: str
    poll_url: str


class DiscoveryClusterIn(BaseModel):
    name: str = Field(..., min_length=2, max_length=120)
    group_name: str = Field(default="Custom", min_length=2, max_length=120)
    description: str | None = Field(default=None, max_length=1000)
    keywords: list[str] = Field(..., min_length=1)
    is_enabled: bool = True
    is_default: bool = False


class DiscoveryClusterOut(BaseModel):
    id: uuid.UUID
    name: str
    slug: str
    group_name: str
    description: str | None
    keywords: list[str]
    is_enabled: bool
    is_default: bool
    sort_order: int
    created_at: datetime
    updated_at: datetime


class DiscoveryClusterGroups(BaseModel):
    groups: dict[str, list[DiscoveryClusterOut]]
    default_cluster_id: uuid.UUID | None


class RunStatus(BaseModel):
    id: uuid.UUID
    status: str
    progress_pct: int
    source_kind: str
    query: str
    engines: dict
    started_at: datetime | None
    completed_at: datetime | None
    error: str | None
    created_at: datetime


class ExtractedCompany(BaseModel):
    name: str
    excerpt: str
    hint_url: str | None = None


class ArticleOut(BaseModel):
    id: uuid.UUID
    url: str
    source: str
    category: str | None
    title: str | None
    dek: str | None
    image_url: str | None
    published_date: date | None
    summary: str | None
    relevance_score: int | None
    relevance_reason: str | None
    status: str
    extracted_companies: list[ExtractedCompany]
    discovery_run_id: uuid.UUID | None
    created_at: datetime


# ── Endpoints ───────────────────────────────────────────────────────────────


def _clean_keywords(keywords: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for kw in keywords:
        v = (kw or "").strip()
        if not v:
            continue
        k = v.lower()
        if k in seen:
            continue
        seen.add(k)
        out.append(v)
    return out


def _cluster_to_out(c: DiscoveryCluster) -> DiscoveryClusterOut:
    return DiscoveryClusterOut(
        id=c.id,
        name=c.name,
        slug=c.slug,
        group_name=c.group_name,
        description=c.description,
        keywords=list(c.keywords or []),
        is_enabled=c.is_enabled,
        is_default=c.is_default,
        sort_order=c.sort_order,
        created_at=c.created_at,
        updated_at=c.updated_at,
    )


@router.get("/clusters", response_model=DiscoveryClusterGroups)
async def list_clusters(
    session: AsyncSession = Depends(get_session),
) -> DiscoveryClusterGroups:
    await ensure_seed_clusters(session)
    rows = (
        await session.execute(
            select(DiscoveryCluster).order_by(
                DiscoveryCluster.group_name.asc(),
                DiscoveryCluster.sort_order.asc(),
                DiscoveryCluster.created_at.asc(),
            )
        )
    ).scalars().all()
    groups: dict[str, list[DiscoveryClusterOut]] = {}
    default_cluster_id: uuid.UUID | None = None
    for c in rows:
        o = _cluster_to_out(c)
        groups.setdefault(c.group_name, []).append(o)
        if c.is_default:
            default_cluster_id = c.id
    return DiscoveryClusterGroups(groups=groups, default_cluster_id=default_cluster_id)


@router.post("/clusters", response_model=DiscoveryClusterOut, status_code=201)
async def create_cluster(
    body: DiscoveryClusterIn,
    x_admin_token: str | None = Header(default=None),
    session: AsyncSession = Depends(get_session),
) -> DiscoveryClusterOut:
    _require_admin_in_prod(x_admin_token)
    await ensure_seed_clusters(session)
    keywords = _clean_keywords(body.keywords)
    if not keywords:
        raise HTTPException(400, "keywords must include at least one non-empty value")
    slug = slugify(body.name)
    exists = (
        await session.execute(select(DiscoveryCluster.id).where(DiscoveryCluster.slug == slug))
    ).scalar_one_or_none()
    if exists is not None:
        slug = f"{slug}-{str(uuid.uuid4())[:8]}"
    sort_order = (
        (await session.execute(select(DiscoveryCluster.sort_order).order_by(DiscoveryCluster.sort_order.desc()).limit(1)))
        .scalar_one_or_none()
    ) or 0
    c = DiscoveryCluster(
        name=body.name.strip(),
        slug=slug,
        group_name=body.group_name.strip() or "Custom",
        description=(body.description or "").strip() or None,
        keywords=keywords,
        is_enabled=body.is_enabled,
        is_default=body.is_default,
        sort_order=sort_order + 1,
    )
    session.add(c)
    await session.flush()
    if c.is_default:
        others = (
            await session.execute(
                select(DiscoveryCluster).where(
                    DiscoveryCluster.id != c.id,
                    DiscoveryCluster.is_default.is_(True),
                )
            )
        ).scalars().all()
        for row in others:
            row.is_default = False
    await session.commit()
    await session.refresh(c)
    return _cluster_to_out(c)


@router.put("/clusters/{cluster_id}", response_model=DiscoveryClusterOut)
async def update_cluster(
    cluster_id: uuid.UUID,
    body: DiscoveryClusterIn,
    x_admin_token: str | None = Header(default=None),
    session: AsyncSession = Depends(get_session),
) -> DiscoveryClusterOut:
    _require_admin_in_prod(x_admin_token)
    await ensure_seed_clusters(session)
    c = await session.get(DiscoveryCluster, cluster_id)
    if c is None:
        raise HTTPException(404, "cluster not found")
    keywords = _clean_keywords(body.keywords)
    if not keywords:
        raise HTTPException(400, "keywords must include at least one non-empty value")
    maybe_slug = slugify(body.name)
    if maybe_slug != c.slug:
        conflict = (
            await session.execute(
                select(DiscoveryCluster.id).where(
                    DiscoveryCluster.slug == maybe_slug,
                    DiscoveryCluster.id != c.id,
                )
            )
        ).scalar_one_or_none()
        c.slug = maybe_slug if conflict is None else f"{maybe_slug}-{str(c.id)[:8]}"
    c.name = body.name.strip()
    c.group_name = body.group_name.strip() or "Custom"
    c.description = (body.description or "").strip() or None
    c.keywords = keywords
    c.is_enabled = body.is_enabled
    old_default = c.is_default
    c.is_default = body.is_default
    if c.is_default:
        others = (
            await session.execute(
                select(DiscoveryCluster).where(
                    DiscoveryCluster.id != c.id,
                    DiscoveryCluster.is_default.is_(True),
                )
            )
        ).scalars().all()
        for row in others:
            row.is_default = False
    elif old_default:
        replacement = (
            await session.execute(
                select(DiscoveryCluster).where(DiscoveryCluster.id != c.id).order_by(
                    DiscoveryCluster.sort_order.asc(), DiscoveryCluster.created_at.asc()
                ).limit(1)
            )
        ).scalar_one_or_none()
        if replacement is not None:
            replacement.is_default = True
    await session.commit()
    await session.refresh(c)
    return _cluster_to_out(c)


@router.delete("/clusters/{cluster_id}")
async def delete_cluster(
    cluster_id: uuid.UUID,
    x_admin_token: str | None = Header(default=None),
    session: AsyncSession = Depends(get_session),
) -> dict[str, bool]:
    _require_admin_in_prod(x_admin_token)
    await ensure_seed_clusters(session)
    c = await session.get(DiscoveryCluster, cluster_id)
    if c is None:
        return {"ok": True}
    was_default = c.is_default
    await session.delete(c)
    await session.flush()
    if was_default:
        replacement = (
            await session.execute(
                select(DiscoveryCluster).order_by(
                    DiscoveryCluster.sort_order.asc(), DiscoveryCluster.created_at.asc()
                ).limit(1)
            )
        ).scalar_one_or_none()
        if replacement is not None:
            replacement.is_default = True
    await session.commit()
    return {"ok": True}


@router.post("/runs", response_model=DiscoveryRunCreated, status_code=202)
async def create_discovery_run(
    body: DiscoveryRunRequest,
    x_admin_token: str | None = Header(default=None),
    session: AsyncSession = Depends(get_session),
) -> DiscoveryRunCreated:
    _require_admin_in_prod(x_admin_token)
    await ensure_seed_clusters(session)
    cluster = await session.get(DiscoveryCluster, body.cluster_id)
    if cluster is None:
        raise HTTPException(400, f"unknown cluster_id: {body.cluster_id}")
    if not cluster.is_enabled:
        raise HTTPException(400, f"cluster is disabled: {cluster.name}")
    keywords = [str(k) for k in (cluster.keywords or []) if str(k).strip()]
    query_core = " ".join(keywords[:8]).strip()
    query = f"{cluster.name} {query_core}".strip()

    # Admission control: refuse if >5 discovery runs are already in flight.
    # Cheap guard until per-user quotas + arq concurrency limits are wired.
    in_flight = (
        await session.execute(
            select(Run).where(
                Run.source_kind == "discovery",
                Run.status.in_(["queued", "researching", "synthesizing"]),
            )
        )
    ).scalars().all()
    if len(in_flight) >= 5:
        raise HTTPException(
            429,
            f"too many discovery runs in flight ({len(in_flight)}); wait for them to finish.",
        )

    run = Run(
        query=f"discover:{cluster.slug}",
        source_kind="discovery",
        status="queued",
        progress_pct=0,
        engines={
            "cluster_id": str(cluster.id),
            "cluster_slug": cluster.slug,
            "cluster_name": cluster.name,
            "cluster_keywords": keywords,
            "query": query,
            "date_from": body.date_from.isoformat() if body.date_from else None,
            "date_to": body.date_to.isoformat() if body.date_to else None,
            "max_articles": body.max_articles,
        },
    )
    session.add(run)
    await session.commit()
    await session.refresh(run)

    params = DiscoveryParams(
        category=cluster.slug,
        cluster_name=cluster.name,
        cluster_keywords=keywords,
        search_query=query,
        date_from=body.date_from,
        date_to=body.date_to,
        max_articles=body.max_articles,
    )
    # Fire in-process. The function owns its own DB session lifecycle.
    asyncio.create_task(_safe_execute(run.id, params))

    return DiscoveryRunCreated(
        run_id=run.id,
        status="queued",
        cluster_id=cluster.id,
        cluster_name=cluster.name,
        sse_url=f"/api/events/runs/{run.id}",
        poll_url=f"/api/discovery/runs/{run.id}",
    )


async def _safe_execute(run_id: uuid.UUID, params: DiscoveryParams) -> None:
    try:
        await execute_discovery(run_id, params)
    except Exception:  # pragma: no cover — orchestrator logs internally
        logger.exception("execute_discovery crashed (run_id=%s)", run_id)


@router.get("/runs/{run_id}", response_model=RunStatus)
async def get_run(
    run_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> RunStatus:
    run = await session.get(Run, run_id)
    if run is None:
        raise HTTPException(404, "run not found")
    return RunStatus(
        id=run.id,
        status=run.status,
        progress_pct=run.progress_pct,
        source_kind=run.source_kind,
        query=run.query,
        engines=run.engines or {},
        started_at=run.started_at,
        completed_at=run.completed_at,
        error=run.error,
        created_at=run.created_at,
    )


@router.get("/runs", response_model=list[RunStatus])
async def list_runs(
    limit: int = Query(20, ge=1, le=100),
    source_kind: str | None = Query(None),
    session: AsyncSession = Depends(get_session),
) -> list[RunStatus]:
    stmt = select(Run).order_by(Run.created_at.desc()).limit(limit)
    if source_kind:
        stmt = stmt.where(Run.source_kind == source_kind)
    rows = (await session.execute(stmt)).scalars().all()
    return [
        RunStatus(
            id=r.id, status=r.status, progress_pct=r.progress_pct,
            source_kind=r.source_kind, query=r.query, engines=r.engines or {},
            started_at=r.started_at, completed_at=r.completed_at,
            error=r.error, created_at=r.created_at,
        )
        for r in rows
    ]


@router.get("/articles", response_model=list[ArticleOut])
async def list_articles(
    category: str | None = Query(None),
    status: Literal[
        "discovered", "ranked", "read", "extracted", "dismissed", "researched", "all"
    ] = Query("extracted", description="Lifecycle filter; 'all' returns every status"),
    run_id: uuid.UUID | None = Query(None),
    min_score: int | None = Query(None, ge=0, le=100),
    limit: int = Query(50, ge=1, le=200),
    session: AsyncSession = Depends(get_session),
) -> list[ArticleOut]:
    stmt = select(TrendArticle)
    if status != "all":
        stmt = stmt.where(TrendArticle.status == status)
    if category:
        stmt = stmt.where(TrendArticle.category == category)
    if run_id:
        stmt = stmt.where(TrendArticle.discovery_run_id == run_id)
    if min_score is not None:
        stmt = stmt.where(TrendArticle.relevance_score >= min_score)
    stmt = stmt.order_by(
        TrendArticle.relevance_score.desc().nulls_last(),
        TrendArticle.created_at.desc(),
    ).limit(limit)

    rows = (await session.execute(stmt)).scalars().all()
    return [_to_article_out(r) for r in rows]


@router.post("/articles/{article_id}/dismiss", response_model=ArticleOut)
async def dismiss_article(
    article_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> ArticleOut:
    a = await session.get(TrendArticle, article_id)
    if a is None:
        raise HTTPException(404, "article not found")
    a.status = "dismissed"
    await session.commit()
    await session.refresh(a)
    return _to_article_out(a)


def _to_article_out(a: TrendArticle) -> ArticleOut:
    companies_raw = a.extracted_companies or []
    companies = [
        ExtractedCompany(
            name=c.get("name", ""),
            excerpt=c.get("excerpt", ""),
            hint_url=c.get("hint_url"),
        )
        for c in companies_raw
        if isinstance(c, dict) and c.get("name")
    ]
    return ArticleOut(
        id=a.id,
        url=a.url,
        source=a.source,
        category=a.category,
        title=a.title,
        dek=a.dek,
        image_url=a.image_url,
        published_date=a.published_date,
        summary=a.summary,
        relevance_score=a.relevance_score,
        relevance_reason=a.relevance_reason,
        status=a.status,
        extracted_companies=companies,
        discovery_run_id=a.discovery_run_id,
        created_at=a.created_at,
    )
