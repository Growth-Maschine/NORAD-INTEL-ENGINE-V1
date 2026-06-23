"""Unit tests for org credential and normalization helpers."""
from __future__ import annotations

import uuid

from app.models.organization_auth_config import OrganizationAuthConfig
from app.services.org_credentials import (
    API_KEY_PREFIX,
    generate_integration_key,
    generate_invite_token,
    hash_secret,
)
from app.services.org_normalization import normalize_domain, normalize_email
from app.services.organizations import compute_security_score


def test_normalize_domain_strips_protocol() -> None:
    assert normalize_domain("https://Acme.Inc/") == "acme.inc"


def test_normalize_email_lowercase() -> None:
    assert normalize_email("User@Example.COM") == "user@example.com"


def test_integration_key_format_and_hash() -> None:
    full_key, prefix, key_hash = generate_integration_key()
    assert full_key.startswith(API_KEY_PREFIX)
    assert prefix == full_key[:20]
    assert key_hash == hash_secret(full_key)
    assert len(key_hash) == 64


def test_invite_token_unique() -> None:
    t1, h1 = generate_invite_token()
    t2, h2 = generate_invite_token()
    assert t1 != t2
    assert h1 != h2
    assert hash_secret(t1) == h1


def test_security_score_provisioning() -> None:
    auth = OrganizationAuthConfig(organization_id=uuid.uuid4())
    assert compute_security_score(auth, provisioning=True) == 78


def test_security_score_with_policies() -> None:
    auth = OrganizationAuthConfig(
        organization_id=uuid.uuid4(),
        mfa_enforced=True,
        sso_only=True,
        scim_enabled=True,
        ip_allowlist_enabled=True,
    )
    assert compute_security_score(auth, provisioning=False) == 100
