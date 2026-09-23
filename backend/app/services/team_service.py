"""Team and membership service."""
from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from ..core.config import get_settings
from ..core.errors import conflict, forbidden, not_found, validation
from ..core.ids import new_id
from ..core.tokens import random_token
from ..models.invitation import Invitation
from ..models.membership import Membership
from ..models.team import Team
from ..models.user import User


def create_team(db: Session, *, leader: User, name: str, description: str | None) -> Team:
    team = Team(
        id=new_id(),
        name=name.strip(),
        description=description,
        archived=False,
        created_at=datetime.now(tz=UTC),
    )
    db.add(team)
    db.flush()
    db.add(
        Membership(
            id=new_id(),
            user_id=leader.id,
            team_id=team.id,
            role="leader",
            joined_at=team.created_at,
            created_at=team.created_at,
        )
    )
    db.flush()
    return team


def get_team(db: Session, team_id: str) -> Team:
    t = db.get(Team, team_id)
    if t is None:
        raise not_found(code="team.not_found")
    return t


def list_user_teams(db: Session, user_id: str) -> list[tuple[Team, Membership]]:
    rows = (
        db.query(Team, Membership)
        .join(Membership, Membership.team_id == Team.id)
        .filter(Membership.user_id == user_id, Membership.removed_at.is_(None))
        .all()
    )
    return rows


def archive_team(db: Session, team: Team) -> None:
    team.archived = True
    team.archived_at = datetime.now(tz=UTC)


def create_invitation(
    db: Session,
    *,
    team: Team,
    invited_by: User,
    email: str,
    existing_member: User | None,
) -> Invitation:
    settings = get_settings()
    if email.lower() == invited_by.email.lower():
        raise validation("Cannot invite yourself.", details={"field": "email"})
    # Already a current member?
    if existing_member is not None:
        already = (
            db.query(Membership)
            .filter(
                Membership.team_id == team.id,
                Membership.user_id == existing_member.id,
                Membership.removed_at.is_(None),
            )
            .one_or_none()
        )
        if already is not None:
            raise conflict("User is already a member.", code="team.already_member")
    now = datetime.now(tz=UTC)
    if existing_member is not None:
        kind = "in_app"
        token = random_token(16)
    else:
        kind = "link"
        token = random_token(32)
    inv = Invitation(
        id=new_id(),
        team_id=team.id,
        email=email.lower(),
        token=token,
        kind=kind,
        invited_by_user_id=invited_by.id,
        invited_user_id=existing_member.id if existing_member else None,
        expires_at=now + timedelta(days=settings.invite_ttl_days),
        created_at=now,
    )
    db.add(inv)
    db.flush()
    return inv


def list_pending_invitations(db: Session, team_id: str) -> list[Invitation]:
    return (
        db.query(Invitation)
        .filter(
            Invitation.team_id == team_id,
            Invitation.accepted_at.is_(None),
            Invitation.revoked_at.is_(None),
        )
        .order_by(Invitation.created_at.desc())
        .all()
    )


def revoke_invitation(db: Session, inv: Invitation) -> None:
    inv.revoked_at = datetime.now(tz=UTC)


def accept_invitation(db: Session, *, token: str, user: User) -> Membership:
    inv = db.query(Invitation).filter(Invitation.token == token).one_or_none()
    if inv is None or inv.revoked_at is not None:
        raise not_found(code="invitation.not_found")
    now = datetime.now(tz=UTC)

    expires = inv.expires_at
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=UTC)
    if expires < now:
        raise validation("Invitation expired.", code="invitation.expired")
    if inv.accepted_at is not None:
        # Already accepted — if same user, return membership; else forbid.
        m = (
            db.query(Membership)
            .filter(Membership.user_id == user.id, Membership.team_id == inv.team_id)
            .one_or_none()
        )
        if m is not None and m.removed_at is None:
            return m
        raise conflict("Invitation already accepted.", code="invitation.consumed")
    team = db.get(Team, inv.team_id)
    if team is None or team.archived:
        raise validation("Team not available.", code="team.unavailable")
    # If in-app invitation, only the addressed user can accept.
    if inv.invited_user_id is not None and inv.invited_user_id != user.id:
        raise forbidden(code="invitation.wrong_recipient")
    # Ensure email matches — except for universal links (Discord-style).
    if not is_universal_link(inv) and inv.email.lower() != user.email.lower():
        raise forbidden(code="invitation.email_mismatch")

    existing = (
        db.query(Membership)
        .filter(Membership.user_id == user.id, Membership.team_id == inv.team_id)
        .one_or_none()
    )
    if existing is not None and existing.removed_at is None:
        inv.accepted_at = now
        db.flush()
        return existing
    if existing is not None and existing.removed_at is not None:
        # Re-joining after removal — restore.
        existing.removed_at = None
        existing.joined_at = now
        existing.role = existing.role or "member"
        existing.created_at = existing.created_at
    else:
        existing = Membership(
            id=new_id(),
            user_id=user.id,
            team_id=inv.team_id,
            role="member",
            joined_at=now,
            created_at=now,
        )
        db.add(existing)
    inv.accepted_at = now
    db.flush()
    return existing


def list_members(db: Session, team_id: str) -> list[tuple[User, Membership]]:
    rows = (
        db.query(User, Membership)
        .join(Membership, Membership.user_id == User.id)
        .filter(Membership.team_id == team_id)
        .order_by(Membership.joined_at.asc())
        .all()
    )
    return rows


def remove_member(db: Session, *, team: Team, target: User) -> None:
    now = datetime.now(tz=UTC)
    m = (
        db.query(Membership)
        .filter(Membership.user_id == target.id, Membership.team_id == team.id)
        .one_or_none()
    )
    if m is None or m.removed_at is not None:
        raise not_found(code="team.member_not_found")
    if m.role == "leader":
        raise validation(
            "Transfer leadership before removing the leader.",
            code="team.leader_removal",
        )
    m.removed_at = now
    # Revoke all refresh sessions for that user.
    from ..models.refresh_session import RefreshSession  # local import to avoid cycles

    db.query(RefreshSession).filter(RefreshSession.user_id == target.id).update(
        {RefreshSession.revoked_at: now}
    )


def transfer_leadership(db: Session, *, team: Team, new_leader: User, actor: User) -> None:
    current = (
        db.query(Membership)
        .filter(
            Membership.team_id == team.id,
            Membership.user_id == actor.id,
            Membership.removed_at.is_(None),
            Membership.role == "leader",
        )
        .one_or_none()
    )
    if current is None:
        raise forbidden(code="team.not_leader")
    target = (
        db.query(Membership)
        .filter(
            Membership.team_id == team.id,
            Membership.user_id == new_leader.id,
            Membership.removed_at.is_(None),
        )
        .one_or_none()
    )
    if target is None:
        raise not_found(code="team.member_not_found")
    current.role = "member"
    target.role = "leader"


def exactly_one_leader(db: Session, team_id: str) -> bool:
    n = (
        db.query(Membership)
        .filter(
            Membership.team_id == team_id,
            Membership.role == "leader",
            Membership.removed_at.is_(None),
        )
        .count()
    )
    return n == 1


def all_member_user_ids(db: Session, team_id: str) -> Iterable[str]:
    rows = (
        db.query(Membership.user_id)
        .filter(Membership.team_id == team_id, Membership.removed_at.is_(None))
        .all()
    )
    return [r[0] for r in rows]

def add_member_direct(
    db: Session,
    *,
    team: Team,
    added_by: User,
    target: User,
) -> Membership:
    """Add an existing TeamLedger user to ``team`` without an invite token.

    Used when a leader types an email that already belongs to a user. The
    invite-link flow is for unknown emails; this flow is the immediate-add
    counterpart and never sends email.

    Returns the created (or re-activated) membership. Raises:
      - ``conflict`` if the user is already a current member.
      - ``validation`` if the leader tries to add themselves.
    """
    if target.id == added_by.id:
        raise validation(
            "You're already a member of this team.",
            code="team.self_add",
            details={"field": "email"},
        )
    existing = (
        db.query(Membership)
        .filter(
            Membership.user_id == target.id,
            Membership.team_id == team.id,
        )
        .one_or_none()
    )
    if existing is not None and existing.removed_at is None:
        raise conflict("User is already a member.", code="team.already_member")
    now = datetime.now(tz=UTC)
    if existing is not None:
        # Re-join: clear removed_at and keep original joined_at / role.
        existing.removed_at = None
        db.flush()
        return existing
    m = Membership(
        id=new_id(),
        user_id=target.id,
        team_id=team.id,
        role="member",
        joined_at=now,
        created_at=now,
    )
    db.add(m)
    db.flush()
    return m

def create_link_invitation(
    db: Session,
    *,
    team: Team,
    invited_by: User,
) -> Invitation:
    """Create a Discord-style invite link (no email target).

    Anyone with the token can join the team after signing up or signing in.
    The token is the only secret; we store a sentinel email so the column
    stays non-null without a schema change. ``accept_invitation`` allows
    any user (regardless of email match) when the invitation is a ``link``
    of this sentinel kind — see ``is_universal_link`` below.
    """
    settings = get_settings()
    now = datetime.now(tz=UTC)
    token = random_token(32)
    sentinel = f"link+{token[:8]}@teamledger.invite"
    inv = Invitation(
        id=new_id(),
        team_id=team.id,
        email=sentinel,
        token=token,
        kind="link",
        invited_by_user_id=invited_by.id,
        invited_user_id=None,
        expires_at=now + timedelta(days=settings.invite_ttl_days),
        created_at=now,
    )
    db.add(inv)
    db.flush()
    return inv


def is_universal_link(inv: Invitation) -> bool:
    """True for link-invitations issued via create_link_invitation (no target email).

    Distinguished by the sentinel ``link+<prefix>@teamledger.invite`` domain.
    For these, ``accept_invitation`` should accept any authenticated user,
    ignoring the email-mismatch rule.
    """
    return inv.email.endswith("@teamledger.invite")


def get_invitation_by_token(db: Session, token: str) -> Invitation:
    inv = db.query(Invitation).filter(Invitation.token == token).one_or_none()
    if inv is None:
        raise not_found(code="invitation.not_found")
    return inv


def public_invitation_view(db: Session, token: str) -> dict:
    """Build a privacy-safe view of an invite token.

    Returns team name + expiry + whether the token is still usable.
    Never includes the leader's email or other members.
    """
    inv = get_invitation_by_token(db, token)
    if inv.revoked_at is not None:
        raise not_found(code="invitation.not_found")
    now = datetime.now(tz=UTC)
    expires = inv.expires_at
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=UTC)
    if expires < now:
        raise not_found(code="invitation.not_found")
    team = db.get(Team, inv.team_id)
    if team is None or team.archived:
        raise not_found(code="invitation.not_found")
    return {
        "token": inv.token,
        "team_id": team.id,
        "team_name": team.name,
        "team_description": team.description,
        "expires_at": expires,
        "kind": "link" if is_universal_link(inv) else inv.kind,
    }
