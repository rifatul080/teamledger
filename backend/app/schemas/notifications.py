"""Notification schemas."""
from __future__ import annotations

from datetime import datetime

from .common import ORMModel


class NotificationRead(ORMModel):
    id: str
    type: str
    title: str
    body: str
    team_id: str | None
    project_id: str | None
    task_id: str | None
    read: bool
    created_at: datetime


class NotificationMark(ORMModel):
    ids: list[str]
