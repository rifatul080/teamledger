"""In-app notifier + console mailer."""
from __future__ import annotations

import logging
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from email.message import EmailMessage

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..core.ids import new_id
from ..models.notification import Notification, NotificationKey
from ..models.user import User

log = logging.getLogger("teamledger.notifications")


@dataclass(frozen=True)
class NotifRequest:
    user_id: str
    type: str
    title: str
    body: str
    team_id: str | None = None
    project_id: str | None = None
    task_id: str | None = None


def bucket_for_due(due: datetime, now: datetime, *, days_3: int = 3, days_1: int = 1) -> str:
    """Stable bucket label for idempotency."""
    delta_days = (due.date() - now.date()).days
    if delta_days == days_3:
        return f"due-{due.date().isoformat()}-3d"
    if delta_days == days_1:
        return f"due-{due.date().isoformat()}-1d"
    if delta_days < 0:
        return f"overdue-{due.date().isoformat()}"
    return f"due-{due.date().isoformat()}"


def emit(
    db: Session,
    reqs: Iterable[NotifRequest],
    *,
    idempotency: tuple[str, str, str] | None = None,
) -> int:
    """Persist notifications. Returns the count of new rows.

    ``idempotency`` is ``(kind, task_id, recipient_id, bucket)`` — when
    supplied, an existing key suppresses the row (idempotent scheduler).
    """
    count = 0
    for req in reqs:
        if idempotency is not None:
            kind, task_id, recipient_id, bucket = idempotency
            key = NotificationKey(
                id=new_id(),
                kind=kind,
                task_id=task_id,
                recipient_id=recipient_id,
                bucket=bucket,
            )
            db.add(key)
            try:
                db.flush()
            except IntegrityError:
                db.rollback()
                continue
        db.add(
            Notification(
                id=new_id(),
                user_id=req.user_id,
                type=req.type,
                title=req.title,
                body=req.body,
                team_id=req.team_id,
                project_id=req.project_id,
                task_id=req.task_id,
            )
        )
        count += 1
    if count:
        db.flush()
    return count


def list_for_user(db: Session, user_id: str, *, limit: int = 50) -> list[Notification]:
    return list(
        db.scalars(
            select(Notification)
            .where(Notification.user_id == user_id)
            .order_by(Notification.created_at.desc())
            .limit(limit)
        )
    )


def unread_count(db: Session, user_id: str) -> int:
    return (
        db.query(Notification)
        .filter(Notification.user_id == user_id, Notification.read.is_(False))
        .count()
    )


def mark_read(db: Session, user_id: str, ids: list[str]) -> int:
    if not ids:
        return 0
    rows = (
        db.query(Notification)
        .filter(Notification.user_id == user_id, Notification.id.in_(ids))
        .all()
    )
    now = datetime.now(tz=UTC)
    for r in rows:
        r.read = True
        r.read_at = now
    return len(rows)


def mark_all_read(db: Session, user_id: str) -> int:
    rows = (
        db.query(Notification)
        .filter(Notification.user_id == user_id, Notification.read.is_(False))
        .all()
    )
    now = datetime.now(tz=UTC)
    for r in rows:
        r.read = True
        r.read_at = now
    return len(rows)


# ---------------------------------------------------------------------------
# Mailer

log_email_header = "===== EMAIL ====="


def render_email(req: NotifRequest, *, from_addr: str) -> EmailMessage:
    msg = EmailMessage()
    msg["Subject"] = req.title
    msg["From"] = from_addr
    msg["To"] = "(recipient)"  # we don't actually send; user lookup not needed
    msg.set_content(req.body)
    return msg


async def maybe_send_email(req: NotifRequest, *, user_email: str | None, from_addr: str) -> None:
    """Console mailer: prints a brief header so dev can verify delivery."""
    if user_email is None:
        return
    line = f"{log_email_header} to={user_email} subject={req.title!r}"
    log.info(line)
    print(line)


async def deliver(db: Session, user: User, *, req: NotifRequest, mail_enabled: bool) -> None:
    from ..core.config import get_settings  # local import

    await maybe_send_email(req, user_email=(user.email if mail_enabled else None), from_addr=get_settings().mail_from)
