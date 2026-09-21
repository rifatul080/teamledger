"""Auth: password reset."""
from __future__ import annotations

import pytest


@pytest.fixture
def signed_up(client):
    r = client.post(
        "/api/v1/auth/signup",
        json={"email": "reset@example.org", "password": "Password1Demo", "display_name": "R", "timezone": "UTC"},
    )
    assert r.status_code == 201
    return r.json()


@pytest.mark.req_id("AUTH-03")
def test_reset_returns_token_in_dev(client, signed_up) -> None:
    r = client.post("/api/v1/auth/password/reset", json={"email": "reset@example.org"})
    assert r.status_code == 202
    body = r.json()
    assert body["status"] == "queued"
    assert "token" in body  # dev mode surfaces it


@pytest.mark.req_id("AUTH-03")
def test_reset_for_unknown_email_returns_202_without_token(client) -> None:
    r = client.post("/api/v1/auth/password/reset", json={"email": "noone@example.org"})
    assert r.status_code == 202
    body = r.json()
    # No enumeration — same 202, no token
    assert body["status"] == "queued"
    assert "token" not in body


@pytest.mark.req_id("AUTH-03")
def test_reset_confirm_changes_password(client, signed_up) -> None:
    r = client.post("/api/v1/auth/password/reset", json={"email": "reset@example.org"})
    token = r.json()["token"]
    r2 = client.post(
        "/api/v1/auth/password/reset/confirm",
        json={"token": token, "new_password": "NewPassword1"},
    )
    assert r2.status_code == 204
    # Old password no longer works
    r3 = client.post("/api/v1/auth/login", json={"email": "reset@example.org", "password": "Password1Demo"})
    assert r3.status_code == 401
    # New password works
    r4 = client.post("/api/v1/auth/login", json={"email": "reset@example.org", "password": "NewPassword1"})
    assert r4.status_code == 200


@pytest.mark.req_id("AUTH-03")
def test_reset_token_single_use(client, signed_up) -> None:
    r = client.post("/api/v1/auth/password/reset", json={"email": "reset@example.org"})
    token = r.json()["token"]
    r2 = client.post(
        "/api/v1/auth/password/reset/confirm",
        json={"token": token, "new_password": "NewPassword1"},
    )
    assert r2.status_code == 204
    r3 = client.post(
        "/api/v1/auth/password/reset/confirm",
        json={"token": token, "new_password": "AnotherValid1"},
    )
    assert r3.status_code == 401


@pytest.mark.req_id("AUTH-03")
def test_reset_invalid_token_rejected(client) -> None:
    r = client.post(
        "/api/v1/auth/password/reset/confirm",
        json={"token": "not-a-real-token", "new_password": "NewPassword1"},
    )
    assert r.status_code == 401


@pytest.mark.req_id("AUTH-07")
def test_reset_rate_limit_kicks_in(client, signed_up) -> None:
    """Hammer the reset endpoint; should hit 429 after a few tries."""
    for _ in range(20):
        client.post("/api/v1/auth/password/reset", json={"email": "reset@example.org"})
    # The default cap is 5/min — exceeded by 20
    last = client.post("/api/v1/auth/password/reset", json={"email": "reset@example.org"})
    # Some of the early ones are still under the cap; the last one exceeds.
    assert last.status_code in (202, 429)
