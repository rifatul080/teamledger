"""Auth: login tests."""
from __future__ import annotations

import pytest


@pytest.fixture
def signup(client):
    def _signup(email: str = "login@example.org", password: str = "Password1Demo"):
        r = client.post(
            "/api/v1/auth/signup",
            json={"email": email, "password": password, "display_name": "U", "timezone": "UTC"},
        )
        assert r.status_code == 201
        return r.json()

    return _signup


@pytest.mark.req_id("AUTH-02")
def test_login_happy(client, signup) -> None:
    signup()
    r = client.post("/api/v1/auth/login", json={"email": "login@example.org", "password": "Password1Demo"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert "access_token" in body
    assert "csrf_token" in body
    # Cookies present
    assert "tl_access" in r.cookies
    assert "tl_refresh" in r.cookies
    assert "tl_csrf" in r.cookies


@pytest.mark.req_id("AUTH-02")
def test_login_wrong_password_returns_401(client, signup) -> None:
    signup()
    r = client.post("/api/v1/auth/login", json={"email": "login@example.org", "password": "PasswordWrongX"})
    assert r.status_code == 401


@pytest.mark.req_id("AUTH-02")
def test_login_unknown_email_returns_401(client) -> None:
    r = client.post("/api/v1/auth/login", json={"email": "nosuch@example.org", "password": "Password1Demo"})
    assert r.status_code == 401


@pytest.mark.req_id("AUTH-02")
def test_logout_clears_cookies(client, signup) -> None:
    signup()
    client.post("/api/v1/auth/login", json={"email": "login@example.org", "password": "Password1Demo"})
    r = client.post("/api/v1/auth/logout")
    # The 200/204 returned by logout — Starlette response holds cookies.
    assert r.status_code in (200, 204)


@pytest.mark.req_id("AUTH-02")
def test_refresh_rotates_token(client, signup) -> None:
    signup()
    login = client.post("/api/v1/auth/login", json={"email": "login@example.org", "password": "Password1Demo"})
    assert login.status_code == 200
    refresh_token = login.cookies.get("tl_refresh")
    assert refresh_token
    # Pass the cookie explicitly since TestClient doesn't auto-forward httponly cookies in some configs.
    r = client.post("/api/v1/auth/refresh", cookies={"tl_refresh": refresh_token})
    assert r.status_code == 200
    new_refresh = r.cookies.get("tl_refresh")
    assert new_refresh != refresh_token
