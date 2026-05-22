"""Anthropic Claude client — used for ranking + synthesis.

Two roles in NORAD:
1. **Haiku (cheap, batch)** — Stage-3 article ranking. Reads ~30 title+deks
   and returns relevance scores + 1-line verdicts.
2. **Sonnet (deep, structured)** — Stage-5 per-article analysis (companies +
   summary) AND the Phase-C synthesizer that produces validated CompanyCardV1.

All calls use the official async SDK. Structured outputs use `tool_use` so
we get JSON the schema validator can trust.
"""
from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Any

from anthropic import AsyncAnthropic

from app.core.config import get_settings
from app.engines._pricing import CLAUDE_MODELS, claude_cost_usd

logger = logging.getLogger(__name__)


# ── Types ───────────────────────────────────────────────────────────────────


@dataclass(slots=True)
class ClaudeMessage:
    role: str  # "user" | "assistant"
    content: str


@dataclass(slots=True)
class ClaudeResponse:
    text: str
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    input_tokens: int = 0
    output_tokens: int = 0
    stop_reason: str | None = None
    model: str = ""
    cost_usd: float = 0.0
    latency_ms: float = 0.0
    status: str = "ok"
    error: str | None = None
    # Snapshot of the kwargs sent to the SDK (system, messages, tools meta).
    # Populated for I/O tracing; never used for retries.
    request_payload: dict[str, Any] = field(default_factory=dict)

    @property
    def first_tool_input(self) -> dict[str, Any] | None:
        """Return the first tool-use input dict, or None."""
        return self.tool_calls[0]["input"] if self.tool_calls else None

    @property
    def response_payload(self) -> dict[str, Any]:
        """Inspectable view of the model's response (text + tool calls + meta)."""
        return {
            "text": self.text,
            "tool_calls": self.tool_calls,
            "stop_reason": self.stop_reason,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
        }


# ── Client ──────────────────────────────────────────────────────────────────


class ClaudeClient:
    def __init__(self, api_key: str):
        if not api_key:
            raise RuntimeError("ANTHROPIC_API_KEY is not configured")
        self._sdk = AsyncAnthropic(api_key=api_key)

    @staticmethod
    def resolve_model(tier_or_model: str) -> str:
        """Map 'haiku'/'sonnet'/'opus' aliases to versioned model names."""
        return CLAUDE_MODELS.get(tier_or_model, tier_or_model)

    async def complete(
        self,
        *,
        model: str = "sonnet",
        system: str | None = None,
        messages: list[ClaudeMessage],
        max_tokens: int = 4096,
        temperature: float = 0.2,
        tools: list[dict[str, Any]] | None = None,
        tool_choice: dict[str, Any] | None = None,
        timeout_s: float = 120.0,
    ) -> ClaudeResponse:
        """Single-shot completion. For structured output, pass a tool spec.

        Returns a ClaudeResponse with cost + latency populated. Never raises —
        errors are captured in `status='error'` so the caller can decide.
        """
        resolved_model = self.resolve_model(model)
        kwargs: dict[str, Any] = {
            "model": resolved_model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
        }
        if system:
            kwargs["system"] = system
        if tools:
            kwargs["tools"] = tools
        if tool_choice:
            kwargs["tool_choice"] = tool_choice

        # Inspectable snapshot of what we sent. Tool input_schemas can be huge
        # (the CompanyCardV1 contract is ~50KB) so we record names + a length
        # only, not the full schema body.
        req_snapshot: dict[str, Any] = {
            "model": resolved_model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "system": system,
            "messages": kwargs["messages"],
            "tools": [
                {"name": t.get("name"), "description": t.get("description"),
                 "input_schema_chars": len(str(t.get("input_schema") or ""))}
                for t in (tools or [])
            ],
            "tool_choice": tool_choice,
        }

        t0 = time.perf_counter()
        try:
            msg = await asyncio.wait_for(
                self._sdk.messages.create(**kwargs),
                timeout=timeout_s,
            )
        except asyncio.TimeoutError:
            return ClaudeResponse(
                text="",
                status="error",
                error=f"Claude timeout after {timeout_s}s",
                model=resolved_model,
                latency_ms=round((time.perf_counter() - t0) * 1000, 1),
                request_payload=req_snapshot,
            )
        except Exception as exc:
            logger.exception("Claude call failed: %s", exc)
            return ClaudeResponse(
                text="",
                status="error",
                error=f"{type(exc).__name__}: {exc}",
                model=resolved_model,
                latency_ms=round((time.perf_counter() - t0) * 1000, 1),
                request_payload=req_snapshot,
            )

        text_parts: list[str] = []
        tool_calls: list[dict[str, Any]] = []
        for block in msg.content:
            btype = getattr(block, "type", None)
            if btype == "text":
                text_parts.append(getattr(block, "text", "") or "")
            elif btype == "tool_use":
                tool_calls.append(
                    {
                        "id": getattr(block, "id", ""),
                        "name": getattr(block, "name", ""),
                        "input": getattr(block, "input", {}) or {},
                    }
                )

        usage = getattr(msg, "usage", None)
        in_tok = getattr(usage, "input_tokens", 0) if usage else 0
        out_tok = getattr(usage, "output_tokens", 0) if usage else 0

        return ClaudeResponse(
            text="".join(text_parts),
            tool_calls=tool_calls,
            input_tokens=in_tok,
            output_tokens=out_tok,
            stop_reason=getattr(msg, "stop_reason", None),
            model=resolved_model,
            cost_usd=claude_cost_usd(resolved_model, in_tok, out_tok),
            latency_ms=round((time.perf_counter() - t0) * 1000, 1),
            status="ok",
            request_payload=req_snapshot,
        )

    async def smoke_check(self) -> dict[str, Any]:
        """Minimal live call — 1 token in, 1 token out. ~$0.00001."""
        t0 = time.perf_counter()
        try:
            await self._sdk.messages.create(
                model=self.resolve_model("haiku"),
                max_tokens=4,
                messages=[{"role": "user", "content": "Reply with: ok"}],
            )
            return {
                "ok": True,
                "latency_ms": round((time.perf_counter() - t0) * 1000, 1),
                "vendor": "anthropic",
            }
        except Exception as exc:
            return {
                "ok": False,
                "latency_ms": round((time.perf_counter() - t0) * 1000, 1),
                "error": f"{type(exc).__name__}: {exc}",
                "vendor": "anthropic",
            }


# ── Singleton accessor ──────────────────────────────────────────────────────

_client: ClaudeClient | None = None


def get_claude_client() -> ClaudeClient:
    global _client
    if _client is None:
        settings = get_settings()
        _client = ClaudeClient(api_key=settings.anthropic_api_key)
    return _client
