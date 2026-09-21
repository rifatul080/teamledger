"""Milestone schemas."""
from __future__ import annotations

from datetime import date

from pydantic import Field

from .common import ORMModel


class MilestoneCreate(ORMModel):
    goal_id: str
    title: str = Field(min_length=1, max_length=255)
    due_date: date


class MilestoneRead(ORMModel):
    id: str
    goal_id: str
    title: str
    due_date: date
    progress_pct: float = 0.0


class MilestoneUpdate(ORMModel):
    title: str | None = None
    due_date: date | None = None
