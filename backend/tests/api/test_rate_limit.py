"""Rate limit tests."""
from __future__ import annotations

import pytest


@pytest.mark.req_id("AUTH-07")
def test_login_rate_limit(client) -> None:
    r = client.post(
        "/api/v1/auth/signup",
        json={"email": "rl@example.org", "password": "Password1Demo", "display_name": "U", "timezone": "UTC"},
    )
    assert r.status_code == 201
    statuses: list[int] = []
    for _ in range(20):
        r = client.post("/api/v1/auth/login", json={"email": "rl@example.org", "password": "wrong"})
        statuses.append(r.status_code)
    assert 429 in statuses


@pytest.mark.req_id("AUTH-07")
def test_reset_rate_limit_per_min(client) -> None:
    statuses: list[int] = []
    for _ in range(20):
        r = client.post("/api/v1/auth/password/reset", json={"email": "noone@example.org"})
        statuses.append(r.status_code)
    assert 429 in statuses
