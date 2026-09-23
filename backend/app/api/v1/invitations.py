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


@router.get("/{token}", status_code=200)
def get_invitation(
    token: str,
    db: Session = Depends(get_db),
) -> dict:
    """Public preview of an invite token — shows team name + expiry.

    Never returns member lists, the inviter's email, or any PII. Used by
    the /accept-invite landing page so non-users see 'you're invited to
    join X' before deciding to sign up.
    """
    return team_service.public_invitation_view(db, token)

