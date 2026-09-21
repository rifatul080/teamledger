"""Milestone model."""
from __future__ import annotations

from datetime import date

from sqlalchemy import Date, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from ..db.base import Base, TimestampMixin


class Milestone(Base, TimestampMixin):
    __tablename__ = "milestones"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    goal_id: Mapped[str] = mapped_column(String(32), ForeignKey("goals.id"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    due_date: Mapped[date] = mapped_column(Date, nullable=False)
