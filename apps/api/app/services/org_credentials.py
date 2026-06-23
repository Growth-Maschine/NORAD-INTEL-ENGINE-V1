"""Cryptographic helpers for org integration keys and invite tokens."""
from __future__ import annotations

import hashlib
import secrets

API_KEY_PREFIX = "norad_org_"
API_KEY_PREFIX_DISPLAY_LEN = 20


def hash_secret(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def generate_integration_key() -> tuple[str, str, str]:
    """Return ``(full_key, key_prefix, key_hash)``."""
    secret = secrets.token_urlsafe(32)
    full_key = f"{API_KEY_PREFIX}{secret}"
    key_prefix = full_key[:API_KEY_PREFIX_DISPLAY_LEN]
    return full_key, key_prefix, hash_secret(full_key)


def generate_invite_token() -> tuple[str, str]:
    """Return ``(token, token_hash)``."""
    token = secrets.token_urlsafe(32)
    return token, hash_secret(token)
