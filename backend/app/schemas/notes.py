"""Notes schemas."""
from __future__ import annotations

from datetime import datetime

from pydantic import Field

from .common import ORMModel


class NoteCreate(ORMModel):
    title: str = Field(default="", max_length=255)
    content: str = Field(default="", max_length=50000)
    pinned: bool = False


class NoteUpdate(ORMModel):
    title: str | None = Field(default=None, max_length=255)
    content: str | None = Field(default=None, max_length=50000)
    pinned: bool | None = None


class NoteRead(ORMModel):
    id: str
    user_id: str
    title: str
    content: str
    pinned: bool
    created_at: datetime
    updated_at: datetime | None = None
