"""Task review model."""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from ..db.base import Base, TimestampMixin

ReviewDecision = Literal["accept", "reject"]


class TaskReview(Base, TimestampMixin):
    __tablename__ = "task_reviews"
    __table_args__ = (
        CheckConstraint("decision in ('accept','reject')", name="taskreview_decision_check"),
        CheckConstraint("quality between 1 and 5", name="taskreview_quality_check"),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    task_id: Mapped[str] = mapped_column(String(32), ForeignKey("tasks.id"), nullable=False, index=True)
    reviewer_user_id: Mapped[str] = mapped_column(String(32), ForeignKey("users.id"), nullable=False, index=True)
    quality: Mapped[int] = mapped_column(Integer, nullable=False)
    decision: Mapped[str] = mapped_column(String(16), nullable=False)
    note: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    decided_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
