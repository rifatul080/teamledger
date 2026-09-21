"""Shared auth test helpers."""
from __future__ import annotations

from typing import Any


class AuthedClient:
    """Wraps a TestClient and re-logins before each request.

    TestClient does not auto-forward httponly cookies between requests in some
    configurations. This helper logs in fresh and passes the cookies back to
    every call.
    """

    def __init__(self, client: Any, email: str, password: str = "Password1Demo") -> None:
        self._c = client
        self._email = email
        self._password = password
        self._cookies: dict[str, str] = {}

    def _login(self) -> None:
        r = self._c.post("/api/v1/auth/login", json={"email": self._email, "password": self._password})
        assert r.status_code == 200, f"login failed for {self._email}: {r.status_code} {r.text}"
        self._cookies = {
            "tl_access": r.cookies.get("tl_access"),
            "tl_refresh": r.cookies.get("tl_refresh"),
            "tl_csrf": r.cookies.get("tl_csrf"),
        }

    def get(self, path: str, **kw: Any):  # type: ignore[no-untyped-def]
        self._login()
        return self._c.get(path, cookies=self._cookies, **kw)

    def post(self, path: str, **kw: Any):  # type: ignore[no-untyped-def]
        self._login()
        return self._c.post(path, cookies=self._cookies, **kw)

    def patch(self, path: str, **kw: Any):  # type: ignore[no-untyped-def]
        self._login()
        return self._c.patch(path, cookies=self._cookies, **kw)

    def delete(self, path: str, **kw: Any):  # type: ignore[no-untyped-def]
        self._login()
        return self._c.delete(path, cookies=self._cookies, **kw)

    def put(self, path: str, **kw: Any):  # type: ignore[no-untyped-def]
        self._login()
        return self._c.put(path, cookies=self._cookies, **kw)


def signup(client: Any, email: str, display: str = "U") -> None:
    r = client.post(
        "/api/v1/auth/signup",
        json={"email": email, "password": "Password1Demo", "display_name": display, "timezone": "UTC"},
    )
    assert r.status_code == 201, f"signup failed for {email}: {r.text}"
