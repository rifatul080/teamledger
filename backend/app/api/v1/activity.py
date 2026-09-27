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
from ...models.audit import AuditEvent
from ...models.membership import Membership
from ...models.notification import Notification
from ...models.user import User

router = APIRouter()


# Mapping of audit action -> activity kind, title, and href template.
# Keys must match the ``action=`` strings actually written by the routers and
# services (grep `action="` under app/api and app/services).
_ACTIVITY_KIND: dict[str, tuple[str, str, str]] = {
    # --- tasks -------------------------------------------------------------
    "task.create": ("task_assigned", "assigned {title}", "/projects/{project_id}?task={task_id}"),
    "task.propose": ("task_assigned", "proposed {title}", "/projects/{project_id}?task={task_id}"),
    "task.update": ("task_assigned", "updated {title}", "/projects/{project_id}?task={task_id}"),
    "task.split": ("task_assigned", "split {title} into a new task", "/projects/{project_id}"),
    "task.submit": ("task_reviewed", "submitted {title} for review", "/projects/{project_id}?task={task_id}"),
    "task.review": ("task_reviewed", "reviewed {title}", "/projects/{project_id}?task={task_id}"),
    # --- goals & milestones -------------------------------------------------
    "goal.create": ("milestone", "created goal {title}", "/projects/{project_id}"),
    "goal.update": ("milestone", "updated goal {title}", "/projects/{project_id}"),
    "goal.delete": ("milestone", "deleted goal {title}", "/projects/{project_id}"),
    "milestone.create": ("milestone", "added milestone {title}", "/projects/{project_id}"),
    "milestone.update": ("milestone", "updated milestone {title}", "/projects/{project_id}"),
    "milestone.delete": ("milestone", "deleted milestone {title}", "/projects/{project_id}"),
    # --- membership ---------------------------------------------------------
    "team.create": ("member", "created the team", "/teams/{team_id}"),
    "team.member_add": ("member", "added a member", "/teams/{team_id}"),
    "team.member_remove": ("member", "removed a member", "/teams/{team_id}"),
    "team.transfer_leader": ("member", "transferred leadership", "/teams/{team_id}"),
    "team.archive": ("member", "archived the team", "/teams/{team_id}"),
    "invitation.create": ("mention", "invited {email}", "/teams/{team_id}"),
    "invitation.revoke": ("mention", "revoked {email}", "/teams/{team_id}"),
    "invitation.accept": ("member", "{email} joined the team", "/teams/{team_id}"),
    # --- projects, scoring, schedule ---------------------------------------
    "project.create": ("system", "created project {title}", "/projects/{project_id}"),
    "project.update": ("system", "updated project {title}", "/projects/{project_id}"),
    "project.set_participants": ("member", "updated the contributors on {title}", "/projects/{project_id}"),
    "project.multipliers_update": ("system", "re-weighted {title}", "/projects/{project_id}"),
    "project.timeliness_update": ("system", "updated the timeline for {title}", "/projects/{project_id}"),
    "score.adjustment_add": ("system", "adjusted {title}'s score", "/projects/{project_id}/scoring"),
    "author_order.finalize": ("system", "finalized the author order for {title}", "/projects/{project_id}/scoring"),
    "schedule.set_plan": ("system", "set a weekly plan", "/teams/{team_id}"),
    # --- account ------------------------------------------------------------
    "auth.signup": ("system", "joined TeamLedger", "/dashboard"),
    "auth.verify_complete": ("system", "verified their email", "/dashboard"),
}


def _project(db: Session, user: User, events: list[AuditEvent]) -> list[dict]:
    """Map audit events to activity items for the home/team feed."""
    import json as _json

    out = []
    actor_names = _actor_names(db, events)
    for ev in events:
        kind, body_tmpl, href_tmpl = _ACTIVITY_KIND.get(
            ev.action, ("system", ev.action.replace(".", " "), "/dashboard")
        )
        # payload may be a JSON string (legacy rows) or already a dict.
        if isinstance(ev.payload, str):
            try:
                payload = _json.loads(ev.payload) if ev.payload else {}
            except Exception:
                payload = {}
        elif ev.payload is None:
            payload = {}
        else:
            payload = dict(ev.payload)
        try:
            title = (
                payload.get("title")
                or payload.get("display_name")
                or payload.get("email")
                or ""
            )
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
                "task_id": payload.get("task_id")
                or (ev.subject_id if ev.subject_kind == "task" else None),
                "message_id": payload.get("message_id")
                or (ev.subject_id if ev.subject_kind == "message" else None),
                "thread_root_id": payload.get("thread_root_id"),
                "actor_user_id": ev.actor_user_id,
                "actor_name": actor_names.get(ev.actor_user_id or ""),
                "self": ev.actor_user_id == user.id,
                "body": body,
                "href": href,
                "read": False,
                "created_at": ev.at.isoformat() if ev.at else datetime.now(tz=UTC).isoformat(),
            }
        )
    return out


def _actor_names(db: Session, events: list[AuditEvent]) -> dict[str, str]:
    """Display names for the actors in this page of the feed (one query)."""
    ids = {ev.actor_user_id for ev in events if ev.actor_user_id}
    if not ids:
        return {}
    return {
        u.id: u.display_name
        for u in db.query(User).filter(User.id.in_(ids)).all()
    }


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
    items = _project(db, user, rows)
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
    items = _project(db, user, rows)
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
