"""Task schemas."""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import Field

from .common import ORMModel

TaskStatus = Literal["todo", "in_progress", "in_review", "needs_rework", "done"]
TaskStatusWithProposal = Literal[
    "proposed", "todo", "in_progress", "in_review", "needs_rework", "done"
]


class TaskCreate(ORMModel):
    milestone_id: str
    title: str = Field(min_length=1, max_length=255)
    description: str | None = None
    assignee_user_id: str
    category_code: str
    weight: int = Field(ge=1, le=10)
    est_hours: int = Field(ge=0)
    start_date: date
    due_date: date


class TaskPropose(ORMModel):
    milestone_id: str
    title: str = Field(min_length=1, max_length=255)
    description: str | None = None
    category_code: str
    weight: int = Field(ge=1, le=10)
    est_hours: int = Field(ge=0)
    start_date: date
    due_date: date


class TaskUpdate(ORMModel):
    title: str | None = None
    description: str | None = None
    assignee_user_id: str | None = None
    category_code: str | None = None
    weight: int | None = Field(default=None, ge=1, le=10)
    est_hours: int | None = Field(default=None, ge=0)
    start_date: date | None = None
    due_date: date | None = None
    status: TaskStatus | None = None


class TaskSplit(ORMModel):
    new_assignee_user_id: str
    weight: int = Field(ge=1, le=10)
    est_hours: int = Field(ge=0)
    category_code: str
    title: str | None = None


class TaskSubmit(ORMModel):
    note: str | None = None


class TaskReview(ORMModel):
    decision: Literal["accept", "reject"]
    quality: int = Field(ge=1, le=5)
    note: str | None = None


class TaskRead(ORMModel):
    id: str
    milestone_id: str
    assignee_user_id: str
    category_code: str
    title: str
    description: str | None
    weight: int
    est_hours: int
    start_date: date
    due_date: date
    status: TaskStatusWithProposal
    points_awarded: Decimal | None
    first_submitted_at: datetime | None
    accepted_at: datetime | None
    proposed: bool
    split_from_task_id: str | None


class TaskCommentCreate(ORMModel):
    body: str = Field(min_length=1, max_length=2000)


class TaskCommentRead(ORMModel):
    id: str
    task_id: str
    author_user_id: str
    body: str
    created_at: datetime
