"""Profile /me tests."""
from __future__ import annotations

import pytest


class _AuthedClient:
    def __init__(self, client, email: str) -> None:
        self._c = client
        self._email = email
        self._cookies: dict[str, str] = {}

    def _login(self) -> None:
        r = self._c.post("/api/v1/auth/login", json={"email": self._email, "password": "Password1Demo"})
        assert r.status_code == 200
        self._cookies = {
            "tl_access": r.cookies.get("tl_access"),
            "tl_refresh": r.cookies.get("tl_refresh"),
            "tl_csrf": r.cookies.get("tl_csrf"),
        }

    def get(self, path: str):
        self._login()
        return self._c.get(path, cookies=self._cookies)

    def patch(self, path: str, body: dict):
        self._login()
        return self._c.patch(path, json=body, cookies=self._cookies)


@pytest.fixture
def auth_client(client):
    client.post(
        "/api/v1/auth/signup",
        json={"email": "me@example.org", "password": "Password1Demo", "display_name": "Me", "timezone": "UTC"},
    )
    return _AuthedClient(client, "me@example.org")


@pytest.mark.req_id("AUTH-04")
def test_get_me_returns_profile(auth_client) -> None:
    r = auth_client.get("/api/v1/me")
    assert r.status_code == 200
    body = r.json()
    assert body["email"] == "me@example.org"
    assert body["display_name"] == "Me"


@pytest.mark.req_id("AUTH-04")
def test_update_display_name(auth_client) -> None:
    r = auth_client.patch("/api/v1/me", {"display_name": "Updated Name"})
    assert r.status_code == 200
    assert r.json()["display_name"] == "Updated Name"


@pytest.mark.req_id("AUTH-04")
def test_update_timezone(auth_client) -> None:
    r = auth_client.patch("/api/v1/me", {"timezone": "America/New_York"})
    assert r.status_code == 200
    assert r.json()["timezone"] == "America/New_York"


@pytest.mark.req_id("AUTH-04")
def test_me_requires_auth(client) -> None:
    r = client.get("/api/v1/me")
    assert r.status_code == 401
