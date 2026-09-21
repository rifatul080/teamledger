"""Schedule schemas."""
from __future__ import annotations

from pydantic import Field

from .common import ORMModel


class ScheduleSlotIn(ORMModel):
    weekday: int = Field(ge=0, le=6)
    start_minute: int = Field(ge=0, le=24 * 60)
    end_minute: int = Field(ge=1, le=24 * 60)


class WeeklyPlanIn(ORMModel):
    user_id: str
    weekly_cap_hours: int = Field(ge=0, le=168)
    slots: list[ScheduleSlotIn] = Field(default_factory=list)


class WeeklyPlanRead(ORMModel):
    id: str
    team_id: str
    user_id: str
    weekly_cap_hours: int
    slots: list[ScheduleSlotIn]
