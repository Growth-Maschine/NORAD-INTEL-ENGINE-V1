"""Schema introspection endpoints.

Used by the frontend (Settings page eventually) and by humans inspecting
what we ask Parallel + Exa to return.
"""
from __future__ import annotations

from fastapi import APIRouter

from app.schemas import empty_card, get_contract_schema, get_full_schema
from app.schemas.tiers import list_tier_c_paths

router = APIRouter(prefix="/schemas", tags=["schemas"])


@router.get("/company_card")
def company_card_full() -> dict:
    """Full V1 schema — what's stored in Postgres."""
    return get_full_schema()


@router.get("/company_card/contract")
def company_card_contract() -> dict:
    """Trimmed schema sent to Parallel + Exa (Tier C fields removed)."""
    return get_contract_schema()


@router.get("/company_card/empty")
def company_card_empty() -> dict:
    """An empty card, all defaults applied. Useful for UI scaffolding."""
    return empty_card().model_dump()


@router.get("/company_card/gaps")
def company_card_gaps() -> dict:
    """List the Tier-C gap fields (require paid integrations)."""
    return {"tier_c_paths": list_tier_c_paths(get_full_schema())}
