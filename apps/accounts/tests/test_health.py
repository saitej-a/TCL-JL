"""T1.7 health probe tests (T1.12-style smoke coverage for Phase 1)."""

import socket
from unittest import mock

import pytest
from django.test import Client
from django.urls import reverse


@pytest.fixture
def client_no_csrf(db) -> Client:
    return Client()


class TestLiveness:
    def test_returns_200_alive(self, client_no_csrf):
        resp = client_no_csrf.get(reverse("health"))
        assert resp.status_code == 200
        assert resp.json() == {"status": "alive"}


class TestReadiness:
    def test_returns_200_when_dependencies_ok(self, client_no_csrf, db):
        resp = client_no_csrf.get(reverse("health-ready"))
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "ok"
        assert body["database"] == "ok"
        assert body["cache"] == "ok"

    def test_returns_503_naming_database_when_db_down(self, client_no_csrf, db):
        with mock.patch(
            "config.views._check_database",
            side_effect=socket.gaierror("db unreachable"),
        ):
            resp = client_no_csrf.get(reverse("health-ready"))
        assert resp.status_code == 503
        body = resp.json()
        assert body["status"] == "not_ready"
        assert body["database"].startswith("down:")
        assert body["cache"] == "ok"  # healthy component still reported

    def test_returns_503_naming_cache_when_cache_down(self, client_no_csrf, db):
        with mock.patch(
            "config.views._check_cache",
            side_effect=ConnectionError("cache unreachable"),
        ):
            resp = client_no_csrf.get(reverse("health-ready"))
        assert resp.status_code == 503
        body = resp.json()
        assert body["database"] == "ok"
        assert body["cache"].startswith("down:")
