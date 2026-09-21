"""Notification models."""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from ..db.base import Base, TimestampMixin

NotifType = Literal[
    "assignment",
    "review_result",
    "mention",
    "deadline_3d",
    "deadline_1d",
    "overdue",
]


class Notification(Base, TimestampMixin):
    __tablename__ = "notifications"
    __table_args__ = (
        CheckConstraint(
            "type in ('assignment','review_result','mention','deadline_3d','deadline_1d','overdue')",
            name="notification_type_check",
        ),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(32), ForeignKey("users.id"), nullable=False, index=True)
    type: Mapped[str] = mapped_column(String(32), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    body: Mapped[str] = mapped_column(String(2000), nullable=False)
    team_id: Mapped[str | None] = mapped_column(String(32), ForeignKey("teams.id"), nullable=True)
    project_id: Mapped[str | None] = mapped_column(String(32), ForeignKey("projects.id"), nullable=True)
    task_id: Mapped[str | None] = mapped_column(String(32), ForeignKey("tasks.id"), nullable=True)
    read: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class NotificationKey(Base, TimestampMixin):
    """Idempotency keys for the scheduler: one row per (type, task_id, recipient, bucket)."""

    __tablename__ = "notification_keys"
    __table_args__ = (
        UniqueConstraint("kind", "task_id", "recipient_id", "bucket", name="uq_notif_key"),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    task_id: Mapped[str] = mapped_column(String(32), nullable=False)
    recipient_id: Mapped[str] = mapped_column(String(32), nullable=False)
    bucket: Mapped[str] = mapped_column(String(64), nullable=False)
