"""Shared auth test helpers."""
from __future__ import annotations

from typing import Any


class AuthedClient:
    """Wraps a TestClient and lazily logs in once, reusing cookies.

    TestClient does not auto-forward httponly cookies between requests in some
    configurations. This helper logs in once per instance and re-uses the
    cookies on subsequent calls. A request returning 401 forces a fresh login.
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

    def _do(self, method: str, path: str, **kw: Any):  # type: ignore[no-untyped-def]
        if not self._cookies:
            self._login()
        r = getattr(self._c, method)(path, cookies=self._cookies, **kw)
        if r.status_code == 401:
            # Cookies stale (e.g. across test boundary) — log in once more.
            self._login()
            r = getattr(self._c, method)(path, cookies=self._cookies, **kw)
        return r

    def get(self, path: str, **kw: Any):  # type: ignore[no-untyped-def]
        return self._do("get", path, **kw)

    def post(self, path: str, **kw: Any):  # type: ignore[no-untyped-def]
        return self._do("post", path, **kw)

    def patch(self, path: str, **kw: Any):  # type: ignore[no-untyped-def]
        return self._do("patch", path, **kw)

    def delete(self, path: str, **kw: Any):  # type: ignore[no-untyped-def]
        return self._do("delete", path, **kw)

    def put(self, path: str, **kw: Any):  # type: ignore[no-untyped-def]
        return self._do("put", path, **kw)


def signup(client: Any, email: str, display: str = "U") -> None:
    r = client.post(
        "/api/v1/auth/signup",
        json={"email": email, "password": "Password1Demo", "display_name": display, "timezone": "UTC"},
    )
    assert r.status_code == 201, f"signup failed for {email}: {r.text}"
