"""TrendHunter category taxonomy.

Sourced from the curated "Pages" sheet in the TrendHunter Excel workbook
(attached_assets/TRENDHUNTER_*.xlsx). The list is small enough to live in
code — when it changes, edit this file rather than seeding a DB table.

Each category resolves to a TrendHunter section URL; we DON'T scrape those
pages directly (anti-bot guards). Instead we hand the category slug + an
optional keyword to Exa with `include_domains=["trendhunter.com"]`, letting
Exa's index do the heavy lifting.

Categories are grouped for UI display; the slug is what the API accepts.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Category:
    slug: str        # canonical id, used by the API
    label: str       # human-readable
    group: str       # UI grouping
    th_url: str      # source TrendHunter page (for reference / link-out)


CATEGORIES: tuple[Category, ...] = (
    # Lifestyle group
    Category("lifestyle",    "Lifestyle",         "Lifestyle", "https://www.trendhunter.com/lifestyle"),
    Category("creditcrunch", "Credit Crunch",     "Lifestyle", "https://www.trendhunter.com/creditcrunch"),
    Category("drinking",     "Drinking",          "Lifestyle", "https://www.trendhunter.com/drinking"),
    Category("food",         "Food",              "Lifestyle", "https://www.trendhunter.com/food"),
    Category("health",       "Health",            "Lifestyle", "https://www.trendhunter.com/health"),
    Category("life",         "Life",              "Lifestyle", "https://www.trendhunter.com/life"),
    Category("sports",       "Sports",            "Lifestyle", "https://www.trendhunter.com/sports"),
    # Business group
    Category("business",     "Business",          "Business",  "https://www.trendhunter.com/business"),
    Category("newventures",  "New Ventures",      "Business",  "https://www.trendhunter.com/newventures"),
    Category("retail",       "Retail",            "Business",  "https://www.trendhunter.com/retail"),
    # Unique group
    Category("unique",       "Unique",            "Unique",    "https://www.trendhunter.com/unique"),
    Category("bizarre",      "Bizarre",           "Unique",    "https://www.trendhunter.com/bizarre"),
    Category("inventions",   "Inventions",        "Unique",    "https://www.trendhunter.com/inventions"),
    # Viral
    Category("viral",        "Viral",             "Viral",     "https://www.trendhunter.com/viral"),
    # Misc
    Category("popculture",   "Pop Culture",       "Misc",      "https://www.trendhunter.com/popculture"),
    Category("celebproducts","Celebrity Products","Misc",      "https://www.trendhunter.com/celebproducts"),
)

CATEGORIES_BY_SLUG: dict[str, Category] = {c.slug: c for c in CATEGORIES}


def get_category(slug: str) -> Category:
    """Look up by slug. Raises KeyError if unknown."""
    cat = CATEGORIES_BY_SLUG.get(slug)
    if cat is None:
        raise KeyError(f"unknown category: {slug!r}")
    return cat


def list_categories_grouped() -> dict[str, list[dict]]:
    """Categories grouped for UI: {group: [{slug, label, th_url}, ...]}."""
    out: dict[str, list[dict]] = {}
    for c in CATEGORIES:
        out.setdefault(c.group, []).append(
            {"slug": c.slug, "label": c.label, "th_url": c.th_url}
        )
    return out
