"""Parallel Web client — agentic research with structured output.

In NORAD, Parallel is one half of the **research engine** (the other half
being Exa-deep). Both fire at the same time on a chosen company; Parallel
does the open-ended web research, returning JSON that conforms to the
CompanyCardV1 contract schema.

The SDK shape varies across versions. We talk to the REST API directly via
`httpx` so we're not coupled to any specific `parallel-web` minor version.
Endpoint: POST /v1/tasks/runs, then poll GET /v1/tasks/runs/{id}.
Docs:     https://docs.parallel.ai/

Task lifecycle (simplified):
    submit  → run_id, status="queued"
    poll    → status in {queued, running, succeeded, failed, timeout}
    when status == "succeeded": result.output_json conforms to output_schema
"""
from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Any

import httpx

from app.core.config import get_settings
from app.engines._pricing import parallel_cost_usd

logger = logging.getLogger(__name__)

PARALLEL_BASE_URL = "https://api.parallel.ai"
DEFAULT_POLL_INTERVAL_S = 5.0
DEFAULT_TIMEOUT_S = 600.0  # 10 min — research can be slow


# ── Types ───────────────────────────────────────────────────────────────────


@dataclass(slots=True)
class ParallelTaskResponse:
    run_id: str
    status: str
    output_json: dict[str, Any] | None = None
    citations: list[dict[str, Any]] = field(default_factory=list)
    processor: str = "core"
    cost_usd: float = 0.0
    latency_ms: float = 0.0
    error: str | None = None

    @property
    def succeeded(self) -> bool:
        return self.status == "succeeded"


# ── Client ──────────────────────────────────────────────────────────────────


class ParallelClient:
    def __init__(self, api_key: str, base_url: str = PARALLEL_BASE_URL):
        if not api_key:
            raise RuntimeError("PARALLEL_API_KEY is not configured")
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")

    def _headers(self) -> dict[str, str]:
        return {
            "x-api-key": self._api_key,
            "content-type": "application/json",
        }

    async def submit_task(
        self,
        *,
        input_payload: dict[str, Any],
        output_schema: dict[str, Any],
        processor: str = "core",
        input_schema: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Create a task run and return the raw response."""
        # Parallel's API expects `output_schema` to be a tagged union with
        # discriminator `type="json"` (NOT "json_schema") and the schema body
        # nested under `json_schema`. Sending the raw schema yields a 422
        # "Field required: json_schema"; using type="json_schema" yields a
        # 422 literal_error "Input should be 'json'".
        body: dict[str, Any] = {
            "input": input_payload,
            "processor": processor,
            "task_spec": {
                "output_schema": {
                    "type": "json",
                    "json_schema": output_schema,
                },
            },
        }
        if input_schema:
            body["task_spec"]["input_schema"] = {
                "type": "json",
                "json_schema": input_schema,
            }
        if metadata:
            body["metadata"] = metadata

        # Explicit per-phase timeouts (connect/read/write/pool). A bare
        # `timeout=30.0` would apply 30s to each phase = ~120s worst case,
        # which lets a slow Parallel server stretch a single request well
        # past our outer wall-clock deadline. Tighter caps + an outer
        # asyncio.wait_for in run_to_completion guarantee a real deadline.
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(connect=10.0, read=20.0, write=10.0, pool=10.0),
        ) as client:
            resp = await client.post(
                f"{self._base_url}/v1/tasks/runs",
                json=body,
                headers=self._headers(),
            )
        resp.raise_for_status()
        return resp.json()

    async def fetch_run(self, run_id: str) -> dict[str, Any]:
        """Poll the current state of a run."""
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(connect=10.0, read=15.0, write=10.0, pool=10.0),
        ) as client:
            resp = await client.get(
                f"{self._base_url}/v1/tasks/runs/{run_id}",
                headers=self._headers(),
            )
        resp.raise_for_status()
        return resp.json()

    async def fetch_result(self, run_id: str) -> dict[str, Any]:
        """Fetch the structured result of a completed run."""
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(connect=10.0, read=20.0, write=10.0, pool=10.0),
        ) as client:
            resp = await client.get(
                f"{self._base_url}/v1/tasks/runs/{run_id}/result",
                headers=self._headers(),
            )
        resp.raise_for_status()
        return resp.json()

    async def run_to_completion(
        self,
        *,
        input_payload: dict[str, Any],
        output_schema: dict[str, Any],
        processor: str = "core",
        input_schema: dict[str, Any] | None = None,
        poll_interval_s: float = DEFAULT_POLL_INTERVAL_S,
        timeout_s: float = DEFAULT_TIMEOUT_S,
        metadata: dict[str, Any] | None = None,
    ) -> ParallelTaskResponse:
        """Submit + poll until terminal state or timeout.

        Best-effort: HTTP, decode, and shape errors are caught and folded into
        a `failed`/`timeout` ParallelTaskResponse with diagnostic `error` text.
        Truly unexpected exceptions (e.g. asyncio cancellation) propagate.

        Wall-clock bounded by an outer `asyncio.wait_for(timeout_s + 30)` so a
        hung Parallel API can't freeze the research pipeline — the inner
        deadline check still fires first under normal conditions; the outer
        cap is the hard backstop when an httpx await itself stalls.
        """
        t0 = time.perf_counter()
        try:
            return await asyncio.wait_for(
                self._run_to_completion_inner(
                    t0=t0,
                    input_payload=input_payload,
                    output_schema=output_schema,
                    processor=processor,
                    input_schema=input_schema,
                    poll_interval_s=poll_interval_s,
                    timeout_s=timeout_s,
                    metadata=metadata,
                ),
                timeout=timeout_s + 30.0,
            )
        except asyncio.TimeoutError:
            return ParallelTaskResponse(
                run_id="",
                status="timeout",
                processor=processor,
                cost_usd=0.0,
                latency_ms=_ms_since(t0),
                error=(
                    f"hard_timeout after {timeout_s + 30:.0f}s — outer wall-clock "
                    "tripped (Parallel API hung mid-poll)."
                ),
            )

    async def _run_to_completion_inner(
        self,
        *,
        t0: float,
        input_payload: dict[str, Any],
        output_schema: dict[str, Any],
        processor: str,
        input_schema: dict[str, Any] | None,
        poll_interval_s: float,
        timeout_s: float,
        metadata: dict[str, Any] | None,
    ) -> ParallelTaskResponse:
        try:
            submit = await self.submit_task(
                input_payload=input_payload,
                output_schema=output_schema,
                processor=processor,
                input_schema=input_schema,
                metadata=metadata,
            )
        except httpx.HTTPStatusError as exc:
            body = ""
            try:
                body = exc.response.text[:400]
            except Exception:
                pass
            return ParallelTaskResponse(
                run_id="",
                status="failed",
                processor=processor,
                latency_ms=_ms_since(t0),
                error=f"submit_failed: {exc} | body={body}",
            )
        except httpx.HTTPError as exc:
            return ParallelTaskResponse(
                run_id="",
                status="failed",
                processor=processor,
                latency_ms=_ms_since(t0),
                error=f"submit_failed: {exc}",
            )

        run_id = submit.get("run_id") or submit.get("id") or ""
        if not run_id:
            return ParallelTaskResponse(
                run_id="",
                status="failed",
                processor=processor,
                latency_ms=_ms_since(t0),
                error=f"submit_no_run_id: response={str(submit)[:300]}",
            )
        deadline = time.perf_counter() + timeout_s

        while True:
            try:
                state = await self.fetch_run(run_id)
            except httpx.HTTPStatusError as exc:
                body = ""
                try:
                    body = exc.response.text[:400]
                except Exception:
                    pass
                return ParallelTaskResponse(
                    run_id=run_id,
                    status="failed",
                    processor=processor,
                    latency_ms=_ms_since(t0),
                    error=f"poll_failed: {exc} | body={body}",
                )
            except httpx.HTTPError as exc:
                return ParallelTaskResponse(
                    run_id=run_id,
                    status="failed",
                    processor=processor,
                    latency_ms=_ms_since(t0),
                    error=f"poll_failed: {exc}",
                )
            except (ValueError, KeyError, TypeError) as exc:
                return ParallelTaskResponse(
                    run_id=run_id,
                    status="failed",
                    processor=processor,
                    latency_ms=_ms_since(t0),
                    error=f"poll_decode_failed: {type(exc).__name__}: {exc}",
                )
            status = state.get("status", "unknown")

            if status in ("succeeded", "completed"):
                try:
                    result = await self.fetch_result(run_id)
                except httpx.HTTPStatusError as exc:
                    body = ""
                    try:
                        body = exc.response.text[:400]
                    except Exception:
                        pass
                    return ParallelTaskResponse(
                        run_id=run_id,
                        status="failed",
                        processor=processor,
                        latency_ms=_ms_since(t0),
                        error=f"result_fetch_failed: {exc} | body={body}",
                    )
                except httpx.HTTPError as exc:
                    return ParallelTaskResponse(
                        run_id=run_id,
                        status="failed",
                        processor=processor,
                        latency_ms=_ms_since(t0),
                        error=f"result_fetch_failed: {exc}",
                    )
                return ParallelTaskResponse(
                    run_id=run_id,
                    status="succeeded",
                    output_json=result.get("output") or result.get("output_json"),
                    citations=result.get("citations") or [],
                    processor=processor,
                    cost_usd=parallel_cost_usd(processor),
                    latency_ms=_ms_since(t0),
                )
            if status in ("failed", "errored", "cancelled", "timeout"):
                return ParallelTaskResponse(
                    run_id=run_id,
                    status="failed",
                    processor=processor,
                    cost_usd=parallel_cost_usd(processor),
                    latency_ms=_ms_since(t0),
                    error=state.get("error") or f"terminal_status={status}",
                )
            if time.perf_counter() >= deadline:
                return ParallelTaskResponse(
                    run_id=run_id,
                    status="timeout",
                    processor=processor,
                    cost_usd=parallel_cost_usd(processor),
                    latency_ms=_ms_since(t0),
                    error=f"poll_timeout after {timeout_s}s",
                )
            await asyncio.sleep(poll_interval_s)

    async def smoke_check(self) -> dict[str, Any]:
        """Verify auth works without spawning a real (paid) task.

        Approach: GET a deliberately-invalid run id. If auth is good we get
        a 404 with a 'Invalid v1 task run id' message; if the key is wrong
        we get 401. Free, fast, and distinguishes auth from network errors.
        """
        t0 = time.perf_counter()
        probe_id = "00000000-0000-0000-0000-000000000000"
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(
                    f"{self._base_url}/v1/tasks/runs/{probe_id}",
                    headers=self._headers(),
                )
            # 404 = auth ok, just a missing resource (expected)
            # 401/403 = auth bad
            ok = resp.status_code == 404
            return {
                "ok": ok,
                "status_code": resp.status_code,
                "latency_ms": _ms_since(t0),
                "vendor": "parallel",
                **({"error": resp.text[:200]} if not ok else {}),
            }
        except Exception as exc:
            return {
                "ok": False,
                "latency_ms": _ms_since(t0),
                "error": f"{type(exc).__name__}: {exc}",
                "vendor": "parallel",
            }


def _ms_since(t0: float) -> float:
    return round((time.perf_counter() - t0) * 1000, 1)


# ── Singleton accessor ──────────────────────────────────────────────────────

_client: ParallelClient | None = None


def get_parallel_client() -> ParallelClient:
    global _client
    if _client is None:
        settings = get_settings()
        _client = ParallelClient(api_key=settings.parallel_api_key)
    return _client
