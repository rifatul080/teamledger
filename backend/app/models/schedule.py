"""Schedule models: weekly availability slots + per-member cap."""
from __future__ import annotations

from sqlalchemy import CheckConstraint, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from ..db.base import Base, TimestampMixin


class WeeklyPlan(Base, TimestampMixin):
    __tablename__ = "weekly_plans"
    __table_args__ = (CheckConstraint("weekly_cap_hours between 0 and 168", name="weekly_plan_cap_check"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    team_id: Mapped[str] = mapped_column(String(32), ForeignKey("teams.id"), nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(String(32), ForeignKey("users.id"), nullable=False, index=True)
    weekly_cap_hours: Mapped[int] = mapped_column(Integer, nullable=False, default=20)


class ScheduleSlot(Base, TimestampMixin):
    """A recurring weekly time slot (Mon-Sun, hour range)."""

    __tablename__ = "schedule_slots"
    __table_args__ = (
        CheckConstraint("weekday between 0 and 6", name="schedule_slot_weekday_check"),
        CheckConstraint("end_minute > start_minute", name="schedule_slot_range_check"),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    weekly_plan_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("weekly_plans.id"), nullable=False, index=True
    )
    weekday: Mapped[int] = mapped_column(Integer, nullable=False)  # 0 = Monday
    start_minute: Mapped[int] = mapped_column(Integer, nullable=False)  # minutes from midnight
    end_minute: Mapped[int] = mapped_column(Integer, nullable=False)
    note: Mapped[str | None] = mapped_column(String(255), nullable=True)
