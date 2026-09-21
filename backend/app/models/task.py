"""Task model with status and submission tracking."""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column

from ..db.base import Base, TimestampMixin

TaskStatus = Literal["todo", "in_progress", "in_review", "needs_rework", "done"]


class Task(Base, TimestampMixin):
    __tablename__ = "tasks"
    __table_args__ = (
        CheckConstraint(
            "status in ('todo','in_progress','in_review','needs_rework','done')",
            name="task_status_check",
        ),
        CheckConstraint("weight between 1 and 10", name="task_weight_check"),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    milestone_id: Mapped[str] = mapped_column(String(32), ForeignKey("milestones.id"), nullable=False, index=True)
    assignee_user_id: Mapped[str] = mapped_column(String(32), ForeignKey("users.id"), nullable=False, index=True)
    category_code: Mapped[str] = mapped_column(String(64), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(String(4000), nullable=True)
    weight: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    est_hours: Mapped[int] = mapped_column(Integer, nullable=False, default=4)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    due_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="todo")
    points_awarded: Mapped[Decimal | None] = mapped_column(Numeric(20, 6), nullable=True)
    first_submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    proposed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    proposer_user_id: Mapped[str | None] = mapped_column(String(32), ForeignKey("users.id"), nullable=True)
    split_from_task_id: Mapped[str | None] = mapped_column(String(32), ForeignKey("tasks.id"), nullable=True)
