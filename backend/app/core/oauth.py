"""Social sign-in: Google and Facebook via the OAuth 2.0 authorization-code flow.

Written directly on ``httpx`` (already a dependency) so both providers share
one code path and the project gains no new library. Everything is driven by
environment configuration — a provider with no client id is simply not
advertised and its endpoints refuse to start, which keeps local development and
CI working without provider secrets.
"""
from __future__ import annotations

import logging
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlencode

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..core.config import Settings, get_settings
from ..core.errors import AppError
from ..core.ids import new_id
from ..core.security import hash_password
from ..models.user import User

log = logging.getLogger("teamledger.oauth")

GOOGLE = "google"
FACEBOOK = "facebook"


@dataclass(frozen=True)
class OAuthProvider:
    id: str
    label: str
    client_id: str
    client_secret: str
    authorize_url: str
    token_url: str
    profile_url: str
    scopes: str

    @property
    def configured(self) -> bool:
        return bool(self.client_id and self.client_secret)


def providers(settings: Settings | None = None) -> dict[str, OAuthProvider]:
    s = settings or get_settings()
    return {
        GOOGLE: OAuthProvider(
            id=GOOGLE,
            label="Google",
            client_id=s.google_client_id,
            client_secret=s.google_client_secret,
            authorize_url="https://accounts.google.com/o/oauth2/v2/auth",
            # These are public, well-known endpoint URLs, not credentials —
            # B106's "looks like a password" heuristic fires on `token_url=`.
            # The actual secrets (client_id/client_secret) come from Settings.
            token_url="https://oauth2.googleapis.com/token",  # nosec B106
            profile_url="https://www.googleapis.com/oauth2/v3/userinfo",
            scopes="openid email profile",
        ),
        FACEBOOK: OAuthProvider(
            id=FACEBOOK,
            label="Facebook",
            client_id=s.facebook_client_id,
            client_secret=s.facebook_client_secret,
            authorize_url="https://www.facebook.com/v20.0/dialog/oauth",
            token_url="https://graph.facebook.com/v20.0/oauth/access_token",  # nosec B106
            profile_url="https://graph.facebook.com/me?fields=id,name,email",
            scopes="email,public_profile",
        ),
    }


def get_provider(provider_id: str, settings: Settings | None = None) -> OAuthProvider:
    table = providers(settings)
    provider = table.get(provider_id.lower())
    if provider is None:
        raise AppError(status_code=404, code="oauth.unknown_provider", message="Unknown provider.")
    if not provider.configured:
        raise AppError(
            status_code=503,
            code="oauth.not_configured",
            message=f"{provider.label} sign-in is not configured on this server.",
        )
    return provider




def exchange_code(
    provider: OAuthProvider,
    code: str,
    *,
    settings: Settings | None = None,
    client: httpx.Client | None = None,
) -> str:
    """Trade the authorization code for an access token."""
    data = {
        "client_id": provider.client_id,
        "client_secret": provider.client_secret,
        "code": code,
        "grant_type": "authorization_code",
        "redirect_uri": redirect_uri(provider.id, settings),
    }
    headers = {"Accept": "application/json"}
    try:
        if client is not None:
            resp = client.post(provider.token_url, data=data, headers=headers)
        else:
            with httpx.Client(timeout=10) as c:
                resp = c.post(provider.token_url, data=data, headers=headers)
    except httpx.HTTPError as e:
        log.warning("oauth token request failed: %s", e)
        raise AppError(
            status_code=502, code="oauth.provider_unreachable", message="Could not reach the provider."
        ) from e
    if resp.status_code >= 400:
        log.warning("oauth token exchange rejected: %s %s", resp.status_code, resp.text[:200])
        raise AppError(
            status_code=400, code="oauth.exchange_failed", message="Sign-in could not be completed."
        )
    token = resp.json().get("access_token")
    if not isinstance(token, str) or not token:
        raise AppError(
            status_code=400, code="oauth.exchange_failed", message="Sign-in could not be completed."
        )
    return token


def fetch_profile(
    provider: OAuthProvider,
    access_token: str,
    *,
    client: httpx.Client | None = None,
) -> tuple[str, str]:
    """Return ``(email, display_name)`` for the authenticated account."""
    headers = {"Authorization": f"Bearer {access_token}", "Accept": "application/json"}
    try:
        if client is not None:
            resp = client.get(provider.profile_url, headers=headers)
        else:
            with httpx.Client(timeout=10) as c:
                resp = c.get(provider.profile_url, headers=headers)
    except httpx.HTTPError as e:
        log.warning("oauth profile request failed: %s", e)
        raise AppError(
            status_code=502, code="oauth.provider_unreachable", message="Could not reach the provider."
        ) from e
    if resp.status_code >= 400:
        log.warning("oauth profile rejected: %s %s", resp.status_code, resp.text[:200])
        raise AppError(
            status_code=400, code="oauth.profile_failed", message="Sign-in could not be completed."
        )
    return _profile_fields(provider.id, resp.json())


def _profile_fields(provider_id: str, payload: dict[str, Any]) -> tuple[str, str]:
    if provider_id == GOOGLE:
        email = payload.get("email")
        name = payload.get("name") or payload.get("given_name") or ""
    else:
        email = payload.get("email")
        name = payload.get("name") or ""
    if not isinstance(email, str) or "@" not in email:
        # Without an address we cannot key the account; the user must grant
        # the email scope.
        raise AppError(
            status_code=400,
            code="oauth.no_email",
            message="This account did not share an email address.",
        )
    return email.lower(), str(name)[:120] or email.split("@")[0]


def upsert_oauth_user(db: Session, *, email: str, display_name: str) -> User:
    """Find the account by email, or create a verified, password-less one."""
    user = db.scalars(select(User).where(User.email == email)).one_or_none()
    now = datetime.now(tz=UTC)
    if user is not None:
        if not user.is_active:
            raise AppError(
                status_code=403, code="auth.disabled", message="This account is disabled."
            )
        # The provider vouched for the address, so treat it as verified.
        if not user.email_verified:
            user.email_verified = True
        user.last_login_at = now
        db.flush()
        return user

    # password_hash is NOT NULL: store a hash of a random secret so the account
    # can never be signed into with a password.
    user = User(
        id=new_id(),
        email=email,
        display_name=display_name or email.split("@")[0],
        timezone="UTC",
        password_hash=hash_password(secrets.token_urlsafe(32)),
        is_active=True,
        email_verified=True,
        last_login_at=now,
        created_at=now,
    )
    db.add(user)
    db.flush()
    return user

def redirect_base(settings: Settings | None = None) -> str:
    s = settings or get_settings()
    return (s.oauth_redirect_base or s.public_base_url).rstrip("/")


def redirect_uri(provider_id: str, settings: Settings | None = None) -> str:
    """The callback URL the provider must have registered."""
    return f"{redirect_base(settings)}/api/v1/auth/oauth/{provider_id}/callback"


def new_state() -> str:
    """CSRF state for the authorization request (single use, 10 min)."""
    return secrets.token_urlsafe(24)


def build_authorize_url(
    provider: OAuthProvider,
    *,
    state: str,
    settings: Settings | None = None,
) -> str:
    params = {
        "client_id": provider.client_id,
        "redirect_uri": redirect_uri(provider.id, settings),
        "response_type": "code",
        "scope": provider.scopes,
        "state": state,
    }
    if provider.id == GOOGLE:
        params["access_type"] = "offline"  # keep the refresh session meaningful
        params["prompt"] = "select_account"
    return f"{provider.authorize_url}?{urlencode(params)}"
