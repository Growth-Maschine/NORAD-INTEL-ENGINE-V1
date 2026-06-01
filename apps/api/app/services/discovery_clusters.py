"""Seed data + helpers for Discovery keyword clusters."""
from __future__ import annotations

import re
import uuid

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.discovery_cluster import DiscoveryCluster

_SLUG_RE = re.compile(r"[^a-z0-9]+")


def slugify(text: str) -> str:
    base = _SLUG_RE.sub("-", text.strip().lower()).strip("-")
    return base or str(uuid.uuid4())


SEED_CLUSTERS: list[dict] = [
    {
        "name": "Nicotine Alternatives",
        "group_name": "Core Product & Industry",
        "description": "Modern oral, smoke-free, and next-generation nicotine formats.",
        "keywords": [
            "nicotine pouch",
            "nicotine-free pouch",
            "oral nicotine",
            "smokeless nicotine",
            "tobacco-free nicotine",
            "synthetic nicotine",
            "nicotine delivery system",
            "nicotine replacement",
            "nicotine innovation",
            "heated tobacco",
            "heat-not-burn",
            "reduced risk product",
            "modern oral",
            "next generation nicotine",
            "vaping alternative",
            "smoke-free product",
            "nicotine wellness",
            "nicotine functional product",
            "oral stimulation product",
        ],
    },
    {
        "name": "Functional Beverage Trends",
        "group_name": "Core Product & Industry",
        "description": "Performance, hydration, cognition, and recovery beverage signals.",
        "keywords": [
            "functional beverage",
            "nootropic drink",
            "adaptogen beverage",
            "hydration beverage",
            "wellness beverage",
            "energy alternative",
            "clean energy drink",
            "mushroom beverage",
            "protein hydration",
            "sleep beverage",
            "stress relief drink",
            "cognition beverage",
            "focus drink",
            "electrolyte innovation",
            "performance beverage",
            "recovery beverage",
            "metabolic beverage",
            "longevity beverage",
            "biohacking drink",
        ],
    },
    {
        "name": "Wellness & Health Products",
        "group_name": "Core Product & Industry",
        "description": "Consumer wellness products, systems, and preventative-health themes.",
        "keywords": [
            "biohacking",
            "wellness technology",
            "functional wellness",
            "preventative health",
            "longevity product",
            "healthy aging",
            "sleep optimization",
            "stress reduction",
            "recovery technology",
            "cognitive enhancement",
            "hormone optimization",
            "metabolic health",
            "personalized wellness",
            "wellness stack",
            "consumer wellness trend",
            "wellness innovation",
        ],
    },
    {
        "name": "CPG / Consumer Product Discovery",
        "group_name": "Core Product & Industry",
        "description": "Emerging CPG, DTC, challenger brands, and premiumization signals.",
        "keywords": [
            "emerging consumer brand",
            "disruptive consumer brand",
            "viral product",
            "premium consumer goods",
            "DTC brand",
            "challenger brand",
            "next-gen CPG",
            "innovative packaging",
            "sustainable packaging",
            "eco-conscious product",
            "convenience innovation",
            "premiumization trend",
            "lifestyle product",
            "subscription consumer product",
            "creator-led brand",
            "influencer-led product",
        ],
    },
]


async def ensure_seed_clusters(session: AsyncSession) -> None:
    existing = (
        await session.execute(select(DiscoveryCluster.id).limit(1))
    ).scalar_one_or_none()
    if existing is not None:
        return

    rows = []
    for i, c in enumerate(SEED_CLUSTERS):
        rows.append(
            {
                "name": c["name"],
                "slug": slugify(c["name"]),
                "group_name": c["group_name"],
                "description": c["description"],
                "keywords": c["keywords"],
                "is_enabled": True,
                "is_default": i == 0,
                "sort_order": i,
            }
        )

    await session.execute(pg_insert(DiscoveryCluster).values(rows))
    await session.commit()
