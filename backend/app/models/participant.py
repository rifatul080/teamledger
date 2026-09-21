"""Project participants: subset of team members that a leader selects."""
from __future__ import annotations

from sqlalchemy import ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from ..db.base import Base, TimestampMixin


class ProjectParticipant(Base, TimestampMixin):
    __tablename__ = "project_participants"
    __table_args__ = (Index("ix_pp_project_user", "project_id", "user_id", unique=True),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    project_id: Mapped[str] = mapped_column(String(32), ForeignKey("projects.id"), nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(String(32), ForeignKey("users.id"), nullable=False, index=True)
