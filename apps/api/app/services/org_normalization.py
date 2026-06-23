"""Domain normalization for organization records."""
from __future__ import annotations

import re

_DOMAIN_RE = re.compile(r"^https?://", re.IGNORECASE)


def normalize_domain(raw: str) -> str:
    value = raw.strip().lower()
    value = _DOMAIN_RE.sub("", value)
    value = value.split("/")[0].strip()
    if not value:
        raise ValueError("domain is required")
    return value


def normalize_email(raw: str) -> str:
    value = raw.strip().lower()
    if not value or "@" not in value:
        raise ValueError("invalid email")
    return value
