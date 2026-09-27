"""Social sign-in: capability probe, start redirect, and the callback session."""
from __future__ import annotations

import pytest
from _helpers import signup


def _configure(monkeypatch) -> None:
    from app.core.config import get_settings

    monkeypatch.setenv("GOOGLE_CLIENT_ID", "google-id")
    monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "google-secret")
    monkeypatch.setenv("FACEBOOK_CLIENT_ID", "fb-id")
    monkeypatch.setenv("FACEBOOK_CLIENT_SECRET", "fb-secret")
    get_settings.cache_clear()


# --------------------------------------------------------------------------
# Capability probe
# --------------------------------------------------------------------------


def test_providers_reports_both_disabled_by_default(client) -> None:
    r = client.get("/api/v1/auth/oauth/providers")
    assert r.status_code == 200, r.text
    ids = {p["id"]: p["configured"] for p in r.json()["providers"]}
    assert ids == {"google": False, "facebook": False}


def test_providers_reports_configured_after_env(client, monkeypatch) -> None:
    _configure(monkeypatch)
    r = client.get("/api/v1/auth/oauth/providers")
    ids = {p["id"]: p["configured"] for p in r.json()["providers"]}
    assert ids == {"google": True, "facebook": True}


# --------------------------------------------------------------------------
# Start
# --------------------------------------------------------------------------


def test_start_unknown_provider_404(client, monkeypatch) -> None:
    _configure(monkeypatch)
    r = client.get("/api/v1/auth/oauth/myspace", follow_redirects=False)
    assert r.status_code == 404, r.text


def test_start_unconfigured_provider_503(client) -> None:
    r = client.get("/api/v1/auth/oauth/google", follow_redirects=False)
    assert r.status_code == 503
    assert "not configured" in r.json()["message"]


def test_start_redirects_to_google_with_state(client, monkeypatch) -> None:
    _configure(monkeypatch)
    r = client.get("/api/v1/auth/oauth/google", follow_redirects=False)
    assert r.status_code == 302, r.text
    assert r.headers["location"].startswith("https://accounts.google.com/o/oauth2/v2/auth")
    assert "client_id=google-id" in r.headers["location"]
    assert "state=" in r.headers["location"]
    assert "tl_oauth_state" in r.cookies
    # The state in the URL is the one we stored in the cookie.
    state = r.cookies.get("tl_oauth_state")
    assert state and f"state={state}" in r.headers["location"]


def test_start_facebook_redirect(client, monkeypatch) -> None:
    _configure(monkeypatch)
    r = client.get("/api/v1/auth/oauth/Facebook", follow_redirects=False)
    assert r.status_code == 302, r.text
    assert r.headers["location"].startswith("https://www.facebook.com/")


# --------------------------------------------------------------------------
# Callback
# --------------------------------------------------------------------------


def _start(client, provider: str = "google") -> str:
    r = client.get(f"/api/v1/auth/oauth/{provider}", follow_redirects=False)
    assert r.status_code == 302, r.text
    return r.cookies.get("tl_oauth_state") or ""


def test_callback_without_state_ignored(client, monkeypatch) -> None:
    _configure(monkeypatch)
    r = client.get(
        "/api/v1/auth/oauth/google/callback?code=abc&state=forged",
        follow_redirects=False,
    )
    assert r.status_code == 302
    assert "/login?error=state" in r.headers["location"]


def test_callback_creates_user_and_sets_session(client, monkeypatch) -> None:
    _configure(monkeypatch)
    import app.api.v1.oauth as oauth_mod

    monkeypatch.setattr(oauth_mod, "exchange_code", lambda *a, **k: "tok")
    monkeypatch.setattr(
        oauth_mod, "fetch_profile", lambda *a, **k: ("ada@example.org", "Ada Lovelace")
    )

    state = _start(client)
    r = client.get(
        f"/api/v1/auth/oauth/google/callback?code=abc&state={state}",
        follow_redirects=False,
    )
    assert r.status_code == 302, r.text
    assert r.headers["location"].endswith("/dashboard")
    assert r.cookies.get("tl_access")
    assert r.cookies.get("tl_refresh")
    assert r.cookies.get("tl_csrf")

    # The session works: /me is the new account.
    me = client.get("/api/v1/me")
    assert me.status_code == 200, me.text
    assert me.json()["email"] == "ada@example.org"
    assert me.json()["display_name"] == "Ada Lovelace"
    assert me.json()["email_verified"] is True



def test_callback_links_an_existing_account(client, monkeypatch) -> None:
    _configure(monkeypatch)
    signup(client, "ada@example.org", "Ada")
    import app.api.v1.oauth as oauth_mod

    monkeypatch.setattr(oauth_mod, "exchange_code", lambda *a, **k: "tok")
    monkeypatch.setattr(oauth_mod, "fetch_profile", lambda *a, **k: ("ada@example.org", "Ada L."))

    state = _start(client)
    r = client.get(
        f"/api/v1/auth/oauth/google/callback?code=abc&state={state}",
        follow_redirects=False,
    )
    assert r.status_code == 302, r.text
    me = client.get("/api/v1/me").json()
    assert me["email"] == "ada@example.org"
    # The existing display name is not overwritten by the provider.
    assert me["display_name"] == "Ada"
    assert me["email_verified"] is True


def test_callback_surfaces_provider_errors(client, monkeypatch) -> None:
    _configure(monkeypatch)
    import app.api.v1.oauth as oauth_mod

    monkeypatch.setattr(oauth_mod, "exchange_code", lambda *a, **k: "tok")

    def _no_email(*_a, **_k):
        from app.core.errors import AppError

        raise AppError(status_code=400, code="oauth.no_email", message="no email")

    monkeypatch.setattr(oauth_mod, "fetch_profile", _no_email)
    state = _start(client)
    r = client.get(
        f"/api/v1/auth/oauth/google/callback?code=abc&state={state}",
        follow_redirects=False,
    )
    # The provider error surfaces as a normal API error and no session is made.
    assert r.status_code == 400, r.text
    assert r.json()["code"] == "oauth.no_email"
    assert client.get("/api/v1/me").status_code == 401


def test_oauth_created_user_cannot_sign_in_with_a_password(client, monkeypatch) -> None:
    """The generated secret is unusable as a password."""
    _configure(monkeypatch)
    import app.api.v1.oauth as oauth_mod

    monkeypatch.setattr(oauth_mod, "exchange_code", lambda *a, **k: "tok")
    monkeypatch.setattr(oauth_mod, "fetch_profile", lambda *a, **k: ("bob@example.org", "Bob"))
    state = _start(client)
    client.get(
        f"/api/v1/auth/oauth/google/callback?code=abc&state={state}",
        follow_redirects=False,
    )
    client.cookies.clear()
    r = client.post(
        "/api/v1/auth/login", json={"email": "bob@example.org", "password": "Password1Demo"}
    )
    assert r.status_code == 401, r.text


# --------------------------------------------------------------------------
# Pure helpers
# --------------------------------------------------------------------------


def test_build_authorize_url_includes_redirect_uri(monkeypatch) -> None:
    from app.core.config import get_settings
    from app.core.oauth import FACEBOOK, build_authorize_url, providers

    _configure(monkeypatch)
    monkeypatch.setenv("OAUTH_REDIRECT_BASE", "https://api.example.com")
    get_settings.cache_clear()
    url = build_authorize_url(providers()[FACEBOOK], state="st", settings=get_settings())
    assert "redirect_uri=https%3A%2F%2Fapi.example.com%2Fapi%2Fv1%2Fauth%2Foauth%2Ffacebook%2Fcallback" in url
    assert "state=st" in url


def test_profile_fields_google_and_facebook() -> None:
    from app.core.errors import AppError
    from app.core.oauth import FACEBOOK, GOOGLE, _profile_fields

    assert _profile_fields(GOOGLE, {"email": "A@Example.com", "name": "Ada"}) == (
        "a@example.com",
        "Ada",
    )
    assert _profile_fields(FACEBOOK, {"email": "b@example.com", "name": "Bo"}) == (
        "b@example.com",
        "Bo",
    )
    with pytest.raises(AppError):
        _profile_fields(GOOGLE, {"name": "No Email"})
