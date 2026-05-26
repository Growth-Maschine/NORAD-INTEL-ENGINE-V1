"""Engine pricing constants — kept in one place for cost accounting.

Prices are USD per million tokens (LLMs) or per call (search engines).
Updated 2026-05; bump these when vendor pricing changes.
"""
from __future__ import annotations

# ── Anthropic Claude (per 1M tokens) ────────────────────────────────────────
CLAUDE_PRICING_PER_M_TOKENS: dict[str, dict[str, float]] = {
    "claude-haiku-4-5":  {"input": 1.00, "output": 5.00},
    "claude-haiku-3-5":  {"input": 0.80, "output": 4.00},
    "claude-sonnet-4-5": {"input": 3.00, "output": 15.00},
    "claude-sonnet-3-5": {"input": 3.00, "output": 15.00},
    "claude-opus-4":     {"input": 15.00, "output": 75.00},
}

# Default model aliases — used when caller asks for a tier, not a version.
CLAUDE_MODELS = {
    "haiku":  "claude-haiku-4-5",
    "sonnet": "claude-sonnet-4-5",
    "opus":   "claude-opus-4",
}

# ── Exa (per call) ──────────────────────────────────────────────────────────
EXA_PRICING_USD: dict[str, float] = {
    "search":       0.005,
    "get_contents": 0.005,   # per URL
    "answer":       0.010,
    "research":     0.050,
}

# ── Parallel Web (per task — varies by processor) ───────────────────────────
PARALLEL_PRICING_USD: dict[str, float] = {
    "lite": 0.20,
    "base": 0.50,
    "core": 1.00,    # default for NORAD research
    "pro":  2.50,
}

# ── Diffbot Knowledge Graph ─────────────────────────────────────────────────
# Diffbot bills by monthly plan quota (Free=400 entities/mo, Startup/Plus=unlimited),
# not per-call $$. We record $0 against engine_calls for parity but still log
# the call so we can monitor latency + status + match score.
DIFFBOT_PRICING_USD: dict[str, float] = {
    "enhance": 0.0,
    "dql_search": 0.0,
    "combine":   0.0,
    "article_extract": 0.0,
    "nl":        0.0,
}


def claude_cost_usd(model: str, input_tokens: int, output_tokens: int) -> float:
    """Compute USD cost for a Claude call. Returns 0 for unknown models."""
    p = CLAUDE_PRICING_PER_M_TOKENS.get(model)
    if not p:
        return 0.0
    return (input_tokens * p["input"] + output_tokens * p["output"]) / 1_000_000


def exa_cost_usd(operation: str, units: int = 1) -> float:
    return EXA_PRICING_USD.get(operation, 0.0) * units


def parallel_cost_usd(processor: str) -> float:
    return PARALLEL_PRICING_USD.get(processor, PARALLEL_PRICING_USD["core"])


def diffbot_cost_usd(operation: str, units: int = 1) -> float:
    """Diffbot calls are plan-bundled — returns $0 today.

    Kept symmetric with the other engine pricing helpers so callers can sum
    `engine_calls.cost_usd` per run without special-casing vendor. If Diffbot
    adds per-call billing later we just bump this map.
    """
    return DIFFBOT_PRICING_USD.get(operation, 0.0) * units
