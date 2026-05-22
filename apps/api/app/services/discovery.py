"""Discovery funnel — 5-stage TrendHunter pipeline.

Stage 1 — Exa search
    Query Exa with `include_domains=["trendhunter.com"]`, the category as a
    keyword bias, and an optional user keyword + date range. Returns up to
    `max_candidates` URLs with title + snippet + published_date.

Stage 2 — Dedup + filter
    Drop URLs already present in `trend_articles` (we never re-process the
    same article). Insert remaining rows in `discovered` status.

Stage 3 — Claude Haiku rank
    Send the candidate list (title + dek) to Haiku in ONE batch call. Haiku
    returns `relevance_score (0-100)` + a 1-line `reason` per article via a
    structured tool. Keep top N (default 15).

Stage 4 — Exa /contents
    For each of the top N, fetch full body text + outbound URLs. Save to
    `trend_articles.body_text` + `reference_urls`. Mark status='read'.

Stage 5 — Claude Sonnet extract (per article)
    For each `read` article, run Sonnet with a tool schema asking for:
      - `summary` (1 paragraph)
      - `companies`: list of `{name, excerpt, hint_url?}` mentioned in body
    Save to `trend_articles.extracted_companies` + `summary`.
    Mark status='extracted'.

Events are emitted at every stage transition so the SSE feed has something
to draw. The `runs.progress_pct` is updated after each stage.
"""
from __future__ import annotations

import asyncio
import json
import logging
import uuid
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession

from app.core.db import get_session_factory
from app.engines import get_claude_client, get_exa_client
from app.engines.claude_client import ClaudeMessage
from app.engines.logging import log_claude_call, log_exa_call
from app.models.run import Run
from app.models.trend_article import TrendArticle
from app.services.categories import get_category
from app.services.run_events import emit, emit_with_session, set_pipeline

logger = logging.getLogger(__name__)

# ── Tunables ────────────────────────────────────────────────────────────────

MAX_CANDIDATES = 30        # Stage 1: Exa search num_results
TOP_N_TO_READ = 15         # Stage 3 → Stage 4 cutoff
EXTRACT_CONCURRENCY = 4    # Stage 5: parallel Sonnet calls

# ── Topic exclusions ────────────────────────────────────────────────────────
# Hard filter: any candidate whose title/snippet matches one of these keywords
# (word-boundary, case-insensitive) is dropped at Stage 1 — it never reaches
# the DB, the ranker, or the synthesizer. Extend this list to add more blocks.
EXCLUDED_TOPIC_KEYWORDS: tuple[str, ...] = (
    "cannabis",
    "marijuana",
    "weed",
    "thc",
    "cbd",
    "cannabinoid",
    "hemp",
    "dispensary",
    "psychedelic",
    "psilocybin",
)

import re as _re  # noqa: E402  (kept local to the filter block)

def _keyword_pattern(k: str) -> str:
    """Build a regex fragment that matches `k` plus its common English plural.
    Words ending in `y` use the y→ies form (dispensary → dispensaries);
    everything else allows an optional `s` / `es` suffix."""
    if k.endswith("y"):
        return _re.escape(k[:-1]) + r"(?:y|ies)"
    return _re.escape(k) + r"(?:s|es)?"


_EXCLUDED_TOPIC_RE = _re.compile(
    # Leading \b prevents catching the keyword as a prefix of an unrelated word
    # (e.g. "embedded" doesn't match "weed"). Trailing plural-form group covers
    # psychedelics, cannabinoids, dispensaries, etc.
    r"\b(?:" + "|".join(_keyword_pattern(k) for k in EXCLUDED_TOPIC_KEYWORDS) + r")\b",
    _re.IGNORECASE,
)


def _is_excluded_topic(*texts: str | None) -> bool:
    """True if any of the provided strings contains an excluded keyword."""
    for t in texts:
        if t and _EXCLUDED_TOPIC_RE.search(t):
            return True
    return False


# ── Params ──────────────────────────────────────────────────────────────────


@dataclass(slots=True)
class DiscoveryParams:
    category: str
    keyword: str | None = None
    date_from: date | None = None
    date_to: date | None = None
    max_articles: int = TOP_N_TO_READ


# ── Tool schemas ────────────────────────────────────────────────────────────

RANK_TOOL = {
    "name": "rank_articles",
    "description": (
        "Score each article for BD/intel relevance. High scores go to articles "
        "that mention specific companies, new product launches, funding events, "
        "or actionable market signals. Generic listicles score low."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "ranked": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "integer", "description": "Article index (0-based)"},
                        "score": {"type": "integer", "minimum": 0, "maximum": 100},
                        "reason": {"type": "string", "description": "≤ 15 words"},
                    },
                    "required": ["id", "score", "reason"],
                },
            }
        },
        "required": ["ranked"],
    },
}

EXTRACT_TOOL = {
    "name": "extract_article",
    "description": (
        "Identify the SUBJECT company of this article — the single company "
        "whose product, launch, funding, or initiative the article is "
        "actually about. Ignore retailers that carry the product, parent "
        "brands mentioned in passing, competitors named for comparison, "
        "and any names that appear only in TrendHunter's 'related articles' "
        "recirculation sidebar / navigation. If the article is a true joint "
        "venture or partnership between two companies, return both. "
        "Otherwise return exactly one."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "summary": {"type": "string", "description": "1 paragraph, ≤ 80 words, about the subject company's product/announcement"},
            "companies": {
                "type": "array",
                "minItems": 1,
                "maxItems": 2,
                "description": "The subject company (1), or both companies if it's a true partnership (2). Never list co-mentions, retailers, or sidebar links.",
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string", "description": "Exact brand/company name as it appears"},
                        "excerpt": {"type": "string", "description": "Verbatim excerpt from the article body (not sidebar) introducing this company. ≤ 240 chars"},
                        "hint_url": {"type": ["string", "null"], "description": "Company website if visible in the article body"},
                    },
                    "required": ["name", "excerpt"],
                },
            },
        },
        "required": ["summary", "companies"],
    },
}


# ── Result ──────────────────────────────────────────────────────────────────


@dataclass(slots=True)
class DiscoveryResult:
    run_id: uuid.UUID
    status: str
    candidates_found: int = 0
    new_articles: int = 0
    ranked: int = 0
    read: int = 0
    extracted: int = 0
    error: str | None = None
    cost_usd: float = 0.0
    elapsed_s: float = 0.0
    article_ids: list[uuid.UUID] = field(default_factory=list)


# ── Orchestrator ────────────────────────────────────────────────────────────


async def execute_discovery(
    run_id: uuid.UUID,
    params: DiscoveryParams,
    *,
    session_factory: async_sessionmaker[AsyncSession] | None = None,
) -> DiscoveryResult:
    """Run the full 5-stage funnel. Updates `runs` + writes `trend_articles`
    + emits `run_events` along the way.

    Designed to be called from either an arq worker job OR an in-process
    `asyncio.create_task` — it owns all DB session lifecycle internally.
    """
    set_pipeline("discovery")
    factory = session_factory or get_session_factory()
    t0 = datetime.now(timezone.utc).timestamp()
    result = DiscoveryResult(run_id=run_id, status="running")
    cost = 0.0

    # Mark run started
    async with factory() as s:
        run = await s.get(Run, run_id)
        if run is None:
            raise RuntimeError(f"run {run_id} not found")
        run.status = "researching"
        run.started_at = datetime.now(timezone.utc)
        run.progress_pct = 5
        await s.commit()

    await emit(
        run_id, "run_started",
        f"Discovery run started: category={params.category!r} keyword={params.keyword!r}",
        meta={"category": params.category, "keyword": params.keyword},
    )

    try:
        # ── Stage 1: Exa search ─────────────────────────────────────────────
        candidates, cost1 = await _stage1_search(run_id, params)
        cost += cost1
        result.candidates_found = len(candidates)
        await _bump_progress(factory, run_id, 20)

        # ── Stage 2: Dedup + insert ─────────────────────────────────────────
        new_articles = await _stage2_dedup_insert(run_id, params, candidates, factory)
        result.new_articles = len(new_articles)
        result.article_ids = [a.id for a in new_articles]
        await _bump_progress(factory, run_id, 30)

        if not new_articles:
            await emit(run_id, "log", "No new articles after dedup — finishing.", level="warn")
            await _finalize(factory, run_id, status="completed", progress=100)
            result.status = "completed"
            result.elapsed_s = round(datetime.now(timezone.utc).timestamp() - t0, 2)
            result.cost_usd = round(cost, 4)
            return result

        # ── Stage 3: Haiku rank ─────────────────────────────────────────────
        kept, cost3 = await _stage3_rank(run_id, new_articles, params.max_articles, factory)
        cost += cost3
        result.ranked = len(kept)
        await _bump_progress(factory, run_id, 50)

        # ── Stage 4: Exa /contents ──────────────────────────────────────────
        readable, cost4 = await _stage4_read(run_id, kept, factory)
        cost += cost4
        result.read = len(readable)
        await _bump_progress(factory, run_id, 75)

        # ── Stage 5: Sonnet extract ─────────────────────────────────────────
        extracted, cost5 = await _stage5_extract(run_id, readable, factory)
        cost += cost5
        result.extracted = len(extracted)

        await _finalize(factory, run_id, status="completed", progress=100)
        result.status = "completed"

    except Exception as exc:
        logger.exception("Discovery run failed: %s", exc)
        result.status = "failed"
        result.error = f"{type(exc).__name__}: {exc}"
        await emit(run_id, "run_failed", str(exc), level="error")
        await _finalize(factory, run_id, status="failed", progress=100, error=str(exc))

    result.elapsed_s = round(datetime.now(timezone.utc).timestamp() - t0, 2)
    result.cost_usd = round(cost, 4)
    await emit(
        run_id,
        "run_completed" if result.status == "completed" else "run_failed",
        f"Discovery {result.status}: {result.extracted} extracted "
        f"from {result.candidates_found} candidates in {result.elapsed_s}s "
        f"(${result.cost_usd:.3f}).",
        meta={
            "result": {
                **asdict(result),
                "run_id": str(result.run_id),
                "article_ids": [str(i) for i in result.article_ids],
            }
        },
    )
    return result


# ── Stages ──────────────────────────────────────────────────────────────────


async def _stage1_search(run_id: uuid.UUID, p: DiscoveryParams) -> tuple[list, float]:
    """Exa search restricted to trendhunter.com."""
    cat = get_category(p.category)
    # Query: keyword takes priority; otherwise use the category label.
    query = (p.keyword or f"trending {cat.label.lower()}").strip()
    await emit(run_id, "stage_started", f"Stage 1 — Exa search: {query!r}",
               meta={"stage": 1, "query": query})

    exa = get_exa_client()
    results, stats = await exa.search(
        query,
        include_domains=["trendhunter.com"],
        start_published_date=p.date_from,
        end_published_date=p.date_to,
        num_results=MAX_CANDIDATES,
    )

    factory = get_session_factory()
    async with factory() as s:
        await log_exa_call(s, stats, run_id=run_id, meta={"stage": 1, "query": query})

    if stats.status != "ok":
        raise RuntimeError(f"Exa search failed: {stats.error}")

    # Topic exclusion filter — drop anything matching EXCLUDED_TOPIC_KEYWORDS
    # before it can hit the DB / ranker / synthesizer.
    kept: list = []
    dropped: list[dict[str, str]] = []
    for c in results:
        if _is_excluded_topic(getattr(c, "title", None), getattr(c, "snippet", None)):
            dropped.append({"url": getattr(c, "url", ""), "title": getattr(c, "title", "") or ""})
            continue
        kept.append(c)
    if dropped:
        await emit(
            run_id, "topic_filter_applied",
            f"Stage 1 — dropped {len(dropped)} excluded-topic candidates "
            f"(keywords: {', '.join(EXCLUDED_TOPIC_KEYWORDS)})",
            meta={"stage": 1, "dropped_count": len(dropped), "dropped": dropped[:20]},
        )

    await emit(
        run_id, "stage_completed",
        f"Stage 1 — kept {len(kept)} of {len(results)} candidates "
        f"({len(dropped)} excluded) (${stats.cost_usd:.4f})",
        meta={
            "stage": 1,
            "count": len(kept),
            "raw_count": len(results),
            "excluded_count": len(dropped),
            "cost_usd": stats.cost_usd,
        },
    )
    return kept, stats.cost_usd


async def _stage2_dedup_insert(
    run_id: uuid.UUID,
    p: DiscoveryParams,
    candidates: list,
    factory: async_sessionmaker[AsyncSession],
) -> list[TrendArticle]:
    """Insert candidates with ON CONFLICT DO NOTHING on `url`, then fetch the
    rows that were *actually* inserted by this run.

    Race-safe: if two discovery runs surface the same URL simultaneously,
    one wins the unique-on-url constraint; the other simply gets fewer
    inserted rows (no IntegrityError, no orphaned commit).
    """
    if not candidates:
        return []

    rows = [
        {
            "url": c.url,
            "source": "trendhunter",
            "category": p.category,
            "title": c.title,
            "dek": c.snippet,
            "published_date": _parse_iso_date(c.published_date),
            "status": "discovered",
            "discovery_run_id": run_id,
            "reference_urls": [],
            "extracted_companies": [],
            "research_run_ids": [],
        }
        for c in candidates
    ]

    async with factory() as s:
        stmt = (
            pg_insert(TrendArticle.__table__)
            .values(rows)
            .on_conflict_do_nothing(index_elements=["url"])
            .returning(TrendArticle.__table__.c.id)
        )
        result = await s.execute(stmt)
        inserted_ids = [r[0] for r in result.fetchall()]
        await s.commit()

        if not inserted_ids:
            new_articles: list[TrendArticle] = []
        else:
            new_articles = list(
                (
                    await s.execute(
                        select(TrendArticle).where(TrendArticle.id.in_(inserted_ids))
                    )
                ).scalars().all()
            )

    await emit(
        run_id, "stage_completed",
        f"Stage 2 — dedup: {len(new_articles)} new of {len(candidates)} "
        f"({len(candidates) - len(new_articles)} already in DB)",
        meta={"stage": 2, "new": len(new_articles), "dupes": len(candidates) - len(new_articles)},
    )
    for ta in new_articles:
        await emit(
            run_id, "article_discovered", ta.title or ta.url,
            meta={"article_id": str(ta.id), "url": ta.url},
        )
    return new_articles


async def _stage3_rank(
    run_id: uuid.UUID,
    articles: list[TrendArticle],
    keep_top_n: int,
    factory: async_sessionmaker[AsyncSession],
) -> tuple[list[TrendArticle], float]:
    """One Haiku call ranks the whole batch."""
    await emit(run_id, "stage_started",
               f"Stage 3 — Haiku ranks {len(articles)} articles",
               meta={"stage": 3, "count": len(articles)})

    items = [
        {"id": i, "title": a.title or "", "dek": a.dek or ""}
        for i, a in enumerate(articles)
    ]
    user_msg = (
        "Rank these TrendHunter articles by BD/intel relevance. High scores "
        "(80+) go to articles that name a specific company, product launch, "
        "funding, or actionable market signal. Score listicles low (≤30).\n\n"
        "HARD EXCLUSIONS — score 0 (zero) regardless of other merit if the "
        "article is primarily about: cannabis, marijuana, weed, THC, CBD, "
        "cannabinoids, hemp products, dispensaries, psychedelics, or "
        "psilocybin. These topics are out of scope for this BD feed.\n\n"
        + json.dumps(items, indent=2)
    )

    claude = get_claude_client()
    resp = await claude.complete(
        model="haiku",
        system="You rank articles for a BD/intel feed. Use the rank_articles tool.",
        messages=[ClaudeMessage(role="user", content=user_msg)],
        tools=[RANK_TOOL],
        tool_choice={"type": "tool", "name": "rank_articles"},
        max_tokens=4096,
        temperature=0.0,
    )

    async with factory() as s:
        await log_claude_call(s, resp, operation="discovery_rank", run_id=run_id,
                              meta={"stage": 3, "count": len(articles)})

    if resp.status != "ok" or not resp.first_tool_input:
        raise RuntimeError(f"Claude rank failed: {resp.error or 'no tool output'}")

    ranked_rows = resp.first_tool_input.get("ranked", [])
    score_by_id = {r["id"]: r for r in ranked_rows if "id" in r}

    # Persist scores; build sorted survivor list
    async with factory() as s:
        for i, a in enumerate(articles):
            r = score_by_id.get(i)
            if not r:
                continue
            db_a = await s.get(TrendArticle, a.id)
            if db_a is None:
                continue
            db_a.relevance_score = int(r.get("score", 0))
            db_a.relevance_reason = (r.get("reason") or "")[:300]
            db_a.status = "ranked"
        await s.commit()

    # Build the survivor list from in-memory + sort
    scored = [
        (a, score_by_id.get(i, {}).get("score", 0))
        for i, a in enumerate(articles)
        if i in score_by_id
    ]
    scored.sort(key=lambda t: t[1], reverse=True)
    kept = [a for a, _ in scored[:keep_top_n]]

    await emit(
        run_id, "stage_completed",
        f"Stage 3 — kept top {len(kept)} (${resp.cost_usd:.4f})",
        meta={"stage": 3, "kept": len(kept), "cost_usd": resp.cost_usd},
    )
    for a in kept:
        score = next((s for x, s in scored if x.id == a.id), 0)
        await emit(
            run_id, "article_ranked",
            f"{a.title or a.url} — {score}/100",
            meta={"article_id": str(a.id), "score": score},
        )
    return kept, resp.cost_usd


async def _stage4_read(
    run_id: uuid.UUID,
    articles: list[TrendArticle],
    factory: async_sessionmaker[AsyncSession],
) -> tuple[list[TrendArticle], float]:
    """Fetch full body + outbound URLs for each top-N article."""
    if not articles:
        return [], 0.0

    await emit(run_id, "stage_started",
               f"Stage 4 — Exa /contents for {len(articles)} articles",
               meta={"stage": 4, "count": len(articles)})

    exa = get_exa_client()
    contents, stats = await exa.get_contents([a.url for a in articles])

    async with factory() as s:
        await log_exa_call(s, stats, run_id=run_id, meta={"stage": 4, "count": len(articles)})

    if stats.status != "ok":
        raise RuntimeError(f"Exa get_contents failed: {stats.error}")

    by_url = {c.url: c for c in contents}
    readable: list[TrendArticle] = []
    async with factory() as s:
        for a in articles:
            c = by_url.get(a.url)
            if c is None:
                continue
            db_a = await s.get(TrendArticle, a.id)
            if db_a is None:
                continue
            db_a.body_text = c.text
            db_a.reference_urls = list(c.outbound_links or [])
            db_a.status = "read"
            readable.append(db_a)
        await s.commit()

    await emit(
        run_id, "stage_completed",
        f"Stage 4 — read {len(readable)} bodies (${stats.cost_usd:.4f})",
        meta={"stage": 4, "read": len(readable), "cost_usd": stats.cost_usd},
    )
    return readable, stats.cost_usd


async def _stage5_extract(
    run_id: uuid.UUID,
    articles: list[TrendArticle],
    factory: async_sessionmaker[AsyncSession],
) -> tuple[list[TrendArticle], float]:
    """Per-article Sonnet extract, run with bounded concurrency."""
    if not articles:
        return [], 0.0

    await emit(run_id, "stage_started",
               f"Stage 5 — Sonnet extract on {len(articles)} articles",
               meta={"stage": 5, "count": len(articles)})

    sem = asyncio.Semaphore(EXTRACT_CONCURRENCY)
    total_cost = 0.0
    extracted: list[TrendArticle] = []

    async def _one(a: TrendArticle) -> tuple[TrendArticle | None, float]:
        async with sem:
            claude = get_claude_client()
            # Truncate body to avoid runaway tokens — 16k chars ≈ 4k tokens
            body = (a.body_text or "")[:16000]
            user_msg = (
                f"ARTICLE TITLE: {a.title}\n"
                f"DEK: {a.dek or ''}\n\n"
                f"BODY:\n{body}\n\n"
                "Use the extract_article tool. Return:\n"
                "1. A one-paragraph summary focused on the SUBJECT company's product/launch.\n"
                "2. The SUBJECT company only — the one whose product this article is about.\n\n"
                "Hard rules:\n"
                "• If the title is 'Precision-Fermented Protein : Vivitein LF' the subject is "
                "the maker of Vivitein LF, not retailers, not competitors, not parent companies "
                "name-dropped, and definitely not unrelated brand names from TrendHunter's "
                "recirculation widgets at the bottom of the page.\n"
                "• Only return 2 companies if the article is explicitly a partnership / JV "
                "between two named parties. Never return more than 2.\n"
                "• The excerpt must come from the article body, not from sidebar/footer text."
            )
            resp = await claude.complete(
                model="sonnet",
                system="You extract BD/intel signal from articles. Use the tool.",
                messages=[ClaudeMessage(role="user", content=user_msg)],
                tools=[EXTRACT_TOOL],
                tool_choice={"type": "tool", "name": "extract_article"},
                max_tokens=2048,
                temperature=0.0,
            )

            async with factory() as s:
                await log_claude_call(
                    s, resp, operation="discovery_extract",
                    run_id=run_id, meta={"stage": 5, "article_id": str(a.id)},
                )

            if resp.status != "ok" or not resp.first_tool_input:
                await emit(run_id, "log",
                           f"Stage 5 — extract failed for {a.title!r}: {resp.error}",
                           level="warn", meta={"article_id": str(a.id)})
                return None, resp.cost_usd

            payload = resp.first_tool_input
            companies = payload.get("companies") or []
            summary = (payload.get("summary") or "").strip()

            async with factory() as s:
                db_a = await s.get(TrendArticle, a.id)
                if db_a is None:
                    return None, resp.cost_usd
                db_a.summary = summary
                db_a.extracted_companies = companies
                db_a.status = "extracted"
                await s.commit()
                await s.refresh(db_a)

            await emit(
                run_id, "article_extracted",
                f"{a.title} — {len(companies)} company(ies)",
                meta={"article_id": str(a.id), "companies": [c.get("name") for c in companies]},
            )
            return db_a, resp.cost_usd

    results = await asyncio.gather(*[_one(a) for a in articles])
    for a, c in results:
        total_cost += c
        if a is not None:
            extracted.append(a)

    await emit(
        run_id, "stage_completed",
        f"Stage 5 — extracted {len(extracted)} (${total_cost:.4f})",
        meta={"stage": 5, "extracted": len(extracted), "cost_usd": total_cost},
    )
    return extracted, total_cost


# ── Helpers ─────────────────────────────────────────────────────────────────


async def _bump_progress(
    factory: async_sessionmaker[AsyncSession],
    run_id: uuid.UUID,
    pct: int,
) -> None:
    async with factory() as s:
        run = await s.get(Run, run_id)
        if run is not None:
            run.progress_pct = pct
            await s.commit()


async def _finalize(
    factory: async_sessionmaker[AsyncSession],
    run_id: uuid.UUID,
    *,
    status: str,
    progress: int,
    error: str | None = None,
) -> None:
    async with factory() as s:
        run = await s.get(Run, run_id)
        if run is None:
            return
        run.status = status
        run.progress_pct = progress
        run.completed_at = datetime.now(timezone.utc)
        if error:
            run.error = error
        await s.commit()


def _parse_iso_date(s: str | None) -> date | None:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00")).date()
    except Exception:
        try:
            return date.fromisoformat(s[:10])
        except Exception:
            return None
