"""Chat schemas."""
from __future__ import annotations

from datetime import datetime

from pydantic import Field

from .common import ORMModel


class MessageSend(ORMModel):
    body: str = Field(min_length=1, max_length=8000)
    client_msg_id: str | None = None  # idempotency
    attachment_version_ids: list[str] = Field(default_factory=list)


class MessageEdit(ORMModel):
    body: str = Field(min_length=1, max_length=8000)


class MessageRead(ORMModel):
    id: str
    team_id: str
    sender_user_id: str | None
    seq: int
    body: str
    mentions: list[str]
    edited_at: datetime | None
    deleted: bool
    created_at: datetime
