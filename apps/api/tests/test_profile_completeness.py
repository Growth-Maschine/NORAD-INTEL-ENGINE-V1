"""Tests for profile completeness extraction."""
from __future__ import annotations

from app.services.profile_completeness import (
    CATALOG_PARAM_COUNT,
    extract_profile_parameters,
    summarize_profile_completeness,
)


def test_catalog_has_44_parameters() -> None:
    assert CATALOG_PARAM_COUNT == 44


def test_identity_fields_extract_verified() -> None:
    card = {
        "company_identity": {
            "company_name": "CocoGoodsCo",
            "website": "https://cocogoodsco.com",
            "legal_entity_name": "Luong Quoi Coconut USA – LQC, Inc.",
            "founded_date": "2015-01-01",
            "headquarters": "916 Pleasant Street, Suite 22, Norwood, MA 02062, USA",
            "status": "subsidiary",
        }
    }
    params = extract_profile_parameters(card)
    by_key = {p.param_key: p for p in params}

    assert by_key["company_name"].coverage_status == "verified"
    assert by_key["company_name"].value == "CocoGoodsCo"
    assert by_key["website"].coverage_status == "verified"
    assert by_key["legal_entity"].coverage_status == "verified"
    assert by_key["founded_date"].coverage_status == "verified"
    assert by_key["headquarters"].coverage_status == "verified"
    assert by_key["company_status"].coverage_status == "verified"


def test_valued_field_uncertain() -> None:
    card = {
        "financials": {
            "revenue_estimate": {
                "value": {"low": 1_000_000, "high": 5_000_000, "currency": "USD"},
                "confidence": "estimated",
                "basis": "Triangulated from press coverage.",
                "sources": [1, 2],
            }
        }
    }
    params = extract_profile_parameters(card)
    rev = next(p for p in params if p.param_key == "revenue_estimate")
    assert rev.coverage_status == "uncertain"
    assert rev.confidence == "estimated"
    assert rev.source_refs == [1, 2]


def test_completeness_pct_formula() -> None:
    params = extract_profile_parameters({})
    summary = summarize_profile_completeness(params)
    assert summary.total_count == 44
    assert summary.missing_count == 44
    assert summary.completeness_pct == 0

    card = {
        "company_identity": {
            "company_name": "Acme",
            "website": "https://acme.com",
            "legal_entity_name": "Acme Inc",
            "founded_date": "2020-01-01",
            "headquarters": "NYC",
            "status": "private",
        },
        "financials": {
            "revenue_estimate": {
                "value": 1_000_000,
                "confidence": "estimated",
                "basis": "guess",
                "sources": [],
            }
        },
    }
    params = extract_profile_parameters(card)
    summary = summarize_profile_completeness(params)
    assert summary.verified_count == 6
    assert summary.uncertain_count == 1
    assert summary.missing_count == 37
