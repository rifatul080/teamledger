"""Goal schemas."""
from __future__ import annotations

from datetime import date

from pydantic import Field

from .common import ORMModel


class GoalCreate(ORMModel):
    project_id: str
    title: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=2000)
    target_date: date


class GoalRead(ORMModel):
    id: str
    project_id: str
    title: str
    description: str | None
    target_date: date
    progress_pct: float = 0.0


class GoalUpdate(ORMModel):
    title: str | None = None
    description: str | None = None
    target_date: date | None = None
