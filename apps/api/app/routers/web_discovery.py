"""Web Discovery API — separate cluster/query system for Exa web discovery."""
from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import date, datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.admin_auth import require_admin
from app.core.db import get_session
from app.engines.exa_client import coerce_exa_highlights
from app.models.article import Article
from app.models.engine_call import EngineCall
from app.models.run import Run
from app.models.web_discovery_cluster import WebDiscoveryCluster
from app.models.web_discovery_query import WebDiscoveryQuery
from app.services.run_events import emit
from app.services.web_discovery import (
    clean_reading_text,
    normalize_article_url,
    safe_execute_web_discovery_run,
)
from app.utils.slug import slugify

router = APIRouter(prefix="/api/web-discovery", tags=["web-discovery"])
logger = logging.getLogger(__name__)


def _require_admin_in_prod(x_admin_token: str | None) -> None:
    """Admin gate disabled — single-user tool, open in all environments."""
    return


def _clean_items(items: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for item in items:
        v = (item or "").strip()
        if not v:
            continue
        key = v.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(v)
    return out


class WebDiscoveryClusterIn(BaseModel):
    name: str = Field(..., min_length=2, max_length=140)
    description: str | None = Field(default=None, max_length=2000)
    priority: str = Field(default="P2 Daily Intelligence")
    is_active: bool = True
    include_keywords: list[str] = Field(default_factory=list)
    exclude_keywords: list[str] = Field(default_factory=list)
    geography_focus: list[str] = Field(default_factory=list)
    source_preferences: list[str] = Field(default_factory=list)
    signal_priorities: list[str] = Field(default_factory=list)


class WebDiscoveryClusterOut(BaseModel):
    id: uuid.UUID
    name: str
    slug: str
    description: str | None
    priority: str
    is_active: bool
    include_keywords: list[str]
    exclude_keywords: list[str]
    geography_focus: list[str]
    source_preferences: list[str]
    signal_priorities: list[str]
    query_count: int
    signal_count: int
    last_run_at: datetime | None
    created_at: datetime
    updated_at: datetime


class WebDiscoveryClusterList(BaseModel):
    clusters: list[WebDiscoveryClusterOut]


class WebDiscoveryQueryIn(BaseModel):
    label: str = Field(..., min_length=2, max_length=160)
    search_query: str = Field(..., min_length=5, max_length=3000)
    search_type: str = Field(default="auto")
    num_results: int = Field(default=10, ge=1, le=100)
    content_highlights: bool = True
    content_text: bool = False
    content_summary: bool = False
    structured_outputs: bool = False
    highlights_max_chars: int | None = Field(default=None, ge=0, le=100000)
    highlights_guiding_query: str | None = Field(default=None, max_length=2000)
    text_max_chars: int | None = Field(default=None, ge=0, le=200000)
    text_main_content_only: bool = True
    summary_max_chars: int | None = Field(default=None, ge=0, le=50000)
    system_prompt: str | None = Field(default=None, max_length=20000)
    output_schema: dict[str, Any] | None = None
    livecrawl_timeout_ms: int = Field(default=10000, ge=0, le=120000)
    max_age_hours: int | None = Field(default=None, ge=-1, le=24 * 365)
    subpages: int = Field(default=0, ge=0, le=20)
    extra_links: int = Field(default=0, ge=0, le=20)
    extra_image_links: int = Field(default=0, ge=0, le=20)
    subpage_target_keywords: list[str] = Field(default_factory=list)
    category: str | None = Field(default=None, max_length=80)
    user_location: str | None = Field(default=None, max_length=8)
    include_domains: list[str] = Field(default_factory=list)
    exclude_domains: list[str] = Field(default_factory=list)
    published_after: date | None = None
    published_before: date | None = None
    crawled_after: date | None = None
    crawled_before: date | None = None
    content_moderation: bool = False
    stream_response: bool = False
    additional_queries: list[str] = Field(default_factory=list)
    is_active: bool = True


class WebDiscoveryQueryOut(BaseModel):
    id: uuid.UUID
    cluster_id: uuid.UUID
    label: str
    search_query: str
    search_type: str
    num_results: int
    content_highlights: bool
    content_text: bool
    content_summary: bool
    structured_outputs: bool
    highlights_max_chars: int | None
    highlights_guiding_query: str | None
    text_max_chars: int | None
    text_main_content_only: bool
    summary_max_chars: int | None
    system_prompt: str | None
    output_schema: dict[str, Any] | None
    livecrawl_timeout_ms: int
    max_age_hours: int | None
    subpages: int
    extra_links: int
    extra_image_links: int
    subpage_target_keywords: list[str]
    category: str | None
    user_location: str | None
    include_domains: list[str]
    exclude_domains: list[str]
    published_after: date | None
    published_before: date | None
    crawled_after: date | None
    crawled_before: date | None
    content_moderation: bool
    stream_response: bool
    additional_queries: list[str]
    is_active: bool
    created_at: datetime
    updated_at: datetime


class WebDiscoveryRunCreated(BaseModel):
    run_id: uuid.UUID
    status: str
    cluster_id: uuid.UUID
    cluster_name: str
    query_count: int
    sse_url: str
    poll_url: str


class WebDiscoveryRunStartIn(BaseModel):
    query_id: uuid.UUID | None = None


class WebDiscoveryRunOut(BaseModel):
    id: uuid.UUID
    status: str
    progress_pct: int
    source_kind: str
    query: str
    display_name: str
    engines: dict[str, Any]
    engine_outputs: dict[str, Any]
    started_at: datetime | None
    completed_at: datetime | None
    error: str | None
    created_at: datetime


class WebDiscoveryQueryRunOut(BaseModel):
    """One completed (or in-flight) run that includes results for a specific query."""

    id: uuid.UUID
    display_name: str
    status: str
    result_count: int
    completed_at: datetime | None
    created_at: datetime
    run_scope: str | None = None


class WebDiscoveryResultItem(BaseModel):
    url: str
    exa_id: str | None = None
    title: str | None = None
    snippet: str | None = None
    published_date: str | None = None
    score: float | None = None
    highlights: list[str] | None = None
    summary: str | None = None
    text: str | None = None
    image: str | None = None
    favicon: str | None = None
    author: str | None = None
    article_id: uuid.UUID | None = None
    ingest_status: str | None = None
    executive_summary: str | None = None
    mentioned_companies: list[dict[str, Any]] = Field(default_factory=list)
    enriched: bool | None = None


class WebDiscoveryQueryResultsOut(BaseModel):
    query_id: uuid.UUID
    run_id: uuid.UUID
    status: str
    result_count: int
    latency_ms: float | None = None
    cost_usd: float = 0.0
    error: str | None = None
    completed_at: datetime | None = None
    query_label: str | None = None
    search_query: str | None = None
    search_type: str | None = None
    num_results: int | None = None
    content_modes: list[str] = Field(default_factory=list)
    results: list[WebDiscoveryResultItem]
    available_runs: list[WebDiscoveryQueryRunOut] = Field(default_factory=list)


def _cluster_out(c: WebDiscoveryCluster, query_count: int | None = None) -> WebDiscoveryClusterOut:
    return WebDiscoveryClusterOut(
        id=c.id,
        name=c.name,
        slug=c.slug,
        description=c.description,
        priority=c.priority,
        is_active=c.is_active,
        include_keywords=list(c.include_keywords or []),
        exclude_keywords=list(c.exclude_keywords or []),
        geography_focus=list(c.geography_focus or []),
        source_preferences=list(c.source_preferences or []),
        signal_priorities=list(c.signal_priorities or []),
        query_count=query_count if query_count is not None else c.query_count,
        signal_count=c.signal_count,
        last_run_at=c.last_run_at,
        created_at=c.created_at,
        updated_at=c.updated_at,
    )


def _stored_run_display_name(run: Run) -> str | None:
    engines = run.engines if isinstance(run.engines, dict) else {}
    raw = engines.get("display_name")
    if raw is None:
        return None
    text = str(raw).strip()
    return text or None


def _count_runs_with_query_slice(
    runs: list[Run],
    query_id: uuid.UUID,
    *,
    only_completed: bool = False,
) -> int:
    n = 0
    for candidate in runs:
        if only_completed and candidate.status != "completed":
            continue
        if _query_slice_from_run(candidate, query_id) is not None:
            n += 1
    return n


async def _cluster_web_discovery_runs(
    session: AsyncSession,
    cluster_id: uuid.UUID,
    *,
    limit: int = 100,
) -> list[Run]:
    stmt = (
        select(Run)
        .where(
            Run.source_kind == "web_discovery",
            Run.engines["cluster_id"].astext == str(cluster_id),
        )
        .order_by(Run.created_at.asc())
        .limit(max(1, min(limit, 100)))
    )
    return list((await session.execute(stmt)).scalars().all())


def _resolve_query_run_display_name(
    run: Run,
    query_label: str,
    run_number: int,
    result_count: int,
) -> str:
    stored = _stored_run_display_name(run)
    if stored:
        return stored
    engines = run.engines if isinstance(run.engines, dict) else {}
    scope = engines.get("run_scope")
    if scope == "cluster_all":
        base = f"{query_label} · Cluster batch"
    else:
        base = f"{query_label} · Run {run_number}"
    if result_count > 0:
        return f"{base} · {result_count} sources"
    return base


def _fallback_cluster_run_display_name(run: Run) -> str:
    stored = _stored_run_display_name(run)
    if stored:
        return stored
    engines = run.engines if isinstance(run.engines, dict) else {}
    cluster_name = str(engines.get("cluster_name") or "Discovery")
    scope = engines.get("run_scope")
    ts = run.completed_at or run.created_at
    when = _format_run_when(ts)
    if scope == "cluster_all":
        qc = engines.get("query_count")
        if qc:
            return f"{cluster_name} · All queries ({qc}) · {when}"
        return f"{cluster_name} · Batch · {when}"
    return f"{cluster_name} · {when}"


def _format_run_when(dt: datetime | None) -> str:
    if dt is None:
        return "—"
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).strftime("%d %b %Y, %H:%M UTC")


def _run_out(r: Run) -> WebDiscoveryRunOut:
    return WebDiscoveryRunOut(
        id=r.id,
        status=r.status,
        progress_pct=r.progress_pct,
        source_kind=r.source_kind,
        query=r.query,
        display_name=_fallback_cluster_run_display_name(r),
        engines=dict(r.engines or {}),
        engine_outputs=dict(r.engine_outputs or {}),
        started_at=r.started_at,
        completed_at=r.completed_at,
        error=r.error,
        created_at=r.created_at,
    )


def _query_out(q: WebDiscoveryQuery) -> WebDiscoveryQueryOut:
    return WebDiscoveryQueryOut(
        id=q.id,
        cluster_id=q.cluster_id,
        label=q.label,
        search_query=q.search_query,
        search_type=q.search_type,
        num_results=q.num_results,
        content_highlights=q.content_highlights,
        content_text=q.content_text,
        content_summary=q.content_summary,
        structured_outputs=q.structured_outputs,
        highlights_max_chars=q.highlights_max_chars,
        highlights_guiding_query=q.highlights_guiding_query,
        text_max_chars=q.text_max_chars,
        text_main_content_only=q.text_main_content_only,
        summary_max_chars=q.summary_max_chars,
        system_prompt=q.system_prompt,
        output_schema=q.output_schema,
        livecrawl_timeout_ms=q.livecrawl_timeout_ms,
        max_age_hours=q.max_age_hours,
        subpages=q.subpages,
        extra_links=q.extra_links,
        extra_image_links=q.extra_image_links,
        subpage_target_keywords=list(q.subpage_target_keywords or []),
        category=q.category,
        user_location=q.user_location,
        include_domains=list(q.include_domains or []),
        exclude_domains=list(q.exclude_domains or []),
        published_after=q.published_after,
        published_before=q.published_before,
        crawled_after=q.crawled_after,
        crawled_before=q.crawled_before,
        content_moderation=q.content_moderation,
        stream_response=q.stream_response,
        additional_queries=list(q.additional_queries or []),
        is_active=q.is_active,
        created_at=q.created_at,
        updated_at=q.updated_at,
    )


@router.get("/clusters", response_model=WebDiscoveryClusterList)
async def list_web_discovery_clusters(
    session: AsyncSession = Depends(get_session),
    _: None = Depends(require_admin),
) -> WebDiscoveryClusterList:
    stmt = (
        select(WebDiscoveryCluster, func.count(WebDiscoveryQuery.id))
        .outerjoin(WebDiscoveryQuery, WebDiscoveryQuery.cluster_id == WebDiscoveryCluster.id)
        .group_by(WebDiscoveryCluster.id)
        .order_by(
            WebDiscoveryCluster.is_active.desc(),
            WebDiscoveryCluster.updated_at.desc(),
            WebDiscoveryCluster.created_at.desc(),
        )
    )
    rows = (await session.execute(stmt)).all()
    return WebDiscoveryClusterList(
        clusters=[_cluster_out(cluster, query_count=count) for cluster, count in rows]
    )


@router.post("/clusters", response_model=WebDiscoveryClusterOut, status_code=201)
async def create_web_discovery_cluster(
    body: WebDiscoveryClusterIn,
    session: AsyncSession = Depends(get_session),
    _: None = Depends(require_admin),
) -> WebDiscoveryClusterOut:
    slug = slugify(body.name)
    conflict = (
        await session.execute(select(WebDiscoveryCluster.id).where(WebDiscoveryCluster.slug == slug))
    ).scalar_one_or_none()
    if conflict is not None:
        slug = f"{slug}-{str(uuid.uuid4())[:8]}"
    cluster = WebDiscoveryCluster(
        name=body.name.strip(),
        slug=slug,
        description=(body.description or "").strip() or None,
        priority=body.priority,
        is_active=body.is_active,
        include_keywords=_clean_items(body.include_keywords),
        exclude_keywords=_clean_items(body.exclude_keywords),
        geography_focus=_clean_items(body.geography_focus),
        source_preferences=_clean_items(body.source_preferences),
        signal_priorities=_clean_items(body.signal_priorities),
    )
    session.add(cluster)
    await session.commit()
    await session.refresh(cluster)
    return _cluster_out(cluster, query_count=0)


@router.get("/clusters/{cluster_id}", response_model=WebDiscoveryClusterOut)
async def get_web_discovery_cluster(
    cluster_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    _: None = Depends(require_admin),
) -> WebDiscoveryClusterOut:
    cluster = await session.get(WebDiscoveryCluster, cluster_id)
    if cluster is None:
        raise HTTPException(404, "web discovery cluster not found")
    query_count = (
        await session.execute(
            select(func.count(WebDiscoveryQuery.id)).where(WebDiscoveryQuery.cluster_id == cluster_id)
        )
    ).scalar_one()
    return _cluster_out(cluster, query_count=query_count)


@router.put("/clusters/{cluster_id}", response_model=WebDiscoveryClusterOut)
async def update_web_discovery_cluster(
    cluster_id: uuid.UUID,
    body: WebDiscoveryClusterIn,
    session: AsyncSession = Depends(get_session),
    _: None = Depends(require_admin),
) -> WebDiscoveryClusterOut:
    cluster = await session.get(WebDiscoveryCluster, cluster_id)
    if cluster is None:
        raise HTTPException(404, "web discovery cluster not found")

    new_slug = slugify(body.name)
    if new_slug != cluster.slug:
        conflict = (
            await session.execute(
                select(WebDiscoveryCluster.id).where(
                    WebDiscoveryCluster.slug == new_slug,
                    WebDiscoveryCluster.id != cluster.id,
                )
            )
        ).scalar_one_or_none()
        cluster.slug = new_slug if conflict is None else f"{new_slug}-{str(cluster.id)[:8]}"

    cluster.name = body.name.strip()
    cluster.description = (body.description or "").strip() or None
    cluster.priority = body.priority
    cluster.is_active = body.is_active
    cluster.include_keywords = _clean_items(body.include_keywords)
    cluster.exclude_keywords = _clean_items(body.exclude_keywords)
    cluster.geography_focus = _clean_items(body.geography_focus)
    cluster.source_preferences = _clean_items(body.source_preferences)
    cluster.signal_priorities = _clean_items(body.signal_priorities)
    await session.commit()
    await session.refresh(cluster)
    query_count = (
        await session.execute(
            select(func.count(WebDiscoveryQuery.id)).where(WebDiscoveryQuery.cluster_id == cluster.id)
        )
    ).scalar_one()
    return _cluster_out(cluster, query_count=query_count)


@router.delete("/clusters/{cluster_id}")
async def delete_web_discovery_cluster(
    cluster_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    _: None = Depends(require_admin),
) -> dict[str, bool]:
    cluster = await session.get(WebDiscoveryCluster, cluster_id)
    if cluster is None:
        return {"ok": True}
    await session.delete(cluster)
    await session.commit()
    return {"ok": True}


@router.post("/clusters/{cluster_id}/runs", response_model=WebDiscoveryRunCreated, status_code=202)
async def start_web_discovery_cluster_run(
    cluster_id: uuid.UUID,
    body: WebDiscoveryRunStartIn | None = None,
    x_admin_token: str | None = Header(default=None),
    session: AsyncSession = Depends(get_session),
) -> WebDiscoveryRunCreated:
    _require_admin_in_prod(x_admin_token)
    cluster = await session.get(WebDiscoveryCluster, cluster_id)
    if cluster is None:
        raise HTTPException(404, "web discovery cluster not found")
    if not cluster.is_active:
        raise HTTPException(400, "cluster is paused; enable it before running")

    active_queries = (
        await session.execute(
            select(WebDiscoveryQuery).where(
                WebDiscoveryQuery.cluster_id == cluster_id,
                WebDiscoveryQuery.is_active.is_(True),
            )
        )
    ).scalars().all()
    target_query_id = body.query_id if body else None
    if target_query_id is not None:
        active_queries = [q for q in active_queries if q.id == target_query_id]
    if not active_queries:
        raise HTTPException(400, "cluster has no active queries")

    in_flight = (
        await session.execute(
            select(Run).where(
                Run.source_kind == "web_discovery",
                Run.status.in_(["queued", "researching", "synthesizing"]),
            )
        )
    ).scalars().all()
    if len(in_flight) >= 5:
        raise HTTPException(
            429,
            f"too many web discovery runs in flight ({len(in_flight)}); wait for one to finish.",
        )

    prior_runs = await _cluster_web_discovery_runs(session, cluster.id, limit=100)
    if target_query_id is not None:
        q = active_queries[0]
        run_no = _count_runs_with_query_slice(
            prior_runs, target_query_id, only_completed=True
        ) + 1
        display_name = f"{q.label} · Run {run_no}"
    else:
        batch_no = sum(
            1
            for r in prior_runs
            if isinstance(r.engines, dict)
            and r.engines.get("run_scope") == "cluster_all"
            and r.status == "completed"
        ) + 1
        display_name = f"{cluster.name} · Batch · Run {batch_no}"

    run = Run(
        query=f"web-discovery:{cluster.slug}",
        source_kind="web_discovery",
        status="queued",
        progress_pct=0,
        engines={
            "pipeline": "web_discovery",
            "cluster_id": str(cluster.id),
            "cluster_slug": cluster.slug,
            "cluster_name": cluster.name,
            "query_count": len(active_queries),
            "query_ids": [str(q.id) for q in active_queries],
            "run_scope": "single_query" if target_query_id else "cluster_all",
            "target_query_id": str(target_query_id) if target_query_id else None,
            "display_name": display_name,
        },
    )
    session.add(run)
    await session.commit()
    await session.refresh(run)

    scope = "this query" if target_query_id else f"{len(active_queries)} queries"
    await emit(
        run.id,
        "run_queued",
        f"Run accepted — starting {scope}.",
        meta={
            "cluster_id": str(cluster.id),
            "query_count": len(active_queries),
            "target_query_id": str(target_query_id) if target_query_id else None,
        },
    )

    asyncio.create_task(
        safe_execute_web_discovery_run(run.id, cluster.id, only_query_id=target_query_id)
    )

    return WebDiscoveryRunCreated(
        run_id=run.id,
        status=run.status,
        cluster_id=cluster.id,
        cluster_name=cluster.name,
        query_count=len(active_queries),
        sse_url=f"/api/events/runs/{run.id}",
        poll_url=f"/api/web-discovery/runs/{run.id}",
    )


@router.get("/clusters/{cluster_id}/runs", response_model=list[WebDiscoveryRunOut])
async def list_web_discovery_cluster_runs(
    cluster_id: uuid.UUID,
    limit: int = 20,
    session: AsyncSession = Depends(get_session),
) -> list[WebDiscoveryRunOut]:
    cluster = await session.get(WebDiscoveryCluster, cluster_id)
    if cluster is None:
        raise HTTPException(404, "web discovery cluster not found")

    stmt = (
        select(Run)
        .where(
            Run.source_kind == "web_discovery",
            Run.engines["cluster_id"].astext == str(cluster_id),
        )
        .order_by(Run.created_at.desc())
        .limit(max(1, min(limit, 100)))
    )
    rows = (await session.execute(stmt)).scalars().all()
    return [_run_out(row) for row in rows]


@router.get("/runs/{run_id}", response_model=WebDiscoveryRunOut)
async def get_web_discovery_run(
    run_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> WebDiscoveryRunOut:
    run = await session.get(Run, run_id)
    if run is None or run.source_kind != "web_discovery":
        raise HTTPException(404, "web discovery run not found")
    return _run_out(run)


@router.get("/clusters/{cluster_id}/queries", response_model=list[WebDiscoveryQueryOut])
async def list_web_discovery_queries(
    cluster_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> list[WebDiscoveryQueryOut]:
    cluster = await session.get(WebDiscoveryCluster, cluster_id)
    if cluster is None:
        raise HTTPException(404, "web discovery cluster not found")
    rows = (
        await session.execute(
            select(WebDiscoveryQuery)
            .where(WebDiscoveryQuery.cluster_id == cluster_id)
            .order_by(WebDiscoveryQuery.created_at.desc())
        )
    ).scalars().all()
    return [_query_out(row) for row in rows]


@router.post("/clusters/{cluster_id}/queries", response_model=WebDiscoveryQueryOut, status_code=201)
async def create_web_discovery_query(
    cluster_id: uuid.UUID,
    body: WebDiscoveryQueryIn,
    x_admin_token: str | None = Header(default=None),
    session: AsyncSession = Depends(get_session),
) -> WebDiscoveryQueryOut:
    _require_admin_in_prod(x_admin_token)
    cluster = await session.get(WebDiscoveryCluster, cluster_id)
    if cluster is None:
        raise HTTPException(404, "web discovery cluster not found")
    query = WebDiscoveryQuery(
        cluster_id=cluster_id,
        label=body.label.strip(),
        search_query=body.search_query.strip(),
        search_type=body.search_type,
        num_results=body.num_results,
        content_highlights=body.content_highlights,
        content_text=body.content_text,
        content_summary=body.content_summary,
        structured_outputs=body.structured_outputs,
        highlights_max_chars=body.highlights_max_chars,
        highlights_guiding_query=(body.highlights_guiding_query or "").strip() or None,
        text_max_chars=body.text_max_chars,
        text_main_content_only=body.text_main_content_only,
        summary_max_chars=body.summary_max_chars,
        system_prompt=(body.system_prompt or "").strip() or None,
        output_schema=body.output_schema,
        livecrawl_timeout_ms=body.livecrawl_timeout_ms,
        max_age_hours=body.max_age_hours,
        subpages=body.subpages,
        extra_links=body.extra_links,
        extra_image_links=body.extra_image_links,
        subpage_target_keywords=_clean_items(body.subpage_target_keywords),
        category=(body.category or "").strip() or None,
        user_location=(body.user_location or "").strip() or None,
        include_domains=_clean_items(body.include_domains),
        exclude_domains=_clean_items(body.exclude_domains),
        published_after=body.published_after,
        published_before=body.published_before,
        crawled_after=body.crawled_after,
        crawled_before=body.crawled_before,
        content_moderation=body.content_moderation,
        stream_response=body.stream_response,
        additional_queries=_clean_items(body.additional_queries),
        is_active=body.is_active,
    )
    session.add(query)
    await session.commit()
    await session.refresh(query)
    return _query_out(query)


def _normalize_result_items(raw: Any) -> list[dict[str, Any]]:
    if not isinstance(raw, list):
        return []
    out: list[dict[str, Any]] = []
    for item in raw:
        if not isinstance(item, dict) or not item.get("url"):
            continue
        highlights = coerce_exa_highlights(item.get("highlights"))
        companies = item.get("mentioned_companies")
        out.append(
            {
                "url": str(item["url"]),
                "exa_id": item.get("exa_id"),
                "title": item.get("title"),
                "snippet": item.get("snippet"),
                "published_date": item.get("published_date"),
                "score": item.get("score"),
                "highlights": highlights,
                "summary": item.get("summary"),
                "text": item.get("text"),
                "image": item.get("image"),
                "favicon": item.get("favicon"),
                "author": item.get("author"),
                "article_id": item.get("article_id"),
                "ingest_status": item.get("ingest_status"),
                "executive_summary": item.get("executive_summary"),
                "mentioned_companies": companies if isinstance(companies, list) else [],
                "enriched": item.get("enriched"),
            }
        )
    return out


async def _hydrate_results_from_articles(
    session: AsyncSession,
    results: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Merge canonical article enrich + body from `articles` (source of truth)."""
    if not results:
        return results

    urls = [normalize_article_url(str(r["url"])) for r in results if r.get("url")]
    article_ids: list[uuid.UUID] = []
    for row in results:
        raw_id = row.get("article_id")
        if not raw_id:
            continue
        try:
            article_ids.append(raw_id if isinstance(raw_id, uuid.UUID) else uuid.UUID(str(raw_id)))
        except (TypeError, ValueError):
            continue

    filters = []
    if urls:
        filters.append(Article.url.in_(urls))
    if article_ids:
        filters.append(Article.id.in_(article_ids))
    if not filters:
        return results

    rows = (await session.execute(select(Article).where(or_(*filters)))).scalars().all()
    by_url = {a.url: a for a in rows}
    by_id = {a.id: a for a in rows}

    for row in results:
        art: Article | None = None
        raw_id = row.get("article_id")
        if raw_id:
            try:
                aid = raw_id if isinstance(raw_id, uuid.UUID) else uuid.UUID(str(raw_id))
                art = by_id.get(aid)
            except (TypeError, ValueError):
                art = None
        if art is None and row.get("url"):
            art = by_url.get(normalize_article_url(str(row["url"])))
        if art is None:
            continue

        row["article_id"] = art.id
        if art.summary:
            row["executive_summary"] = art.summary
            row["enriched"] = True
        if art.mentioned_companies:
            row["mentioned_companies"] = list(art.mentioned_companies)
        if art.body_text:
            row["text"] = clean_reading_text(art.body_text)
        if not row.get("ingest_status"):
            row["ingest_status"] = "created"

    return results


def _query_slice_from_run(run: Run, query_id: uuid.UUID) -> dict[str, Any] | None:
    payload = run.engine_outputs if isinstance(run.engine_outputs, dict) else {}
    queries = payload.get("queries")
    if not isinstance(queries, list):
        return None
    qid = str(query_id)
    for item in queries:
        if isinstance(item, dict) and str(item.get("query_id")) == qid:
            return item
    return None


async def _query_run_list_for_row(
    session: AsyncSession,
    row: WebDiscoveryQuery,
    *,
    limit: int = 30,
) -> list[WebDiscoveryQueryRunOut]:
    """Runs that include this query — newest first, with human-readable names."""
    cluster_runs = await _cluster_web_discovery_runs(session, row.cluster_id, limit=100)
    matched: list[tuple[Run, dict[str, Any], int]] = []
    run_number = 0
    for run in cluster_runs:
        slice_ = _query_slice_from_run(run, row.id)
        if slice_ is None:
            continue
        run_number += 1
        matched.append((run, slice_, run_number))

    out: list[WebDiscoveryQueryRunOut] = []
    for run, slice_, number in reversed(matched):
        rc = int(
            slice_.get("result_count") or len(_normalize_result_items(slice_.get("results")))
        )
        engines = run.engines if isinstance(run.engines, dict) else {}
        out.append(
            WebDiscoveryQueryRunOut(
                id=run.id,
                display_name=_resolve_query_run_display_name(
                    run, row.label, number, rc
                ),
                status=run.status,
                result_count=rc,
                completed_at=run.completed_at,
                created_at=run.created_at,
                run_scope=str(engines.get("run_scope")) if engines.get("run_scope") else None,
            )
        )
        if len(out) >= max(1, min(limit, 50)):
            break
    return out


@router.get("/queries/{query_id}", response_model=WebDiscoveryQueryOut)
async def get_web_discovery_query(
    query_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> WebDiscoveryQueryOut:
    row = await session.get(WebDiscoveryQuery, query_id)
    if row is None:
        raise HTTPException(404, "web discovery query not found")
    return _query_out(row)


@router.get("/queries/{query_id}/runs", response_model=list[WebDiscoveryQueryRunOut])
async def list_web_discovery_query_runs(
    query_id: uuid.UUID,
    limit: int = 30,
    session: AsyncSession = Depends(get_session),
) -> list[WebDiscoveryQueryRunOut]:
    """Runs that produced (or are producing) results for this query — newest first."""
    row = await session.get(WebDiscoveryQuery, query_id)
    if row is None:
        raise HTTPException(404, "web discovery query not found")
    return await _query_run_list_for_row(session, row, limit=limit)


@router.get("/queries/{query_id}/results", response_model=WebDiscoveryQueryResultsOut)
async def get_web_discovery_query_results(
    query_id: uuid.UUID,
    run_id: uuid.UUID | None = None,
    session: AsyncSession = Depends(get_session),
) -> WebDiscoveryQueryResultsOut:
    """Latest (or specified) run payload for one query — full Exa result cards."""
    row = await session.get(WebDiscoveryQuery, query_id)
    if row is None:
        raise HTTPException(404, "web discovery query not found")

    run: Run | None = None
    if run_id is not None:
        run = await session.get(Run, run_id)
        if run is None or run.source_kind != "web_discovery":
            raise HTTPException(404, "web discovery run not found")
    else:
        stmt = (
            select(Run)
            .where(
                Run.source_kind == "web_discovery",
                Run.engines["cluster_id"].astext == str(row.cluster_id),
                Run.status == "completed",
            )
            .order_by(Run.completed_at.desc().nullslast(), Run.created_at.desc())
            .limit(20)
        )
        candidates = (await session.execute(stmt)).scalars().all()
        best: tuple[Run, dict[str, Any]] | None = None
        for candidate in candidates:
            slice_ = _query_slice_from_run(candidate, query_id)
            if slice_ is None:
                continue
            if best is None:
                best = (candidate, slice_)
                continue
            cur_n = len(_normalize_result_items(slice_.get("results")))
            best_n = len(_normalize_result_items(best[1].get("results")))
            if cur_n > best_n:
                best = (candidate, slice_)
        if best is not None:
            run = best[0]

    if run is None:
        raise HTTPException(404, "no completed run results for this query yet")

    slice_ = _query_slice_from_run(run, query_id)
    if slice_ is None:
        raise HTTPException(404, "query not part of this run")

    results = _normalize_result_items(slice_.get("results"))
    if not results:
        call = (
            await session.execute(
                select(EngineCall)
                .where(
                    EngineCall.run_id == run.id,
                    EngineCall.vendor == "exa",
                    EngineCall.meta["query_id"].astext == str(query_id),
                    EngineCall.status == "ok",
                )
                .order_by(EngineCall.created_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        if call and isinstance(call.response_payload, dict):
            results = _normalize_result_items(call.response_payload.get("results"))

    results = await _hydrate_results_from_articles(session, results)

    content_modes: list[str] = []
    if row.content_highlights:
        content_modes.append("highlights")
    if row.content_text:
        content_modes.append("text")
    if row.content_summary:
        content_modes.append("summary")

    available_runs = await _query_run_list_for_row(session, row, limit=30)

    return WebDiscoveryQueryResultsOut(
        query_id=query_id,
        run_id=run.id,
        status=str(slice_.get("status") or run.status),
        result_count=int(slice_.get("result_count") or len(results)),
        latency_ms=float(slice_["latency_ms"]) if slice_.get("latency_ms") is not None else None,
        cost_usd=float(slice_.get("cost_usd") or 0.0),
        error=str(slice_["error"]) if slice_.get("error") else None,
        completed_at=run.completed_at,
        query_label=row.label,
        search_query=row.search_query,
        search_type=row.search_type,
        num_results=row.num_results,
        content_modes=content_modes,
        results=[WebDiscoveryResultItem(**item) for item in results],
        available_runs=available_runs,
    )


@router.put("/queries/{query_id}", response_model=WebDiscoveryQueryOut)
async def update_web_discovery_query(
    query_id: uuid.UUID,
    body: WebDiscoveryQueryIn,
    x_admin_token: str | None = Header(default=None),
    session: AsyncSession = Depends(get_session),
) -> WebDiscoveryQueryOut:
    _require_admin_in_prod(x_admin_token)
    row = await session.get(WebDiscoveryQuery, query_id)
    if row is None:
        raise HTTPException(404, "web discovery query not found")
    row.label = body.label.strip()
    row.search_query = body.search_query.strip()
    row.search_type = body.search_type
    row.num_results = body.num_results
    row.content_highlights = body.content_highlights
    row.content_text = body.content_text
    row.content_summary = body.content_summary
    row.structured_outputs = body.structured_outputs
    row.highlights_max_chars = body.highlights_max_chars
    row.highlights_guiding_query = (body.highlights_guiding_query or "").strip() or None
    row.text_max_chars = body.text_max_chars
    row.text_main_content_only = body.text_main_content_only
    row.summary_max_chars = body.summary_max_chars
    row.system_prompt = (body.system_prompt or "").strip() or None
    row.output_schema = body.output_schema
    row.livecrawl_timeout_ms = body.livecrawl_timeout_ms
    row.max_age_hours = body.max_age_hours
    row.subpages = body.subpages
    row.extra_links = body.extra_links
    row.extra_image_links = body.extra_image_links
    row.subpage_target_keywords = _clean_items(body.subpage_target_keywords)
    row.category = (body.category or "").strip() or None
    row.user_location = (body.user_location or "").strip() or None
    row.include_domains = _clean_items(body.include_domains)
    row.exclude_domains = _clean_items(body.exclude_domains)
    row.published_after = body.published_after
    row.published_before = body.published_before
    row.crawled_after = body.crawled_after
    row.crawled_before = body.crawled_before
    row.content_moderation = body.content_moderation
    row.stream_response = body.stream_response
    row.additional_queries = _clean_items(body.additional_queries)
    row.is_active = body.is_active
    await session.commit()
    await session.refresh(row)
    return _query_out(row)


@router.delete("/queries/{query_id}")
async def delete_web_discovery_query(
    query_id: uuid.UUID,
    x_admin_token: str | None = Header(default=None),
    session: AsyncSession = Depends(get_session),
) -> dict[str, bool]:
    _require_admin_in_prod(x_admin_token)
    row = await session.get(WebDiscoveryQuery, query_id)
    if row is None:
        return {"ok": True}
    await session.delete(row)
    await session.commit()
    return {"ok": True}


class ArticleOut(BaseModel):
    id: uuid.UUID
    url: str
    title: str
    summary: str | None
    body_text: str | None
    source_name: str | None
    published_at: datetime | None
    ingested_at: datetime
    cluster_id: uuid.UUID | None
    query_run_id: uuid.UUID | None
    source_query_id: uuid.UUID | None
    category_tag: str | None
    priority_score: int | None
    mentioned_companies: list[dict[str, Any]]
    source_metadata: dict[str, Any]
    status: str
    created_at: datetime
    updated_at: datetime


def _article_out(row: Article) -> ArticleOut:
    return ArticleOut(
        id=row.id,
        url=row.url,
        title=row.title,
        summary=row.summary,
        body_text=row.body_text,
        source_name=row.source_name,
        published_at=row.published_at,
        ingested_at=row.ingested_at,
        cluster_id=row.cluster_id,
        query_run_id=row.query_run_id,
        source_query_id=row.source_query_id,
        category_tag=row.category_tag,
        priority_score=row.priority_score,
        mentioned_companies=list(row.mentioned_companies or []),
        source_metadata=dict(row.source_metadata or {}),
        status=row.status,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


@router.get("/articles", response_model=list[ArticleOut])
async def list_articles(
    cluster_id: uuid.UUID | None = Query(None),
    query_run_id: uuid.UUID | None = Query(None),
    source_query_id: uuid.UUID | None = Query(None),
    status: str = Query("active"),
    limit: int = Query(50, ge=1, le=200),
    session: AsyncSession = Depends(get_session),
) -> list[ArticleOut]:
    stmt = select(Article).order_by(Article.ingested_at.desc()).limit(limit)
    if status != "all":
        stmt = stmt.where(Article.status == status)
    if cluster_id is not None:
        stmt = stmt.where(Article.cluster_id == cluster_id)
    if query_run_id is not None:
        stmt = stmt.where(Article.query_run_id == query_run_id)
    if source_query_id is not None:
        stmt = stmt.where(Article.source_query_id == source_query_id)
    rows = (await session.execute(stmt)).scalars().all()
    return [_article_out(r) for r in rows]


@router.get("/articles/{article_id}", response_model=ArticleOut)
async def get_article(
    article_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> ArticleOut:
    row = await session.get(Article, article_id)
    if row is None:
        raise HTTPException(404, "article not found")
    return _article_out(row)


@router.post("/articles/{article_id}/dismiss", response_model=ArticleOut)
async def dismiss_article(
    article_id: uuid.UUID,
    x_admin_token: str | None = Header(default=None),
    session: AsyncSession = Depends(get_session),
) -> ArticleOut:
    _require_admin_in_prod(x_admin_token)
    row = await session.get(Article, article_id)
    if row is None:
        raise HTTPException(404, "article not found")
    row.status = "dismissed"
    await session.commit()
    await session.refresh(row)
    return _article_out(row)
