"""OAuth 2.0 endpoints: start, callback, and a capability probe for the UI.

The session itself is unchanged — a successful callback mints the same cookie
bundle as ``POST /auth/login``, so every existing request keeps working and
"remember me" (the 14-day refresh cookie) applies to social sign-in too.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from ...api.deps import get_db
from ...core.config import get_settings
from ...core.oauth import (
    build_authorize_url,
    exchange_code,
    fetch_profile,
    get_provider,
    new_state,
    providers,
    upsert_oauth_user,
)
from ...services.auth_service import issue_token_bundle
from .auth import _set_auth_cookies

log = logging.getLogger("teamledger.oauth")

router = APIRouter(prefix="/auth/oauth", tags=["auth"])

STATE_COOKIE = "tl_oauth_state"
STATE_MAX_AGE = 600  # 10 minutes is plenty for one redirect round trip


@router.get("/providers")
def list_providers() -> dict:
    """Which social buttons the UI should render."""
    return {
        "providers": [
            {"id": p.id, "label": p.label, "configured": p.configured}
            for p in providers().values()
        ]
    }


@router.get("/{provider_id}")
def start(provider_id: str, request: Request) -> RedirectResponse:
    """Kick off the provider's consent screen (state stored in a cookie)."""
    provider = get_provider(provider_id)
    settings = get_settings()
    state = new_state()
    url = build_authorize_url(provider, state=state, settings=settings)
    log.info("oauth start: %s", provider.id)
    resp = RedirectResponse(url, status_code=302)
    secure = settings.cookie_samesite == "none"
    resp.set_cookie(
        STATE_COOKIE,
        state,
        max_age=STATE_MAX_AGE,
        httponly=True,
        samesite="lax",
        secure=secure,
        path="/",
    )
    return resp


@router.get("/{provider_id}/callback")
def callback(
    provider_id: str,
    request: Request,
    code: str = Query(default=""),
    state: str = Query(default=""),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    """Exchange the code, upsert the user, and sign them in."""
    settings = get_settings()
    frontend = settings.public_base_url.rstrip("/")
    fail = lambda reason: RedirectResponse(  # noqa: E731 - tiny local helper
        f"{frontend}/login?error={reason}", status_code=302
    )

    provider = get_provider(provider_id, settings)
    expected = request.cookies.get(STATE_COOKIE, "")
    if not state or not expected or state != expected:
        log.warning("oauth callback rejected: state mismatch")
        return fail("state")

    access_token = exchange_code(provider, code, settings=settings)
    email, display_name = fetch_profile(provider, access_token)
    user = upsert_oauth_user(db, email=email, display_name=display_name)
    bundle = issue_token_bundle(
        db, user, ip=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    db.commit()

    resp = RedirectResponse(f"{frontend}/dashboard", status_code=302)
    _set_auth_cookies(
        resp,
        access=bundle.access_token,
        refresh=bundle.refresh_token,
        csrf=bundle.csrf_token,
    )
    resp.delete_cookie(STATE_COOKIE, path="/")
    return resp
