"""Helper for persisting an EngineCall row.

Engine clients return cost + latency in their response dataclasses; this
helper writes one row per call to the `engine_calls` table so we can run
cost analytics (sum per run, p95 latency per vendor, error rate per op).

We also persist the full request + response payloads (truncated) so a
post-mortem on any bad run can replay exactly what we sent and what came
back, without re-hitting the vendor.

Kept separate from the clients so cost logging is opt-in by the caller —
the clients themselves stay free of DB coupling (easier to test, reusable
in CLI / scripts).
"""
from __future__ import annotations

import json
import logging
import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.engines.claude_client import ClaudeResponse
from app.engines.diffbot_client import DiffbotEnhanceResponse
from app.engines.exa_client import ExaCallStats, ExaContent
from app.engines.parallel_client import ParallelTaskResponse
from app.models.engine_call import EngineCall

logger = logging.getLogger(__name__)


# Cap each JSONB payload so a runaway response can't blow up a row. 100KB is
# generous: the full CompanyCardV1 tool output is typically 30-50KB.
_PAYLOAD_CHAR_CAP = 100_000


def _truncate_payload(p: Any) -> Any:
    """Best-effort cap: if the serialized payload exceeds the cap, replace with
    a sentinel string carrying head+length so callers can still inspect."""
    if p is None:
        return None
    try:
        s = json.dumps(p, ensure_ascii=False, default=str)
    except Exception:
        return {"_log_error": "unserializable_payload"}
    if len(s) <= _PAYLOAD_CHAR_CAP:
        return p
    return {
        "_truncated": True,
        "_original_chars": len(s),
        "_head": s[:_PAYLOAD_CHAR_CAP],
    }


async def log_exa_call(
    session: AsyncSession,
    stats: ExaCallStats,
    *,
    run_id: uuid.UUID | None = None,
    meta: dict[str, Any] | None = None,
    request_payload: dict[str, Any] | None = None,
    response_payload: dict[str, Any] | None = None,
    commit: bool = True,
) -> EngineCall:
    row = EngineCall(
        run_id=run_id,
        vendor="exa",
        operation=stats.operation,
        units=stats.units,
        cost_usd=stats.cost_usd,
        latency_ms=stats.latency_ms,
        status=stats.status,
        error=stats.error,
        meta=meta or {},
        request_payload=_truncate_payload(request_payload),
        response_payload=_truncate_payload(response_payload),
    )
    session.add(row)
    if commit:
        await session.commit()
    return row


async def log_claude_call(
    session: AsyncSession,
    resp: ClaudeResponse,
    *,
    operation: str,
    run_id: uuid.UUID | None = None,
    meta: dict[str, Any] | None = None,
    request_payload: dict[str, Any] | None = None,
    response_payload: dict[str, Any] | None = None,
    commit: bool = True,
) -> EngineCall:
    # Default to the snapshot captured by claude_client itself.
    req = request_payload if request_payload is not None else resp.request_payload
    rsp = response_payload if response_payload is not None else resp.response_payload
    row = EngineCall(
        run_id=run_id,
        vendor="anthropic",
        operation=operation,
        model=resp.model,
        units=1,
        input_tokens=resp.input_tokens,
        output_tokens=resp.output_tokens,
        cost_usd=resp.cost_usd,
        latency_ms=resp.latency_ms,
        status=resp.status,
        error=resp.error,
        meta=meta or {},
        request_payload=_truncate_payload(req),
        response_payload=_truncate_payload(rsp),
    )
    session.add(row)
    if commit:
        await session.commit()
    return row


async def log_diffbot_call(
    session: AsyncSession,
    resp: DiffbotEnhanceResponse,
    *,
    operation: str = "enhance",
    run_id: uuid.UUID | None = None,
    meta: dict[str, Any] | None = None,
    request_payload: dict[str, Any] | None = None,
    response_payload: dict[str, Any] | None = None,
    commit: bool = True,
) -> EngineCall:
    """Persist one Diffbot call to engine_calls.

    Defaults: `request_payload` = the sanitized params snapshot (no token);
    `response_payload` = the full Diffbot body (truncated downstream).
    Match score + hits land in `meta` so post-hoc cost queries can filter
    high-confidence hits without parsing the JSONB body.
    """
    req = request_payload if request_payload is not None else resp.request_params
    rsp = response_payload if response_payload is not None else resp.response_body
    row = EngineCall(
        run_id=run_id,
        vendor="diffbot",
        operation=operation,
        units=1,
        cost_usd=resp.cost_usd,
        latency_ms=resp.latency_ms,
        status=resp.status,
        error=resp.error,
        meta={
            **(meta or {}),
            "score": resp.score,
            "esscore": resp.esscore,
            "hits": resp.hits,
            "has_entity": resp.entity is not None,
            "kg_version": resp.kg_version,
        },
        request_payload=_truncate_payload(req),
        response_payload=_truncate_payload(rsp),
    )
    session.add(row)
    if commit:
        await session.commit()
    return row


async def log_parallel_call(
    session: AsyncSession,
    resp: ParallelTaskResponse,
    *,
    operation: str = "task_run",
    run_id: uuid.UUID | None = None,
    meta: dict[str, Any] | None = None,
    request_payload: dict[str, Any] | None = None,
    response_payload: dict[str, Any] | None = None,
    commit: bool = True,
) -> EngineCall:
    status = "ok" if resp.succeeded else ("timeout" if resp.status == "timeout" else "error")
    # Default response payload = the structured output_json + citations.
    rsp = response_payload if response_payload is not None else {
        "status": resp.status,
        "output_json": resp.output_json,
        "citations": resp.citations,
    }
    row = EngineCall(
        run_id=run_id,
        vendor="parallel",
        operation=operation,
        processor=resp.processor,
        units=1,
        cost_usd=resp.cost_usd,
        latency_ms=resp.latency_ms,
        status=status,
        error=resp.error,
        meta={**(meta or {}), "parallel_run_id": resp.run_id},
        request_payload=_truncate_payload(request_payload),
        response_payload=_truncate_payload(rsp),
    )
    session.add(row)
    if commit:
        await session.commit()
    return row
