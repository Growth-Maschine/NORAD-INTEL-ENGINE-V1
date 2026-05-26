"""App-level settings service.

Stores global research-engine config in the `app_kv` table under key
`research_config`. Falls back to compiled-in defaults when the row is absent
so a fresh install boots without any pre-seed step.

Schema (the JSON shape stored under `app_kv.value`):

    {
      "parallel": {
        "processor": "pro" | "core" | "ultra" | ...,
        "timeout_s": 600
      },
      "exa": {
        "search_type": "deep" | "auto" | "fast" | "neural" | "keyword",
        "deep_model":  "deep-reasoning" | "deep" | "deep-lite",
        "num_results": 10
      },
      "diffbot": {
        "enabled": true,
        "score_threshold": 0.0
      }
    }

Backward compat: older rows that predate `diffbot` still validate — Pydantic
fills in the default block, so the API always returns a fully-populated
ResearchConfig regardless of what's persisted.
"""
from __future__ import annotations

import asyncio
import time
from typing import Any

from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.app_kv import AppKV

_KEY = "research_config"

# Valid enum values — keep in lockstep with vendor APIs.
PARALLEL_PROCESSORS = ("lite", "base", "core", "pro", "ultra", "ultra2x", "ultra4x", "ultra8x")
EXA_SEARCH_TYPES = ("auto", "fast", "neural", "keyword", "deep")
EXA_DEEP_MODELS = ("deep-lite", "deep", "deep-reasoning")


class ParallelConfig(BaseModel):
    processor: str = "pro"
    timeout_s: int = Field(default=600, ge=30, le=3600)


class ExaConfig(BaseModel):
    search_type: str = "deep"
    deep_model: str = "deep-reasoning"
    num_results: int = Field(default=10, ge=1, le=50)


class DiffbotConfig(BaseModel):
    """Diffbot Knowledge Graph (Enhance) toggles.

    `enabled` is the master kill-switch — when False, Stage 2 must skip the
    Diffbot call entirely (wiring lands in Step 3 of the plan).

    `score_threshold` is the per-call match-confidence cutoff in [0.0, 1.0].
    Default `0.0` = no gating: every hit is forwarded to the synthesizer with
    its score attached, matching the "let Claude weigh it" decision in PLAN.md.
    Raising it lets the operator suppress weak matches without code changes.
    """

    enabled: bool = True
    score_threshold: float = Field(default=0.0, ge=0.0, le=1.0)


class ResearchConfig(BaseModel):
    parallel: ParallelConfig = Field(default_factory=ParallelConfig)
    exa: ExaConfig = Field(default_factory=ExaConfig)
    diffbot: DiffbotConfig = Field(default_factory=DiffbotConfig)


_DEFAULTS = ResearchConfig()

# Tiny in-process cache so hot research paths don't hit the DB per call.
# Settings change rarely; a 30s TTL is plenty for "did the user just save?".
_CACHE: dict[str, Any] = {"value": None, "ts": 0.0}
_CACHE_TTL_S = 30.0
_CACHE_LOCK = asyncio.Lock()


def _validate(value: dict[str, Any]) -> ResearchConfig:
    """Coerce a stored dict into a ResearchConfig, falling back per-block.

    If the user persisted a partial config (e.g. just `parallel`) we still
    want `exa` to inherit defaults — Pydantic's default_factory handles that.
    Unknown enum values fall back to defaults (with a log message later if
    we want one) rather than 500ing the API.
    """
    cfg = ResearchConfig.model_validate(value or {})
    if cfg.parallel.processor not in PARALLEL_PROCESSORS:
        cfg.parallel.processor = _DEFAULTS.parallel.processor
    if cfg.exa.search_type not in EXA_SEARCH_TYPES:
        cfg.exa.search_type = _DEFAULTS.exa.search_type
    if cfg.exa.deep_model not in EXA_DEEP_MODELS:
        cfg.exa.deep_model = _DEFAULTS.exa.deep_model
    return cfg


async def get_research_config(session: AsyncSession) -> ResearchConfig:
    """Return current config from DB, with cache + default fallback."""
    now = time.monotonic()
    if _CACHE["value"] is not None and (now - _CACHE["ts"]) < _CACHE_TTL_S:
        return _CACHE["value"]

    async with _CACHE_LOCK:
        # Re-check under lock (avoid stampede).
        if _CACHE["value"] is not None and (time.monotonic() - _CACHE["ts"]) < _CACHE_TTL_S:
            return _CACHE["value"]

        row = await session.scalar(select(AppKV).where(AppKV.key == _KEY))
        if row is None:
            cfg = _DEFAULTS
        else:
            cfg = _validate(row.value)
        _CACHE["value"] = cfg
        _CACHE["ts"] = time.monotonic()
        return cfg


async def update_research_config(
    session: AsyncSession, partial: dict[str, Any]
) -> ResearchConfig:
    """Merge `partial` into the stored config and return the new value.

    Partial-merge semantics: top-level keys (`parallel`, `exa`) are deep-merged
    so the caller can PATCH just one engine without nuking the other.

    Concurrency: we take a row-level lock (`SELECT ... FOR UPDATE`) on the
    `app_kv` row before the read-merge-write so simultaneous PUTs serialize
    instead of last-writer-wins overwriting each other.
    """
    # Read-with-lock from the live row (not cache) so the merge sees the
    # latest committed state. If the row doesn't exist yet we just merge
    # onto defaults.
    row = await session.scalar(
        select(AppKV).where(AppKV.key == _KEY).with_for_update()
    )
    current_value: dict[str, Any] = row.value if row is not None else _DEFAULTS.model_dump()

    merged: dict[str, Any] = dict(current_value)
    for k, v in (partial or {}).items():
        if isinstance(v, dict) and isinstance(merged.get(k), dict):
            merged[k] = {**merged[k], **v}
        else:
            merged[k] = v
    cfg = _validate(merged)

    stmt = (
        pg_insert(AppKV)
        .values(key=_KEY, value=cfg.model_dump())
        .on_conflict_do_update(
            index_elements=[AppKV.key],
            set_={"value": cfg.model_dump()},
        )
    )
    await session.execute(stmt)
    await session.commit()

    _CACHE["value"] = cfg
    _CACHE["ts"] = time.monotonic()
    return cfg


def invalidate_cache() -> None:
    """Force the next `get_research_config` call to re-read from DB."""
    _CACHE["value"] = None
    _CACHE["ts"] = 0.0
