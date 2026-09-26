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


# ---------------------------------------------------------------------------
# v2 — direct transactional email senders for verification + password reset.
# Real mailers (Resend, SES, SMTP) plug in via `MAIL_BACKEND`.

_log = logging.getLogger("teamledger.mail")

PUBLIC_BASE_URL = ""  # set per call from settings when needed


def send_verification_email(*, to: str, token: str, settings) -> dict:
    """Send an email verification link.

    The link is {settings.public_base_url}/verify-email?token=<token>.
    For Resend we POST to the API; for the console mailer we just log.
    """
    link = f"{settings.public_base_url.rstrip('/')}/verify-email?token={token}"
    subject = "Verify your TeamLedger email"
    body = (
        "Welcome to TeamLedger.\n\n"
        f"Confirm your email by opening this link (valid 24 hours):\n\n  {link}\n\n"
        "If you did not sign up, you can ignore this email."
    )
    return _send(to=to, subject=subject, body=body, settings=settings, kind="verify")


def send_password_reset_email(*, to: str, token: str, settings) -> dict:
    link = f"{settings.public_base_url.rstrip('/')}/login?reset_token={token}"
    subject = "Reset your TeamLedger password"
    body = (
        "Someone (hopefully you) asked to reset the TeamLedger password for this email.\n\n"
        f"Open this link to set a new password:\n\n  {link}\n\n"
        "If you didn't ask, you can ignore this email."
    )
    return _send(to=to, subject=subject, body=body, settings=settings, kind="reset")


def _send(*, to: str, subject: str, body: str, settings, kind: str) -> dict:
    """Pluggable backend switch."""
    backend = settings.mail_backend
    if backend == "console":
        _log.info("EMAIL(%s) to=%s subject=%r", kind, to, subject)
        print(f"=== EMAIL ({kind}) ===\nTo: {to}\nSubject: {subject}\n\n{body}\n=== END EMAIL ===")
        return {"status": "console", "to": to}
    if backend == "smtp":
        return _send_smtp(to=to, subject=subject, body=body, settings=settings)
    if backend == "resend":
        return _send_resend(to=to, subject=subject, body=body, settings=settings)
    _log.warning("Unknown mail backend %r; falling back to console", backend)
    return {"status": "console-fallback", "to": to}


def _send_resend(*, to: str, subject: str, body: str, settings) -> dict:
    """Send via the Resend HTTPS API (api.resend.com). Free tier: 100 emails/day
    and 3,000/month — plenty for low-volume verification traffic."""
    if not getattr(settings, "resend_api_key", ""):
        _log.warning("Resend API key not set; falling back to console")
        print(f"=== EMAIL (resend-no-key-fallback) ===\nTo: {to}\nSubject: {subject}\n\n{body}\n=== END EMAIL ===")
        return {"status": "console-fallback", "to": to}
    try:
        import json as _json
        import urllib.request as _u
        req = _u.Request(
            "https://api.resend.com/emails",
            data=_json.dumps(
                {
                    "from": getattr(settings, "resend_from", "TeamLedger <noreply@teamledger.app>"),
                    "to": [to],
                    "subject": subject,
                    "text": body,
                }
            ).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {settings.resend_api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        # Target is the hardcoded https://api.resend.com/emails literal built
        # above — configuration, never user-controlled input.
        with _u.urlopen(req, timeout=10) as r:  # nosec B310
            return {"status": "ok", "provider": "resend", "code": r.status}
    except Exception as e:
        _log.exception("Resend send failed: %s", e)
        return {"status": "error", "provider": "resend", "error": str(e)}


def _send_smtp(*, to: str, subject: str, body: str, settings) -> dict:
    try:
        import smtplib
        from email.message import EmailMessage as _EM

        msg = _EM()
        msg["Subject"] = subject
        msg["From"] = settings.mail_from
        msg["To"] = to
        msg.set_content(body)
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10) as s:
            s.send_message(msg)
        return {"status": "ok", "provider": "smtp"}
    except Exception as e:
        _log.exception("SMTP send failed: %s", e)
        return {"status": "error", "provider": "smtp", "error": str(e)}
