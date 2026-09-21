"""Auth endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy.orm import Session

from ...api.deps import get_db
from ...api.rate_limit import limiter as rate_limiter
from ...core.config import get_settings
from ...core.errors import AppError
from ...core.ids import new_id
from ...models.audit import AuditEvent
from ...schemas.auth import (
    AccessTokenResponse,
    LoginRequest,
    PasswordResetConfirm,
    PasswordResetRequest,
    SignupRequest,
    UserPublic,
)
from ...services.auth_service import (
    authenticate,
    complete_password_reset,
    create_user,
    issue_token_bundle,
    revoke_refresh,
    rotate_refresh,
    start_password_reset,
)

router = APIRouter(prefix="/auth", tags=["auth"])


def _set_auth_cookies(response: Response, *, access: str, refresh: str, csrf: str) -> None:
    settings = get_settings()
    secure = settings.app_env != "development"
    response.set_cookie(
        "tl_access",
        access,
        httponly=True,
        secure=secure,
        samesite="lax",
        max_age=settings.access_token_ttl_min * 60,
        path="/",
    )
    response.set_cookie(
        "tl_refresh",
        refresh,
        httponly=True,
        secure=secure,
        samesite="lax",
        max_age=settings.refresh_token_ttl_days * 24 * 3600,
        path="/api/v1/auth",
    )
    response.set_cookie(
        "tl_csrf",
        csrf,
        secure=secure,
        samesite="lax",
        max_age=settings.refresh_token_ttl_days * 24 * 3600,
        path="/",
    )


@router.post("/signup", response_model=UserPublic, status_code=status.HTTP_201_CREATED)
def signup(payload: SignupRequest, db: Session = Depends(get_db)) -> UserPublic:
    user = create_user(
        db,
        email=payload.email,
        password=payload.password,
        display_name=payload.display_name,
        timezone=payload.timezone,
    )
    db.add(
        AuditEvent(
            id=new_id(),
            actor_user_id=user.id,
            action="auth.signup",
            subject_kind="user",
            subject_id=user.id,
            payload=None,
            at=user.created_at,
        )
    )
    db.commit()
    return UserPublic.model_validate(user)


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
        db,
        refresh_token=token,
        ip=ip,
        user_agent=request.headers.get("user-agent"),
    )
    db.commit()
    _set_auth_cookies(response, access=bundle.access_token, refresh=bundle.refresh_token, csrf=bundle.csrf_token)
    return AccessTokenResponse(
        access_token=bundle.access_token,
        csrf_token=bundle.csrf_token,
        expires_in=bundle.expires_in,
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
def reset_request(
    payload: PasswordResetRequest,
    db: Session = Depends(get_db),
) -> dict:
    settings = get_settings()
    if not rate_limiter.hit(("reset", payload.email.lower()), settings.reset_rate_limit_per_min):
        raise AppError(status_code=429, code="rate.exceeded", message="Too many reset attempts.")
    ticket = start_password_reset(db, email=payload.email)
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
