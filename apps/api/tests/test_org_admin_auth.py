"""Admin auth on organization routes."""
from __future__ import annotations

import os
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.main import create_app

_ADMIN_HEADERS = {"X-Admin-Token": "secret"}


@pytest.fixture
def client() -> TestClient:
    return TestClient(create_app())


def test_org_routes_open_in_debug(client: TestClient) -> None:
    with patch.dict(os.environ, {"DEBUG": "true", "NORAD_ADMIN_TOKEN": "secret"}, clear=False):
        from app.core.config import get_settings

        get_settings.cache_clear()
        try:
            res = client.get("/api/admin/organizations")
            assert res.status_code == 200
            assert "items" in res.json()
        finally:
            get_settings.cache_clear()


def test_org_routes_require_token_in_prod(client: TestClient) -> None:
    with patch.dict(os.environ, {"DEBUG": "false", "NORAD_ADMIN_TOKEN": "secret"}, clear=False):
        from app.core.config import get_settings

        get_settings.cache_clear()
        try:
            assert client.get("/api/admin/organizations").status_code == 401
            assert (
                client.get("/api/admin/organizations", headers=_ADMIN_HEADERS).status_code
                == 200
            )
        finally:
            get_settings.cache_clear()
