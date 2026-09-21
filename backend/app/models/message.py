"""Chat message model with monotonic per-team seq."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ..db.base import Base, TimestampMixin


class ChatMessage(Base, TimestampMixin):
    __tablename__ = "chat_messages"
    __table_args__ = (
        Index("ix_msg_team_seq", "team_id", "seq"),
        Index("ix_msg_sender", "sender_user_id"),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    team_id: Mapped[str] = mapped_column(String(32), ForeignKey("teams.id"), nullable=False)
    sender_user_id: Mapped[str | None] = mapped_column(String(32), ForeignKey("users.id"), nullable=True)
    seq: Mapped[int] = mapped_column(BigInteger, nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    mentions: Mapped[str] = mapped_column(String(2000), nullable=False, default="")  # comma-separated user ids
    edited_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class MessageRead(Base, TimestampMixin):
    __tablename__ = "message_reads"
    __table_args__ = (
        Index("ix_msgread_user_team", "user_id", "team_id"),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(32), ForeignKey("users.id"), nullable=False)
    team_id: Mapped[str] = mapped_column(String(32), ForeignKey("teams.id"), nullable=False)
    last_read_seq: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
