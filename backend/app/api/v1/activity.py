"""v2 — Activity feed, derived from the existing audit log (no parallel feed).

The audit log already records every privileged action. We project it into a
chronological, typed feed for the home dashboard and per-team page, with a
'unread' state keyed on the actor_user_id (you didn't trigger the event
yourself) and an explicit read marker on Notification rows.
"""
from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ...api.deps import current_user, get_db
from ...core.ids import new_id
from ...models.audit import AuditEvent
from ...models.membership import Membership
from ...models.notification import Notification
from ...models.user import User

router = APIRouter()


# Mapping of action -> activity kind, title, and href template.
_ACTIVITY_KIND: dict[str, tuple[str, str, str]] = {
    "task.created": ("task_assigned", "{title}", "/projects/{project_id}?task={task_id}"),
    "task.submitted": ("task_reviewed", "submitted {title}", "/projects/{project_id}?task={task_id}"),
    "task.accepted": ("task_reviewed", "{title} accepted", "/projects/{project_id}?task={task_id}"),
    "task.rejected": ("task_reviewed", "{title} needs rework", "/projects/{project_id}?task={task_id}"),
    "task.split": ("task_assigned", "{title} split", "/projects/{project_id}?task={task_id}"),
    "milestone.completed": ("milestone", "{title}", "/projects/{project_id}"),
    "milestone.uncompleted": ("milestone", "{title}", "/projects/{project_id}"),
    "project.finalize": ("system", "{title} contribution record finalized", "/projects/{project_id}/scoring"),
    "score.adjustment_add": ("system", "+/- adjustment on {title}", "/projects/{project_id}/scoring"),
    "author.order_finalize": ("system", "{title} author order finalized", "/projects/{project_id}/scoring"),
    "invitation.create": ("mention", "invited {email}", "/teams/{team_id}"),
    "invitation.revoke": ("mention", "revoked {email}", "/teams/{team_id}"),
    "team.member_remove": ("mention", "removed a member", "/teams/{team_id}"),
    "team.transfer_leader": ("mention", "transferred leadership", "/teams/{team_id}"),
    "team.archive": ("mention", "archived the team", "/teams/{team_id}"),
    "chat.message": ("mention", "posted in chat", "/teams/{team_id}/chat?msg={message_id}"),
    "chat.reaction": ("reaction", "reacted in chat", "/teams/{team_id}/chat?msg={message_id}"),
    "chat.thread_reply": ("thread_reply", "replied in a thread", "/teams/{team_id}/chat?msg={message_id}"),
}


def _project(user: User, events: list[AuditEvent]) -> list[dict]:
    """Map audit events to activity items for the home/team feed."""
    out = []
    for ev in events:
        kind, body_tmpl, href_tmpl = _ACTIVITY_KIND.get(
            ev.action, ("system", ev.action.replace(".", " "), "/dashboard")
        )
        payload = ev.payload or {}
        try:
            title = payload.get("title") or payload.get("display_name") or payload.get("email") or ""
            body = body_tmpl.format(
                title=title,
                email=payload.get("email", payload.get("removed_email", "")),
                project_id=ev.project_id or "",
                task_id=payload.get("task_id") or ev.subject_id or "",
                team_id=ev.team_id or "",
                message_id=payload.get("message_id") or "",
            )
        except KeyError:
            body = ev.action
        href = href_tmpl.format(
            project_id=ev.project_id or "",
            task_id=payload.get("task_id") or ev.subject_id or "",
            team_id=ev.team_id or "",
            message_id=payload.get("message_id") or "",
        )
        out.append(
            {
                "id": ev.id,
                "kind": kind,
                "team_id": ev.team_id,
                "project_id": ev.project_id,
                "task_id": payload.get("task_id"),
                "message_id": payload.get("message_id"),
                "thread_root_id": payload.get("thread_root_id"),
                "actor_user_id": ev.actor_user_id,
                "body": body,
                "href": href,
                # 'read' is tracked separately per user; we treat all as unread
                # at first; the /activity/read endpoint marks Notification rows.
                "read": False,
                "created_at": ev.at.isoformat() if ev.at else datetime.now(tz=UTC).isoformat(),
            }
        )
    return out


@router.get("/activity")
def activity_all(
    limit: int = Query(default=40, ge=1, le=200),
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict:
    """Activity feed from the existing audit log, scoped to teams the caller
    is currently a member of. Events the caller themselves triggered are
    included too — the UI marks 'self' rows quieter."""
    team_ids = [
        m.team_id for m in db.query(Membership).filter(Membership.user_id == user.id).all()
    ]
    if not team_ids:
        return {"items": [], "unread": 0, "by_kind": {}}
    rows = (
        db.query(AuditEvent)
        .filter(AuditEvent.team_id.in_(team_ids))
        .order_by(AuditEvent.at.desc())
        .limit(limit)
        .all()
    )
    items = _project(user, rows)
    return _unread_summary(db, user.id, items)


@router.get("/teams/{team_id}/activity")
def activity_team(
    team_id: str,
    limit: int = Query(default=40, ge=1, le=200),
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict:
    m = (
        db.query(Membership)
        .filter(Membership.team_id == team_id, Membership.user_id == user.id)
        .one_or_none()
    )
    if m is None:
        from ...core.errors import not_found
        raise not_found(code="team.not_found")
    rows = (
        db.query(AuditEvent)
        .filter(AuditEvent.team_id == team_id)
        .order_by(AuditEvent.at.desc())
        .limit(limit)
        .all()
    )
    items = _project(user, rows)
    return _unread_summary(db, user.id, items)


@router.get("/activity/unread-count")
def unread_count(db: Session = Depends(get_db), user: User = Depends(current_user)) -> dict:
    rows = (
        db.query(Notification)
        .filter(Notification.user_id == user.id, Notification.read.is_(False))
        .all()
    )
    by_kind: dict[str, int] = {}
    for r in rows:
        by_kind[r.type or "system"] = by_kind.get(r.type or "system", 0) + 1
    return {"unread": len(rows), "by_kind": by_kind}


@router.post("/activity/read")
def mark_read(
    payload: dict,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict:
    """Mark activity rows read. Accepts either {ids: [...]} or {all: true}
    or {kind: 'mention'}."""
    from ...core.errors import validation as _v

    now = datetime.now(tz=UTC)
    q = db.query(Notification).filter(Notification.user_id == user.id, Notification.read.is_(False))
    if payload.get("all"):
        rows = q.all()
    elif payload.get("kind"):
        rows = q.filter(Notification.type == payload["kind"]).all()
    elif payload.get("ids"):
        rows = q.filter(Notification.id.in_(payload["ids"])).all()
    else:
        raise _v("Provide one of: ids, all, kind.")
    for r in rows:
        r.read = True
        r.read_at = now
    db.commit()
    return {"marked": len(rows)}


def _unread_summary(db: Session, user_id: str, items: list[dict]) -> dict:
    """For simplicity the API treats all items in the feed as relevant; the
    'unread' count comes from the Notification table directly."""
    unread = db.query(Notification).filter(Notification.user_id == user_id, Notification.read.is_(False)).count()
    by_kind: dict[str, int] = {}
    for r in db.query(Notification).filter(Notification.user_id == user_id, Notification.read.is_(False)).all():
        by_kind[r.type or "system"] = by_kind.get(r.type or "system", 0) + 1
    return {"items": items, "unread": unread, "by_kind": by_kind}
