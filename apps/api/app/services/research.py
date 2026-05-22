"""Research engine — the heart of NORAD.

For one chosen company, this service runs the full Company-Card synthesis:

    Stage 1  build_input            — read trend_article context (if any),
                                       normalize company name + domain hint
    Stage 2  fan_out (gather)       — Parallel Task API  +  Exa search/contents
                                       fire in parallel; either alone is enough
                                       to proceed, only both-failed kills the run
    Stage 3  synthesize             — Claude Sonnet merges structured Parallel
                                       output + Exa snippets into one validated
                                       CompanyCardV1 via tool_use
    Stage 4  persist                — upsert Company → insert Card → backfill
                                       Signals + Sources → flip Run to completed,
                                       point Company.canonical_card_id at the
                                       fresh card

Cost shape (default config: Parallel `pro` + Exa `deep` + Sonnet 4.5):
    Parallel pro       ≈ $2.50  / run  (flat per task, processor=pro)
    Exa deep search    ≈ $0.01  / run  (2 deep searches @ $0.005 ea)
    Exa get_contents   ≈ $0.025 / run  (~5 URLs @ $0.005 ea)
    Claude Sonnet 4.5  ≈ $0.30-0.50 / run  (varies with parallel JSON size)
    ─────────────────────────────────────────────────────
    ≈ $2.80 - $3.10 / company

Switching Parallel back to `core` ($1.00) drops total to ≈ $1.30 / company.
Configurable from /settings (persisted in app_kv research_config).

Notes on robustness:
    * Both engines independently catch their own errors; a half-result still
      produces a card (with `confidence="unknown"` on the missing block).
    * Pydantic validation is the contract. If the synthesizer returns garbage,
      the run is failed with a `synthesis_failed` event — no orphan card.
    * Tier-C fields are auto-stubbed by `CompanyCardV1` defaults — the engines
      are not asked to fill them (the trimmed contract schema excludes them).
"""
from __future__ import annotations

import asyncio
import json
import logging
import uuid
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.services.settings import ResearchConfig
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timezone
from typing import Any
from urllib.parse import urlparse

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession

from app.core.db import get_session_factory
from app.engines import get_claude_client, get_exa_client, get_parallel_client
from app.engines.claude_client import ClaudeMessage
from app.engines.exa_client import ExaCallStats, ExaContent
from app.engines.logging import log_claude_call, log_exa_call, log_parallel_call
from app.engines.parallel_client import ParallelTaskResponse
from app.models import Card, Company, Run, Signal, Source, TrendArticle
from app.schemas import CompanyCardV1, get_contract_schema
from app.schemas.common import Source as SourceSchema
from app.services.run_events import emit, set_pipeline

logger = logging.getLogger(__name__)


# ── Tunables ─────────────────────────────────────────────────────────────────

PARALLEL_PROCESSOR = "pro"  # default — overridden per-run from app_kv research_config
PARALLEL_TIMEOUT_S = 600.0
EXA_QUERIES_PER_RUN = 2
EXA_TOP_N_CONTENTS = 5
EXA_SEARCH_TYPE = "deep"     # default — overridden per-run from app_kv
EXA_DEEP_MODEL = "deep-reasoning"
EXA_NUM_RESULTS = 10
SYNTH_MODEL = "sonnet"
SYNTH_MAX_TOKENS = 16000  # cards can be large
SYNTH_TIMEOUT_S = 300.0


# ── Input + Result ───────────────────────────────────────────────────────────


@dataclass(slots=True)
class ResearchParams:
    company_name: str
    domain_hint: str | None = None
    trend_article_id: uuid.UUID | None = None
    company_id: uuid.UUID | None = None  # if re-researching an existing company


@dataclass
class ResearchResult:
    run_id: uuid.UUID
    status: str
    company_id: uuid.UUID | None = None
    card_id: uuid.UUID | None = None
    elapsed_s: float = 0.0
    cost_usd: float = 0.0
    error: str | None = None
    engines: dict[str, Any] = field(default_factory=dict)


# ── Public entry point ──────────────────────────────────────────────────────


async def execute_research(run_id: uuid.UUID, p: ResearchParams) -> ResearchResult:
    """Run the full research pipeline for one company. Never raises —
    failures are recorded on the Run row + emitted as run_events.
    """
    set_pipeline("research")
    factory = get_session_factory()
    t0 = datetime.now(timezone.utc)

    # Mark run as researching + progress 5
    await _update_run(factory, run_id, status="researching", progress=5, started=True)
    await emit(
        run_id,
        "run_started",
        f"Research start: {p.company_name}",
        meta={
            "company_name": p.company_name,
            "domain_hint": p.domain_hint,
            "trend_article_id": str(p.trend_article_id) if p.trend_article_id else None,
        },
    )

    total_cost = 0.0
    try:
        # Load global engine config once per run (DB-cached).
        from app.services.settings import get_research_config
        async with factory() as s:
            cfg = await get_research_config(s)

        # ── Stage 1: build research input ─────────────────────────────────
        article_ctx = await _stage1_load_article_context(p, factory)
        await _update_run(factory, run_id, progress=15)
        await emit(
            run_id,
            "stage_completed",
            "Stage 1 — built research input"
            + (f" with article context ({article_ctx.source!r})" if article_ctx else ""),
            meta={"stage": 1, "has_article_ctx": bool(article_ctx)},
        )

        # ── Stage 2: fan-out (Parallel + Exa) ─────────────────────────────
        await emit(
            run_id, "stage_started",
            "Stage 2 — Parallel Task + Exa research (parallel)",
            meta={"stage": 2},
        )
        parallel_resp, exa_bundle = await asyncio.gather(
            _stage2_parallel(run_id, p, article_ctx, factory, cfg),
            _stage2_exa(run_id, p, factory, cfg),
            return_exceptions=False,  # each inner fn never raises
        )
        total_cost += parallel_resp.cost_usd + exa_bundle.cost_usd

        parallel_ok = parallel_resp.succeeded and isinstance(
            parallel_resp.output_json, dict
        )
        exa_ok = bool(exa_bundle.contents)
        if not parallel_ok and not exa_ok:
            raise RuntimeError(
                "both engines failed: "
                f"parallel={parallel_resp.error}; exa=no contents"
            )

        await _update_run(factory, run_id, progress=55, status="synthesizing")
        await emit(
            run_id, "stage_completed",
            f"Stage 2 — Parallel {'OK' if parallel_ok else 'FAIL'} "
            f"(${parallel_resp.cost_usd:.3f}), Exa {len(exa_bundle.contents)} reads "
            f"(${exa_bundle.cost_usd:.3f})",
            meta={
                "stage": 2,
                "parallel_ok": parallel_ok,
                "exa_reads": len(exa_bundle.contents),
                "parallel_cost": parallel_resp.cost_usd,
                "exa_cost": exa_bundle.cost_usd,
            },
        )

        # ── Stage 3: Claude synthesizer ───────────────────────────────────
        await emit(
            run_id, "stage_started",
            "Stage 3 — Claude Sonnet synthesizing CompanyCardV1",
            meta={"stage": 3},
        )
        card_dict, claude_cost = await _stage3_synthesize(
            run_id, p, article_ctx, parallel_resp, exa_bundle, factory
        )
        total_cost += claude_cost
        card_dict = _sanitize_card_dict(card_dict)
        try:
            card_model = CompanyCardV1.model_validate(card_dict)
        except ValidationError as ve:
            # Common Claude failure: it returns `"foo"` where the contract
            # wants `Valued[str]` (`{value, confidence, basis}`). Walk the
            # error locs, coerce each offending path into a proper Valued
            # dict, then try validation once more before giving up.
            coerced = _coerce_valued_paths(card_dict, ve)
            if coerced:
                try:
                    card_model = CompanyCardV1.model_validate(card_dict)
                    await emit(
                        run_id, "synthesis_coerce_recovered",
                        f"Auto-wrapped {coerced} bare scalar(s) into Valued[] "
                        "to recover from synth's flattening.",
                        level="warn",
                        meta={"stage": 3, "coerced_paths": coerced},
                    )
                except ValidationError as ve2:
                    await emit(
                        run_id, "log",
                        f"Synthesizer output failed validation: {_short_err(ve2)}",
                        level="warn",
                        meta={"stage": 3, "validation_error": str(ve2)[:2000]},
                    )
                    raise RuntimeError(f"synthesis_validation_failed: {_short_err(ve2)}") from ve2
            else:
                await emit(
                    run_id, "log",
                    f"Synthesizer output failed validation: {_short_err(ve)}",
                    level="warn",
                    meta={"stage": 3, "validation_error": str(ve)[:2000]},
                )
                raise RuntimeError(f"synthesis_validation_failed: {_short_err(ve)}") from ve

        await _update_run(factory, run_id, progress=85)
        await emit(
            run_id, "stage_completed",
            f"Stage 3 — synthesized card ({len(card_model.signals)} signals, "
            f"{len(card_model.sources_and_confidence.sources)} sources, "
            f"${claude_cost:.3f})",
            meta={
                "stage": 3,
                "cost": claude_cost,
                "signal_count": len(card_model.signals),
                "source_count": len(card_model.sources_and_confidence.sources),
            },
        )

        # ── Stage 4: persist ──────────────────────────────────────────────
        # Cancellation check: if the user cancelled during synthesis, bail
        # before we create / mutate any Company / Card / Signal / Source rows.
        async with factory() as s:
            _check_run = await s.get(Run, run_id)
            if _check_run is not None and _check_run.status == "cancelled":
                await emit(
                    run_id, "run_cancelled",
                    "Run was cancelled by the user — skipping persistence.",
                    level="warn",
                    meta={"stage": 4, "cost_usd": round(total_cost, 4)},
                )
                return ResearchResult(
                    run_id=run_id,
                    status="cancelled",
                    elapsed_s=round((datetime.now(timezone.utc) - t0).total_seconds(), 1),
                    cost_usd=round(total_cost, 4),
                )

        company_id, card_id = await _stage4_persist(
            run_id, p, card_model, factory
        )

        elapsed = (datetime.now(timezone.utc) - t0).total_seconds()
        await _update_run(
            factory,
            run_id,
            status="completed",
            progress=100,
            completed=True,
            company_id=company_id,
            card_id=card_id,
            engine_outputs={
                "parallel_run_id": parallel_resp.run_id,
                "exa_query_count": exa_bundle.query_count,
                "synth_cost_usd": claude_cost,
                "total_cost_usd": round(total_cost, 4),
            },
        )
        await emit(
            run_id, "run_completed",
            f"Research complete: {p.company_name} ({elapsed:.1f}s, ${total_cost:.3f})",
            meta={
                "elapsed_s": round(elapsed, 1),
                "cost_usd": round(total_cost, 4),
                "company_id": str(company_id),
                "card_id": str(card_id),
            },
        )
        return ResearchResult(
            run_id=run_id,
            status="completed",
            company_id=company_id,
            card_id=card_id,
            elapsed_s=round(elapsed, 1),
            cost_usd=round(total_cost, 4),
        )

    except Exception as exc:  # noqa: BLE001 — top-level capture
        elapsed = (datetime.now(timezone.utc) - t0).total_seconds()
        err = f"{type(exc).__name__}: {exc}"
        logger.exception("execute_research crashed run_id=%s", run_id)
        await _update_run(
            factory, run_id, status="failed", error=err, completed=True
        )
        await emit(
            run_id, "run_failed", f"Research failed: {err}",
            level="error",
            meta={"elapsed_s": round(elapsed, 1), "cost_usd": round(total_cost, 4)},
        )
        return ResearchResult(
            run_id=run_id,
            status="failed",
            elapsed_s=round(elapsed, 1),
            cost_usd=round(total_cost, 4),
            error=err,
        )


# ── Stage 1: build research input ────────────────────────────────────────────


@dataclass(slots=True)
class _ArticleContext:
    article_id: uuid.UUID
    title: str | None
    summary: str | None
    url: str
    source: str


async def _stage1_load_article_context(
    p: ResearchParams,
    factory: async_sessionmaker[AsyncSession],
) -> _ArticleContext | None:
    if not p.trend_article_id:
        return None
    async with factory() as s:
        article = await s.get(TrendArticle, p.trend_article_id)
        if article is None:
            return None
        # Bind in the article excerpt for the named company if we have it.
        excerpt = None
        for c in article.extracted_companies or []:
            if (c.get("name") or "").lower() == p.company_name.lower():
                excerpt = c.get("excerpt")
                break
        return _ArticleContext(
            article_id=article.id,
            title=article.title,
            summary=excerpt or article.summary,
            url=article.url,
            source=article.source or "trendhunter",
        )


# ── Stage 2a: Parallel ───────────────────────────────────────────────────────


# Compact research brief Parallel emits. Kept small + flat so it fits well
# under Parallel's 15 KB task_spec cap. Claude reads this as evidence (NOT as
# the final contract) and reconciles it with the full CompanyCardV1 schema.
_PARALLEL_MIN_SIGNALS = 3
_PARALLEL_MIN_SOURCES = 3

_PARALLEL_RESEARCH_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["company_name", "summary", "sources"],
    "properties": {
        "company_name": {"type": "string"},
        "legal_entity_name": {"type": ["string", "null"]},
        "domain": {"type": ["string", "null"]},
        "website": {"type": ["string", "null"]},
        "headquarters": {"type": ["string", "null"]},
        "founded_year": {"type": ["integer", "null"]},
        "founders": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Founder full names.",
        },
        "ceo": {"type": ["string", "null"]},
        "status": {
            "type": ["string", "null"],
            "description": "private | public | subsidiary | acquired | unknown",
        },
        "industry": {"type": ["string", "null"]},
        "category": {"type": ["string", "null"]},
        "business_type": {
            "type": ["string", "null"],
            "description": "b2b | b2c | b2b2c | marketplace | unknown",
        },
        "summary": {
            "type": "string",
            "description": "2-4 sentence what-they-do summary.",
        },
        "products": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Core products / SKUs / SaaS modules.",
        },
        "revenue_estimate_usd": {
            "type": ["string", "null"],
            "description": "Rough revenue band e.g. '$5M-$10M ARR' or null.",
        },
        "employee_count_estimate": {"type": ["integer", "null"]},
        "hiring_pace": {
            "type": ["string", "null"],
            "description": "growing_fast | growing | flat | shrinking | unknown",
        },
        "total_funding_usd": {"type": ["number", "null"]},
        "last_round_type": {"type": ["string", "null"]},
        "last_round_date": {
            "type": ["string", "null"],
            "description": "YYYY-MM-DD or YYYY-MM.",
        },
        "last_round_amount_usd": {"type": ["number", "null"]},
        "investors": {
            "type": "array",
            "items": {"type": "string"},
        },
        "competitors": {
            "type": "array",
            "items": {"type": "string"},
        },
        "competitive_advantage": {"type": ["string", "null"]},
        "signals": {
            "type": "array",
            "description": (
                f"REQUIRED: at least {_PARALLEL_MIN_SIGNALS} items, ideally 3-8. "
                "These are the strongest growth/funding/momentum/risk signals "
                "for the company. Even for small / low-profile companies, you "
                "MUST derive 3+ signals from whatever evidence exists: product "
                "launches, founder background, hiring posts, niche category "
                "positioning, customer review themes, social/PR mentions, "
                "press coverage. Do not return fewer than 3 — synthesize from "
                "available evidence. (Parallel's API rejects JSON-schema "
                "`minItems`, so this is enforced via prompt + downstream "
                "retry.)"
            ),
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["type", "headline"],
                "properties": {
                    "type": {
                        "type": "string",
                        "description": "growth | funding | hiring | product | partnership | risk | strategic",
                    },
                    "date": {
                        "type": ["string", "null"],
                        "description": "YYYY-MM-DD if known.",
                    },
                    "headline": {"type": "string"},
                    "evidence": {"type": ["string", "null"]},
                    "weight": {
                        "type": ["integer", "null"],
                        "description": "1-10 strength of signal.",
                    },
                    "source_urls": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                },
            },
        },
        "sources": {
            "type": "array",
            "description": "Every URL referenced above, with title + publish date if known.",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["url"],
                "properties": {
                    "url": {"type": "string"},
                    "title": {"type": ["string", "null"]},
                    "date_published": {"type": ["string", "null"]},
                    "trust_tier": {
                        "type": ["string", "null"],
                        "description": "A=official | B=major-press | C=trade | D=blog | E=social",
                    },
                },
            },
        },
        "notes_for_synthesizer": {
            "type": ["string", "null"],
            "description": "Anything Claude should know that doesn't fit above.",
        },
    },
}


async def _stage2_parallel(
    run_id: uuid.UUID,
    p: ResearchParams,
    article_ctx: _ArticleContext | None,
    factory: async_sessionmaker[AsyncSession],
    cfg: "ResearchConfig",
) -> ParallelTaskResponse:
    """Submit a Parallel Task and wait for it. Logs cost on completion."""
    client = get_parallel_client()
    payload: dict[str, Any] = {
        "company_name": p.company_name,
        "domain_hint": p.domain_hint or "",
        "instruction": (
            "Build a compact evidence brief for this company against the "
            "provided output_schema (identity, funding, signals, sources). "
            "This is NOT the final card — a downstream synthesizer will merge "
            "your brief with other web evidence into a richer schema. "
            "Be precise: cite real URLs, prefer concrete facts over speculation, "
            "and leave optional fields null when uncertain rather than guessing."
        ),
    }
    if article_ctx:
        payload["article_context"] = (
            f"Source: {article_ctx.url}\n"
            f"Title: {article_ctx.title or ''}\n"
            f"Excerpt: {article_ctx.summary or ''}"
        )

    # Parallel caps `task_spec` at 15 KB; the full CompanyCardV1 contract is
    # ~54 KB. Send a compact research brief instead — Claude (Stage 3) holds
    # the strict contract and merges Parallel's evidence stream into it.
    resp = await client.run_to_completion(
        input_payload=payload,
        output_schema=_PARALLEL_RESEARCH_SCHEMA,
        processor=cfg.parallel.processor,
        timeout_s=float(cfg.parallel.timeout_s),
        metadata={"run_id": str(run_id), "vendor": "norad"},
    )
    async with factory() as s:
        await log_parallel_call(
            s, resp, operation="task_run", run_id=run_id,
            meta={"company_name": p.company_name},
            request_payload={
                "input_payload": payload,
                "processor": cfg.parallel.processor,
                "output_schema_chars": len(json.dumps(_PARALLEL_RESEARCH_SCHEMA)),
            },
        )
    return resp


# ── Stage 2b: Exa ────────────────────────────────────────────────────────────


@dataclass(slots=True)
class _ExaBundle:
    contents: list[ExaContent]
    query_count: int
    cost_usd: float


async def _stage2_exa(
    run_id: uuid.UUID,
    p: ResearchParams,
    factory: async_sessionmaker[AsyncSession],
    cfg: "ResearchConfig",
) -> _ExaBundle:
    """Two broad searches (company + recent news/funding), then /contents on top N.
    All failures are swallowed — we just return whatever we got.
    """
    client = get_exa_client()
    base = p.company_name
    domain = p.domain_hint or _guess_domain(p.company_name)
    queries = [
        f"{base} company overview product founders" + (f" site:{domain}" if domain else ""),
        f"{base} funding investors news 2024 2025",
    ][:EXA_QUERIES_PER_RUN]

    all_urls: list[str] = []
    seen = set()
    total_cost = 0.0
    # Build I/O records as we go so we can persist them alongside stats below.
    io_records: list[tuple[ExaCallStats, dict[str, Any], dict[str, Any]]] = []
    for q in queries:
        results, stats = await client.search(
            q,
            num_results=cfg.exa.num_results,
            search_type=cfg.exa.search_type,
            deep_model=cfg.exa.deep_model,
        )
        total_cost += stats.cost_usd
        io_records.append((
            stats,
            {
                "query": q,
                "num_results": cfg.exa.num_results,
                "search_type": cfg.exa.search_type,
                "deep_model": cfg.exa.deep_model,
            },
            {"urls": [r.url for r in results], "count": len(results)},
        ))
        for r in results:
            if r.url and r.url not in seen:
                seen.add(r.url)
                all_urls.append(r.url)
        if len(all_urls) >= EXA_TOP_N_CONTENTS * 2:
            break

    top_urls = all_urls[:EXA_TOP_N_CONTENTS]
    contents: list[ExaContent] = []
    if top_urls:
        contents, gc_stats = await client.get_contents(top_urls)
        total_cost += gc_stats.cost_usd
        io_records.append((
            gc_stats,
            {"urls": top_urls},
            {
                "fetched": [
                    {"url": c.url, "title": c.title, "chars": len(c.text or "")}
                    for c in contents
                ],
            },
        ))

    async with factory() as s:
        for st, req, rsp in io_records:
            await log_exa_call(
                s, st, run_id=run_id,
                meta={"company_name": p.company_name},
                request_payload=req,
                response_payload=rsp,
            )

    return _ExaBundle(
        contents=contents,
        query_count=len(queries),
        cost_usd=round(total_cost, 4),
    )


def _guess_domain(name: str) -> str | None:
    """Cheap heuristic — strip whitespace/special, append .com. Not always right
    but as a *hint* (site: filter is optional) it costs nothing to be wrong."""
    slug = "".join(c.lower() for c in name if c.isalnum())
    return f"{slug}.com" if 2 <= len(slug) <= 40 else None


# ── Stage 3: Claude synthesizer ──────────────────────────────────────────────


_SYNTH_SYSTEM = """You are the NORAD research synthesizer.

Your job: produce ONE high-quality CompanyCardV1 JSON describing the target \
company, by merging two evidence streams:

1. PARALLEL — a COMPACT evidence brief (identity, funding, signals, sources) \
returned by an agentic web-research engine. This is NOT the full CompanyCardV1 \
contract — it's pre-vetted candidate facts you must verify against Exa \
snippets and expand into the richer card schema (products_and_skus, \
people_and_decision_map, strategic_fit, scores, etc.).
2. EXA — raw text snippets from 3-8 web pages we crawled in real time. Use \
these to add detail, attribute sources, and override Parallel where Exa \
disagrees clearly.

Rules (these are absolute):
- Return the card via the synthesize_company_card tool. Do not include any \
prose outside the tool call.
- Every `Valued` field that has a non-null `value` MUST set `confidence` to \
one of: confirmed, estimated, inferred. NEVER set both a value and \
confidence="unknown".
- `confidence="confirmed"` MUST cite at least one source (integer id into \
the sources list). Don't fake citations.
- `confidence="estimated"` or `"inferred"` MUST include a non-empty `basis` \
string explaining the reasoning.
- `sources_and_confidence.sources` MUST contain AT LEAST 3 entries (target \
3-8). A CANDIDATE SOURCE REGISTRY is provided in the user message — it lists \
URLs (with ids) we already fetched. Build `sources_and_confidence.sources` by \
SELECTING from that registry (keep the ids stable). You may also add Parallel-\
cited URLs that aren't in the registry by appending new ids continuing the \
numbering. NEVER invent a URL that isn't in the registry or in the Parallel \
output. Use the resulting ids in Valued.sources and Signal.source_refs.
- `signals` MUST contain AT LEAST 3 entries (target 3-8). This is non-negotiable, \
even for tiny / under-the-radar companies. Each signal's `type` MUST be EXACTLY \
ONE of these six enum values (no other strings — the contract will reject \
anything else):
    growth | fundraising | acquisition | partnership | risk | strategic
  If you don't see obvious growth or funding signals, derive signals from what \
IS visible and slot them into the closest enum bucket — examples:
    * product launches or SKU expansion          → type="growth"
    * founder background / prior exits           → type="strategic"
    * hiring posts on LinkedIn / job boards      → type="growth"
    * niche category positioning vs incumbents   → type="strategic"
    * customer review themes / NPS sentiment     → type="risk"  (negative) or "growth" (positive)
    * partnership / distribution mentions        → type="partnership"
    * press, podcast, or social mentions         → type="growth"
    * regulatory exposure or category headwinds  → type="risk"
    * M&A chatter or acquihire rumors            → type="acquisition"
    * round announcements / SAFE / crowdfund     → type="fundraising"
  Each signal must include type (one of the six above), headline, weight 1-10, \
and reference at least one source id. NEVER return an empty signals array — \
that means you did not read the evidence carefully enough.
- For `scores`: produce honest 0-100 numbers across all sub-scores. Lower is \
fine — don't inflate.
- For `strategic_fit`: write a NORAD/Growth-Maschine-specific take. Recommend \
one action (outreach_partnership | outreach_investment | outreach_acquisition \
| monitor | pass) with rationale.
- If something is genuinely unknown, leave `value: null` and \
`confidence: "unknown"`. Honest > wrong.
- Do not invent URLs. Do not invent person names, funding amounts, \
investors, or revenue numbers.
"""

_SYNTH_MIN_SIGNALS = 3
_SYNTH_MIN_SOURCES = 3


# ── Candidate-source registry ────────────────────────────────────────────────
# We don't trust the synthesizer to invent its own sources list — empirically
# Claude omits `sources_and_confidence.sources` entirely on some runs even
# though the schema says it's required (tool_use is best-effort, not strict).
# So we build a numbered registry of URLs we KNOW we fetched (Exa contents
# first, then unique URLs cited in the Parallel `basis` block) and:
#   1. show it to Claude in the user message so it just picks ids
#   2. deterministically backfill if Claude still returns empty sources

# Hosts that are unambiguously high-quality primary sources → Tier A.
_TRUST_A_HOSTS = {
    "sec.gov", "uspto.gov", "fda.gov", "ftc.gov", "europa.eu",
}
# Quality secondary sources (filings aggregators, mainstream press) → Tier B.
_TRUST_B_HOSTS = {
    "crunchbase.com", "pitchbook.com", "linkedin.com",
    "techcrunch.com", "bloomberg.com", "reuters.com", "wsj.com",
    "ft.com", "forbes.com", "businesswire.com", "prnewswire.com",
    "nytimes.com", "theinformation.com", "axios.com",
}


def _infer_trust_tier(url: str) -> str:
    try:
        host = urlparse(url).netloc.lower().lstrip("www.")
    except Exception:
        return "C"
    if any(host == h or host.endswith("." + h) for h in _TRUST_A_HOSTS):
        return "A"
    if any(host == h or host.endswith("." + h) for h in _TRUST_B_HOSTS):
        return "B"
    return "C"


def _build_candidate_sources(
    exa_contents: list[ExaContent],
    parallel_output: dict[str, Any] | None,
    parallel_citations: list[dict[str, Any]] | None = None,
    max_total: int = 12,
) -> list[SourceSchema]:
    """Numbered registry of URLs we already fetched / Parallel cited.

    Exa contents come first (we have the full text, freshest evidence), then
    unique URLs from three Parallel locations (any of which may be empty
    depending on Parallel's response shape that day):
      * `parallel_citations` — top-level `result.citations[]`
      * `parallel_output["basis"][].citations[].url` — per-field provenance
      * `parallel_output["sources"][].url` — flat sources list if present
    Dedup by normalized URL. Returns at most `max_total` entries with stable
    integer ids 1..N.
    """
    seen: set[str] = set()
    out: list[SourceSchema] = []
    today = date.today().isoformat()

    def _norm(u: str) -> str:
        u = (u or "").strip()
        if u.endswith("/"):
            u = u[:-1]
        return u.lower()

    next_id = 1
    # Pass 1: Exa contents (we have title + body + published date).
    for c in exa_contents:
        if not c.url:
            continue
        n = _norm(c.url)
        if n in seen:
            continue
        seen.add(n)
        out.append(
            SourceSchema(
                id=next_id,
                url=c.url,
                title=c.title or None,
                type="other",
                trust_tier=_infer_trust_tier(c.url),
                date_published=str(c.published_date) if c.published_date else None,
                date_found=today,
                last_checked=today,
                snippet=((c.text or "").strip()[:280] or None),
            )
        )
        next_id += 1
        if len(out) >= max_total:
            return out

    # Helper to add a single citation-shaped dict.
    # Returns True ONLY when the registry is full (caller should stop). Skips
    # (dup / empty url) return False so the next candidate is still considered.
    def _add(url: str, title: str | None, snippet: str | None) -> bool:
        nonlocal next_id
        if not url:
            return False
        n = _norm(url)
        if n in seen:
            return False
        seen.add(n)
        out.append(
            SourceSchema(
                id=next_id,
                url=url,
                title=title or None,
                type="other",
                trust_tier=_infer_trust_tier(url),
                date_found=today,
                last_checked=today,
                snippet=(snippet or "")[:280] or None,
            )
        )
        next_id += 1
        return len(out) >= max_total

    # Pass 2: top-level Parallel citations (most reliable shape).
    for cit in parallel_citations or []:
        excerpts = cit.get("excerpts") or []
        snippet = excerpts[0] if excerpts else cit.get("snippet")
        if _add(cit.get("url") or "", cit.get("title"), snippet):
            return out

    # Pass 3: Parallel `basis[].citations[]` (per-field provenance — what
    # `pro` processor historically returns).
    for basis_item in (parallel_output or {}).get("basis", []) or []:
        for cit in basis_item.get("citations", []) or []:
            excerpts = cit.get("excerpts") or []
            snippet = excerpts[0] if excerpts else None
            if _add(cit.get("url") or "", cit.get("title"), snippet):
                return out

    # Pass 4: flat `sources[]` if Parallel returned one.
    for src in (parallel_output or {}).get("sources", []) or []:
        if isinstance(src, dict):
            if _add(src.get("url") or "", src.get("title"), src.get("snippet")):
                return out
        elif isinstance(src, str):
            if _add(src, None, None):
                return out
    return out


def _candidate_registry_block(candidates: list[SourceSchema]) -> str:
    """Render the registry as a numbered text block for Claude."""
    if not candidates:
        return "(no candidate sources — build sources from Parallel citations)"
    lines = []
    for s in candidates:
        date_part = f" ({s.date_published})" if s.date_published else ""
        title_part = f" — {s.title}" if s.title else ""
        lines.append(f"  [{s.id}] {s.url}{title_part}{date_part}  [trust={s.trust_tier}]")
    return "\n".join(lines)


async def _stage3_synthesize(
    run_id: uuid.UUID,
    p: ResearchParams,
    article_ctx: _ArticleContext | None,
    parallel_resp: ParallelTaskResponse,
    exa_bundle: _ExaBundle,
    factory: async_sessionmaker[AsyncSession],
) -> tuple[dict[str, Any], float]:
    """Send Claude both evidence streams + the contract schema as a tool spec.
    Returns (card_dict, cost_usd)."""

    contract_schema = get_contract_schema()
    tool = {
        "name": "synthesize_company_card",
        "description": "Emit the final CompanyCardV1 for this company.",
        "input_schema": contract_schema,
    }

    # Bound Exa text size so we stay under model context.
    exa_block_parts: list[str] = []
    for i, c in enumerate(exa_bundle.contents, start=1):
        body = (c.text or "").strip()[:6000]
        exa_block_parts.append(
            f"[{i}] URL: {c.url}\nTITLE: {c.title or ''}\nDATE: {c.published_date or ''}\n"
            f"TEXT:\n{body}\n"
        )
    exa_block = "\n---\n".join(exa_block_parts) or "(no Exa snippets available)"

    parallel_json = (
        json.dumps(parallel_resp.output_json, ensure_ascii=False, indent=2)[:90000]
        if parallel_resp.output_json
        else "(Parallel call did not return structured JSON)"
    )

    article_block = ""
    if article_ctx:
        article_block = (
            "ORIGINATING TREND ARTICLE\n"
            f"URL: {article_ctx.url}\n"
            f"TITLE: {article_ctx.title or ''}\n"
            f"EXCERPT: {article_ctx.summary or ''}\n\n"
        )

    # Build the deterministic candidate source registry. Claude will cite by id.
    candidate_sources = _build_candidate_sources(
        exa_bundle.contents,
        parallel_resp.output_json,
        parallel_citations=parallel_resp.citations,
    )
    candidate_block = _candidate_registry_block(candidate_sources)

    user_msg = (
        f"TARGET COMPANY: {p.company_name}\n"
        f"DOMAIN HINT: {p.domain_hint or '(none)'}\n\n"
        f"{article_block}"
        f"CANDIDATE SOURCE REGISTRY ({len(candidate_sources)} verified URLs — "
        "fetched by Exa or cited by Parallel — cite by id, don't invent):\n"
        f"{candidate_block}\n\n"
        f"PARALLEL OUTPUT (pre-structured JSON):\n```json\n{parallel_json}\n```\n\n"
        f"EXA SNIPPETS ({len(exa_bundle.contents)} pages):\n{exa_block}\n\n"
        "Produce the final CompanyCardV1 via the synthesize_company_card tool. "
        "Your `sources_and_confidence.sources` array MUST include the registry "
        "entries (preserving their ids) plus any extra Parallel-cited URLs you "
        "want to attribute."
    )

    client = get_claude_client()
    messages = [ClaudeMessage(role="user", content=user_msg)]
    resp = await client.complete(
        model=SYNTH_MODEL,
        system=_SYNTH_SYSTEM,
        messages=messages,
        max_tokens=SYNTH_MAX_TOKENS,
        temperature=0.2,
        tools=[tool],
        tool_choice={"type": "tool", "name": "synthesize_company_card"},
        timeout_s=SYNTH_TIMEOUT_S,
    )
    async with factory() as s:
        await log_claude_call(
            s, resp, operation="synthesize_card", run_id=run_id,
            meta={"company_name": p.company_name, "attempt": 1},
        )
    if resp.status != "ok":
        raise RuntimeError(f"claude_synthesis_failed: {resp.error}")
    tool_input = resp.first_tool_input
    if not isinstance(tool_input, dict):
        raise RuntimeError("claude_synthesis_returned_no_tool_use")

    total_cost = resp.cost_usd

    # ── Retry-on-thin: if Claude returned <3 signals or <3 sources, nudge once.
    signals = tool_input.get("signals") or []
    sources = (
        (tool_input.get("sources_and_confidence") or {}).get("sources") or []
    )
    if (
        len(signals) < _SYNTH_MIN_SIGNALS
        or len(sources) < _SYNTH_MIN_SOURCES
    ):
        await emit(
            run_id, "synthesis_retry",
            f"Synth returned thin output (signals={len(signals)}, "
            f"sources={len(sources)}); requesting expansion.",
            level="warn",
            meta={
                "stage": 3,
                "signals_returned": len(signals),
                "sources_returned": len(sources),
                "min_signals": _SYNTH_MIN_SIGNALS,
                "min_sources": _SYNTH_MIN_SOURCES,
            },
        )
        # True assistant replay: include the actual previous tool payload so
        # Claude can diff against itself and expand. Cap the replay JSON to
        # keep us under context — the model needs the structure, not every
        # nested character.
        prev_payload_json = json.dumps(tool_input, ensure_ascii=False)[:60000]
        retry_messages = [
            ClaudeMessage(role="user", content=user_msg),
            ClaudeMessage(
                role="assistant",
                content=(
                    "I previously emitted the following synthesize_company_card "
                    "payload (shown here as JSON for reference):\n"
                    f"```json\n{prev_payload_json}\n```"
                ),
            ),
            ClaudeMessage(
                role="user",
                content=(
                    f"That call returned only {len(signals)} signals and "
                    f"{len(sources)} sources, which is below the contract "
                    f"minimum of {_SYNTH_MIN_SIGNALS} signals and "
                    f"{_SYNTH_MIN_SOURCES} sources. Re-emit the FULL card via "
                    "the synthesize_company_card tool, keeping the good "
                    "fields you already produced and EXPANDING signals to at "
                    f"least {_SYNTH_MIN_SIGNALS} (derive them from product "
                    "launches, founder background, hiring activity, niche "
                    "positioning, customer reviews, partnerships, or category "
                    f"trends — see the system rules) and sources to at least "
                    f"{_SYNTH_MIN_SOURCES} from the Exa snippets you were "
                    "given. Don't invent facts — but DO surface the signals "
                    "and sources that are clearly present in the evidence."
                ),
            ),
        ]
        resp2 = await client.complete(
            model=SYNTH_MODEL,
            system=_SYNTH_SYSTEM,
            messages=retry_messages,
            max_tokens=SYNTH_MAX_TOKENS,
            temperature=0.3,
            tools=[tool],
            tool_choice={"type": "tool", "name": "synthesize_company_card"},
            timeout_s=SYNTH_TIMEOUT_S,
        )
        async with factory() as s:
            await log_claude_call(
                s, resp2, operation="synthesize_card_retry", run_id=run_id,
                meta={"company_name": p.company_name, "attempt": 2},
            )
        if resp2.status == "ok":
            total_cost += resp2.cost_usd
            ti2 = resp2.first_tool_input
            if isinstance(ti2, dict):
                new_signals = ti2.get("signals") or []
                new_sources = (
                    (ti2.get("sources_and_confidence") or {}).get("sources") or []
                )
                # Accept retry only if STRICTLY better: no dimension regresses
                # AND at least one dimension improves. Equal-quality retries
                # are rejected to avoid burning a $0.40 second pass for nothing.
                no_regression = (
                    len(new_signals) >= len(signals)
                    and len(new_sources) >= len(sources)
                )
                strictly_better = (
                    len(new_signals) > len(signals)
                    or len(new_sources) > len(sources)
                )
                if no_regression and strictly_better:
                    tool_input = ti2
                    signals, sources = new_signals, new_sources
        await emit(
            run_id, "synthesis_retry_done",
            f"Retry produced signals={len(signals)}, sources={len(sources)}.",
            meta={
                "stage": 3,
                "signals_final": len(signals),
                "sources_final": len(sources),
            },
        )

    # ── Defensive: dedupe Claude-emitted source ids ─────────────────────────
    # Claude usually emits unique ids in its tool_use output, but tool_use is
    # best-effort. If it ever returns two sources with the same id, renumber
    # the duplicates AND remap signals[].source_refs accordingly so the card
    # validates and signal footnotes still point somewhere real.
    sac_existing = tool_input.get("sources_and_confidence") or {}
    raw_existing_sources = sac_existing.get("sources") or []
    id_remap: dict[int, int] = {}
    seen_ids: set[int] = set()
    if raw_existing_sources:
        max_seen_id = max(
            (s.get("id") for s in raw_existing_sources
             if isinstance(s, dict) and isinstance(s.get("id"), int)),
            default=0,
        )
        next_free = max_seen_id + 1
        for s in raw_existing_sources:
            if not isinstance(s, dict):
                continue
            sid = s.get("id")
            if not isinstance(sid, int):
                continue
            if sid in seen_ids:
                s["id"] = next_free
                id_remap[sid] = next_free  # last-wins remap for signal refs
                seen_ids.add(next_free)
                next_free += 1
            else:
                seen_ids.add(sid)
        # Best-effort: remap signal source_refs (the most common cite site).
        # We can't safely remap Valued.sources nested in arbitrary blocks
        # because the same id-collision is genuinely ambiguous — but signals
        # is shallow enough to fix cleanly.
        if id_remap:
            for sig in tool_input.get("signals") or []:
                if not isinstance(sig, dict):
                    continue
                refs = sig.get("source_refs") or sig.get("sources") or []
                if isinstance(refs, list):
                    key = "source_refs" if "source_refs" in sig else "sources"
                    sig[key] = [id_remap.get(r, r) if isinstance(r, int) else r for r in refs]
            await emit(
                run_id, "sources_deduped",
                f"Renumbered {len(id_remap)} duplicate source id(s) from Claude.",
                level="warn",
                meta={"stage": 3, "remapped_count": len(id_remap)},
            )

    # ── Deterministic source backfill ───────────────────────────────────────
    # If Claude still left sources empty/short after the retry, merge in our
    # candidate registry so the card has real, citable URLs. This is safe:
    # registry URLs were either fetched by Exa or cited by Parallel — none are
    # hallucinated. Existing Claude-emitted sources keep their ids; we append
    # only the registry URLs Claude didn't already include.
    if candidate_sources:
        existing = (
            (tool_input.get("sources_and_confidence") or {}).get("sources") or []
        )
        existing_urls = {
            (s.get("url") or "").strip().lower().rstrip("/")
            for s in existing
            if isinstance(s, dict)
        }
        existing_ids = {
            s.get("id") for s in existing if isinstance(s, dict) and isinstance(s.get("id"), int)
        }
        next_id = (max(existing_ids) + 1) if existing_ids else 1

        appended: list[dict[str, Any]] = []
        for cand in candidate_sources:
            norm = cand.url.strip().lower().rstrip("/")
            if norm in existing_urls:
                continue
            d = cand.model_dump(mode="json")
            # Preserve the registry id we showed Claude when it's free, so any
            # `Valued.sources` / `Signal.source_refs` Claude wrote against the
            # registry still align. Only renumber on collision with Claude's
            # own ids (which take precedence — Claude chose them first).
            if cand.id in existing_ids:
                # Skip any pre-reserved ids, then claim the next free one.
                while next_id in existing_ids:
                    next_id += 1
                d["id"] = next_id
                existing_ids.add(next_id)
                next_id += 1
            else:
                existing_ids.add(cand.id)
                next_id = max(next_id, cand.id + 1)
            appended.append(d)
            existing_urls.add(norm)

        if appended:
            merged_sources = list(existing) + appended
            sac = dict(tool_input.get("sources_and_confidence") or {})
            sac["sources"] = merged_sources
            # If Claude left coverage_summary blank, give it a sane default.
            if not sac.get("coverage_summary"):
                sac["coverage_summary"] = (
                    f"Backfilled {len(appended)} of {len(merged_sources)} "
                    "sources from Exa + Parallel citations."
                )
            tool_input["sources_and_confidence"] = sac

            await emit(
                run_id, "sources_backfilled",
                f"Backfilled {len(appended)} source(s) from candidate registry "
                f"(Claude returned {len(existing)}, final total {len(merged_sources)}).",
                level="info",
                meta={
                    "stage": 3,
                    "claude_sources": len(existing),
                    "backfilled": len(appended),
                    "final_total": len(merged_sources),
                },
            )

    return tool_input, total_cost


# ── Stage 4: persistence ─────────────────────────────────────────────────────


async def _stage4_persist(
    run_id: uuid.UUID,
    p: ResearchParams,
    card: CompanyCardV1,
    factory: async_sessionmaker[AsyncSession],
) -> tuple[uuid.UUID, uuid.UUID]:
    """Upsert Company, insert Card + Signals + Sources, point canonical FK."""
    ident = card.company_identity
    domain = _normalize_domain(ident.domain or ident.website or p.domain_hint)
    company_name = ident.company_name or p.company_name

    today = date.today().isoformat()
    card.created_date = card.created_date or today
    card.last_updated_date = today

    async with factory() as s:
        # Upsert Company (by run-id pin first, then by domain, then create).
        company: Company | None = None
        if p.company_id:
            company = await s.get(Company, p.company_id)
        if company is None and domain:
            company = (
                await s.execute(select(Company).where(Company.domain == domain))
            ).scalars().first()
        if company is None:
            company = Company(
                domain=domain,
                company_name=company_name,
                legal_entity_name=ident.legal_entity_name,
                website=ident.website,
                logo_url=ident.logo_url,
                industry=card.classification.industry,
                category=card.classification.category,
                status=ident.status,
                headquarters_country=_extract_country(ident.headquarters),
            )
            s.add(company)
            await s.flush()  # populate company.id
        else:
            # Refresh denormalized columns from this new card.
            company.company_name = company_name
            company.domain = domain or company.domain
            company.website = ident.website or company.website
            company.logo_url = ident.logo_url or company.logo_url
            company.industry = card.classification.industry or company.industry
            company.category = card.classification.category or company.category
            company.status = ident.status or company.status
            company.headquarters_country = (
                _extract_country(ident.headquarters) or company.headquarters_country
            )

        # Insert Card. Set card_id on the model so it serializes into the JSONB.
        card_row = Card(
            company_id=company.id,
            run_id=run_id,
            schema_version=card.schema_version,
            card={},  # filled below after we know card_row.id
            score_overall=card.scores.overall,
            score_growth=card.scores.growth,
            score_momentum=card.scores.momentum,
            score_fundraising=card.scores.fundraising_likelihood,
            score_acquisition=card.scores.acquisition_likelihood,
            score_partnership_fit=card.scores.partnership_fit,
            score_strategic_fit=card.scores.strategic_fit,
            score_risk=card.scores.risk,
            review_status="draft",
        )
        s.add(card_row)
        await s.flush()
        card.card_id = str(card_row.id)
        card_row.card = card.model_dump(mode="json")

        # Point the company at its new canonical card.
        company.canonical_card_id = card_row.id

        # Insert sources + build local_id → uuid lookup (UI-friendly)
        for src in card.sources_and_confidence.sources:
            s.add(
                Source(
                    company_id=company.id,
                    card_id=card_row.id,
                    local_id=src.id,
                    url=src.url,
                    title=src.title,
                    type=src.type,
                    trust_tier=src.trust_tier,
                    date_published=_safe_date(src.date_published),
                    date_found=_safe_date(src.date_found) or date.today(),
                    last_checked=_safe_date(src.last_checked) or date.today(),
                    snippet=src.snippet,
                    freshness_score=src.freshness_score,
                )
            )

        # Insert signals
        for sig in card.signals:
            s.add(
                Signal(
                    company_id=company.id,
                    card_id=card_row.id,
                    type=sig.type,
                    subtype=sig.subtype,
                    headline=sig.headline or "",
                    evidence=sig.evidence,
                    weight=int(sig.weight or 5),
                    signal_date=_safe_date(sig.date),
                    source_refs=sig.sources or [],
                )
            )

        await s.commit()
        return company.id, card_row.id


# ── DB helpers ───────────────────────────────────────────────────────────────


async def _update_run(
    factory: async_sessionmaker[AsyncSession],
    run_id: uuid.UUID,
    *,
    status: str | None = None,
    progress: int | None = None,
    started: bool = False,
    completed: bool = False,
    error: str | None = None,
    company_id: uuid.UUID | None = None,
    card_id: uuid.UUID | None = None,
    engine_outputs: dict[str, Any] | None = None,
) -> None:
    async with factory() as s:
        run = await s.get(Run, run_id)
        if run is None:
            return
        # Cancellation lock: once a run is cancelled, the background asyncio
        # task may still be churning through Parallel/Exa/Claude (we have no
        # cancel token plumbed through those calls). Refuse all further DB
        # writes against this run so we don't flip the row back to
        # researching/synthesizing/completed and don't attach a fresh
        # company_id / card_id to a row the user explicitly cancelled.
        if run.status == "cancelled":
            return
        if status:
            run.status = status
        if progress is not None:
            run.progress_pct = progress
        if started and run.started_at is None:
            run.started_at = datetime.now(timezone.utc)
        if completed:
            run.completed_at = datetime.now(timezone.utc)
        if error is not None:
            run.error = error
        if company_id is not None:
            run.company_id = company_id
        if card_id is not None:
            run.card_id = card_id
        if engine_outputs is not None:
            run.engine_outputs = {**(run.engine_outputs or {}), **engine_outputs}
        await s.commit()


# ── Utils ────────────────────────────────────────────────────────────────────


def _normalize_domain(s: str | None) -> str | None:
    if not s:
        return None
    s = s.strip().lower()
    if "://" in s:
        s = urlparse(s).netloc or s
    s = s.split("/")[0]
    if s.startswith("www."):
        s = s[4:]
    return s or None


def _extract_country(hq: str | None) -> str | None:
    if not hq:
        return None
    # crude: last comma-separated token
    parts = [p.strip() for p in hq.split(",") if p.strip()]
    return parts[-1] if parts else None


def _safe_date(v: Any) -> date | None:
    if v is None:
        return None
    if isinstance(v, date):
        return v
    s = str(v).strip()
    if not s:
        return None
    try:
        return date.fromisoformat(s[:10])
    except ValueError:
        return None


_VALID_CONFIDENCE = {"confirmed", "estimated", "inferred", "unknown"}

# Mirror of schemas.blocks.SignalType. Kept inline to avoid import cycles;
# if you add a new SignalType, add it here too.
_VALID_SIGNAL_TYPES = {
    "growth", "fundraising", "acquisition", "partnership", "risk", "strategic",
}
# Loose remap for the common Claude mis-emissions we see in the wild. Anything
# not in this map AND not in _VALID_SIGNAL_TYPES gets the signal dropped (we
# would rather lose one bad row than fail the whole run on enum validation).
_SIGNAL_TYPE_ALIASES = {
    "product": "growth",
    "product_launch": "growth",
    "launch": "growth",
    "hiring": "growth",
    "team": "growth",
    "press": "growth",
    "marketing": "growth",
    "traction": "growth",
    "review": "risk",
    "reviews": "risk",
    "sentiment": "risk",
    "regulatory": "risk",
    "compliance": "risk",
    "funding": "fundraising",
    "raise": "fundraising",
    "round": "fundraising",
    "ma": "acquisition",
    "m&a": "acquisition",
    "exit": "acquisition",
    "distribution": "partnership",
    "channel": "partnership",
    "founder": "strategic",
    "leadership": "strategic",
    "positioning": "strategic",
    "category": "strategic",
}


def _sanitize_card_dict(d: Any) -> Any:
    """Best-effort fix-up for common Claude mistakes before pydantic validation.

    Walks the synth output looking for `Valued` shapes (dict with a 'confidence'
    key) and:
      - if value is non-null but confidence='unknown' → flip to 'inferred' so
        we keep the value (Claude clearly meant something), and stamp a basis;
      - if confidence is 'estimated'/'inferred' but basis missing → add a
        boilerplate basis so the validator passes;
      - normalizes weird confidence strings (e.g. "Confirmed", "high") to a
        valid enum value.

    Also prunes/remaps `signals[].type` against the SignalType enum so a single
    bad row doesn't detonate the whole Pydantic validation pass. Bad rows are
    dropped (the retry-on-thin path will fire if we fall below the floor).
    """
    if isinstance(d, dict):
        # Signal type sanitization — runs before recursion so the child dicts
        # we recurse into are already normalized.
        sigs = d.get("signals")
        if isinstance(sigs, list):
            cleaned: list[Any] = []
            for s in sigs:
                if not isinstance(s, dict):
                    continue
                t_raw = s.get("type")
                t = (
                    t_raw.lower().strip().replace("-", "_").replace(" ", "_")
                    if isinstance(t_raw, str) else ""
                )
                if t in _VALID_SIGNAL_TYPES:
                    s["type"] = t
                    cleaned.append(s)
                elif t in _SIGNAL_TYPE_ALIASES:
                    s["type"] = _SIGNAL_TYPE_ALIASES[t]
                    cleaned.append(s)
                # else: silently drop — retry path will catch it
            d["signals"] = cleaned
        if "confidence" in d:
            conf_raw = d.get("confidence")
            conf = (
                conf_raw.lower().strip() if isinstance(conf_raw, str) else "unknown"
            )
            if conf not in _VALID_CONFIDENCE:
                # crude bucketing for "high"/"low"/"medium" etc
                if conf in ("high", "verified", "known"):
                    conf = "confirmed"
                elif conf in ("medium", "moderate", "likely"):
                    conf = "estimated"
                elif conf in ("low", "guess", "speculative"):
                    conf = "inferred"
                else:
                    conf = "unknown"
            value = d.get("value")
            basis = (d.get("basis") or "").strip() if isinstance(d.get("basis"), str) else ""
            srcs_present = bool(d.get("sources"))
            # Preserve evidence integrity: if the model said "unknown" but
            # left a value, only keep the value when it also gave us *some*
            # justification (basis text or a source ref). Otherwise drop the
            # value — honest > wrong.
            if value is not None and conf == "unknown":
                if basis or srcs_present:
                    conf = "confirmed" if srcs_present else "inferred"
                else:
                    d["value"] = None
            # `confirmed` claims no sources: Claude over-claimed.
            #   - if a basis exists → downgrade to `inferred` (we have reasoning,
            #     just no citation, which is exactly what inferred means).
            #   - if no basis either → drop to `unknown` and null the value.
            #     Honest > wrong.
            if conf == "confirmed" and not srcs_present:
                if basis:
                    conf = "inferred"
                else:
                    conf = "unknown"
                    d["value"] = None
            # `estimated`/`inferred` with no basis at all → previously we dropped
            # the value. Keep that behavior, but only when sources are also
            # missing. If Claude cited sources but skipped the rationale, stamp
            # a minimal basis pointing at those sources so we don't lose the
            # value over a missing one-liner.
            if conf in ("estimated", "inferred") and not basis:
                if srcs_present:
                    d["basis"] = "Derived from cited sources."
                else:
                    conf = "unknown"
                    d["value"] = None
            d["confidence"] = conf
            # Normalize sources to ints
            srcs = d.get("sources")
            if isinstance(srcs, list):
                d["sources"] = [s for s in (
                    int(x) if isinstance(x, (int, str)) and str(x).isdigit() else None
                    for x in srcs
                ) if s is not None]
        for k, v in list(d.items()):
            d[k] = _sanitize_card_dict(v)
        return d
    if isinstance(d, list):
        return [_sanitize_card_dict(x) for x in d]
    return d


def _coerce_valued_paths(card_dict: Any, ve: ValidationError) -> int:
    """Recover from "expected Valued[X], got scalar" by wrapping the offending
    paths in-place.

    Claude occasionally flattens a `Valued[str]` field — say
    `business_model.business_model_summary` — into a bare string instead of
    `{"value": "...", "confidence": "...", "basis": "..."}`. Rather than nuke a
    14-minute, $3 research run over a JSON shape mismatch, we walk each
    `model_type` error in `ve`, navigate to its loc in `card_dict`, and if the
    leaf value is a bare scalar (str/int/float/bool), wrap it into a Valued
    shape. Returns the number of paths we successfully patched.
    """
    patched = 0
    for err in ve.errors():
        if err.get("type") != "model_type":
            continue
        loc = err.get("loc") or ()
        if not loc:
            continue
        # Walk to the parent of the leaf.
        parent: Any = card_dict
        try:
            for key in loc[:-1]:
                parent = parent[key] if isinstance(key, str) else parent[key]
        except (KeyError, IndexError, TypeError):
            continue
        leaf_key = loc[-1]
        if not isinstance(parent, (dict, list)):
            continue
        try:
            current = parent[leaf_key]
        except (KeyError, IndexError, TypeError):
            continue
        if isinstance(current, dict):
            # Already a dict — different problem, leave it.
            continue
        if current is None:
            continue
        # Wrap scalars into Valued[X]. Strings get basis text; numbers/bools
        # become confirmed values without basis (the validator will accept
        # `confirmed` only if a source is cited, so we go with `inferred` and
        # a stamped basis so it passes regardless).
        wrapped = {
            "value": current,
            "confidence": "inferred",
            "basis": "Synthesizer emitted a bare value; auto-wrapped to satisfy Valued[] contract.",
            "sources": [],
        }
        try:
            parent[leaf_key] = wrapped
            patched += 1
        except (TypeError, IndexError):
            continue
    return patched


def _short_err(ve: ValidationError) -> str:
    errs = ve.errors()[:3]
    return "; ".join(
        f"{'.'.join(str(x) for x in e['loc'])}: {e['msg']}" for e in errs
    )
