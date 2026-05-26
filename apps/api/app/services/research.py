"""Research engine — the heart of NORAD.

For one chosen company, this service runs the full Company-Card synthesis:

    Stage 1  build_input            — read trend_article context (if any),
                                       normalize company name + domain hint
    Stage 2  fan_out (gather)       — Parallel + Exa + Diffbot KG run together.
                                       When `domain_hint` is known up front all
                                       three fan out concurrently; otherwise
                                       Parallel + Exa fire in parallel, we wait
                                       for Exa, derive a likely domain from its
                                       URLs, then call Diffbot with that hint
                                       (or name-only if Exa was empty). Any one
                                       engine failing never kills the run.
    Stage 3  synthesize             — Claude Sonnet merges Parallel brief + Exa
                                       snippets + Diffbot KG entity into one
                                       validated CompanyCardV1 via tool_use.
                                       Diffbot origin URLs are eligible for
                                       `confidence="confirmed"` cites.
    Stage 4  persist                — upsert Company → insert Card → backfill
                                       Signals + Sources → flip Run to completed,
                                       point Company.canonical_card_id at the
                                       fresh card

Cost shape (default config: Parallel `pro` + Exa `deep` + Diffbot KG + Sonnet 4.5):
    Parallel pro       ≈ $2.50  / run  (flat per task, processor=pro)
    Exa deep search    ≈ $0.01  / run  (2 deep searches @ $0.005 ea)
    Exa get_contents   ≈ $0.025 / run  (~5 URLs @ $0.005 ea)
    Diffbot Enhance    ≈ $0.00  / run  (plan-bundled — see _pricing.diffbot_*)
    Claude Sonnet 4.5  ≈ $0.30-0.50 / run  (varies with parallel JSON size)
    ─────────────────────────────────────────────────────
    ≈ $2.80 - $3.10 / company

Switching Parallel back to `core` ($1.00) drops total to ≈ $1.30 / company.
Configurable from /settings (persisted in app_kv research_config).

Notes on robustness:
    * Each engine independently catches its own errors; a half-result still
      produces a card (with `confidence="unknown"` on the missing blocks).
      Only an all-three-failed Stage 2 kills the run.
    * Pydantic validation is the contract. If the synthesizer returns garbage,
      the run is failed with a `synthesis_failed` event — no orphan card.
    * Tier-C fields are auto-stubbed by `CompanyCardV1` defaults — the engines
      are not asked to fill them (the trimmed contract schema excludes them).
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
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
from app.engines import (
    get_claude_client,
    get_diffbot_client,
    get_exa_client,
    get_parallel_client,
)
from app.engines.claude_client import ClaudeMessage
from app.engines.diffbot_client import DiffbotEnhanceResponse
from app.engines.exa_client import ExaCallStats, ExaContent
from app.engines.logging import (
    log_claude_call,
    log_diffbot_call,
    log_exa_call,
    log_parallel_call,
)
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

        # ── Stage 2: fan-out (Parallel + Exa + Diffbot) ───────────────────
        # Branched sequencing per Diffbot integration plan:
        #   * domain_hint known up front → fan out all three concurrently
        #     (Parallel ‖ Exa ‖ Diffbot[url=domain_hint])
        #   * no domain_hint → start Parallel + Exa concurrently, await Exa,
        #     derive a likely domain from its URLs, then fire Diffbot with
        #     that hint. Falls back to name-only Diffbot if Exa yielded
        #     nothing usable. Parallel keeps running through all of this and
        #     is awaited at the end.
        if p.domain_hint:
            await emit(
                run_id, "stage_started",
                f"Stage 2 — Parallel + Exa + Diffbot (domain={p.domain_hint!r}, fan-out)",
                meta={"stage": 2, "diffbot_mode": "fan_out", "domain_hint": p.domain_hint},
            )
            parallel_resp, exa_bundle, diffbot_resp = await asyncio.gather(
                _stage2_parallel(run_id, p, article_ctx, factory, cfg),
                _stage2_exa(run_id, p, factory, cfg),
                _stage2_diffbot(run_id, p, factory, cfg, url_hint=p.domain_hint),
                return_exceptions=False,  # each inner fn never raises
            )
            derived_domain: str | None = None
        else:
            await emit(
                run_id, "stage_started",
                "Stage 2 — Parallel + Exa first, Diffbot after Exa-derived domain",
                meta={"stage": 2, "diffbot_mode": "sequential", "domain_hint": None},
            )
            # Start Parallel as a background task — it can run for 5-10 minutes
            # under the `pro` processor, so we don't want to block on it just
            # to feed Diffbot a domain hint.
            parallel_task = asyncio.create_task(
                _stage2_parallel(run_id, p, article_ctx, factory, cfg)
            )
            try:
                exa_bundle = await _stage2_exa(run_id, p, factory, cfg)
                derived_domain = _derive_domain_from_exa(exa_bundle, p.company_name)
                if derived_domain:
                    await emit(
                        run_id, "diffbot_domain_derived",
                        f"Derived domain {derived_domain!r} from Exa results.",
                        meta={"stage": 2, "derived_domain": derived_domain},
                    )
                diffbot_resp = await _stage2_diffbot(
                    run_id, p, factory, cfg, url_hint=derived_domain
                )
                parallel_resp = await parallel_task
            except BaseException:
                # Make sure Parallel doesn't keep running detached if we
                # bail out before awaiting it. (asyncio.create_task pins it
                # to the loop; cancellation is best-effort.)
                if not parallel_task.done():
                    parallel_task.cancel()
                raise
        total_cost += (
            parallel_resp.cost_usd + exa_bundle.cost_usd + diffbot_resp.cost_usd
        )

        parallel_ok = parallel_resp.succeeded and isinstance(
            parallel_resp.output_json, dict
        )
        exa_ok = bool(exa_bundle.contents)
        diffbot_ok = diffbot_resp.succeeded  # gated entity record
        if not parallel_ok and not exa_ok and not diffbot_ok:
            raise RuntimeError(
                "all engines failed: "
                f"parallel={parallel_resp.error}; exa=no contents; "
                f"diffbot={diffbot_resp.error or 'no entity'}"
            )

        await _update_run(factory, run_id, progress=55, status="synthesizing")
        await emit(
            run_id, "stage_completed",
            f"Stage 2 — Parallel {'OK' if parallel_ok else 'FAIL'} "
            f"(${parallel_resp.cost_usd:.3f}), Exa {len(exa_bundle.contents)} reads "
            f"(${exa_bundle.cost_usd:.3f}), Diffbot "
            f"{'HIT' if diffbot_ok else 'MISS'} (score={diffbot_resp.score:.2f})",
            meta={
                "stage": 2,
                "parallel_ok": parallel_ok,
                "exa_reads": len(exa_bundle.contents),
                "parallel_cost": parallel_resp.cost_usd,
                "exa_cost": exa_bundle.cost_usd,
                "diffbot_ok": diffbot_ok,
                "diffbot_score": diffbot_resp.score,
                "diffbot_hits": diffbot_resp.hits,
                "diffbot_cost": diffbot_resp.cost_usd,
            },
        )

        # ── Stage 3: Claude synthesizer ───────────────────────────────────
        await emit(
            run_id, "stage_started",
            "Stage 3 — Claude Sonnet synthesizing CompanyCardV1",
            meta={"stage": 3},
        )
        card_dict, claude_cost = await _stage3_synthesize(
            run_id, p, article_ctx, parallel_resp, exa_bundle, diffbot_resp, factory, cfg
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
                    {
                        "url": c.url,
                        "title": c.title,
                        "chars": len(c.text or ""),
                        "text_preview": (c.text or "")[:2000] or None,
                        "published_date": c.published_date,
                    }
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


# ── Stage 2c: Diffbot Knowledge Graph ────────────────────────────────────────

# Hosts that are NEVER useful as a derived "this is the company's domain"
# signal — they're aggregators / press / social, not the org itself.
# Used by `_derive_domain_from_exa()`.
_DOMAIN_DERIVE_BLOCKLIST = {
    "linkedin.com", "twitter.com", "x.com", "facebook.com", "youtube.com",
    "instagram.com", "tiktok.com", "github.com", "medium.com",
    "crunchbase.com", "pitchbook.com", "tracxn.com", "owler.com",
    "wikipedia.org", "wikidata.org",
    "techcrunch.com", "bloomberg.com", "reuters.com", "wsj.com",
    "ft.com", "forbes.com", "businesswire.com", "prnewswire.com",
    "nytimes.com", "theinformation.com", "axios.com", "venturebeat.com",
    "trendhunter.com", "producthunt.com",
    "google.com", "bing.com", "duckduckgo.com",
}


def _derive_domain_from_exa(
    exa_bundle: "_ExaBundle",
    company_name: str,
) -> str | None:
    """Pick a likely company domain from Exa's fetched URLs.

    Heuristic, in order:
      1. Most-frequent non-blocklisted host across the Exa contents. Ties
         broken by URL ordering (preserves Exa's relevance ranking).
      2. If the top host contains the company-name slug (lowercased,
         alphanumeric only), prefer it strongly — that's almost certainly
         the homepage.
    Returns `None` if Exa returned nothing usable; the caller should fall
    back to name-only Diffbot in that case.
    """
    if not exa_bundle.contents:
        return None

    slug = "".join(c.lower() for c in company_name if c.isalnum())
    counts: dict[str, int] = {}
    name_match: str | None = None
    for c in exa_bundle.contents:
        if not c.url:
            continue
        try:
            host = urlparse(c.url).netloc.lower()
        except Exception:
            continue
        if host.startswith("www."):
            host = host[4:]
        if not host or "." not in host:
            continue
        # Strip aggregators / press — these mention the company, they aren't it.
        if any(host == h or host.endswith("." + h) for h in _DOMAIN_DERIVE_BLOCKLIST):
            continue
        counts[host] = counts.get(host, 0) + 1
        # Strong signal: host's bare-name segment contains the company slug
        # (e.g. company "Stripe" + host "stripe.com" → instant win).
        if name_match is None and slug and len(slug) >= 3:
            bare = host.split(".")[0]
            if slug in bare or bare in slug:
                name_match = host

    if name_match:
        return name_match
    if not counts:
        return None
    # Most-frequent wins; preserves first-seen order on ties (insertion order).
    return max(counts.items(), key=lambda kv: kv[1])[0]


async def _stage2_diffbot(
    run_id: uuid.UUID,
    p: ResearchParams,
    factory: async_sessionmaker[AsyncSession],
    cfg: "ResearchConfig",
    *,
    url_hint: str | None = None,
) -> DiffbotEnhanceResponse:
    """Call Diffbot KG Enhance for `p.company_name`, with `url_hint` if known.

    `url_hint` should be a bare domain (e.g. "stripe.com") — pass either
    `p.domain_hint` (when known up front), the result of
    `_derive_domain_from_exa()` (when Exa filled it in), or None to let
    Diffbot do a name-only lookup.

    Behavior:
      * Master kill-switch: when `cfg.diffbot.enabled` is False, returns a
        synthetic `status='ok'` / `hits=0` / `entity=None` response without
        touching the network or writing to `engine_calls`. The synthesizer
        treats this exactly like a Diffbot miss.
      * Emits `diffbot_lookup_started` and `diffbot_lookup_completed`
        run_events with score/hits/has_entity in `meta` so the SSE feed
        surfaces what happened on the timeline.
      * Never raises — failures fold into the response object (status='error'
        or 'timeout') so the orchestrator keeps moving.
      * Always logs the call to `engine_calls` (unless gated off).
    """
    if not cfg.diffbot.enabled:
        await emit(
            run_id, "diffbot_lookup_skipped",
            "Diffbot disabled in settings — skipping KG lookup.",
            level="info",
            meta={"stage": 2, "reason": "disabled_in_settings"},
        )
        return DiffbotEnhanceResponse(status="ok", hits=0)

    await emit(
        run_id, "diffbot_lookup_started",
        f"Diffbot KG: looking up {p.company_name!r}"
        + (f" (url={url_hint})" if url_hint else " (name-only)"),
        meta={
            "stage": 2,
            "company_name": p.company_name,
            "url_hint": url_hint,
        },
    )

    client = get_diffbot_client()
    resp = await client.enhance_organization(
        name=p.company_name,
        url=url_hint,
    )

    async with factory() as s:
        await log_diffbot_call(
            s, resp, operation="enhance", run_id=run_id,
            meta={"company_name": p.company_name},
        )

    # Optional score gate (kept here, not in the synthesizer prompt, so the
    # default of `0.0` is a pure no-op). If the operator raised the threshold
    # in /settings and Diffbot's match score sits below it, treat the call as
    # a miss for synthesis purposes — we still keep the engine_calls row above
    # for auditing.
    score_ok = resp.score >= cfg.diffbot.score_threshold
    suppressed_below_threshold = bool(
        resp.succeeded and not score_ok and cfg.diffbot.score_threshold > 0.0
    )
    effective_succeeded = resp.succeeded and score_ok

    await emit(
        run_id, "diffbot_lookup_completed",
        (
            f"Diffbot {'HIT' if effective_succeeded else 'MISS'} — "
            f"score={resp.score:.2f}, hits={resp.hits}, "
            f"latency={resp.latency_ms:.0f}ms"
            + (f" (below threshold {cfg.diffbot.score_threshold:.2f})"
               if suppressed_below_threshold else "")
        ),
        level="warn" if resp.status != "ok" else "info",
        meta={
            "stage": 2,
            "score": resp.score,
            "hits": resp.hits,
            "has_entity": resp.entity is not None,
            "status": resp.status,
            "latency_ms": resp.latency_ms,
            "score_threshold": cfg.diffbot.score_threshold,
            "below_threshold": suppressed_below_threshold,
        },
    )

    # If we suppressed below threshold, return an effective-miss response so
    # downstream synthesis treats it like Diffbot had nothing for us.
    if suppressed_below_threshold:
        return DiffbotEnhanceResponse(
            status="ok",
            hits=0,
            kg_version=resp.kg_version,
            cost_usd=resp.cost_usd,
            latency_ms=resp.latency_ms,
            request_params=resp.request_params,
        )
    return resp


# ── Stage 3: Claude synthesizer ──────────────────────────────────────────────


_SYNTH_SYSTEM = """You are the NORAD research synthesizer.

Your job: produce ONE high-quality CompanyCardV1 JSON describing the target \
company, by merging THREE evidence streams:

1. PARALLEL — a COMPACT evidence brief (identity, funding, signals, sources) \
returned by an agentic web-research engine. This is NOT the full CompanyCardV1 \
contract — it's pre-vetted candidate facts you must verify against Exa \
snippets and expand into the richer card schema (products_and_skus, \
people_and_decision_map, strategic_fit, scores, etc.).
2. EXA — raw text snippets from 3-8 web pages we crawled in real time. Use \
these to add detail, attribute sources, and override Parallel where Exa \
disagrees clearly.
3. DIFFBOT KG — a pre-structured Organization record from Diffbot's knowledge \
graph (~150 fields: founders, employees, funding, competitors, categories, \
HQ, etc.) PLUS a `score` between 0 and 1 indicating Diffbot's confidence \
that the entity it matched is actually the target company. Each Diffbot \
fact carries one or more **origin URLs** — the pages Diffbot crawled to \
extract that fact. Treat Diffbot origin URLs as first-party provenance: \
facts cited to those origins are eligible for `confidence="confirmed"`. \
Diffbot may be empty (`Diffbot MISS`) — in that case ignore this stream. \
When Diffbot disagrees with Parallel/Exa on a fact, weigh Diffbot more \
heavily as `score` approaches 1.0, less heavily as it approaches 0.5, and \
prefer Exa below that. Never assume Diffbot's match is correct just because \
it returned a hit — cross-check identity (domain, HQ, founder names) before \
trusting its facts.

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


# How many Diffbot origin URLs to surface in the candidate registry. Diffbot
# entities can carry dozens of origins; we cap to keep the prompt token-bounded.
_DIFFBOT_MAX_ORIGINS = 6
# How many Diffbot competitors to list in the evidence block (66 for Stripe
# in our smoke test — synthesizer prompt would balloon if we sent them all).
_DIFFBOT_MAX_COMPETITORS = 10


def _diffbot_origin_urls(entity: dict[str, Any] | None) -> list[str]:
    """Pull origin URLs from a Diffbot entity record.

    Diffbot exposes origins under a few different keys depending on the
    KG version and entity type. We try them in order of specificity:
      - `origins` (plural list of URLs)
      - `origin` (sometimes a single URL string)
      - `allUris` (catch-all uri list incl. wiki/crunchbase/etc.)
      - `homepageUri` (last resort — the company's own homepage)
    Returns a deduped, order-preserving list capped at `_DIFFBOT_MAX_ORIGINS`.
    """
    if not isinstance(entity, dict):
        return []
    out: list[str] = []
    seen: set[str] = set()

    def _push(u: Any) -> None:
        if not isinstance(u, str):
            return
        u = u.strip()
        if not u or not (u.startswith("http://") or u.startswith("https://")):
            return
        norm = u.lower().rstrip("/")
        if norm in seen:
            return
        seen.add(norm)
        out.append(u)

    origins = entity.get("origins") or entity.get("allOriginHashes") or []
    if isinstance(origins, list):
        for o in origins:
            _push(o)
    _push(entity.get("origin"))
    all_uris = entity.get("allUris") or []
    if isinstance(all_uris, list):
        for u in all_uris:
            _push(u)
    _push(entity.get("homepageUri"))
    return out[:_DIFFBOT_MAX_ORIGINS]


def _render_diffbot_evidence(resp: DiffbotEnhanceResponse) -> str:
    """Render a compact, Claude-readable summary of a Diffbot entity.

    We deliberately do NOT json-dump the raw entity — it's ~150 fields, many
    of them nested arrays (competitors at 66 entries for Stripe in our smoke
    test). Instead we pick the high-signal ones and label them so the
    synthesizer can map them directly onto CompanyCardV1 fields.

    Always safe to call: on miss / disabled / error, returns a single-line
    explanation rather than failing — the user message includes the block
    unconditionally so prompt structure stays stable across runs.
    """
    if resp.status == "timeout":
        return "(Diffbot lookup timed out — no KG evidence available)"
    if resp.status == "error":
        return f"(Diffbot lookup errored: {resp.error or 'unknown'} — no KG evidence available)"
    if not resp.succeeded:
        return (
            f"(Diffbot MISS — no entity matched. score={resp.score:.2f}, "
            f"hits={resp.hits}. Skip this stream.)"
        )

    e = resp.entity or {}
    lines: list[str] = [
        f"Match score: {resp.score:.2f} (hits={resp.hits})",
    ]

    def _add(label: str, value: Any) -> None:
        if value in (None, "", [], {}):
            return
        if isinstance(value, list):
            value = ", ".join(str(v) for v in value if v not in (None, ""))
            if not value:
                return
        lines.append(f"  {label}: {value}")

    _add("Name", e.get("name") or e.get("fullName"))
    _add("Aka", e.get("nameAlt"))
    desc = e.get("description") or ""
    if isinstance(desc, str) and desc:
        _add("Description", desc[:600])
    _add("Homepage", e.get("homepageUri"))
    _add("HQ", _fmt_address(e.get("address")) or e.get("location", {}).get("address") if isinstance(e.get("location"), dict) else None)
    _add("Founded", _fmt_field_str(e.get("foundingDate")))
    _add("Is public", e.get("isPublic"))
    _add("Stock symbol", _fmt_field_str(e.get("stock")))
    _add("Employees", _fmt_field_int(e.get("nbEmployees")) or e.get("nbEmployeesMax") or e.get("nbEmployeesMin"))
    founders = e.get("founders") or []
    if isinstance(founders, list):
        names = [f.get("name") for f in founders if isinstance(f, dict) and f.get("name")]
        if names:
            _add("Founders", names[:6])
    ceo = e.get("ceo")
    if isinstance(ceo, dict):
        _add("CEO", ceo.get("name"))
    elif isinstance(ceo, str):
        _add("CEO", ceo)
    industries = e.get("industries") or []
    if isinstance(industries, list):
        names = [i.get("name") if isinstance(i, dict) else i for i in industries]
        _add("Industries", [n for n in names if n][:6])
    categories = e.get("categories") or []
    if isinstance(categories, list):
        names = [c.get("name") if isinstance(c, dict) else c for c in categories]
        _add("Categories", [n for n in names if n][:6])
    parent = e.get("parentCompany")
    if isinstance(parent, dict):
        _add("Parent", parent.get("name"))
    competitors = e.get("competitors") or []
    if isinstance(competitors, list):
        names = [c.get("name") if isinstance(c, dict) else c for c in competitors]
        names = [n for n in names if n][:_DIFFBOT_MAX_COMPETITORS]
        if names:
            _add(f"Competitors (top {_DIFFBOT_MAX_COMPETITORS})", names)
    funding = e.get("investments") or []
    if isinstance(funding, list) and funding:
        # Just count + most recent if shape is known.
        _add("Funding rounds (count)", len(funding))
    _add("Wikipedia", e.get("wikipediaUri"))
    _add("Crunchbase", e.get("crunchbaseUri"))
    _add("LinkedIn", e.get("linkedInUri"))

    origins = _diffbot_origin_urls(e)
    if origins:
        lines.append(
            f"  Diffbot origins ({len(origins)} URLs — first-party "
            "provenance, eligible for confidence=confirmed):"
        )
        for u in origins:
            lines.append(f"    - {u}")

    return "\n".join(lines)


def _fmt_field_str(v: Any) -> str | None:
    """Diffbot often wraps scalars as `{value: ..., precision: ..., str: ...}`."""
    if isinstance(v, dict):
        return v.get("str") or v.get("value") or None
    if isinstance(v, str):
        return v or None
    return None


def _fmt_field_int(v: Any) -> int | None:
    if isinstance(v, dict):
        val = v.get("value")
        if isinstance(val, (int, float)):
            return int(val)
    if isinstance(v, (int, float)):
        return int(v)
    return None


def _fmt_address(a: Any) -> str | None:
    if not isinstance(a, dict):
        return None
    parts = [
        a.get("street"),
        a.get("city"),
        a.get("region") or a.get("regionName"),
        a.get("country") or a.get("countryName"),
    ]
    s = ", ".join(p for p in parts if p)
    return s or None


def _unwrap_parallel_output(
    output: dict[str, Any] | None,
) -> tuple[dict[str, Any], list[Any]]:
    """Parallel Task API v2 wraps the schema in `{type, basis, content}`."""
    if not isinstance(output, dict):
        return {}, []
    content = output.get("content")
    basis = output.get("basis") or []
    if isinstance(content, dict):
        return content, basis if isinstance(basis, list) else []
    return output, basis if isinstance(basis, list) else []


_NAME_STOPWORDS = frozenset({
    "therapeutics", "health", "healthcare", "wellness", "labs", "lab",
    "inc", "corp", "corporation", "company", "co", "group", "holdings",
    "the", "and", "for",
})


def _normalize_domain(d: str | None) -> str | None:
    if not d or not isinstance(d, str):
        return None
    d = d.strip().lower()
    if d.startswith("http"):
        d = urlparse(d).netloc or d
    d = d.removeprefix("www.")
    return d.split("/")[0] or None


def _name_tokens(name: str) -> set[str]:
    return {
        t for t in re.sub(r"[^a-z0-9]+", " ", name.lower()).split()
        if len(t) >= 3 and t not in _NAME_STOPWORDS
    }


def _names_likely_match(query: str, entity_name: str) -> bool:
    qa = _name_tokens(query)
    eb = _name_tokens(entity_name)
    if not qa or not eb:
        return False
    return bool(qa & eb)


def _diffbot_entity_trusted(
    resp: DiffbotEnhanceResponse,
    *,
    company_name: str,
    domain_hint: str | None,
    score_threshold: float,
) -> bool:
    """Gate Diffbot→card promotion so a wrong KG match (e.g. Miror vs Mirador)
    never overwrites a good Parallel/Exa synthesis."""
    if not resp.succeeded or not resp.entity:
        return False
    e = resp.entity
    hint = _normalize_domain(domain_hint)
    homepage = _normalize_domain(e.get("homepageUri"))
    if hint and homepage:
        if hint == homepage or hint in homepage or homepage in hint:
            return True
        hint_root = hint.split(".")[0]
        home_root = homepage.split(".")[0]
        if len(hint_root) >= 4 and hint_root == home_root:
            return True
    db_name = str(e.get("name") or e.get("fullName") or "")
    if _names_likely_match(company_name, db_name):
        return resp.score >= score_threshold
    return resp.score >= max(score_threshold, 0.92)


def _ensure_block(tool_input: dict[str, Any], key: str) -> dict[str, Any]:
    block = tool_input.get(key)
    if not isinstance(block, dict):
        block = {}
        tool_input[key] = block
    return block


def _plain_missing(v: Any) -> bool:
    if v is None or v == "" or v == "unknown":
        return True
    if isinstance(v, list) and len(v) == 0:
        return True
    return False


def _valued_missing(v: Any) -> bool:
    if not isinstance(v, dict):
        return True
    val = v.get("value")
    conf = v.get("confidence")
    if val in (None, "", [], {}):
        return True
    if conf in (None, "unknown"):
        return True
    return False


def _confirmed_valued(
    value: Any,
    basis: str,
    source_ids: list[int] | None = None,
) -> dict[str, Any]:
    out: dict[str, Any] = {
        "value": value,
        "confidence": "confirmed",
        "basis": basis,
    }
    if source_ids:
        out["sources"] = source_ids
    return out


def _parse_founded_year(v: Any) -> int | None:
    s = _fmt_field_str(v)
    if not s:
        return None
    if s.startswith("d"):
        s = s[1:]
    m = re.match(r"(\d{4})", s)
    return int(m.group(1)) if m else None


def _parse_founded_date(v: Any) -> str | None:
    s = _fmt_field_str(v)
    if not s:
        return None
    if s.startswith("d"):
        s = s[1:]
    m = re.match(r"(\d{4}-\d{2}-\d{2})", s)
    return m.group(1) if m else None


def _diffbot_source_ids(
    tool_input: dict[str, Any],
    entity: dict[str, Any],
) -> list[int]:
    url_map = _url_to_source_id_map(tool_input)
    ids: list[int] = []
    for u in _diffbot_origin_urls(entity):
        norm = u.strip().lower().rstrip("/")
        sid = url_map.get(norm)
        if sid is not None and sid not in ids:
            ids.append(sid)
    return ids[:4]


def _promote_diffbot_fields_into_card(
    tool_input: dict[str, Any],
    diffbot_resp: DiffbotEnhanceResponse,
    *,
    company_name: str,
    domain_hint: str | None,
    score_threshold: float,
) -> tuple[dict[str, Any], int]:
    if not _diffbot_entity_trusted(
        diffbot_resp,
        company_name=company_name,
        domain_hint=domain_hint,
        score_threshold=score_threshold,
    ):
        return tool_input, 0

    e = diffbot_resp.entity or {}
    promoted = 0
    src_ids = _diffbot_source_ids(tool_input, e)
    basis = f"Diffbot Knowledge Graph (match score {diffbot_resp.score:.2f})."

    identity = _ensure_block(tool_input, "company_identity")
    if _plain_missing(identity.get("description")):
        desc = e.get("description")
        if isinstance(desc, str) and desc.strip():
            identity["description"] = desc.strip()
            promoted += 1
    if _plain_missing(identity.get("headquarters")):
        hq = _fmt_address(e.get("address"))
        if not hq and isinstance(e.get("location"), dict):
            hq = e["location"].get("address")
        if hq:
            identity["headquarters"] = hq
            promoted += 1
    if _plain_missing(identity.get("founded_year")):
        yr = _parse_founded_year(e.get("foundingDate"))
        if yr:
            identity["founded_year"] = yr
            promoted += 1
    if _plain_missing(identity.get("founded_date")):
        fd = _parse_founded_date(e.get("foundingDate"))
        if fd:
            identity["founded_date"] = fd
            promoted += 1
    homepage = e.get("homepageUri")
    if isinstance(homepage, str) and homepage.strip():
        dom = _normalize_domain(homepage)
        if _plain_missing(identity.get("website")):
            identity["website"] = (
                homepage if homepage.startswith("http") else f"https://{homepage}"
            )
            promoted += 1
        if dom and _plain_missing(identity.get("domain")):
            identity["domain"] = dom
            promoted += 1
    if _plain_missing(identity.get("company_linkedin")):
        li = e.get("linkedInUri")
        if isinstance(li, str) and li.strip():
            identity["company_linkedin"] = li.strip()
            promoted += 1
    if identity.get("status") in (None, "", "unknown"):
        if e.get("isPublic") is True:
            identity["status"] = "public"
            promoted += 1
        elif e.get("isPublic") is False:
            identity["status"] = "private"
            promoted += 1

    social = identity.get("social_handles")
    if not isinstance(social, dict):
        social = {}
        identity["social_handles"] = social
    for key, field in (
        ("linkedin", "linkedInUri"),
        ("twitter", "twitterUri"),
        ("facebook", "facebookUri"),
        ("instagram", "instagramUri"),
        ("youtube", "youtubeUri"),
    ):
        if _plain_missing(social.get(key)):
            val = e.get(field)
            if isinstance(val, str) and val.strip():
                social[key] = val.strip()
                promoted += 1

    people = _ensure_block(tool_input, "people_and_decision_map")
    if not people.get("ceo"):
        ceo_raw = e.get("ceo")
        if isinstance(ceo_raw, dict) and ceo_raw.get("name"):
            people["ceo"] = {
                "name": ceo_raw["name"],
                "title": ceo_raw.get("title") or "CEO",
                "linkedin_url": ceo_raw.get("linkedInUri"),
                "sources": src_ids,
            }
            promoted += 1
    if not people.get("founders"):
        founders: list[dict[str, Any]] = []
        for f in e.get("founders") or []:
            if isinstance(f, dict) and f.get("name"):
                founders.append({
                    "name": f["name"],
                    "title": f.get("title"),
                    "linkedin_url": f.get("linkedInUri"),
                    "is_founder": True,
                    "sources": src_ids,
                })
        if founders:
            people["founders"] = founders
            promoted += 1
    if not people.get("executives"):
        execs: list[dict[str, Any]] = []
        for x in e.get("executives") or e.get("boardMembers") or []:
            if isinstance(x, dict) and x.get("name"):
                execs.append({
                    "name": x["name"],
                    "title": x.get("title"),
                    "linkedin_url": x.get("linkedInUri"),
                    "sources": src_ids,
                })
        if execs:
            people["executives"] = execs[:12]
            promoted += 1

    traction = _ensure_block(tool_input, "traction_and_momentum")
    if _valued_missing(traction.get("employee_count_estimate")):
        emp = (
            _fmt_field_int(e.get("nbEmployees"))
            or _fmt_field_int(e.get("nbEmployeesMax"))
            or _fmt_field_int(e.get("nbEmployeesMin"))
        )
        if emp:
            traction["employee_count_estimate"] = _confirmed_valued(
                emp, basis, src_ids
            )
            promoted += 1

    classification = _ensure_block(tool_input, "classification")
    if _plain_missing(classification.get("industry")):
        industries = e.get("industries") or []
        if isinstance(industries, list):
            for i in industries:
                name = i.get("name") if isinstance(i, dict) else i
                if isinstance(name, str) and name.strip():
                    classification["industry"] = name.strip()
                    promoted += 1
                    break

    market = _ensure_block(tool_input, "market_and_competitors")
    if not market.get("direct_competitors"):
        comps: list[str] = []
        for c in e.get("competitors") or []:
            if isinstance(c, dict) and c.get("name"):
                comps.append(str(c["name"]))
            elif isinstance(c, str):
                comps.append(c)
        if comps:
            market["direct_competitors"] = comps[:_DIFFBOT_MAX_COMPETITORS]
            promoted += 1

    return tool_input, promoted


def _promote_parallel_brief_fields_into_card(
    tool_input: dict[str, Any],
    parallel_output: dict[str, Any] | None,
) -> tuple[dict[str, Any], int]:
    """Fill obvious gaps from Parallel's research brief (same-company stream)."""
    brief, _ = _unwrap_parallel_output(parallel_output)
    if not brief:
        return tool_input, 0

    promoted = 0
    basis = "Parallel web research brief (deterministic backfill)."

    identity = _ensure_block(tool_input, "company_identity")
    if _plain_missing(identity.get("description")) and brief.get("summary"):
        identity["description"] = str(brief["summary"]).strip()
        promoted += 1
    for key, src in (
        ("legal_entity_name", "legal_entity_name"),
        ("website", "website"),
        ("domain", "domain"),
        ("headquarters", "headquarters"),
    ):
        if _plain_missing(identity.get(key)) and brief.get(src):
            identity[key] = brief[src]
            promoted += 1
    if _plain_missing(identity.get("founded_year")) and brief.get("founded_year"):
        identity["founded_year"] = brief["founded_year"]
        promoted += 1

    classification = _ensure_block(tool_input, "classification")
    for key in ("industry", "category", "business_type"):
        if _plain_missing(classification.get(key)) and brief.get(key):
            classification[key] = brief[key]
            promoted += 1

    products_block = _ensure_block(tool_input, "products_and_skus")
    if not products_block.get("products"):
        raw = brief.get("products") or []
        products = [
            {"name": p, "hero": i == 0}
            for i, p in enumerate(raw)
            if isinstance(p, str) and p.strip()
        ]
        if products:
            products_block["products"] = products
            promoted += 1
    if not products_block.get("product_categories") and brief.get("products"):
        cats = [p for p in brief.get("products") or [] if isinstance(p, str)]
        if cats:
            products_block["product_categories"] = cats[:8]
            promoted += 1

    market = _ensure_block(tool_input, "market_and_competitors")
    if not market.get("direct_competitors") and brief.get("competitors"):
        market["direct_competitors"] = [
            c for c in brief["competitors"] if isinstance(c, str)
        ]
        promoted += 1
    if _valued_missing(market.get("competitive_advantage")) and brief.get(
        "competitive_advantage"
    ):
        market["competitive_advantage"] = _confirmed_valued(
            brief["competitive_advantage"], basis
        )
        promoted += 1

    biz = _ensure_block(tool_input, "business_model")
    if _valued_missing(biz.get("business_model_summary")) and brief.get("summary"):
        biz["business_model_summary"] = _confirmed_valued(brief["summary"], basis)
        promoted += 1

    people = _ensure_block(tool_input, "people_and_decision_map")
    if not people.get("ceo") and brief.get("ceo"):
        people["ceo"] = {"name": str(brief["ceo"]), "title": "CEO"}
        promoted += 1
    if not people.get("founders") and brief.get("founders"):
        people["founders"] = [
            {"name": n, "is_founder": True}
            for n in brief["founders"]
            if isinstance(n, str) and n.strip()
        ]
        promoted += 1

    traction = _ensure_block(tool_input, "traction_and_momentum")
    if _valued_missing(traction.get("employee_count_estimate")):
        emp = brief.get("employee_count_estimate")
        if isinstance(emp, int) and emp > 0:
            traction["employee_count_estimate"] = _confirmed_valued(emp, basis)
            promoted += 1
    if _valued_missing(traction.get("hiring_pace")) and brief.get("hiring_pace"):
        traction["hiring_pace"] = _confirmed_valued(brief["hiring_pace"], basis)
        promoted += 1

    funding = _ensure_block(tool_input, "funding_and_investors")
    if _plain_missing(funding.get("last_round_type")) and brief.get("last_round_type"):
        funding["last_round_type"] = brief["last_round_type"]
        promoted += 1
    if _plain_missing(funding.get("last_round_date")) and brief.get("last_round_date"):
        funding["last_round_date"] = brief["last_round_date"]
        promoted += 1
    if not funding.get("known_investors") and brief.get("investors"):
        funding["known_investors"] = [
            i for i in brief["investors"] if isinstance(i, str)
        ]
        promoted += 1

    return tool_input, promoted


def _build_candidate_sources(
    exa_contents: list[ExaContent],
    parallel_output: dict[str, Any] | None,
    parallel_citations: list[dict[str, Any]] | None = None,
    diffbot_resp: DiffbotEnhanceResponse | None = None,
    max_total: int = 14,
) -> list[SourceSchema]:
    """Numbered registry of URLs we already fetched / Parallel + Diffbot cited.

    Order of precedence (richer evidence first):
      1. Exa contents — we have full text, freshest evidence
      2. Diffbot origin URLs — KG-vetted first-party provenance per fact
      3. Parallel top-level `citations[]`
      4. Parallel `basis[].citations[]` — per-field provenance
      5. Parallel flat `sources[]` if present
    Dedup by normalized URL. Returns at most `max_total` entries with stable
    integer ids 1..N. Bumped from 12 to 14 to make room for the Diffbot
    origins without crowding out Exa/Parallel.
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

    # Pass 2: Diffbot origin URLs (KG-vetted first-party provenance). We use
    # a labelled snippet so Claude can recognize these as Diffbot-attributed
    # in the registry, which makes them eligible for confidence=confirmed.
    if diffbot_resp is not None and diffbot_resp.succeeded:
        diffbot_score = diffbot_resp.score
        for u in _diffbot_origin_urls(diffbot_resp.entity):
            label = f"Diffbot origin (match score {diffbot_score:.2f})"
            if _add(u, None, label):
                return out

    # Pass 3: top-level Parallel citations (most reliable shape).
    for cit in parallel_citations or []:
        excerpts = cit.get("excerpts") or []
        snippet = excerpts[0] if excerpts else cit.get("snippet")
        if _add(cit.get("url") or "", cit.get("title"), snippet):
            return out

    # Pass 4: Parallel `basis[].citations[]` (per-field provenance — what
    # `pro` processor historically returns).
    for basis_item in (parallel_output or {}).get("basis", []) or []:
        for cit in basis_item.get("citations", []) or []:
            excerpts = cit.get("excerpts") or []
            snippet = excerpts[0] if excerpts else None
            if _add(cit.get("url") or "", cit.get("title"), snippet):
                return out

    # Pass 5: flat `sources[]` on the unwrapped Parallel brief.
    brief, _ = _unwrap_parallel_output(parallel_output)
    for src in brief.get("sources") or []:
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


def _dedupe_claude_source_ids(
    tool_input: dict[str, Any],
) -> tuple[dict[str, Any], dict[int, int]]:
    """Renumber duplicate source ids and remap signal refs. Returns id_remap."""
    sac_existing = tool_input.get("sources_and_confidence") or {}
    raw_existing_sources = sac_existing.get("sources") or []
    id_remap: dict[int, int] = {}
    seen_ids: set[int] = set()
    if not raw_existing_sources:
        return tool_input, id_remap

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
            id_remap[sid] = next_free
            seen_ids.add(next_free)
            next_free += 1
        else:
            seen_ids.add(sid)

    if id_remap:
        for sig in tool_input.get("signals") or []:
            if not isinstance(sig, dict):
                continue
            refs = sig.get("source_refs") or sig.get("sources") or []
            if isinstance(refs, list):
                key = "source_refs" if "source_refs" in sig else "sources"
                sig[key] = [
                    id_remap.get(r, r) if isinstance(r, int) else r for r in refs
                ]
    return tool_input, id_remap


def _merge_candidate_sources_into_card(
    tool_input: dict[str, Any],
    candidate_sources: list[SourceSchema],
) -> tuple[dict[str, Any], int]:
    """Append registry URLs Claude omitted. Returns count appended."""
    if not candidate_sources:
        return tool_input, 0

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
        if cand.id in existing_ids:
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

    if not appended:
        return tool_input, 0

    merged_sources = list(existing) + appended
    sac = dict(tool_input.get("sources_and_confidence") or {})
    sac["sources"] = merged_sources
    if not sac.get("coverage_summary"):
        sac["coverage_summary"] = (
            f"Backfilled {len(appended)} of {len(merged_sources)} "
            "sources from Exa + Parallel + Diffbot citations."
        )
    tool_input["sources_and_confidence"] = sac
    return tool_input, len(appended)


def _url_to_source_id_map(tool_input: dict[str, Any]) -> dict[str, int]:
    out: dict[str, int] = {}
    for s in (tool_input.get("sources_and_confidence") or {}).get("sources") or []:
        if not isinstance(s, dict):
            continue
        url = s.get("url")
        sid = s.get("id")
        if isinstance(url, str) and isinstance(sid, int):
            norm = url.strip().lower().rstrip("/")
            out[norm] = sid
    return out


def _map_parallel_signal_type(raw: Any) -> str | None:
    if not isinstance(raw, str):
        return None
    t = raw.lower().strip().replace("-", "_").replace(" ", "_")
    if t in _VALID_SIGNAL_TYPES:
        return t
    return _SIGNAL_TYPE_ALIASES.get(t)


def _harvest_parallel_signals_if_thin(
    tool_input: dict[str, Any],
    parallel_output: dict[str, Any] | None,
    *,
    min_signals: int = _SYNTH_MIN_SIGNALS,
) -> tuple[dict[str, Any], int]:
    """Promote Parallel's `signals[]` when Claude under-delivered on first pass."""
    existing = [s for s in (tool_input.get("signals") or []) if isinstance(s, dict)]
    if len(existing) >= min_signals:
        return tool_input, 0

    url_to_id = _url_to_source_id_map(tool_input)
    harvested: list[dict[str, Any]] = []
    seen_headlines: set[str] = {
        (s.get("headline") or "").strip().lower() for s in existing if s.get("headline")
    }

    brief, _ = _unwrap_parallel_output(parallel_output)
    for ps in brief.get("signals") or []:
        if not isinstance(ps, dict):
            continue
        headline = (ps.get("headline") or "").strip()
        if not headline:
            continue
        norm_headline = headline.lower()
        if norm_headline in seen_headlines:
            continue
        sig_type = _map_parallel_signal_type(ps.get("type"))
        if not sig_type:
            continue

        source_ids: list[int] = []
        for url in ps.get("source_urls") or []:
            if not isinstance(url, str):
                continue
            norm = url.strip().lower().rstrip("/")
            if norm in url_to_id:
                source_ids.append(url_to_id[norm])

        weight = ps.get("weight")
        if not isinstance(weight, int) or weight < 1 or weight > 10:
            weight = 5

        harvested.append({
            "type": sig_type,
            "headline": headline,
            "evidence": ps.get("evidence"),
            "date": ps.get("date"),
            "weight": weight,
            "sources": source_ids,
        })
        seen_headlines.add(norm_headline)
        if len(existing) + len(harvested) >= min_signals:
            break

    if not harvested:
        return tool_input, 0

    tool_input["signals"] = existing + harvested
    return tool_input, len(harvested)


async def _postprocess_synth_tool_input(
    run_id: uuid.UUID,
    tool_input: dict[str, Any],
    candidate_sources: list[SourceSchema],
    parallel_output: dict[str, Any] | None,
    *,
    diffbot_resp: DiffbotEnhanceResponse | None = None,
    company_name: str = "",
    domain_hint: str | None = None,
    diffbot_score_threshold: float = 0.0,
) -> dict[str, Any]:
    """Deterministic first-pass cleanup — no extra LLM cost."""
    tool_input, id_remap = _dedupe_claude_source_ids(tool_input)
    if id_remap:
        await emit(
            run_id, "sources_deduped",
            f"Renumbered {len(id_remap)} duplicate source id(s) from Claude.",
            level="warn",
            meta={"stage": 3, "remapped_count": len(id_remap)},
        )

    claude_sources_before = len(
        (tool_input.get("sources_and_confidence") or {}).get("sources") or []
    )
    tool_input, backfilled = _merge_candidate_sources_into_card(
        tool_input, candidate_sources
    )
    if backfilled:
        await emit(
            run_id, "sources_backfilled",
            f"Backfilled {backfilled} source(s) from candidate registry "
            f"(Claude returned {claude_sources_before}, "
            f"final total {claude_sources_before + backfilled}).",
            level="info",
            meta={
                "stage": 3,
                "claude_sources": claude_sources_before,
                "backfilled": backfilled,
                "final_total": claude_sources_before + backfilled,
            },
        )

    signals_before = len(tool_input.get("signals") or [])
    tool_input, harvested = _harvest_parallel_signals_if_thin(
        tool_input, parallel_output
    )
    if harvested:
        await emit(
            run_id, "signals_harvested",
            f"Harvested {harvested} signal(s) from Parallel brief "
            f"(Claude returned {signals_before}, now {signals_before + harvested}).",
            level="info",
            meta={
                "stage": 3,
                "claude_signals": signals_before,
                "harvested": harvested,
                "final_total": signals_before + harvested,
            },
        )

    tool_input, parallel_promoted = _promote_parallel_brief_fields_into_card(
        tool_input, parallel_output
    )
    if parallel_promoted:
        await emit(
            run_id, "parallel_fields_promoted",
            f"Backfilled {parallel_promoted} card field(s) from Parallel brief.",
            level="info",
            meta={"stage": 3, "promoted": parallel_promoted},
        )

    if diffbot_resp is not None:
        tool_input, diffbot_promoted = _promote_diffbot_fields_into_card(
            tool_input,
            diffbot_resp,
            company_name=company_name,
            domain_hint=domain_hint,
            score_threshold=diffbot_score_threshold,
        )
        if diffbot_promoted:
            await emit(
                run_id, "diffbot_fields_promoted",
                f"Backfilled {diffbot_promoted} card field(s) from Diffbot KG "
                f"(score={diffbot_resp.score:.2f}).",
                level="info",
                meta={
                    "stage": 3,
                    "promoted": diffbot_promoted,
                    "diffbot_score": diffbot_resp.score,
                },
            )

    return tool_input


async def _stage3_synthesize(
    run_id: uuid.UUID,
    p: ResearchParams,
    article_ctx: _ArticleContext | None,
    parallel_resp: ParallelTaskResponse,
    exa_bundle: _ExaBundle,
    diffbot_resp: DiffbotEnhanceResponse,
    factory: async_sessionmaker[AsyncSession],
    cfg: "ResearchConfig",
) -> tuple[dict[str, Any], float]:
    """Send Claude all three evidence streams + the contract schema as a tool spec.
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
        diffbot_resp=diffbot_resp,
    )
    candidate_block = _candidate_registry_block(candidate_sources)

    diffbot_evidence = _render_diffbot_evidence(diffbot_resp)

    user_msg = (
        f"TARGET COMPANY: {p.company_name}\n"
        f"DOMAIN HINT: {p.domain_hint or '(none)'}\n\n"
        f"{article_block}"
        f"CANDIDATE SOURCE REGISTRY ({len(candidate_sources)} verified URLs — "
        "fetched by Exa, cited by Parallel, or attached as Diffbot origins — "
        "cite by id, don't invent):\n"
        f"{candidate_block}\n\n"
        f"PARALLEL OUTPUT (pre-structured JSON):\n```json\n{parallel_json}\n```\n\n"
        f"EXA SNIPPETS ({len(exa_bundle.contents)} pages):\n{exa_block}\n\n"
        f"DIFFBOT KG EVIDENCE:\n{diffbot_evidence}\n\n"
        "PRE-FLIGHT (mandatory before calling the tool):\n"
        f"- `signals`: at least {_SYNTH_MIN_SIGNALS} entries. Parallel's `signals[]` "
        "block is pre-vetted — translate each into the card signal schema.\n"
        f"- `sources_and_confidence.sources`: at least {_SYNTH_MIN_SOURCES} entries "
        "from the CANDIDATE SOURCE REGISTRY above (preserve the exact ids shown).\n\n"
        "Produce the final CompanyCardV1 via the synthesize_company_card tool. "
        "Your `sources_and_confidence.sources` array MUST include the registry "
        "entries (preserving their ids) plus any extra Parallel-cited URLs you "
        "want to attribute. When citing a Diffbot-attributed fact, point the "
        "Valued field's `sources` at the corresponding Diffbot-origin id from "
        "the registry — those origins are first-party and eligible for "
        "`confidence=\"confirmed\"`."
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

    # ── Deterministic post-process (free — fixes the common failure mode where
    # Claude fills identity blocks but omits sources[] / under-populates
    # signals[] even though Parallel + the registry already have them).
    tool_input = await _postprocess_synth_tool_input(
        run_id,
        tool_input,
        candidate_sources,
        parallel_resp.output_json,
        diffbot_resp=diffbot_resp,
        company_name=p.company_name,
        domain_hint=p.domain_hint,
        diffbot_score_threshold=cfg.diffbot.score_threshold,
    )

    signals = tool_input.get("signals") or []
    sources = (
        (tool_input.get("sources_and_confidence") or {}).get("sources") or []
    )

    # ── Retry-on-thin (worst case only): signals still below floor after
    # harvest. Never burn a second LLM pass for missing sources — the
    # registry backfill above handles that deterministically.
    if len(signals) < _SYNTH_MIN_SIGNALS:
        await emit(
            run_id, "synthesis_retry",
            f"Synth returned thin signals ({len(signals)}<{_SYNTH_MIN_SIGNALS}) "
            "after registry backfill + Parallel harvest; requesting expansion.",
            level="warn",
            meta={
                "stage": 3,
                "signals_returned": len(signals),
                "sources_returned": len(sources),
                "min_signals": _SYNTH_MIN_SIGNALS,
                "min_sources": _SYNTH_MIN_SOURCES,
                "reason": "signals_below_floor",
            },
        )
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
                    f"That call returned only {len(signals)} signals, below the "
                    f"contract minimum of {_SYNTH_MIN_SIGNALS}. Sources are already "
                    f"covered ({len(sources)} in the card). Re-emit the FULL card "
                    "via the synthesize_company_card tool, keeping every good field "
                    f"you already produced and EXPANDING `signals` to at least "
                    f"{_SYNTH_MIN_SIGNALS}. Derive them from Parallel's signals[] "
                    "block, Exa snippets, and Diffbot KG evidence — see system "
                    "rules for valid types. Don't invent facts — surface what's "
                    "clearly present in the evidence."
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
                ti2 = await _postprocess_synth_tool_input(
                    run_id,
                    ti2,
                    candidate_sources,
                    parallel_resp.output_json,
                    diffbot_resp=diffbot_resp,
                    company_name=p.company_name,
                    domain_hint=p.domain_hint,
                    diffbot_score_threshold=cfg.diffbot.score_threshold,
                )
                new_signals = ti2.get("signals") or []
                # Accept retry only if strictly more signals (sources already
                # handled deterministically — don't regress signal count).
                if len(new_signals) > len(signals):
                    tool_input = ti2
                    signals = new_signals
        sources = (
            (tool_input.get("sources_and_confidence") or {}).get("sources") or []
        )
        await emit(
            run_id, "synthesis_retry_done",
            f"Retry produced signals={len(signals)}, sources={len(sources)}.",
            meta={
                "stage": 3,
                "signals_final": len(signals),
                "sources_final": len(sources),
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
