"""Teams endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Path, status
from sqlalchemy.orm import Session

from ...api.deps import audit, current_user, get_db, require_membership, require_role
from ...core.errors import locked, not_found
from ...models.invitation import Invitation
from ...models.team import Team
from ...models.user import User
from ...realtime.hub import hub
from ...schemas.teams import (
    InvitationCreate,
    InvitationRead,
    TeamCreate,
    TeamRead,
    TeamUpdate,
    TransferLeader,
)
from ...services import team_service

router = APIRouter(prefix="/teams", tags=["teams"])


def _check_not_archived(team: Team) -> None:
    if team.archived:
        raise locked(message="Team is archived.", code="team.archived")


def _team_to_read(team: Team, role: str | None) -> dict:
    return {
        "id": team.id,
        "name": team.name,
        "description": team.description,
        "archived": team.archived,
        "created_at": team.created_at,
        "role": role,
    }


@router.post("", response_model=TeamRead, status_code=status.HTTP_201_CREATED)
def create_team(
    payload: TeamCreate,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict:
    team = team_service.create_team(db, leader=user, name=payload.name, description=payload.description)
    audit(
        db,
        actor_user_id=user.id,
        team_id=team.id,
        action="team.create",
        subject_kind="team",
        subject_id=team.id,
        payload={"name": team.name},
    )
    db.commit()
    return _team_to_read(team, "leader")


@router.get("", response_model=list[TeamRead])
def list_my_teams(
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> list[dict]:
    rows = team_service.list_user_teams(db, user.id)
    return [_team_to_read(team, m.role) for team, m in rows]


@router.get("/{team_id}", response_model=TeamRead)
def get_team(
    team_id: str = Path(...),
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict:
    m = require_membership(team_id, db, user.id)
    team = team_service.get_team(db, team_id)
    return _team_to_read(team, m.role)


@router.patch("/{team_id}", response_model=TeamRead)
def update_team(
    payload: TeamUpdate,
    team_id: str = Path(...),
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict:
    m = require_role(team_id, db, user.id, role="leader")
    team = team_service.get_team(db, team_id)
    _check_not_archived(team)
    if payload.name is not None:
        team.name = payload.name.strip()
    if payload.description is not None:
        team.description = payload.description
    db.commit()
    return _team_to_read(team, m.role)


@router.post("/{team_id}/archive", status_code=204)
def archive_team(
    team_id: str = Path(...),
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> None:
    require_role(team_id, db, user.id, role="leader")
    team = team_service.get_team(db, team_id)
    team_service.archive_team(db, team)
    audit(db, actor_user_id=user.id, team_id=team.id, action="team.archive", subject_kind="team", subject_id=team.id)
    db.commit()


@router.delete("/{team_id}/members/{user_id}", status_code=204)
async def remove_member(
    team_id: str,
    user_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> None:
    require_role(team_id, db, user.id, role="leader")
    team = team_service.get_team(db, team_id)
    _check_not_archived(team)
    target = db.get(User, user_id)
    if target is None:
        raise not_found(code="user.not_found")
    team_service.remove_member(db, team=team, target=target)
    audit(
        db,
        actor_user_id=user.id,
        team_id=team.id,
        action="team.member_remove",
        subject_kind="user",
        subject_id=target.id,
        payload={"removed_email": target.email},
    )
    db.commit()
    await hub.disconnect_user_from_team(team.id, target.id)


@router.post("/{team_id}/transfer-leader", response_model=TeamRead)
def transfer_leader(
    payload: TransferLeader,
    team_id: str = Path(...),
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict:
    require_role(team_id, db, user.id, role="leader")
    team = team_service.get_team(db, team_id)
    new_leader = db.get(User, payload.new_leader_user_id)
    if new_leader is None:
        raise not_found(code="user.not_found")
    team_service.transfer_leadership(db, team=team, new_leader=new_leader, actor=user)
    audit(
        db,
        actor_user_id=user.id,
        team_id=team.id,
        action="team.transfer_leader",
        subject_kind="user",
        subject_id=new_leader.id,
    )
    db.commit()
    return _team_to_read(team, "member")


@router.post(
    "/{team_id}/invitations",
    response_model=InvitationRead,
    status_code=status.HTTP_201_CREATED,
)
def create_invitation(
    payload: InvitationCreate,
    team_id: str = Path(...),
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> InvitationRead:
    require_role(team_id, db, user.id, role="leader")
    team = team_service.get_team(db, team_id)
    _check_not_archived(team)
    existing = db.query(User).filter(User.email == payload.email.lower()).one_or_none()
    inv = team_service.create_invitation(
        db, team=team, invited_by=user, email=payload.email, existing_member=existing
    )
    audit(
        db,
        actor_user_id=user.id,
        team_id=team.id,
        action="invitation.create",
        subject_kind="invitation",
        subject_id=inv.id,
        payload={"email": inv.email, "kind": inv.kind},
    )
    db.commit()
    out = InvitationRead.model_validate(inv)
    if inv.kind == "link":
        out.token = inv.token
    return out


@router.get("/{team_id}/invitations", response_model=list[InvitationRead])
def list_invitations(
    team_id: str = Path(...),
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> list[InvitationRead]:
    require_role(team_id, db, user.id, role="leader")
    rows = team_service.list_pending_invitations(db, team_id)
    return [InvitationRead.model_validate(r) for r in rows]


@router.delete("/{team_id}/invitations/{inv_id}", status_code=204)
def revoke_invitation(
    team_id: str,
    inv_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> None:
    require_role(team_id, db, user.id, role="leader")
    inv = db.get(Invitation, inv_id)
    if inv is None or inv.team_id != team_id:
        raise not_found(code="invitation.not_found")
    team_service.revoke_invitation(db, inv)
    audit(
        db,
        actor_user_id=user.id,
        team_id=team_id,
        action="invitation.revoke",
        subject_kind="invitation",
        subject_id=inv.id,
    )
    db.commit()


@router.get("/{team_id}/members", response_model=list[dict])
def list_members(
    team_id: str = Path(...),
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> list[dict]:
    require_membership(team_id, db, user.id)
    rows = team_service.list_members(db, team_id)
    return [
        {
            "user_id": u.id,
            "email": u.email,
            "display_name": u.display_name,
            "role": m.role,
            "joined_at": m.joined_at.isoformat(),
            "removed_at": m.removed_at.isoformat() if m.removed_at else None,
        }
        for u, m in rows
    ]
