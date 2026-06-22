"""Persist materialized profile-completeness rows for a card."""
from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Card, CardProfileParameter
from app.services.profile_completeness import (
    extract_profile_parameters,
    summarize_profile_completeness,
)


def persist_card_profile_parameters_sync(
    session: AsyncSession,
    *,
    card_row: Card,
    card_dict: dict,
) -> None:
    """Insert 49 ``card_profile_parameters`` rows and update card summary columns."""
    params = extract_profile_parameters(card_dict)
    summary = summarize_profile_completeness(params)

    for p in params:
        session.add(
            CardProfileParameter(
                company_id=card_row.company_id,
                card_id=card_row.id,
                param_key=p.param_key,
                group_name=p.group_name,
                sort_order=p.sort_order,
                label=p.label,
                value=p.value,
                confidence=p.confidence,
                basis=p.basis,
                source_refs=p.source_refs,
                coverage_status=p.coverage_status,
            )
        )

    card_row.profile_completeness_pct = summary.completeness_pct
    card_row.profile_verified_count = summary.verified_count
    card_row.profile_uncertain_count = summary.uncertain_count
    card_row.profile_missing_count = summary.missing_count


async def load_card_profile_parameters(
    session: AsyncSession,
    card_id: uuid.UUID,
) -> list[CardProfileParameter]:
    from sqlalchemy import select

    return list(
        (
            await session.execute(
                select(CardProfileParameter)
                .where(CardProfileParameter.card_id == card_id)
                .order_by(CardProfileParameter.sort_order.asc())
            )
        ).scalars().all()
    )
