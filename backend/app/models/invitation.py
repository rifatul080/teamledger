"""Invitations — tokenised invites for unknown emails; in-app invitations for known users."""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from ..db.base import Base, TimestampMixin

InviteKind = Literal["link", "in_app"]


class Invitation(Base, TimestampMixin):
    __tablename__ = "invitations"
    __table_args__ = (
        CheckConstraint("kind in ('link','in_app')", name="invitation_kind_check"),
        Index("ix_invitation_token", "token", unique=True),
        Index("ix_invitation_team_email", "team_id", "email"),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    team_id: Mapped[str] = mapped_column(String(32), ForeignKey("teams.id"), nullable=False, index=True)
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    token: Mapped[str] = mapped_column(String(64), nullable=False)
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    invited_by_user_id: Mapped[str] = mapped_column(String(32), ForeignKey("users.id"), nullable=False)
    invited_user_id: Mapped[str | None] = mapped_column(String(32), ForeignKey("users.id"), nullable=True)
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
