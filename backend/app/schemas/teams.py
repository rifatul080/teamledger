"""Team schemas."""
from __future__ import annotations

from datetime import datetime

from pydantic import EmailStr, Field

from .common import ORMModel


class TeamCreate(ORMModel):
    name: str = Field(min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=500)


class TeamUpdate(ORMModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=500)


class TeamRead(ORMModel):
    id: str
    name: str
    description: str | None
    archived: bool
    created_at: datetime
    role: str | None = None  # caller's role if resolvable


class InvitationCreate(ORMModel):
    email: EmailStr


class InvitationRead(ORMModel):
    id: str
    team_id: str
    email: EmailStr
    kind: str
    token: str | None = None  # link invitations only, for the leader to share
    expires_at: datetime
    accepted_at: datetime | None
    revoked_at: datetime | None


class TransferLeader(ORMModel):
    new_leader_user_id: str


class AddMemberBody(ORMModel):
    """Body for POST /teams/{id}/members — add an existing user by email."""

    email: EmailStr


class MemberRead(ORMModel):
    user_id: str
    email: EmailStr
    display_name: str
    role: str
    avatar_url: str | None = None
