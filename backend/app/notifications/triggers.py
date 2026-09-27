"""Real-time notification triggers (task assignment, chat @mentions).

``scheduler.py`` handles *time-based* reminders and is deliberately
idempotent via ``NotificationKey`` buckets. This module handles *event-based*
notifications: something just happened, so the recipient should know now.

Two properties matter here:

1. The in-app row is written in the caller's transaction (via ``mail.emit``),
   so a rolled-back request never leaves a phantom notification behind.
2. The email is fire-and-forget on a tiny worker thread, so neither the REST
   handler nor the chat WebSocket ever blocks on a mail provider (Resend/SMTP
   are network calls with multi-second timeouts).
"""
from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor

from sqlalchemy.orm import Session

from ..core.config import get_settings
from ..models.message import ChatMessage
from ..models.task import Task
from ..models.user import User
from . import mail as notif

log = logging.getLogger("teamledger.notify")

# Two workers is plenty: these jobs are pure network calls to a mail API.
_pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix="tl-mail")

SNIPPET_CHARS = 200


def _run_email(fn, **kwargs) -> None:
    """Send an email off-thread. Never raises — mail is best effort."""
    try:
        settings = get_settings()
    except Exception:  # pragma: no cover - settings always load in practice
        log.exception("settings unavailable; skipping notification email")
        return

    def _job() -> None:
        try:
            fn(settings=settings, **kwargs)
        except Exception:
            log.exception("notification email failed: %s", fn.__name__)

    try:
        _pool.submit(_job)
    except RuntimeError:  # interpreter shutting down
        log.warning("mail pool unavailable; skipping notification email")


def _team_name(db: Session, team_id: str | None) -> str:
    if not team_id:
        return ""
    from ..models.team import Team

    team = db.get(Team, team_id)
    return team.name if team else ""


def _due_text(task: Task) -> str | None:
    return task.due_date.isoformat() if getattr(task, "due_date", None) else None


def notify_task_assigned(
    db: Session,
    *,
    task: Task,
    actor: User,
    assignee: User,
    team_id: str,
    project_id: str,
    project_name: str = "",
) -> int:
    """Create the in-app row + email for a task assigned to ``assignee``.

    Returns the number of notifications created (0 when the actor assigned the
    task to themselves — self-assignment needs no notification).
    """
    if assignee.id == actor.id:
        return 0

    due = _due_text(task)
    due_suffix = f" — due {due}" if due else ""
    team_name = _team_name(db, team_id)
    scope = project_name or "the project"

    created = notif.emit(
        db,
        [
            notif.NotifRequest(
                user_id=assignee.id,
                type="task_assigned",
                title=f"{actor.display_name} assigned you “{task.title}”",
                body=(
                    f"{task.title}{due_suffix} in {scope}."
                    + (f" Team: {team_name}." if team_name else "")
                ),
                team_id=team_id,
                project_id=project_id,
                task_id=task.id,
            )
        ],
    )

    _run_email(
        notif.send_task_assignment_email,
        to=assignee.email,
        assignee_name=assignee.display_name,
        assigner_name=actor.display_name,
        task_title=task.title,
        project_name=scope,
        due_date=due,
    )
    return created


def notify_mentions(
    db: Session,
    *,
    team_id: str,
    team_name: str,
    sender: User,
    message: ChatMessage,
    mentioned_user_ids: list[str],
) -> int:
    """Create the in-app row + email for every member named in a chat message.

    The sender never notifies themselves, duplicates are collapsed, and a
    mention of a user who has since left the team is skipped.
    """
    targets: list[User] = []
    seen: set[str] = set()
    for uid in mentioned_user_ids:
        if not uid or uid == sender.id or uid in seen:
            continue
        seen.add(uid)
        user = db.get(User, uid)
        if user is not None and user.is_active:
            targets.append(user)
    if not targets:
        return 0

    body = message.body or ""
    snippet = body[:SNIPPET_CHARS] + ("…" if len(body) > SNIPPET_CHARS else "")

    created = notif.emit(
        db,
        [
            notif.NotifRequest(
                user_id=u.id,
                type="mention",
                title=f"{sender.display_name} mentioned you in {team_name or 'team chat'}",
                body=snippet,
                team_id=team_id,
            )
            for u in targets
        ],
    )

    for u in targets:
        _run_email(
            notif.send_mention_email,
            to=u.email,
            recipient_name=u.display_name,
            sender_name=sender.display_name,
            team_name=team_name or "your team",
            snippet=snippet,
        )
    return created
