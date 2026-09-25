"""Auth endpoints (v2 — email verification + signup rate limit + avatars)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request, Response, status
from sqlalchemy.orm import Session

from ...api.deps import audit as audit_log, current_user, get_db
from ...api.rate_limit import limiter as rate_limiter
from ...core.config import get_settings
from ...core.errors import AppError, validation
from ...models.user import User
from ...notifications import mail as mailer
from ...schemas.auth import (
    AccessTokenResponse,
    InstitutionHint,
    LoginRequest,
    PasswordResetConfirm,
    PasswordResetRequest,
    ProfileUpdate,
    SignupRequest,
    UserPublic,
    VerifyEmailRequest,
)
from ...services.auth_service import (
    authenticate,
    complete_email_verification,
    complete_password_reset,
    create_user,
    derive_institution_hint_from_email,
    issue_token_bundle,
    revoke_refresh,
    rotate_refresh,
    start_email_verification,
    start_password_reset,
)
from ...services.profile_service import (
    avatar_url_for_user,
    build_user_public,
    update_profile,
)

router = APIRouter(prefix="/auth", tags=["auth"])


def _set_auth_cookies(response: Response, *, access: str, refresh: str, csrf: str) -> None:
    settings = get_settings()
    # SameSite=None requires Secure=True (browsers reject it otherwise).
    # SameSite=None is needed when the frontend and API are on different
    # origins (e.g. Vercel + Render split deploy); same-origin mono-host
    # deploys use the default "lax".
    samesite = settings.cookie_samesite
    secure = settings.app_env not in {"development", "test"} or samesite == "none"
    response.set_cookie(
        "tl_access", access, httponly=True, secure=secure, samesite=samesite,
        max_age=settings.access_token_ttl_min * 60, path="/",
    )
    response.set_cookie(
        "tl_refresh", refresh, httponly=True, secure=secure, samesite=samesite,
        max_age=settings.refresh_token_ttl_days * 24 * 3600, path="/",
    )
    response.set_cookie(
        "tl_csrf", csrf, secure=secure, samesite=samesite,
        max_age=settings.refresh_token_ttl_days * 24 * 3600, path="/",
    )


@router.get("/institution-hint", response_model=InstitutionHint)
def institution_hint(email: str = Query(..., min_length=3)) -> InstitutionHint:
    """Best-effort guess of an institution name from the email domain.

    This is non-PII — the caller already knows the email; we just match
    common academic TLDs (ac.uk, edu, ac.jp, …). Returns { hint: null }
    for non-academic domains so the frontend can decide not to pre-fill.
    """
    hint = derive_institution_hint_from_email(email)
    return InstitutionHint(hint=hint)


@router.post("/signup", response_model=UserPublic, status_code=status.HTTP_201_CREATED)
def signup(
    payload: SignupRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> UserPublic:
    settings = get_settings()
    # Per-IP AND per-email signup caps (spec: signup endpoint is rate limited
    # the same way login is — addresses enumeration + script-signup abuse).
    ip = request.client.host if request.client else None
    if ip and not rate_limiter.hit(("signup_ip", ip), settings.signup_rate_limit_per_min):
        raise AppError(status_code=429, code="rate.exceeded", message="Too many signups from this network.")
    if not rate_limiter.hit(("signup_email", payload.email.lower()), settings.signup_rate_limit_per_min):
        raise AppError(status_code=429, code="rate.exceeded", message="Too many signup attempts for this email.")

    # If the client passed a hint, accept it. Otherwise let the service try.
    institution = payload.institution or payload.institution_hint or None
    user = create_user(
        db,
        email=payload.email,
        password=payload.password,
        display_name=payload.display_name,
        timezone=payload.timezone,
        institution=institution,
        email_verified=False,
    )
    audit_log(
        db,
        actor_user_id=user.id,
        action="auth.signup",
        subject_kind="user",
        subject_id=user.id,
        when=user.created_at,
    )
    # Issue an email verification ticket; mailer is pluggable, dev = console.
    ticket = start_email_verification(db, user=user)
    audit_log(
        db,
        actor_user_id=user.id,
        action="auth.verify_request",
        subject_kind="user",
        subject_id=user.id,
        payload={"expires_at": ticket.expires_at.isoformat()},
        when=user.created_at,
    )
    mailer.send_verification_email(to=user.email, token=ticket.token, settings=settings)
    db.commit()

    # Auto-login on signup (UX parity with v1).
    bundle = issue_token_bundle(db, user, ip=ip, user_agent=request.headers.get("user-agent"))
    db.commit()
    _set_auth_cookies(
        response,
        access=bundle.access_token,
        refresh=bundle.refresh_token,
        csrf=bundle.csrf_token,
    )
    return build_user_public(user)


@router.post("/verify-email", response_model=UserPublic)
def verify_email(payload: VerifyEmailRequest, db: Session = Depends(get_db)) -> UserPublic:
    user = complete_email_verification(db, token=payload.token)
    audit_log(
        db,
        actor_user_id=user.id,
        action="auth.verify_complete",
        subject_kind="user",
        subject_id=user.id,
        when=user.created_at,
    )
    db.commit()
    return build_user_public(user)


@router.post("/resend-verification", status_code=202)
def resend_verification(
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict:
    if user.email_verified:
        return {"status": "already_verified"}
    ticket = start_email_verification(db, user=user)
    settings = get_settings()
    mailer.send_verification_email(to=user.email, token=ticket.token, settings=settings)
    db.commit()
    return {"status": "queued"}


@router.post("/login", response_model=AccessTokenResponse)
def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> AccessTokenResponse:
    settings = get_settings()
    ip = request.client.host if request.client else None
    if not rate_limiter.hit(("login", payload.email.lower()), settings.login_rate_limit_per_min):
        raise AppError(status_code=429, code="rate.exceeded", message="Too many login attempts.")
    user = authenticate(db, email=payload.email, password=payload.password)
    bundle = issue_token_bundle(db, user, ip=ip, user_agent=request.headers.get("user-agent"))
    db.commit()
    _set_auth_cookies(response, access=bundle.access_token, refresh=bundle.refresh_token, csrf=bundle.csrf_token)
    return AccessTokenResponse(
        access_token=bundle.access_token,
        csrf_token=bundle.csrf_token,
        expires_in=bundle.expires_in,
    )


@router.post("/refresh", response_model=AccessTokenResponse)
def refresh(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> AccessTokenResponse:
    token = request.cookies.get("tl_refresh") or ""
    ip = request.client.host if request.client else None
    bundle = rotate_refresh(
        db, refresh_token=token, ip=ip, user_agent=request.headers.get("user-agent"),
    )
    db.commit()
    _set_auth_cookies(response, access=bundle.access_token, refresh=bundle.refresh_token, csrf=bundle.csrf_token)
    return AccessTokenResponse(
        access_token=bundle.access_token, csrf_token=bundle.csrf_token, expires_in=bundle.expires_in,
    )


@router.post("/logout", status_code=204)
def logout(request: Request, db: Session = Depends(get_db)) -> Response:
    token = request.cookies.get("tl_refresh")
    if token:
        revoke_refresh(db, refresh_token=token)
        db.commit()
    resp = Response(status_code=204)
    for name in ("tl_access", "tl_refresh", "tl_csrf"):
        resp.delete_cookie(name, path="/")
    return resp


@router.post("/password/reset", status_code=202)
def reset_request(payload: PasswordResetRequest, db: Session = Depends(get_db)) -> dict:
    settings = get_settings()
    if not rate_limiter.hit(("reset", payload.email.lower()), settings.reset_rate_limit_per_min):
        raise AppError(status_code=429, code="rate.exceeded", message="Too many reset attempts.")
    ticket = start_password_reset(db, email=payload.email)
    if ticket is not None:
        mailer.send_password_reset_email(to=payload.email, token=ticket.token, settings=settings)
    db.commit()
    if ticket is not None and settings.app_env in ("development", "test"):
        return {
            "status": "queued",
            "token": ticket.token,
            "expires_at": ticket.expires_at.isoformat(),
        }
    return {"status": "queued"}


@router.post("/password/reset/confirm", status_code=204)
def reset_confirm(payload: PasswordResetConfirm, db: Session = Depends(get_db)) -> Response:
    complete_password_reset(db, token=payload.token, new_password=payload.new_password)
    db.commit()
    return Response(status_code=204)
