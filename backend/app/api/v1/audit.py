"""Audit log endpoint — leader-only."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ...api.deps import current_user, get_db, require_role
from ...core.errors import not_found
from ...models.audit import AuditEvent
from ...models.team import Team
from ...models.user import User

router = APIRouter(prefix="/teams", tags=["audit"])


@router.get("/{team_id}/audit")
def team_audit(
    team_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict:
    if db.get(Team, team_id) is None:
        raise not_found()
    require_role(team_id, db, user.id, role="leader")
    rows = (
        db.query(AuditEvent)
        .filter(AuditEvent.team_id == team_id)
        .order_by(AuditEvent.at.desc())
        .limit(500)
        .all()
    )
    return {
        "items": [
            {
                "id": r.id,
                "action": r.action,
                "subject_kind": r.subject_kind,
                "subject_id": r.subject_id,
                "actor_user_id": r.actor_user_id,
                "at": r.at.isoformat(),
                "payload": r.payload,
            }
            for r in rows
        ]
    }
