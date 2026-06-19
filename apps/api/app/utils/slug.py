"""Shared slug helpers."""
from __future__ import annotations

import re
import uuid

_SLUG_RE = re.compile(r"[^a-z0-9]+")


def slugify(text: str) -> str:
    base = _SLUG_RE.sub("-", text.strip().lower()).strip("-")
    return base or str(uuid.uuid4())
