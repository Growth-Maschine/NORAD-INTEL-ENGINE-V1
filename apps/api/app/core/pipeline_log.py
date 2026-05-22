"""Structured file logger for both NORAD pipelines (research + discovery).

Why this exists
---------------
`engine_calls` captures per-vendor cost/latency/payloads. `run_events` captures
high-level state changes. Neither gives you a *single chronological tail* you
can `tail -f` while debugging.

This module writes one JSONL line per pipeline event to
`apps/api/logs/pipeline.jsonl` with rotation, so:
- `tail -f apps/api/logs/pipeline.jsonl | jq .` — live trace any run.
- `jq 'select(.run_id=="…")' apps/api/logs/pipeline.jsonl` — replay one run end to end.
- LLM I/O lands here too (truncated) when callers pass `meta={"request_payload":…, "response_payload":…}`.

Schema per line
---------------
    ts          ISO-8601 UTC
    pipeline    "research" | "discovery"
    stage       int | null (1..N)
    run_id      str | null
    kind        short slug ("run_started", "stage_completed", "synth_io", …)
    level       "info" | "warn" | "error"
    message     human one-liner
    meta        free-form dict
"""
from __future__ import annotations

import json
import logging
import logging.handlers
import os
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# ── Paths + rotation ────────────────────────────────────────────────────────

# Default log dir = <repo>/apps/api/logs regardless of cwd.
# pipeline_log.py lives at apps/api/app/core/pipeline_log.py → parents[2] = apps/api
_DEFAULT_LOG_DIR = Path(__file__).resolve().parents[2] / "logs"
_LOG_DIR = Path(os.environ.get("NORAD_LOG_DIR", str(_DEFAULT_LOG_DIR)))
_LOG_FILE = _LOG_DIR / "pipeline.jsonl"
_MAX_BYTES = 10 * 1024 * 1024  # 10 MB / file
_BACKUPS = 5

_lock = threading.Lock()
_logger: logging.Logger | None = None


def _ensure_logger() -> logging.Logger:
    global _logger
    if _logger is not None:
        return _logger
    with _lock:
        if _logger is not None:
            return _logger
        _LOG_DIR.mkdir(parents=True, exist_ok=True)
        lg = logging.getLogger("norad.pipeline")
        lg.setLevel(logging.INFO)
        lg.propagate = False
        # only one file handler ever, even on hot reload
        handler_marker = "norad.pipeline.file"
        if not any(getattr(h, "_norad_tag", "") == handler_marker for h in lg.handlers):
            handler = logging.handlers.RotatingFileHandler(
                _LOG_FILE, maxBytes=_MAX_BYTES, backupCount=_BACKUPS, encoding="utf-8"
            )
            handler.setFormatter(logging.Formatter("%(message)s"))
            handler._norad_tag = handler_marker  # type: ignore[attr-defined]
            lg.addHandler(handler)
        _logger = lg
        return _logger


# ── Truncation helpers ──────────────────────────────────────────────────────

_MAX_STR = 4000
_MAX_LIST = 50


def _truncate(v: Any, depth: int = 0) -> Any:
    """Best-effort cap on payload sizes so a single bad run can't bloat the log."""
    if depth > 6:
        return "…(depth-capped)"
    if isinstance(v, str):
        return v if len(v) <= _MAX_STR else v[:_MAX_STR] + f"…(+{len(v) - _MAX_STR} chars)"
    if isinstance(v, list):
        out = [_truncate(x, depth + 1) for x in v[:_MAX_LIST]]
        if len(v) > _MAX_LIST:
            out.append(f"…(+{len(v) - _MAX_LIST} items)")
        return out
    if isinstance(v, dict):
        return {k: _truncate(val, depth + 1) for k, val in v.items()}
    if isinstance(v, (int, float, bool)) or v is None:
        return v
    if isinstance(v, uuid.UUID):
        return str(v)
    return str(v)[:_MAX_STR]


# ── Public API ──────────────────────────────────────────────────────────────


def log_event(
    *,
    pipeline: str,
    kind: str,
    message: str = "",
    run_id: uuid.UUID | str | None = None,
    stage: int | None = None,
    level: str = "info",
    meta: dict[str, Any] | None = None,
) -> None:
    """Append a JSONL event to the pipeline log. Never raises."""
    try:
        lg = _ensure_logger()
        line = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "pipeline": pipeline,
            "stage": stage,
            "run_id": str(run_id) if run_id else None,
            "kind": kind,
            "level": level,
            "message": message,
            "meta": _truncate(meta or {}),
        }
        lg.info(json.dumps(line, ensure_ascii=False, default=str))
    except Exception:  # pragma: no cover — observability path
        # never let logging break the pipeline
        logging.getLogger(__name__).exception("pipeline_log failed (swallowed)")


def log_path() -> Path:
    """Where the live log file lives — useful in tests + admin endpoints."""
    return _LOG_FILE
