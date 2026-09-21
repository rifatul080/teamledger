"""Auth: signup tests."""
from __future__ import annotations

import pytest


@pytest.mark.req_id("AUTH-01")
def test_signup_happy(client) -> None:
    r = client.post(
        "/api/v1/auth/signup",
        json={
            "email": "alice@example.org",
            "password": "Password1Demo",
            "display_name": "Alice",
            "timezone": "UTC",
        },
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["email"] == "alice@example.org"
    assert body["display_name"] == "Alice"


@pytest.mark.req_id("AUTH-01")
def test_signup_dup_email_conflict(client) -> None:
    payload = {
        "email": "dup@example.org",
        "password": "Password1Demo",
        "display_name": "Dup",
        "timezone": "UTC",
    }
    r1 = client.post("/api/v1/auth/signup", json=payload)
    assert r1.status_code == 201
    r2 = client.post("/api/v1/auth/signup", json=payload)
    assert r2.status_code == 409


@pytest.mark.req_id("AUTH-01")
def test_signup_weak_password_rejected(client) -> None:
    r = client.post(
        "/api/v1/auth/signup",
        json={"email": "weak@example.org", "password": "short", "display_name": "W", "timezone": "UTC"},
    )
    assert r.status_code == 422
    body = r.json()
    assert body["code"] == "req.invalid"


@pytest.mark.req_id("AUTH-01")
def test_signup_invalid_email_rejected(client) -> None:
    r = client.post(
        "/api/v1/auth/signup",
        json={"email": "not-an-email", "password": "Password1Demo", "display_name": "X", "timezone": "UTC"},
    )
    assert r.status_code == 422


@pytest.mark.req_id("AUTH-01")
def test_signup_at_normalizes_email(client) -> None:
    """Different casing should be treated as duplicates (emails are stored lowercased)."""
    r = client.post(
        "/api/v1/auth/signup",
        json={"email": "Mixed@Example.org", "password": "Password1Demo", "display_name": "M", "timezone": "UTC"},
    )
    assert r.status_code == 201
    body = r.json()
    assert body["email"] == "mixed@example.org"
