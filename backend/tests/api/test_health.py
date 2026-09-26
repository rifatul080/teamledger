"""Health / readiness probes (docs/deployment.md § Health, liveness, readiness).

These endpoints are the supported scrape targets for uptime monitors and
keep-alive pings, so the contract they expose is worth locking down.
"""
from __future__ import annotations

import pytest


@pytest.mark.req_id("OPS-01")
def test_liveness_ok(client) -> None:
    r = client.get("/api/v1/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["service"] == "teamledger-api"


@pytest.mark.req_id("OPS-01")
def test_liveness_needs_no_auth(client) -> None:
    # A probe must work without cookies or an Authorization header.
    assert client.get("/api/v1/health").status_code == 200


@pytest.mark.req_id("OPS-01")
def test_readiness_reports_database_and_migration(client) -> None:
    r = client.get("/api/v1/health/db")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["database"] == "ok"
    # The db_engine fixture runs `alembic upgrade head`, so a revision exists.
    assert body["migration"]


@pytest.mark.req_id("OPS-01")
def test_readiness_returns_503_when_database_unreachable(client, app) -> None:
    """A dead database must surface as 503 + the standard error envelope."""
    from app.api import deps

    class _BrokenSession:
        def execute(self, *_args, **_kwargs):
            raise RuntimeError("connection refused")

        def close(self) -> None:  # pragma: no cover - teardown only
            pass

    def _broken_db():
        yield _BrokenSession()

    app.dependency_overrides[deps.get_db] = _broken_db
    try:
        r = client.get("/api/v1/health/db")
    finally:
        app.dependency_overrides.pop(deps.get_db, None)

    assert r.status_code == 503
    body = r.json()
    assert body["code"] == "db.unavailable"
    assert body["message"]
