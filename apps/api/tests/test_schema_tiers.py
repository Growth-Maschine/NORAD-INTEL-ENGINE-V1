"""Regression tests for the CompanyCardV1 schema contract.

These pin the fixtures the engine adapters and worker depend on:
- Tier-C fields are removed from the contract schema
- Top-level blocks are required in both schemas
- Valued.* attribution rules actually fire
"""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.schemas import CompanyCardV1, empty_card, get_contract_schema, get_full_schema
from app.schemas.common import Valued
from app.schemas.tiers import list_tier_c_paths

EXPECTED_TIER_C_PATHS = {
    "financials.aov_estimate",
    "financials.cac_estimate",
    "financials.ltv_estimate",
    "financials.revenue_by_channel",
    "traction_and_momentum.web_traffic_monthly",
    "traction_and_momentum.web_traffic_growth_90d",
    "traction_and_momentum.social_follower_growth_90d",
    "traction_and_momentum.social_engagement_rate",
    "traction_and_momentum.search_volume_growth_90d",
    "distribution_and_channels.retail_velocity_proxy",
    "brand_marketing_sentiment.engagement_rate",
    "brand_marketing_sentiment.branded_search_volume",
}


def test_empty_card_validates() -> None:
    """An untouched empty card must roundtrip cleanly."""
    card = empty_card()
    CompanyCardV1.model_validate(card.model_dump())


def test_full_schema_has_top_level_required() -> None:
    schema = get_full_schema()
    required = set(schema["required"])
    must_have = {
        "company_identity",
        "products_and_skus",
        "people_and_decision_map",
        "financials",
        "signals",
        "scores",
        "sources_and_confidence",
    }
    assert must_have.issubset(required), required


def test_contract_drops_tier_c_paths() -> None:
    full = get_full_schema()
    contract = get_contract_schema()
    # Tier C present in full
    full_paths = set(list_tier_c_paths(full))
    assert EXPECTED_TIER_C_PATHS.issubset(full_paths)
    # Tier C absent from contract
    contract_paths = set(list_tier_c_paths(contract))
    assert contract_paths == set(), f"Tier C leaked into contract: {contract_paths}"


def test_contract_valued_requires_confidence() -> None:
    contract = get_contract_schema()
    valued_defs = [d for d in contract["$defs"] if d.startswith("Valued")]
    assert valued_defs, "No Valued_* defs found in contract"
    for name in valued_defs:
        req = set(contract["$defs"][name].get("required", []))
        assert "confidence" in req, f"{name} doesn't require confidence"


def test_valued_rejects_value_with_unknown_confidence() -> None:
    with pytest.raises(ValidationError):
        Valued[int](value=42, confidence="unknown")


def test_valued_rejects_estimated_without_basis() -> None:
    with pytest.raises(ValidationError):
        Valued[int](value=42, confidence="estimated", basis=None)


def test_valued_rejects_confirmed_without_sources() -> None:
    with pytest.raises(ValidationError):
        Valued[int](value=42, confidence="confirmed", sources=[])


def test_valued_accepts_well_formed() -> None:
    v = Valued[int](
        value=42,
        confidence="estimated",
        basis="triangulated from employee count and SKU pricing",
        sources=[0, 3],
    )
    assert v.value == 42


def test_valued_unknown_null_is_fine() -> None:
    """Empty card uses unknown + null — must still be valid."""
    v = Valued[int]()
    assert v.value is None and v.confidence == "unknown"
