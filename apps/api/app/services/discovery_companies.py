"""Persist Web Discovery Sonnet mentions as ``companies`` rows linked to articles."""
from __future__ import annotations

import re
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Article, Company

_MENTION_KEYS = (
    "name",
    "context",
    "hint_url",
    "industry",
    "hq_or_market",
    "role_in_story",
    "company_id",
)


def normalize_company_name(name: str) -> str:
    cleaned = re.sub(r"\s+", " ", (name or "").strip().lower())
    return cleaned[:255]


def _mention_dict(item: dict[str, Any], *, company_id: uuid.UUID) -> dict[str, Any]:
    return {
        "name": str(item.get("name") or "").strip(),
        "context": str(item.get("context") or "").strip(),
        "hint_url": item.get("hint_url"),
        "industry": item.get("industry"),
        "hq_or_market": item.get("hq_or_market"),
        "role_in_story": item.get("role_in_story"),
        "company_id": str(company_id),
    }


async def persist_discovery_companies(
    session: AsyncSession,
    *,
    article_id: uuid.UUID,
    mentions: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Upsert one ``companies`` row per mention for this article; return JSON with ``company_id``."""
    out: list[dict[str, Any]] = []
    for raw in mentions:
        if not isinstance(raw, dict):
            continue
        name = str(raw.get("name") or "").strip()
        if not name:
            continue
        norm = normalize_company_name(name)
        row = (
            await session.execute(
                select(Company).where(
                    Company.source_article_id == article_id,
                    Company.normalized_name == norm,
                )
            )
        ).scalars().first()

        hint = raw.get("hint_url")
        website = str(hint).strip() if hint else None
        industry = str(raw.get("industry") or "").strip() or None
        hq = str(raw.get("hq_or_market") or "").strip() or None
        role = str(raw.get("role_in_story") or "").strip() or None
        context = str(raw.get("context") or "").strip() or None

        if row is None:
            row = Company(
                company_name=name[:255],
                normalized_name=norm,
                origin="web_discovery",
                source_article_id=article_id,
                discovery_role=role[:64] if role else None,
                discovery_context=context,
                website=website,
                industry=industry[:128] if industry else None,
                headquarters_country=hq[:64] if hq else None,
            )
            session.add(row)
            await session.flush()
        else:
            row.company_name = name[:255]
            row.discovery_role = role[:64] if role else row.discovery_role
            row.discovery_context = context or row.discovery_context
            if website:
                row.website = website
            if industry:
                row.industry = industry[:128]
            if hq:
                row.headquarters_country = hq[:64]

        out.append(_mention_dict(raw, company_id=row.id))

    return out


async def sync_article_discovery_companies(session: AsyncSession, article: Article) -> None:
    """Backfill ``company_id`` on ``mentioned_companies`` from relational rows."""
    mentions = list(article.mentioned_companies or [])
    if not mentions:
        return
    synced = await persist_discovery_companies(
        session, article_id=article.id, mentions=mentions
    )
    article.mentioned_companies = synced
