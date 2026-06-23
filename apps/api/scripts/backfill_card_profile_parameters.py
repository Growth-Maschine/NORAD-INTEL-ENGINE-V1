"""Backfill ``card_profile_parameters`` for existing cards.

Usage (from repo root):
  cd apps/api && CORS_ORIGINS='["http://localhost:5173"]' \
    .venv/bin/python ../../scripts/backfill_card_profile_parameters.py
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

API_ROOT = Path(__file__).resolve().parents[1] / "apps" / "api"
sys.path.insert(0, str(API_ROOT))

from sqlalchemy import select  # noqa: E402

from app.core.db import get_session_factory  # noqa: E402
from app.models import Card  # noqa: E402
from app.services.card_profile_parameters import persist_card_profile_parameters_sync  # noqa: E402
from app.services.profile_completeness import CATALOG_PARAM_COUNT  # noqa: E402


async def main() -> None:
    factory = get_session_factory()
    updated = 0
    skipped = 0
    async with factory() as session:
        cards = (await session.execute(select(Card).order_by(Card.created_at.asc()))).scalars().all()
        for card in cards:
            if not card.card:
                skipped += 1
                continue
            from app.models import CardProfileParameter

            existing = (
                await session.execute(
                    select(CardProfileParameter.id)
                    .where(CardProfileParameter.card_id == card.id)
                    .limit(1)
                )
            ).scalar_one_or_none()
            if existing is not None:
                skipped += 1
                continue

            persist_card_profile_parameters_sync(session, card_row=card, card_dict=card.card)
            updated += 1
            if updated % 10 == 0:
                await session.flush()
        await session.commit()

    print(f"backfill complete: {updated} cards materialized, {skipped} skipped")
    print(f"catalog size: {CATALOG_PARAM_COUNT} parameters per card")


if __name__ == "__main__":
    asyncio.run(main())
