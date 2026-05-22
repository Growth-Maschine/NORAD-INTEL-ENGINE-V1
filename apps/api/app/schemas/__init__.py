"""Pydantic schemas for the NORAD Company Card and related types.

Public surface:
    from app.schemas import CompanyCardV1, get_full_schema, get_contract_schema

`CompanyCardV1` is the canonical card stored in Postgres.
`get_contract_schema()` returns the trimmed JSON Schema sent to Parallel + Exa
(Tier C "gap" fields removed — those are stubbed by the worker post-hoc).
"""
from app.schemas.company_card import (
    CompanyCardV1,
    empty_card,
    get_contract_schema,
    get_full_schema,
)

__all__ = [
    "CompanyCardV1",
    "empty_card",
    "get_contract_schema",
    "get_full_schema",
]
