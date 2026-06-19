"""Web Discovery pipeline — Exa search, article consolidate, Sonnet enrich.

Per active Query in a Run:
  1. Exa search (+ contents per query flags)
  2. Dedup against `articles.url`
  3. Consolidate new hits → `articles` (full original body + metadata)
  4. Sonnet per article → executive summary + mentioned_companies

Never raises — failures fold into run status + run_events.
"""
from __future__ import annotations

import asyncio
import logging
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from typing import Any
from urllib.parse import urlparse

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.db import get_session_factory
from app.engines import get_claude_client, get_exa_client
from app.engines.claude_client import ClaudeMessage
from app.engines.exa_client import serialize_exa_search_result
from app.engines.logging import log_claude_call, log_exa_call
from app.models.article import Article
from app.models.run import Run
from app.models.web_discovery_cluster import WebDiscoveryCluster
from app.models.web_discovery_query import WebDiscoveryQuery
from app.services.discovery_companies import persist_discovery_companies, sync_article_discovery_companies
from app.services.run_events import emit, set_pipeline

logger = logging.getLogger(__name__)

ENRICH_MODEL = "sonnet"
ENRICH_MAX_TOKENS = 4096
ENRICH_TIMEOUT_S = 120.0
ENRICH_BODY_CAP = 14_000
ENRICH_CONCURRENCY = 4

_ARTICLE_ENRICH_TOOL: dict[str, Any] = {
    "name": "analyze_article",
    "description": (
        "Produce an executive summary and list companies mentioned in the article. "
        "Only include facts stated in the article text."
    ),
    "input_schema": {
        "type": "object",
        "additionalProperties": False,
        "required": ["executive_summary", "companies"],
        "properties": {
            "executive_summary": {
                "type": "string",
                "description": (
                    "2-4 sentences: what happened and why it matters for the search query."
                ),
            },
            "companies": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["name", "context"],
                    "properties": {
                        "name": {"type": "string"},
                        "context": {
                            "type": "string",
                            "description": "What this article says about the company.",
                        },
                        "hint_url": {"type": ["string", "null"]},
                        "industry": {"type": ["string", "null"]},
                        "hq_or_market": {"type": ["string", "null"]},
                        "role_in_story": {
                            "type": ["string", "null"],
                            "description": "subject | competitor | investor | partner | mentioned",
                        },
                    },
                },
            },
        },
    },
}

_ENRICH_SYSTEM = """You are a business-development intelligence analyst.

Given a search query and a news/article, write:
1. executive_summary — 2-4 sentences tied to WHY this matters for the query (not generic recap).
2. companies — every company explicitly mentioned. Use only facts from the article.
   - name: company name as written
   - context: 1-2 sentences from the article about them
   - hint_url: company website/URL if stated, else null
   - industry / hq_or_market: only if stated in text
   - role_in_story: subject | competitor | investor | partner | mentioned

If no companies are mentioned, return an empty companies array.
Call the analyze_article tool exactly once."""


@dataclass(slots=True)
class WebDiscoveryRunResult:
    run_id: uuid.UUID
    status: str
    query_count: int = 0
    total_results: int = 0
    new_articles: int = 0
    duplicates_skipped: int = 0
    enriched: int = 0
    cost_usd: float = 0.0
    error: str | None = None
    engine_outputs: dict[str, Any] = field(default_factory=dict)


def exa_search_type(raw: str) -> tuple[str, str | None]:
    value = (raw or "auto").strip().lower()
    if value in {"instant", "fast"}:
        return "fast", None
    if value in {"deep", "deep-lite", "deep-reasoning"}:
        return "deep", value
    return "auto", None


def exa_contents_for_query(q: WebDiscoveryQuery) -> dict[str, Any] | None:
    contents: dict[str, Any] = {}
    if q.content_highlights:
        highlights: Any = True
        if q.highlights_guiding_query or q.highlights_max_chars is not None:
            highlights = {}
            if q.highlights_guiding_query:
                highlights["query"] = q.highlights_guiding_query
            if q.highlights_max_chars is not None:
                highlights["maxCharacters"] = q.highlights_max_chars
        contents["highlights"] = highlights
    if q.content_text:
        text: Any = True
        if q.text_max_chars is not None:
            text = {"maxCharacters": q.text_max_chars}
        contents["text"] = text
    if q.content_summary:
        summary: Any = True
        if q.summary_max_chars is not None:
            summary = {"maxCharacters": q.summary_max_chars}
        contents["summary"] = summary
    return contents or None


def normalize_article_url(url: str) -> str:
    raw = (url or "").strip()
    if not raw:
        return ""
    parsed = urlparse(raw)
    if not parsed.scheme:
        raw = f"https://{raw}"
        parsed = urlparse(raw)
    path = parsed.path.rstrip("/") or ""
    return f"{parsed.scheme.lower()}://{parsed.netloc.lower()}{path}"


def source_name_from_url(url: str) -> str | None:
    try:
        host = urlparse(url).netloc.lower()
        if host.startswith("www."):
            host = host[4:]
        return host or None
    except Exception:
        return None


def parse_published_at(value: str | None) -> datetime | None:
    if not value:
        return None
    text = str(value).strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = f"{text[:-1]}+00:00"
    try:
        dt = datetime.fromisoformat(text)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except ValueError:
        pass
    try:
        d = date.fromisoformat(text[:10])
        return datetime(d.year, d.month, d.day, tzinfo=timezone.utc)
    except ValueError:
        return None


def clean_reading_text(text: str) -> str:
    """Strip Exa highlight crumbs and markdown noise for human-readable display."""
    import re

    raw = (text or "").strip()
    if not raw:
        return ""

    lines: list[str] = []
    for line in raw.splitlines():
        stripped = line.strip()
        if not stripped:
            lines.append("")
            continue
        if re.fullmatch(r"#{1,6}\s*[\w\s\-–—|&'\".,!?★☆•·]+", stripped):
            continue
        if re.fullmatch(r"[\|\-\s:]+", stripped):
            continue
        stripped = re.sub(r"\s*\.\.\.\s*", " ", stripped)
        stripped = re.sub(r"\s{2,}", " ", stripped).strip()
        if len(stripped) < 3:
            continue
        lines.append(stripped)

    merged: list[str] = []
    buf: list[str] = []
    for line in lines:
        if not line:
            if buf:
                merged.append(" ".join(buf))
                buf = []
            continue
        buf.append(line)
    if buf:
        merged.append(" ".join(buf))

    paragraphs: list[str] = []
    for block in merged:
        parts = re.split(r"(?<=[.!?])\s+(?=[A-Z0-9\"“])", block)
        if len(parts) > 1 and all(len(p) < 220 for p in parts):
            paragraphs.extend(p.strip() for p in parts if p.strip())
        else:
            paragraphs.append(block)

    return "\n\n".join(paragraphs)


def consolidate_body_text(hit: dict[str, Any]) -> str:
    text = (hit.get("text") or "").strip()
    if text:
        return clean_reading_text(text)
    highlights = hit.get("highlights")
    if isinstance(highlights, list) and highlights:
        joined = "\n\n".join(str(h).strip() for h in highlights if str(h).strip())
        if joined:
            return clean_reading_text(joined)
    snippet = (hit.get("snippet") or "").strip()
    if snippet:
        return clean_reading_text(snippet)
    exa_summary = (hit.get("summary") or "").strip()
    return clean_reading_text(exa_summary)


def exa_priority_score(score: float | None) -> int | None:
    if score is None:
        return None
    try:
        val = float(score)
    except (TypeError, ValueError):
        return None
    if 0 <= val <= 1:
        return max(0, min(100, int(round(val * 100))))
    return max(0, min(100, int(round(val))))


def build_source_metadata(hit: dict[str, Any]) -> dict[str, Any]:
    return {
        "exa_id": hit.get("exa_id"),
        "snippet": hit.get("snippet"),
        "highlights": hit.get("highlights"),
        "exa_summary": hit.get("summary"),
        "score": hit.get("score"),
        "image": hit.get("image"),
        "favicon": hit.get("favicon"),
        "author": hit.get("author"),
        "published_date": hit.get("published_date"),
    }


async def execute_web_discovery_run(
    run_id: uuid.UUID,
    cluster_id: uuid.UUID,
    *,
    only_query_id: uuid.UUID | None = None,
    session_factory: async_sessionmaker[AsyncSession] | None = None,
) -> WebDiscoveryRunResult:
    set_pipeline("web_discovery")
    factory = session_factory or get_session_factory()
    exa = get_exa_client()
    result = WebDiscoveryRunResult(run_id=run_id, status="running")

    async with factory() as s:
        run = await s.get(Run, run_id)
        if run is None:
            raise RuntimeError(f"run {run_id} not found")
        cluster = await s.get(WebDiscoveryCluster, cluster_id)
        if cluster is None:
            raise RuntimeError(f"cluster {cluster_id} not found")
        queries = (
            await s.execute(
                select(WebDiscoveryQuery)
                .where(
                    WebDiscoveryQuery.cluster_id == cluster_id,
                    WebDiscoveryQuery.is_active.is_(True),
                )
                .order_by(WebDiscoveryQuery.created_at.asc())
            )
        ).scalars().all()
        if only_query_id is not None:
            queries = [q for q in queries if q.id == only_query_id]
        run.status = "researching"
        run.started_at = datetime.now(timezone.utc)
        run.progress_pct = 5
        await s.commit()

    cluster_name = cluster.name
    cluster_slug = cluster.slug
    await emit(
        run_id,
        "run_started",
        f"Web discovery run started for cluster '{cluster_name}' with {len(queries)} active queries.",
        meta={
            "cluster_id": str(cluster_id),
            "query_count": len(queries),
            "only_query_id": str(only_query_id) if only_query_id else None,
        },
    )

    if not queries:
        await _finalize_run(
            factory,
            run_id,
            cluster_id,
            status="failed",
            progress=100,
            error="No active queries in cluster.",
            engine_outputs={},
        )
        await emit(run_id, "run_failed", "No active queries in cluster.", level="error")
        result.status = "failed"
        result.error = "No active queries in cluster."
        return result

    total_cost = 0.0
    total_results = 0
    new_articles = 0
    duplicates_skipped = 0
    enriched_count = 0
    query_summaries: list[dict[str, Any]] = []
    enrich_sem = asyncio.Semaphore(ENRICH_CONCURRENCY)

    try:
        for index, query in enumerate(queries, start=1):
            await emit(
                run_id,
                "query_started",
                f"Running query {index}/{len(queries)}: {query.label}",
                meta={"query_id": str(query.id), "label": query.label},
            )

            mapped_type, deep_model = exa_search_type(query.search_type)
            exa_contents = exa_contents_for_query(query)
            hits, stats = await exa.search(
                query.search_query,
                include_domains=list(query.include_domains or []) or None,
                exclude_domains=list(query.exclude_domains or []) or None,
                start_published_date=query.published_after,
                end_published_date=query.published_before,
                num_results=query.num_results,
                category=query.category,
                search_type=mapped_type,
                deep_model=deep_model,
                contents=exa_contents,
            )
            serialized = [serialize_exa_search_result(r) for r in hits]

            async with factory() as s:
                await log_exa_call(
                    s,
                    stats,
                    run_id=run_id,
                    meta={
                        "pipeline": "web_discovery",
                        "query_id": str(query.id),
                        "query_label": query.label,
                        "search_type": query.search_type,
                    },
                    request_payload={
                        "query": query.search_query,
                        "search_type": query.search_type,
                        "num_results": query.num_results,
                        "contents": exa_contents,
                    },
                    response_payload={
                        "result_count": len(serialized),
                        "results": serialized,
                    },
                )

            total_cost += float(stats.cost_usd or 0.0)
            total_results += len(serialized)

            existing_urls = await _load_existing_urls(factory, serialized)
            seen_new: set[str] = set()
            new_hits: list[dict[str, Any]] = []
            for h in serialized:
                norm = normalize_article_url(str(h.get("url") or ""))
                if not norm or norm in existing_urls or norm in seen_new:
                    continue
                seen_new.add(norm)
                new_hits.append(h)
            duplicates_skipped += len(serialized) - len(new_hits)

            await emit(
                run_id,
                "stage_completed",
                f"Dedup: {len(new_hits)} new · {len(serialized) - len(new_hits)} already ingested",
                meta={
                    "stage": "dedup",
                    "query_id": str(query.id),
                    "new": len(new_hits),
                    "dupes": len(serialized) - len(new_hits),
                },
            )

            ingest_tasks = [
                _ingest_and_enrich_hit(
                    factory,
                    enrich_sem,
                    run_id=run_id,
                    cluster_id=cluster_id,
                    cluster_slug=cluster_slug,
                    query=query,
                    hit=hit,
                )
                for hit in new_hits
            ]
            ingest_outcomes = await asyncio.gather(*ingest_tasks) if ingest_tasks else []

            processed: list[dict[str, Any]] = []
            url_to_outcome = {
                normalize_article_url(str(o.get("url") or "")): o for o in ingest_outcomes
            }
            for hit in serialized:
                norm = normalize_article_url(str(hit.get("url") or ""))
                outcome = url_to_outcome.get(norm)
                if outcome:
                    merged = {**hit, **outcome}
                    if outcome.get("ingest_status") == "created":
                        new_articles += 1
                    if outcome.get("enriched"):
                        enriched_count += 1
                    total_cost += float(outcome.get("enrich_cost_usd") or 0.0)
                else:
                    merged = {
                        **hit,
                        "ingest_status": "duplicate",
                        "article_id": None,
                        "enriched": False,
                    }
                processed.append(merged)

            query_summaries.append(
                {
                    "query_id": str(query.id),
                    "label": query.label,
                    "status": stats.status,
                    "result_count": len(serialized),
                    "new_articles": sum(1 for p in processed if p.get("ingest_status") == "created"),
                    "duplicates_skipped": sum(1 for p in processed if p.get("ingest_status") == "duplicate"),
                    "latency_ms": stats.latency_ms,
                    "cost_usd": stats.cost_usd,
                    "error": stats.error,
                    "results": processed,
                }
            )

            await emit(
                run_id,
                "query_completed",
                f"{query.label}: {len(serialized)} results ({stats.status})",
                level="warn" if stats.status != "ok" else "info",
                meta=query_summaries[-1],
            )

            progress = min(95, 5 + int((index / len(queries)) * 85))
            engine_outputs = _build_engine_outputs(
                cluster_id,
                queries,
                index,
                total_results,
                total_cost,
                new_articles,
                duplicates_skipped,
                enriched_count,
                query_summaries,
            )
            await _patch_run_progress(factory, run_id, progress, engine_outputs)

        engine_outputs = _build_engine_outputs(
            cluster_id,
            queries,
            len(queries),
            total_results,
            total_cost,
            new_articles,
            duplicates_skipped,
            enriched_count,
            query_summaries,
        )
        await _finalize_run(
            factory,
            run_id,
            cluster_id,
            status="completed",
            progress=100,
            error=None,
            engine_outputs=engine_outputs,
        )
        result.status = "completed"

    except Exception as exc:
        logger.exception("Web discovery run failed run_id=%s: %s", run_id, exc)
        result.status = "failed"
        result.error = f"{type(exc).__name__}: {exc}"
        await emit(run_id, "run_failed", str(exc), level="error")
        await _finalize_run(
            factory,
            run_id,
            cluster_id,
            status="failed",
            progress=100,
            error=str(exc),
            engine_outputs=_build_engine_outputs(
                cluster_id,
                queries,
                len(query_summaries),
                total_results,
                total_cost,
                new_articles,
                duplicates_skipped,
                enriched_count,
                query_summaries,
            ),
        )

    result.query_count = len(queries)
    result.total_results = total_results
    result.new_articles = new_articles
    result.duplicates_skipped = duplicates_skipped
    result.enriched = enriched_count
    result.cost_usd = round(total_cost, 4)
    result.engine_outputs = _build_engine_outputs(
        cluster_id,
        queries,
        len(query_summaries),
        total_results,
        total_cost,
        new_articles,
        duplicates_skipped,
        enriched_count,
        query_summaries,
    )

    await emit(
        run_id,
        "run_completed" if result.status == "completed" else "run_failed",
        (
            f"Web discovery {result.status}: {result.new_articles} new articles, "
            f"{result.enriched} enriched, ${result.cost_usd:.3f}."
        ),
        meta={
            "cluster_id": str(cluster_id),
            "query_count": result.query_count,
            "total_results": result.total_results,
            "new_articles": result.new_articles,
            "duplicates_skipped": result.duplicates_skipped,
            "enriched": result.enriched,
            "total_cost_usd": result.cost_usd,
        },
        level="error" if result.status == "failed" else "info",
    )
    return result


async def safe_execute_web_discovery_run(
    run_id: uuid.UUID,
    cluster_id: uuid.UUID,
    only_query_id: uuid.UUID | None = None,
) -> None:
    try:
        await execute_web_discovery_run(run_id, cluster_id, only_query_id=only_query_id)
    except Exception as exc:  # pragma: no cover
        logger.exception("web-discovery run crashed (run_id=%s): %s", run_id, exc)
        factory = get_session_factory()
        async with factory() as s:
            run = await s.get(Run, run_id)
            if run is not None:
                run.status = "failed"
                run.progress_pct = 100
                run.error = f"{type(exc).__name__}: {exc}"
                run.completed_at = datetime.now(timezone.utc)
                await s.commit()
        await emit(run_id, "run_failed", str(exc), level="error")


async def _load_existing_urls(
    factory: async_sessionmaker[AsyncSession],
    hits: list[dict[str, Any]],
) -> set[str]:
    norms = {normalize_article_url(str(h.get("url") or "")) for h in hits}
    norms.discard("")
    if not norms:
        return set()
    async with factory() as s:
        rows = (
            await s.execute(select(Article.url).where(Article.url.in_(norms)))
        ).scalars().all()
    return set(rows)


async def _ingest_and_enrich_hit(
    factory: async_sessionmaker[AsyncSession],
    sem: asyncio.Semaphore,
    *,
    run_id: uuid.UUID,
    cluster_id: uuid.UUID,
    cluster_slug: str,
    query: WebDiscoveryQuery,
    hit: dict[str, Any],
) -> dict[str, Any]:
    url = normalize_article_url(str(hit.get("url") or ""))
    if not url:
        return {"url": "", "ingest_status": "failed", "enriched": False, "enrich_cost_usd": 0.0}

    title = (hit.get("title") or "").strip() or "Untitled"
    body_text = consolidate_body_text(hit)
    now = datetime.now(timezone.utc)

    article = Article(
        url=url,
        title=title[:500],
        body_text=body_text or None,
        source_name=source_name_from_url(url),
        published_at=parse_published_at(hit.get("published_date")),
        ingested_at=now,
        cluster_id=cluster_id,
        query_run_id=run_id,
        source_query_id=query.id,
        category_tag=cluster_slug[:80] if cluster_slug else None,
        priority_score=exa_priority_score(hit.get("score")),
        mentioned_companies=[],
        source_metadata=build_source_metadata(hit),
        status="active",
    )

    async with factory() as s:
        try:
            s.add(article)
            await s.commit()
            await s.refresh(article)
        except IntegrityError:
            await s.rollback()
            existing = (
                await s.execute(select(Article).where(Article.url == url))
            ).scalars().first()
            if existing is None:
                return {
                    "url": url,
                    "article_id": None,
                    "ingest_status": "duplicate",
                    "enriched": False,
                    "executive_summary": None,
                    "mentioned_companies": [],
                    "enrich_cost_usd": 0.0,
                }
            if existing.summary and existing.mentioned_companies:
                await sync_article_discovery_companies(s, existing)
                await s.commit()
                return {
                    "url": url,
                    "article_id": str(existing.id),
                    "ingest_status": "duplicate",
                    "enriched": True,
                    "executive_summary": existing.summary,
                    "mentioned_companies": list(existing.mentioned_companies or []),
                    "enrich_cost_usd": 0.0,
                }
            return {
                "url": url,
                "article_id": str(existing.id),
                "ingest_status": "duplicate",
                "enriched": False,
                "executive_summary": existing.summary,
                "mentioned_companies": list(existing.mentioned_companies or []),
                "enrich_cost_usd": 0.0,
            }

    await emit(
        run_id,
        "article_consolidated",
        title,
        meta={
            "article_id": str(article.id),
            "url": url,
            "query_id": str(query.id),
            "body_chars": len(body_text or ""),
        },
    )

    enrich_cost = 0.0
    enriched = False
    async with sem:
        summary, companies, enrich_cost, ok = await _enrich_article(
            factory,
            run_id=run_id,
            article_id=article.id,
            search_query=query.search_query,
            title=title,
            url=url,
            body_text=body_text,
        )
        enriched = ok

    if enriched:
        async with factory() as s:
            row = await s.get(Article, article.id)
            if row is not None:
                row.summary = summary
                companies = await persist_discovery_companies(
                    s,
                    article_id=row.id,
                    mentions=companies,
                )
                row.mentioned_companies = companies
                await s.commit()
        await emit(
            run_id,
            "article_enriched",
            title,
            meta={
                "article_id": str(article.id),
                "company_count": len(companies),
                "query_id": str(query.id),
            },
        )

    return {
        "url": url,
        "article_id": str(article.id),
        "ingest_status": "created",
        "enriched": enriched,
        "executive_summary": summary if enriched else None,
        "mentioned_companies": companies if enriched else [],
        "enrich_cost_usd": enrich_cost,
    }


async def _enrich_article(
    factory: async_sessionmaker[AsyncSession],
    *,
    run_id: uuid.UUID,
    article_id: uuid.UUID,
    search_query: str,
    title: str,
    url: str,
    body_text: str,
) -> tuple[str | None, list[dict[str, Any]], float, bool]:
    body = (body_text or "").strip()
    if len(body) > ENRICH_BODY_CAP:
        body = body[:ENRICH_BODY_CAP] + "\n\n[truncated]"

    user_msg = (
        f"SEARCH QUERY:\n{search_query}\n\n"
        f"ARTICLE URL:\n{url}\n\n"
        f"TITLE:\n{title}\n\n"
        f"BODY:\n{body or '(no body text — use title/snippet only)'}"
    )

    client = get_claude_client()
    resp = await client.complete(
        model=ENRICH_MODEL,
        system=_ENRICH_SYSTEM,
        messages=[ClaudeMessage(role="user", content=user_msg)],
        max_tokens=ENRICH_MAX_TOKENS,
        temperature=0.2,
        tools=[_ARTICLE_ENRICH_TOOL],
        tool_choice={"type": "tool", "name": "analyze_article"},
        timeout_s=ENRICH_TIMEOUT_S,
    )

    async with factory() as s:
        await log_claude_call(
            s,
            resp,
            operation="web_discovery_enrich_article",
            run_id=run_id,
            meta={"article_id": str(article_id), "pipeline": "web_discovery"},
        )

    cost = float(resp.cost_usd or 0.0)
    if resp.status != "ok":
        await emit(
            run_id,
            "log",
            f"Enrich failed for {title[:80]}: {resp.error or resp.status}",
            level="warn",
            meta={"article_id": str(article_id)},
        )
        return None, [], cost, False

    payload = resp.first_tool_input or {}
    summary = str(payload.get("executive_summary") or "").strip() or None
    companies_raw = payload.get("companies")
    companies: list[dict[str, Any]] = []
    if isinstance(companies_raw, list):
        for item in companies_raw:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name") or "").strip()
            if not name:
                continue
            companies.append(
                {
                    "name": name,
                    "context": str(item.get("context") or "").strip(),
                    "hint_url": item.get("hint_url"),
                    "industry": item.get("industry"),
                    "hq_or_market": item.get("hq_or_market"),
                    "role_in_story": item.get("role_in_story"),
                }
            )
    return summary, companies, cost, bool(summary)


def _build_engine_outputs(
    cluster_id: uuid.UUID,
    queries: list[WebDiscoveryQuery],
    completed_queries: int,
    total_results: int,
    total_cost: float,
    new_articles: int,
    duplicates_skipped: int,
    enriched: int,
    query_summaries: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "pipeline": "web_discovery",
        "cluster_id": str(cluster_id),
        "query_count": len(queries),
        "completed_queries": completed_queries,
        "total_results": total_results,
        "new_articles": new_articles,
        "duplicates_skipped": duplicates_skipped,
        "enriched": enriched,
        "total_cost_usd": round(total_cost, 4),
        "queries": query_summaries,
    }


async def _patch_run_progress(
    factory: async_sessionmaker[AsyncSession],
    run_id: uuid.UUID,
    progress: int,
    engine_outputs: dict[str, Any],
) -> None:
    async with factory() as s:
        run = await s.get(Run, run_id)
        if run is not None:
            run.progress_pct = progress
            run.engine_outputs = engine_outputs
            await s.commit()


async def _finalize_run(
    factory: async_sessionmaker[AsyncSession],
    run_id: uuid.UUID,
    cluster_id: uuid.UUID,
    *,
    status: str,
    progress: int,
    error: str | None,
    engine_outputs: dict[str, Any],
) -> None:
    async with factory() as s:
        run = await s.get(Run, run_id)
        cluster = await s.get(WebDiscoveryCluster, cluster_id)
        if run is not None:
            run.status = status
            run.progress_pct = progress
            run.completed_at = datetime.now(timezone.utc)
            run.error = error
            run.engine_outputs = engine_outputs
        if cluster is not None and status == "completed":
            cluster.last_run_at = datetime.now(timezone.utc)
            cluster.signal_count = int(engine_outputs.get("new_articles") or 0)
        await s.commit()
