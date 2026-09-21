"""Security headers and error envelope tests."""
from __future__ import annotations

import pytest


@pytest.mark.req_id("AUTH-06")
def test_security_headers_on_health(client) -> None:
    r = client.get("/healthz")
    assert r.status_code == 200
    assert r.headers["X-Content-Type-Options"] == "nosniff"
    assert r.headers["X-Frame-Options"] == "DENY"
    assert r.headers["Referrer-Policy"] == "same-origin"


@pytest.mark.req_id("AUTH-06")
def test_error_envelope_shape(client) -> None:
    r = client.get("/api/v1/auth/login")  # GET unsupported
    # 405 from FastAPI; envelope wrapper turns it into code/http.error
    assert r.status_code in (405, 422)
    body = r.json()
    assert "code" in body
    assert "message" in body


@pytest.mark.req_id("AUTH-06")
def test_request_id_in_response(client) -> None:
    r = client.get("/healthz", headers={"X-Request-Id": "abc-123"})
    assert r.headers["X-Request-Id"] == "abc-123"
