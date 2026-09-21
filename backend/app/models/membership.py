"""Membership model — leader|member role attached to a team."""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from ..db.base import Base, TimestampMixin

Role = Literal["leader", "member"]


class Membership(Base, TimestampMixin):
    __tablename__ = "memberships"
    __table_args__ = (
        CheckConstraint("role in ('leader','member')", name="membership_role_check"),
        Index("ix_membership_user_team", "user_id", "team_id", unique=True),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(32), ForeignKey("users.id"), nullable=False, index=True)
    team_id: Mapped[str] = mapped_column(String(32), ForeignKey("teams.id"), nullable=False, index=True)
    role: Mapped[str] = mapped_column(String(16), nullable=False, default="member")
    joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    removed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
