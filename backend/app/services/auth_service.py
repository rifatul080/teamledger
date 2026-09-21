"""Auth service: signup, login, refresh, password reset."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from ..core.config import get_settings
from ..core.errors import conflict, not_found, unauthorized, validation
from ..core.ids import new_id
from ..core.security import hash_password, password_strength_ok, verify_password
from ..core.tokens import encode_jwt, hash_token, random_token
from ..models.password_reset import PasswordResetToken
from ..models.refresh_session import RefreshSession
from ..models.user import User


@dataclass(frozen=True)
class TokenBundle:
    access_token: str
    refresh_token: str
    csrf_token: str
    expires_in: int


@dataclass(frozen=True)
class PasswordResetTicket:
    user_id: str
    token: str
    expires_at: datetime


def create_user(
    db: Session,
    *,
    email: str,
    password: str,
    display_name: str,
    timezone: str,
) -> User:
    if not password_strength_ok(password):
        raise validation(
            "Password must be at least 10 characters and contain a letter and a digit."
        )
    if db.query(User).filter(User.email == email.lower()).first():
        raise conflict("Email already registered.", code="auth.email_taken")
    user = User(
        id=new_id(),
        email=email.lower(),
        display_name=display_name.strip(),
        timezone=timezone or "UTC",
        password_hash=hash_password(password),
        is_active=True,
        created_at=datetime.now(tz=timezone.utc),
    )
    db.add(user)
    db.flush()
    return user


def authenticate(db: Session, *, email: str, password: str) -> User:
    user = db.query(User).filter(User.email == email.lower()).one_or_none()
    if user is None or not user.is_active:
        # Same error to avoid account enumeration.
        raise unauthorized(code="auth.invalid_credentials", message="Invalid email or password.")
    if not verify_password(user.password_hash, password):
        raise unauthorized(code="auth.invalid_credentials", message="Invalid email or password.")
    user.last_login_at = datetime.now(tz=UTC)
    db.flush()
    return user


def _new_family_id() -> str:
    return new_id()


def issue_token_bundle(db: Session, user: User, *, ip: str | None = None, user_agent: str | None = None) -> TokenBundle:
    settings = get_settings()
    family = _new_family_id()
    refresh_plain = random_token(32)
    refresh_hash = hash_token(refresh_plain)
    csrf = random_token(24)
    now = datetime.now(tz=UTC)
    expires_at = now + timedelta(days=settings.refresh_token_ttl_days)
    db.add(
        RefreshSession(
            id=new_id(),
            user_id=user.id,
            family_id=family,
            token_hash=refresh_hash,
            created_at=now,
            expires_at=expires_at,
            user_agent=(user_agent or "")[:255] or None,
            ip=(ip or "")[:64] or None,
            created_at_db=now,
        )
    )
    db.flush()
    access = encode_jwt(
        {"sub": user.id, "email": user.email, "role": "user"},
        ttl_seconds=settings.access_token_ttl_min * 60,
    )
    return TokenBundle(
        access_token=access,
        refresh_token=refresh_plain,
        csrf_token=csrf,
        expires_in=settings.access_token_ttl_min * 60,
    )


def rotate_refresh(db: Session, refresh_token: str, *, ip: str | None = None, user_agent: str | None = None) -> TokenBundle:
    settings = get_settings()
    th = hash_token(refresh_token)
    session = db.query(RefreshSession).filter(RefreshSession.token_hash == th).one_or_none()
    if session is None:
        raise unauthorized(code="auth.refresh_invalid", message="Refresh token invalid.")
    if session.revoked_at is not None or session.used_at is not None:
        # Reuse detected — revoke the whole family.
        db.query(RefreshSession).filter(RefreshSession.family_id == session.family_id).update(
            {RefreshSession.revoked_at: datetime.now(tz=UTC)}
        )
        db.flush()
        raise unauthorized(code="auth.refresh_reuse", message="Refresh token reuse detected.")
    now = datetime.now(tz=UTC)
    if session.expires_at < now:
        raise unauthorized(code="auth.refresh_expired", message="Refresh token expired.")
    user = db.get(User, session.user_id)
    if user is None or not user.is_active:
        raise unauthorized()
    # Rotate: mark old used, issue new in same family
    session.used_at = now
    new_plain = random_token(32)
    new_hash = hash_token(new_plain)
    expires_at = now + timedelta(days=settings.refresh_token_ttl_days)
    db.add(
        RefreshSession(
            id=new_id(),
            user_id=user.id,
            family_id=session.family_id,
            token_hash=new_hash,
            created_at=now,
            expires_at=expires_at,
            user_agent=(user_agent or "")[:255] or None,
            ip=(ip or "")[:64] or None,
            created_at_db=now,
        )
    )
    db.flush()
    access = encode_jwt(
        {"sub": user.id, "email": user.email, "role": "user"},
        ttl_seconds=settings.access_token_ttl_min * 60,
    )
    csrf = random_token(24)
    return TokenBundle(
        access_token=access,
        refresh_token=new_plain,
        csrf_token=csrf,
        expires_in=settings.access_token_ttl_min * 60,
    )


def revoke_refresh(db: Session, refresh_token: str | None) -> None:
    if not refresh_token:
        return
    th = hash_token(refresh_token)
    session = db.query(RefreshSession).filter(RefreshSession.token_hash == th).one_or_none()
    if session is None:
        return
    session.revoked_at = datetime.now(tz=UTC)


def start_password_reset(db: Session, *, email: str) -> PasswordResetTicket | None:
    """Returns a ticket to email. If the user does not exist, returns None.
    The API still responds 202 (no enumeration)."""
    user = db.query(User).filter(User.email == email.lower()).one_or_none()
    if user is None:
        return None
    settings = get_settings()
    now = datetime.now(tz=UTC)
    plain = random_token(32)
    db.add(
        PasswordResetToken(
            id=new_id(),
            user_id=user.id,
            token_hash=hash_token(plain),
            created_at=now,
            expires_at=now + timedelta(minutes=settings.password_reset_ttl_min),
            created_at_db=now,
        )
    )
    db.flush()
    return PasswordResetTicket(user_id=user.id, token=plain, expires_at=now)


def complete_password_reset(db: Session, *, token: str, new_password: str) -> None:
    if not password_strength_ok(new_password):
        raise validation(
            "Password must be at least 10 characters and contain a letter and a digit."
        )
    th = hash_token(token)
    row = db.query(PasswordResetToken).filter(PasswordResetToken.token_hash == th).one_or_none()
    if row is None or row.used_at is not None:
        raise unauthorized(code="auth.reset_invalid", message="Reset link invalid or used.")
    now = datetime.now(tz=UTC)
    if row.expires_at < now:
        raise unauthorized(code="auth.reset_expired", message="Reset link expired.")
    user = db.get(User, row.user_id)
    if user is None:
        raise not_found()
    user.password_hash = hash_password(new_password)
    row.used_at = now
    # Invalidate all refresh sessions.
    db.query(RefreshSession).filter(RefreshSession.user_id == user.id).update(
        {RefreshSession.revoked_at: now}
    )
    db.flush()


def change_password(db: Session, user: User, *, current: str, new: str) -> None:
    if not verify_password(user.password_hash, current):
        raise unauthorized(code="auth.wrong_password", message="Current password is incorrect.")
    if not password_strength_ok(new):
        raise validation(
            "Password must be at least 10 characters and contain a letter and a digit."
        )
    user.password_hash = hash_password(new)
