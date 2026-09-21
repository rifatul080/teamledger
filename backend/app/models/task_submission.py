"""Submission events for tasks — captures first-submission time used for lateness."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from ..db.base import Base, TimestampMixin


class TaskSubmission(Base, TimestampMixin):
    __tablename__ = "task_submissions"
    __table_args__ = (Index("ix_submission_task_seq", "task_id", "seq"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    task_id: Mapped[str] = mapped_column(String(32), ForeignKey("tasks.id"), nullable=False, index=True)
    seq: Mapped[int] = mapped_column(nullable=False, default=1)
    submitted_by_user_id: Mapped[str] = mapped_column(String(32), ForeignKey("users.id"), nullable=False)
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
