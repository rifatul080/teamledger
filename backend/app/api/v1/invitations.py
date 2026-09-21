"""Public invitation accept endpoint."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ...api.deps import audit, current_user, get_db
from ...models.user import User
from ...services import team_service

router = APIRouter(prefix="/invitations", tags=["invitations"])


@router.post("/{token}/accept", status_code=200)
def accept(
    token: str,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict:
    m = team_service.accept_invitation(db, token=token, user=user)
    audit(
        db,
        actor_user_id=user.id,
        team_id=m.team_id,
        action="invitation.accept",
        subject_kind="team",
        subject_id=m.team_id,
    )
    db.commit()
    return {"team_id": m.team_id, "role": m.role}
