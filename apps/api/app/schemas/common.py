"""Shared primitives used across every Company Card block.

Design notes:
- `Valued[T]` is the universal wrapper for any field that can be wrong. It
  forces a `confidence` label and (optionally) a basis + a list of source
  references. This kills hallucination at the schema level — the model must
  declare how it knows a thing.
- Sources live in a top-level registry (`CompanyCardV1.sources_and_confidence
  .sources`); field-level `Valued.sources` are integer indexes into that list.
  Saves storage and lets us score source quality once per card.
- Tier (A/B/C) is attached to *fields* via `json_schema_extra={"tier": ...}`.
  See `app.schemas.tiers` for what each tier means.
"""
from __future__ import annotations

from typing import Generic, Literal, TypeVar

from pydantic import BaseModel, ConfigDict, Field, model_validator

T = TypeVar("T")

# ── Enums ────────────────────────────────────────────────────────────────────

Confidence = Literal["confirmed", "estimated", "inferred", "unknown"]
"""How sure are we about this value?

- confirmed: directly stated by the company or a primary regulatory source
- estimated: not directly disclosed but reasonable estimate from triangulation
- inferred:  reasoned from indirect evidence (e.g. hiring → fundraising soon)
- unknown:   genuinely don't know (default for missing data + Tier C gaps)
"""

Tier = Literal["A", "B", "C"]
"""Tool-capability tier for a field.

- A: Parallel + Exa reliably extract this from public web
- B: Sometimes available; often "unknown" — acceptable
- C: Requires paid data (Phyllo/Similarweb/SPINS/Apollo/etc) — stubbed by worker
"""

SourceType = Literal[
    "press_release",
    "news_article",
    "company_website",
    "company_blog",
    "linkedin",
    "investor_database",  # Crunchbase, PitchBook, Tracxn
    "regulatory_filing",  # FDA, SEC, USPTO
    "patent_database",
    "podcast",
    "social_media",
    "review_site",  # Trustpilot, Amazon reviews
    "reddit",
    "wikipedia",
    "industry_report",
    "academic",
    "other",
]

TrustTier = Literal["A", "B", "C", "D"]
"""Source trust ranking.

- A: primary source (company itself, regulator, SEC filing)
- B: major news outlet, established trade press
- C: blog, aggregator, niche publication
- D: unverified or anonymous
"""

CompanyStatus = Literal[
    "private",
    "public",
    "acquired",
    "subsidiary",
    "defunct",
    "stealth",
    "unknown",
]

BusinessType = Literal["b2b", "b2c", "b2b2c", "marketplace", "unknown"]

# ── Building blocks ──────────────────────────────────────────────────────────


class Money(BaseModel):
    """A single monetary value with currency."""

    model_config = ConfigDict(extra="ignore")
    amount: float | None = None
    currency: str = "USD"


class MoneyRange(BaseModel):
    """A range — used heavily for revenue / valuation estimates."""

    model_config = ConfigDict(extra="ignore")
    low: float | None = None
    high: float | None = None
    currency: str = "USD"


class Period(BaseModel):
    """ISO date range (strings, not date objects — JSON-Schema friendly)."""

    model_config = ConfigDict(extra="ignore")
    start: str | None = None  # YYYY-MM-DD
    end: str | None = None  # YYYY-MM-DD


class Source(BaseModel):
    """One source URL with provenance metadata."""

    model_config = ConfigDict(extra="ignore")
    id: int  # local index, referenced by Valued.sources
    url: str
    title: str | None = None
    type: SourceType = "other"
    trust_tier: TrustTier = "C"
    date_published: str | None = None  # YYYY-MM-DD
    date_found: str | None = None  # YYYY-MM-DD
    last_checked: str | None = None  # YYYY-MM-DD
    snippet: str | None = None
    freshness_score: float | None = Field(default=None, ge=0, le=1)


class Valued(BaseModel, Generic[T]):
    """Wrapper that forces a confidence label + source attribution.

    Used for any field that can be wrong, estimated, or synthesized.
    For Tier C gap fields, `gap_reason` carries the dependency (e.g.
    "requires_phyllo") so the UI can show "we'll fill this when X integrates".

    Strictness rules (enforced post-validate):
    - If `value` is set, `confidence` must not be "unknown".
    - If confidence is "estimated" or "inferred", `basis` must be non-empty.
    - If confidence is "confirmed", at least one source must be cited.
    These rules force engines to back claims with evidence; missing evidence
    means the field stays null and honest.
    """

    model_config = ConfigDict(extra="ignore")
    value: T | None = None
    confidence: Confidence = "unknown"
    basis: str | None = None
    sources: list[int] = Field(default_factory=list)
    gap_reason: str | None = None

    @model_validator(mode="after")
    def _enforce_attribution(self) -> "Valued":
        if self.value is None:
            return self
        if self.confidence == "unknown":
            raise ValueError(
                "Valued.value is set but confidence='unknown' — "
                "declare confirmed/estimated/inferred or leave value null."
            )
        if self.confidence in ("estimated", "inferred") and not (self.basis or "").strip():
            raise ValueError(
                f"confidence='{self.confidence}' requires a non-empty 'basis' explaining the reasoning."
            )
        if self.confidence == "confirmed" and not self.sources:
            raise ValueError(
                "confidence='confirmed' requires at least one source reference."
            )
        return self


# ── Field helpers ────────────────────────────────────────────────────────────


def tier_a(description: str = "", **kwargs) -> Field:  # type: ignore[valid-type]
    """Shorthand: a Tier-A field with default empty Valued()."""
    extra = {"tier": "A", **kwargs.pop("json_schema_extra", {})}
    return Field(  # type: ignore[no-any-return]
        default_factory=Valued,
        description=description,
        json_schema_extra=extra,
        **kwargs,
    )


def tier_b(description: str = "", **kwargs) -> Field:  # type: ignore[valid-type]
    """Tier-B: inconsistently available. Engines try, often returns unknown."""
    extra = {"tier": "B", **kwargs.pop("json_schema_extra", {})}
    return Field(  # type: ignore[no-any-return]
        default_factory=Valued,
        description=description,
        json_schema_extra=extra,
        **kwargs,
    )


def tier_c(description: str = "", gap_reason: str = "") -> Field:  # type: ignore[valid-type]
    """Tier-C: not asked of engines. Stubbed by worker with gap_reason."""

    def _factory() -> Valued:
        return Valued(value=None, confidence="unknown", gap_reason=gap_reason or None)

    return Field(  # type: ignore[no-any-return]
        default_factory=_factory,
        description=description,
        json_schema_extra={"tier": "C", "gap_reason": gap_reason},
    )
