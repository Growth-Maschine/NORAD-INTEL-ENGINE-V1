"""Top-level `CompanyCardV1` envelope.

The card is the unit we store in Postgres (`cards` table). It versions the
shape so future v2 cards can coexist with v1 in the same column.
"""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.blocks import (
    BrandMarketingSentiment,
    BusinessModel,
    Classification,
    CompanyIdentity,
    DistributionAndChannels,
    Financials,
    FundingAndInvestors,
    LegalRegulatoryRisk,
    MarketAndCompetitors,
    PeopleAndDecisionMap,
    ProductsAndSkus,
    Scores,
    Signal,
    SourcesAndConfidence,
    StrategicFit,
    TechnologyIpDefensibility,
    TractionAndMomentum,
)
from app.schemas.tiers import enforce_contract_required, strip_tier_c

# Top-level blocks that we require engines to return (even if empty objects).
# Forces structure on the JSON output contract — engines can't omit a block.
_REQUIRED_TOP_BLOCKS = [
    "schema_version",
    "company_identity",
    "classification",
    "products_and_skus",
    "people_and_decision_map",
    "financials",
    "funding_and_investors",
    "traction_and_momentum",
    "distribution_and_channels",
    "market_and_competitors",
    "business_model",
    "strategic_fit",
    "legal_regulatory_risk",
    "brand_marketing_sentiment",
    "technology_ip_defensibility",
    "signals",
    "scores",
    "sources_and_confidence",
]


class CompanyCardV1(BaseModel):
    """The canonical NORAD company-intel card (schema v1).

    16 blocks + signals[] + scores + sources_and_confidence, exactly per spec.
    Every block defaults to empty/unknown so an empty card is valid — the
    research pipeline fills what it can and leaves the rest honestly null.
    """

    # Top-level is strict: any unknown root block from the synthesizer is a
    # contract violation and should fail loudly. Nested blocks use extra="ignore"
    # so harmless LLM hallucinations inside a block (e.g. an extra adjective
    # field) silently drop instead of failing the whole run.
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1.0"] = "1.0"
    card_id: str | None = None  # UUID, assigned at insert
    created_date: str | None = None  # YYYY-MM-DD, when first researched
    last_updated_date: str | None = None  # YYYY-MM-DD, last re-research

    company_identity: CompanyIdentity = Field(default_factory=CompanyIdentity)
    classification: Classification = Field(default_factory=Classification)
    products_and_skus: ProductsAndSkus = Field(default_factory=ProductsAndSkus)
    people_and_decision_map: PeopleAndDecisionMap = Field(
        default_factory=PeopleAndDecisionMap
    )
    financials: Financials = Field(default_factory=Financials)
    funding_and_investors: FundingAndInvestors = Field(
        default_factory=FundingAndInvestors
    )
    traction_and_momentum: TractionAndMomentum = Field(
        default_factory=TractionAndMomentum
    )
    distribution_and_channels: DistributionAndChannels = Field(
        default_factory=DistributionAndChannels
    )
    market_and_competitors: MarketAndCompetitors = Field(
        default_factory=MarketAndCompetitors
    )
    business_model: BusinessModel = Field(default_factory=BusinessModel)
    strategic_fit: StrategicFit = Field(default_factory=StrategicFit)
    legal_regulatory_risk: LegalRegulatoryRisk = Field(
        default_factory=LegalRegulatoryRisk
    )
    brand_marketing_sentiment: BrandMarketingSentiment = Field(
        default_factory=BrandMarketingSentiment
    )
    technology_ip_defensibility: TechnologyIpDefensibility = Field(
        default_factory=TechnologyIpDefensibility
    )
    signals: list[Signal] = Field(default_factory=list)
    scores: Scores = Field(default_factory=Scores)
    sources_and_confidence: SourcesAndConfidence = Field(
        default_factory=SourcesAndConfidence
    )


# ── Helpers ──────────────────────────────────────────────────────────────────


def empty_card() -> CompanyCardV1:
    """Return a fully-empty card. Useful for UI scaffolding + tests."""
    return CompanyCardV1()


def get_full_schema() -> dict[str, Any]:
    """The full JSON Schema — what's stored in Postgres."""
    return enforce_contract_required(
        CompanyCardV1.model_json_schema(),
        required_top_level=_REQUIRED_TOP_BLOCKS,
    )


def get_contract_schema() -> dict[str, Any]:
    """The trimmed JSON Schema — what we send Parallel + Exa as the output contract.

    Drops Tier-C fields (paid-data dependencies) and forces top-level blocks +
    `Valued.confidence` to be required so engines must return structure.
    Worker auto-stubs Tier-C fields after the engines return.
    """
    return enforce_contract_required(
        strip_tier_c(CompanyCardV1.model_json_schema()),
        required_top_level=_REQUIRED_TOP_BLOCKS,
    )
