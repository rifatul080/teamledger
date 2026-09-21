"""Shared FastAPI dependencies (current user, role checks, etc.)."""
from __future__ import annotations

import json
from collections.abc import Callable, Iterable
from datetime import UTC, datetime
from typing import Any

from fastapi import Depends, Header, Request
from sqlalchemy.orm import Session

from ..core.clock import Clock, SystemClock
from ..core.errors import AppError, forbidden, not_found, unauthorized
from ..core.tokens import decode_jwt
from ..db.session import get_sessionmaker
from ..models.membership import Membership
from ..models.user import User


def get_clock() -> Clock:
    return SystemClock()


def get_db() -> Iterable[Session]:
    SessionLocal = get_sessionmaker()
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def current_user(
    request: Request,
    db: Session = Depends(get_db),
) -> User:
    """Read the access cookie and resolve the user. Raises 401 otherwise."""
    token = request.cookies.get("tl_access")
    if not token:
        # Fallback to Authorization header for testing convenience
        auth = request.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            token = auth[len("Bearer ") :].strip()
    if not token:
        raise unauthorized()
    try:
        payload = decode_jwt(token)
    except Exception:
        raise unauthorized(code="auth.invalid_token") from None
    sub = payload.get("sub")
    if not isinstance(sub, str):
        raise unauthorized(code="auth.invalid_token")
    user = db.get(User, sub)
    if user is None or not user.is_active:
        raise unauthorized(code="auth.invalid_token")
    request.state.user_id = user.id
    request.state.user_payload = payload
    return user


def require_csrf(request: Request, x_csrf_token: str | None = Header(default=None)) -> None:
    if request.method in {"GET", "HEAD", "OPTIONS"}:
        return
    cookie = request.cookies.get("tl_csrf")
    if (
        request.cookies.get("tl_access")
        and (not cookie or not x_csrf_token or cookie != x_csrf_token)
    ):
        raise AppError(
            status_code=403,
            code="auth.csrf",
            message="CSRF token missing or invalid.",
        )


def require_membership(
    team_id: str,
    db: Session,
    user_id: str,
    *,
    allow_removed: bool = False,
) -> Membership:
    m = (
        db.query(Membership)
        .filter(Membership.user_id == user_id, Membership.team_id == team_id)
        .one_or_none()
    )
    if m is None:
        raise not_found(code="team.not_found")
    if m.removed_at is not None and not allow_removed:
        raise forbidden(code="team.removed", message="You are no longer a member of this team.")
    return m


def require_role(team_id: str, db: Session, user_id: str, role: str) -> Membership:
    m = require_membership(team_id, db, user_id)
    if m.role != role:
        raise forbidden(
            code="perm.role_required",
            message=f"This action requires the {role} role.",
            details={"required": role},
        )
    return m


def audit(
    db: Session,
    *,
    actor_user_id: str | None,
    team_id: str | None,
    project_id: str | None,
    action: str,
    subject_kind: str,
    subject_id: str,
    payload: dict[str, Any] | None = None,
    when: datetime | None = None,
) -> None:
    from ..core.ids import new_id  # local import to avoid cycles
    from ..models.audit import AuditEvent

    event = AuditEvent(
        id=new_id(),
        actor_user_id=actor_user_id,
        team_id=team_id,
        project_id=project_id,
        action=action,
        subject_kind=subject_kind,
        subject_id=subject_id,
        payload=json.dumps(payload) if payload else None,
        at=when or datetime.now(tz=UTC),
    )
    db.add(event)


def is_leader(membership: Membership) -> bool:
    return membership.role == "leader"


def role_guard(*, leader: bool = False, member: bool = True) -> Callable[[Membership], Membership]:
    def _check(m: Membership) -> Membership:
        if m.role == "leader":
            return m
        if member:
            return m
        raise forbidden()

    _check.requires_leader = leader  # type: ignore[attr-defined]
    return _check
