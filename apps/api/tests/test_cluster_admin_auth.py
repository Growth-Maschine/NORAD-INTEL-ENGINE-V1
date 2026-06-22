"""Tests for admin auth on all 5 cluster routes (Phase 0)."""
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


def test_cluster_routes_open_in_debug(client: TestClient) -> None:
    with patch.dict(os.environ, {"DEBUG": "true", "NORAD_ADMIN_TOKEN": "secret"}, clear=False):
        from app.core.config import get_settings

        get_settings.cache_clear()
        try:
            res = client.post(
                "/api/web-discovery/clusters",
                json={"name": "Auth Test Cluster"},
            )
            assert res.status_code == 201
            cluster_id = res.json()["id"]
            assert client.get(f"/api/web-discovery/clusters/{cluster_id}").status_code == 200
            assert client.get("/api/web-discovery/clusters").status_code == 200
            client.delete(f"/api/web-discovery/clusters/{cluster_id}")
        finally:
            get_settings.cache_clear()


def test_cluster_routes_require_token_in_prod(client: TestClient) -> None:
    with patch.dict(os.environ, {"DEBUG": "false", "NORAD_ADMIN_TOKEN": "secret"}, clear=False):
        from app.core.config import get_settings

        get_settings.cache_clear()
        try:
            assert client.get("/api/web-discovery/clusters").status_code == 401
            assert client.post(
                "/api/web-discovery/clusters",
                json={"name": "Should Fail"},
            ).status_code == 401

            created = client.post(
                "/api/web-discovery/clusters",
                json={"name": "Auth Test Cluster Prod"},
                headers=_ADMIN_HEADERS,
            )
            assert created.status_code == 201
            cluster_id = created.json()["id"]

            assert (
                client.get(
                    f"/api/web-discovery/clusters/{cluster_id}",
                    headers=_ADMIN_HEADERS,
                ).status_code
                == 200
            )
            assert (
                client.get("/api/web-discovery/clusters", headers=_ADMIN_HEADERS).status_code
                == 200
            )

            client.delete(
                f"/api/web-discovery/clusters/{cluster_id}",
                headers=_ADMIN_HEADERS,
            )
        finally:
            get_settings.cache_clear()
