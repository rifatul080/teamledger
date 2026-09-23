"""v2 — profile, avatars, institution hint, email verification, signup rate limit."""
from __future__ import annotations

import io

from PIL import Image

from tests.api._helpers import AuthedClient, signup


def _png_bytes(w=8, h=8):
    buf = io.BytesIO()
    Image.new("RGB", (w, h), (200, 100, 50)).save(buf, format="PNG")
    return buf.getvalue()


def _jpeg_bytes(w=8, h=8):
    buf = io.BytesIO()
    Image.new("RGB", (w, h), (200, 100, 50)).save(buf, format="JPEG")
    return buf.getvalue()


def test_institution_hint_academic_domain(client):
    r = client.get("/api/v1/auth/institution-hint", params={"email": "alice@cs.ox.ac.uk"})
    assert r.status_code == 200
    assert r.json().get("hint") in {"UK university", "Educational institution"}


def test_institution_hint_non_academic_is_null(client):
    r = client.get("/api/v1/auth/institution-hint", params={"email": "bob@gmail.com"})
    assert r.status_code == 200
    assert r.json().get("hint") in (None,)


def test_signup_creates_user_with_email_unverified(client):
    r = client.post(
        "/api/v1/auth/signup",
        json={
            "email": "new@example.org",
            "password": "VeryStrongPassword1",
            "display_name": "New Person",
            "institution": "ETH",
        },
    )
    assert r.status_code == 201
    body = r.json()
    assert body["email_verified"] is False
    assert body["institution"] == "ETH"
    assert body["avatar_url"] is None


def test_avatar_upload_and_download(client):
    signup(client, "ava@example.org")
    h = AuthedClient(client, "ava@example.org")
    files = {"file": ("avatar.png", _png_bytes(64, 64), "image/png")}
    r = h.post("/api/v1/me/avatar", files=files)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["avatar_url"].startswith("/api/v1/users/")
    r2 = client.get(body["avatar_url"])
    assert r2.status_code == 200
    assert r2.headers["content-type"] in (
        "image/png",
        "image/jpeg",
        "image/gif",
        "image/webp",
    )


def test_avatar_upload_jpeg(client):
    """Regression: JPEG bytes used to crash with KeyError: 'JPG' because
    PIL's format key is 'JPEG', not 'JPG'."""
    signup(client, "jp@example.org")
    h = AuthedClient(client, "jp@example.org")
    files = {"file": ("avatar.jpg", _jpeg_bytes(64, 64), "image/jpeg")}
    r = h.post("/api/v1/me/avatar", files=files)
    assert r.status_code == 200, r.text


def test_avatar_upload_rejects_non_image_bytes(client):
    signup(client, "bad@example.org")
    h = AuthedClient(client, "bad@example.org")
    files = {"file": ("evil.png", b"not actually png", "image/png")}
    r = h.post("/api/v1/me/avatar", files=files)
    assert r.status_code in (400, 422)


def test_email_verification_invalid_token_401(client):
    r = client.post("/api/v1/auth/verify-email", json={"token": "this-does-not-exist"})
    assert r.status_code == 401


def test_resend_verification_requires_auth(client):
    r = client.post("/api/v1/auth/resend-verification")
    assert r.status_code in (401, 403)


def test_search_endpoint_returns_empty_for_new_user(client):
    signup(client, "searcher@example.org", "Searcher")
    h = AuthedClient(client, "searcher@example.org")
    r = h.get("/api/v1/search", params={"q": "nope"})
    assert r.status_code == 200
    body = r.json()
    assert body["tasks"] == [] and body["messages"] == [] and body["files"] == []


def test_activity_feed_empty_for_new_user(client):
    signup(client, "quiet@example.org")
    h = AuthedClient(client, "quiet@example.org")
    r = h.get("/api/v1/activity")
    assert r.status_code == 200
    body = r.json()
    assert body["items"] == []
    assert body["unread"] == 0
