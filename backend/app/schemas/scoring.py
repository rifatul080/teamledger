"""Scoring + author order schemas."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import Field

from .common import ORMModel


class TaskScoreRead(ORMModel):
    task_id: str
    assignee_user_id: str
    category_code: str
    weight: int
    quality: int
    days_late: int | None
    timeliness: Decimal
    category_multiplier: Decimal
    points: Decimal


class ParticipantScoreRead(ORMModel):
    user_id: str
    display_name: str
    total_points: Decimal
    share_pct: Decimal
    by_category: dict[str, Decimal]
    tasks: list[TaskScoreRead]
    adjustments: list[AdjustmentSummary]


class AdjustmentSummary(ORMModel):
    delta: Decimal
    reason: str
    author_user_id: str
    created_at: datetime


class OrderPositionRead(ORMModel):
    position: int
    user_id: str
    suggested: bool
    note: str | None


class ScoreRead(ORMModel):
    project_id: str
    formula_version: str
    total_points: Decimal
    participants: list[ParticipantScoreRead]
    suggested_order: list[OrderPositionRead]
    final_order: list[OrderPositionRead] | None


class FinalPositionIn(ORMModel):
    position: int = Field(ge=1)
    user_id: str
    note: str | None = None


class FinalizeOrderRequest(ORMModel):
    positions: list[FinalPositionIn]
